import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import os
import json
import tempfile
import hashlib
import uuid
import shutil
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

# Import existing modules
from database import (
    init_db,
    save_jd,
    get_all_jds,
    get_jd_by_id,
    delete_jd,
    save_analysis,
    get_all_analyses,
    get_analyses_by_jd,
    get_analysis_detail,
    delete_analysis,
    find_analysis_by_hash_or_filename,
)
from extract_cv import (
    process_cv_and_jd,
    extract_text_from_cv,
    is_groq_configured,
    CandidateResume,
    JobDescription,
    extract_information,
    CVExtractionError,
)
from scoring_cv import CVScoresAggregator, AdvancedFilter
from cv_tailor import (
    tailor_cv_to_jd,
    analyze_cv_detailed,
    generate_markdown_report,
    generate_html_report,
)
from chatbot import InterviewChatbot

# Initialize database
try:
    init_db()
except Exception as e:
    print(f"Lỗi khởi tạo Database: {e}")

from auth import verify_token, router as auth_router
from fastapi import Depends

app = FastAPI(title="ATS API", description="FastAPI Backend for Smart Recruitment System")

app.include_router(auth_router)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend origin e.g. ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global dictionary to hold interview sessions
# Key: analysis_id (or a session uuid) -> value: InterviewChatbot instance
interview_sessions: Dict[str, InterviewChatbot] = {}


# --- REQUEST/RESPONSE SCHEMAS ---

class JdCreate(BaseModel):
    name: str
    content: str


class ScoreWeights(BaseModel):
    skills: float = 0.4
    experience: float = 0.3
    education: float = 0.1
    language: float = 0.1
    stability: float = 0.1


# Helper to detect language
def detect_cv_language_by_text(text: str) -> str:
    import re
    vietnamese_chars = re.findall(
        r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]',
        text.lower(),
    )
    ratio = len(vietnamese_chars) / max(len(text), 1)
    return "vi" if ratio > 0.02 else "en"


@app.get("/")
def read_root():
    return {"status": "running", "groq_configured": is_groq_configured()}


# ==========================================
#  JD PROFILES API
# ==========================================

@app.get("/api/jds", dependencies=[Depends(verify_token)])
def list_jds():
    try:
        return get_all_jds()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jds/{jd_id}", dependencies=[Depends(verify_token)])
def get_jd(jd_id: str):
    jd = get_jd_by_id(jd_id)
    if not jd:
        raise HTTPException(status_code=404, detail="Không tìm thấy JD")
    return jd


@app.post("/api/jds", dependencies=[Depends(verify_token)])
def create_jd(payload: JdCreate):
    if not payload.name.strip() or not payload.content.strip():
        raise HTTPException(status_code=400, detail="Tên và nội dung JD không được để trống")
    try:
        parsed_data = {}
        try:
            # AI parsing of JD structure
            parsed_jd_obj = extract_information(payload.content.strip(), JobDescription, "jd")
            parsed_data = parsed_jd_obj.model_dump() if hasattr(parsed_jd_obj, "model_dump") else {}
        except Exception as parse_err:
            print(f"Không thể phân tích cấu trúc JD bằng AI: {parse_err}")
        
        jd_id = save_jd(payload.name.strip(), payload.content.strip(), parsed_data)
        return {"id": jd_id, "name": payload.name, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/jds/{jd_id}", dependencies=[Depends(verify_token)])
def remove_jd(jd_id: str):
    success = delete_jd(jd_id)
    if not success:
        raise HTTPException(status_code=400, detail="Không thể xóa JD hoặc JD không tồn tại")
    return {"status": "success", "message": f"Đã xóa JD {jd_id}"}


# ==========================================
#  CV ANALYSIS API
# ==========================================

@app.post("/api/analyses", dependencies=[Depends(verify_token)])
async def analyze_cvs(
    jd_id: str = Form(...),
    jd_content_manual: Optional[str] = Form(None),
    w_skills: int = Form(40),
    w_exp: int = Form(30),
    w_edu: int = Form(10),
    w_lang: int = Form(10),
    w_stab: int = Form(10),
    files: List[UploadFile] = File(...),
):
    # Validate weights
    total_weight = w_skills + w_exp + w_edu + w_lang + w_stab
    if total_weight != 100:
        raise HTTPException(status_code=400, detail=f"Tổng trọng số phải bằng 100% (hiện tại: {total_weight}%)")
    
    weights = {
        "skills": w_skills / 100.0,
        "experience": w_exp / 100.0,
        "education": w_edu / 100.0,
        "language": w_lang / 100.0,
        "stability": w_stab / 100.0,
    }

    # Fetch target JD content
    jd_content = ""
    jd_name = ""
    if jd_id == "manual":
        if not jd_content_manual or not jd_content_manual.strip():
            raise HTTPException(status_code=400, detail="Nội dung JD thủ công không được để trống")
        jd_content = jd_content_manual.strip()
        jd_name = "JD thủ công"
    else:
        jd = get_jd_by_id(jd_id)
        if not jd:
            raise HTTPException(status_code=404, detail="Không tìm thấy JD được chỉ định")
        jd_content = jd["content"]
        jd_name = jd["name"]

    all_results = []
    
    # Process files
    for file in files:
        # Read file into bytes
        file_bytes = await file.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        
        # Check cache in DB (if not manual JD)
        cached_analysis = None
        if jd_id != "manual":
            try:
                cached_analysis = find_analysis_by_hash_or_filename(file_hash, file.filename, jd_id)
            except Exception as e:
                print(f"Lỗi tìm cache: {e}")

        if cached_analysis:
            # Reconstruct response from cache
            all_results.append({
                "id": cached_analysis["id"],
                "name": cached_analysis.get("candidate_name", "N/A"),
                "email": cached_analysis.get("email", ""),
                "filename": file.filename,
                "score": cached_analysis.get("total_score", 0),
                "recommendation": cached_analysis.get("recommendation", ""),
                "scoring_result": {
                    "final_score_pct": cached_analysis.get("total_score", 0),
                    "recommendation": cached_analysis.get("recommendation", ""),
                    "breakdown": cached_analysis.get("scoring_breakdown", {})
                },
                "analysis": cached_analysis.get("analysis_report", {}),
                "cached": True,
                "jd_name": jd_name
            })
            continue

        # Process new file
        tmp_suffix = f".{file.filename.split('.')[-1]}"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=tmp_suffix) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            
            # Extract and Score
            cv_data, jd_data, resume_obj, jd_obj = process_cv_and_jd(tmp_path, jd_content, jd_id)
            
            # Scoring
            agg = CVScoresAggregator(weights=weights)
            scoring_result = agg.score_cv(cv_data, jd_data)
            
            # Detail Analysis
            try:
                analysis_report = analyze_cv_detailed(resume_obj, jd_obj, scoring_result)
            except Exception as e:
                print(f"Lỗi chi tiết báo cáo: {e}")
                sk = scoring_result["breakdown"].get("skills", {}).get("details", {})
                analysis_report = AnalysisReport(
                    compatibility_score=scoring_result["final_score_pct"],
                    score_message=scoring_result["recommendation"],
                    missing_keywords=sk.get("missing_critical_skills", []) + sk.get("missing_nice_skills", []),
                    missing_skills_technical=sk.get("missing_critical_skills", []),
                    missing_skills_soft=[], strengths=[], suggestions=[],
                    areas_for_improvement=[], next_steps=[],
                )
            
            # Save to Database
            analysis_id = ""
            try:
                analysis_id = save_analysis(
                    candidate_name=getattr(resume_obj, "name", "N/A"),
                    email=getattr(resume_obj, "email", "") or "",
                    filename=file.filename,
                    jd_id=jd_id,
                    jd_name=jd_name,
                    total_score=scoring_result["final_score_pct"],
                    recommendation=scoring_result["recommendation"],
                    scoring_breakdown=scoring_result["breakdown"],
                    resume_data=resume_obj.model_dump() if hasattr(resume_obj, "model_dump") else {},
                    analysis_report=analysis_report.model_dump() if hasattr(analysis_report, "model_dump") else {},
                    filter_results={},
                    weights_used=weights,
                    file_hash=file_hash,
                )
            except Exception as db_err:
                print(f"Lỗi lưu DB: {db_err}")

            all_results.append({
                "id": analysis_id,
                "name": getattr(resume_obj, "name", "N/A"),
                "email": getattr(resume_obj, "email", ""),
                "filename": file.filename,
                "score": scoring_result["final_score_pct"],
                "recommendation": scoring_result["recommendation"],
                "scoring_result": scoring_result,
                "analysis": analysis_report.model_dump() if hasattr(analysis_report, "model_dump") else {},
                "cached": False,
                "jd_name": jd_name
            })
            
        except CVExtractionError as err:
            import traceback
            print(f"Lỗi trích xuất CV {file.filename}:")
            traceback.print_exc()
            all_results.append({
                "name": "Lỗi",
                "filename": file.filename,
                "score": 0,
                "recommendation": str(err),
                "error_detail": str(err),
                "is_user_error": True,
            })
        except Exception as err:
            import traceback
            error_detail = traceback.format_exc()
            print(f"Lỗi không xác định khi phân tích CV {file.filename}:")
            traceback.print_exc()
            all_results.append({
                "name": "Lỗi",
                "filename": file.filename,
                "score": 0,
                "recommendation": f"Lỗi hệ thống: {err}",
                "error_detail": error_detail,
                "is_user_error": False,
            })
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                    
    return all_results


# ==========================================
#  ANALYSIS HISTORY API
# ==========================================

@app.get("/api/analyses", dependencies=[Depends(verify_token)])
def list_analyses(
    jd_id: Optional[str] = None,
    min_score: float = 0.0,
    filter_status: str = "all", # all, pass, fail
    uni_filter: Optional[str] = None, # Comma separated
    min_exp: float = 0.0,
    required_skills: Optional[str] = None, # Comma separated
    min_degree: str = "none",
    min_stability: int = 0,
    lang_name: Optional[str] = None,
    lang_level: Optional[str] = None,
):
    try:
        if jd_id:
            records = get_analyses_by_jd(jd_id)
        else:
            records = get_all_analyses()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Re-fetch full details for advanced filtering if filters are present
    has_advanced_filter = bool(
        uni_filter or min_exp > 0 or required_skills or min_degree != "none" or min_stability > 0 or (lang_name and lang_level)
    )

    filtered_records = []
    
    # Setup filter configuration
    filter_config = {}
    if uni_filter and uni_filter.strip():
        filter_config["universities"] = [u.strip() for u in uni_filter.split(",") if u.strip()]
    if min_exp > 0:
        filter_config["min_experience_years"] = min_exp
    if lang_name and lang_level:
        filter_config["language"] = {"name": lang_name.lower(), "min_level": lang_level}
    if required_skills and required_skills.strip():
        filter_config["required_skills"] = [s.strip() for s in required_skills.split(",") if s.strip()]
    if min_degree and min_degree != "none":
        filter_config["min_degree"] = min_degree
    if min_stability > 0:
        filter_config["min_stability_pct"] = min_stability

    for r in records:
        score = r.get("total_score", 0)
        # Score filter
        if score < min_score:
            continue
            
        # Reconstruct resume_obj and apply filters if necessary
        resume_data = r.get("resume_data", {})
        resume_obj = None
        if resume_data:
            try:
                resume_obj = CandidateResume(**resume_data)
            except Exception:
                pass

        # Apply filter results
        dynamic_filter_results = {}
        if filter_config and resume_obj:
            skills_details = r.get("scoring_breakdown", {}).get("skills", {}).get("details", {})
            cv_data = {
                "languages": {lang.name.lower(): lang.level.lower() for lang in resume_obj.languages},
                "matched_must_have_skills": skills_details.get("matched_critical_skills", []) + skills_details.get("equivalent_critical_skills", []),
                "matched_nice_to_have_skills": skills_details.get("matched_nice_skills", []) + skills_details.get("equivalent_nice_skills", []),
            }
            dynamic_filter_results = AdvancedFilter.apply_filters(
                cv_data, resume_obj, {"breakdown": r.get("scoring_breakdown", {})}, filter_config
            )
            r["filter_results"] = dynamic_filter_results
        
        # Check pass status
        passed = True
        if dynamic_filter_results and "passed" in dynamic_filter_results:
            passed = dynamic_filter_results["passed"]
            
        if filter_status == "pass" and not passed:
            continue
        if filter_status == "fail" and passed and dynamic_filter_results:
            continue

        # Add record
        filtered_records.append({
            "id": r["id"],
            "candidate_name": r.get("candidate_name", "N/A"),
            "email": r.get("email", ""),
            "filename": r.get("filename", ""),
            "jd_id": r.get("jd_id", ""),
            "jd_name": r.get("jd_name", "N/A"),
            "total_score": score,
            "recommendation": r.get("recommendation", ""),
            "filter_results": r.get("filter_results", {}),
            "created_at": r.get("created_at"),
            "weights_used": r.get("weights_used", {})
        })
        
    return filtered_records


@app.get("/api/analyses/{analysis_id}", dependencies=[Depends(verify_token)])
def get_analysis(analysis_id: str):
    detail = get_analysis_detail(analysis_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Không tìm thấy chi tiết phân tích")
    return detail


@app.delete("/api/analyses/{analysis_id}", dependencies=[Depends(verify_token)])
def remove_analysis(analysis_id: str):
    success = delete_analysis(analysis_id)
    if not success:
        raise HTTPException(status_code=400, detail="Không thể xóa bản ghi phân tích")
    return {"status": "success", "message": f"Đã xóa bản ghi {analysis_id}"}


@app.post("/api/analyses/clear", dependencies=[Depends(verify_token)])
def clear_all_analyses(confirm: str = Form(...)):
    if confirm != "XOA TAT CA":
        raise HTTPException(status_code=400, detail="Mã xác nhận xóa không chính xác")
    try:
        all_a = get_all_analyses()
        count = 0
        for a in all_a:
            delete_analysis(a["id"])
            count += 1
        return {"status": "success", "message": f"Đã xóa toàn bộ {count} bản ghi phân tích"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
#  REPORT DOWNLOADS API
# ==========================================

@app.get("/api/analyses/{analysis_id}/report/html", dependencies=[Depends(verify_token)])
def download_html_report(analysis_id: str):
    detail = get_analysis_detail(analysis_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Không tìm thấy chi tiết phân tích")
        
    resume_data = detail.get("resume_data", {})
    analysis_report_data = detail.get("analysis_report", {})
    scoring_result = {
        "final_score_pct": detail.get("total_score", 0),
        "recommendation": detail.get("recommendation", ""),
        "breakdown": detail.get("scoring_breakdown", {})
    }
    
    try:
        from cv_tailor import AnalysisReport, CandidateResume
        resume_obj = CandidateResume(**resume_data) if resume_data else None
        analysis_report_obj = AnalysisReport(**analysis_report_data) if analysis_report_data else None
        
        html_content = generate_html_report(
            analysis_report_obj,
            detail.get("candidate_name", "Resume"),
            detail.get("jd_name", "Position"),
            scoring_result,
            resume_obj=resume_obj,
            created_at=detail.get("created_at")
        )
        import urllib.parse
        raw_filename = f"Bao_Cao_{detail.get('candidate_name', 'Resume').replace(' ', '_')}.html"
        safe_filename = urllib.parse.quote(raw_filename)
        return HTMLResponse(
            content=html_content, 
            status_code=200,
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo báo cáo HTML: {e}")


@app.get("/api/analyses/{analysis_id}/report/md", dependencies=[Depends(verify_token)])
def download_md_report(analysis_id: str):
    detail = get_analysis_detail(analysis_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Không tìm thấy chi tiết phân tích")
        
    resume_data = detail.get("resume_data", {})
    analysis_report_data = detail.get("analysis_report", {})
    scoring_result = {
        "final_score_pct": detail.get("total_score", 0),
        "recommendation": detail.get("recommendation", ""),
        "breakdown": detail.get("scoring_breakdown", {})
    }
    
    try:
        from cv_tailor import AnalysisReport, CandidateResume
        resume_obj = CandidateResume(**resume_data) if resume_data else None
        analysis_report_obj = AnalysisReport(**analysis_report_data) if analysis_report_data else None
        
        md_content = generate_markdown_report(
            analysis_report_obj,
            detail.get("candidate_name", "Resume"),
            detail.get("jd_name", "Position"),
            scoring_result,
            resume_obj=resume_obj,
            created_at=detail.get("created_at")
        )
        import urllib.parse
        raw_filename = f"Bao_Cao_{detail.get('candidate_name', 'Resume').replace(' ', '_')}.md"
        safe_filename = urllib.parse.quote(raw_filename)
        return Response(
            content=md_content,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo báo cáo Markdown: {e}")


# ==========================================
#  INTERVIEW BOT API
# ==========================================

class StartInterviewRequest(BaseModel):
    analysis_id: str


class SubmitAnswerRequest(BaseModel):
    answer: str


@app.post("/api/interview/start", dependencies=[Depends(verify_token)])
def start_interview(payload: StartInterviewRequest):
    detail = get_analysis_detail(payload.analysis_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Không tìm thấy kết quả phân tích CV tương ứng")
        
    resume_data = detail.get("resume_data", {})
    scoring_breakdown = detail.get("scoring_breakdown", {})
    
    # Reconstruct resume_obj and jd_obj
    try:
        # Load associated JD
        jd_id = detail.get("jd_id", "")
        jd_content = ""
        if jd_id and jd_id != "manual":
            jd = get_jd_by_id(jd_id)
            if jd:
                jd_content = jd["content"]
        
        # Build resume_obj
        resume_obj = CandidateResume(**resume_data) if resume_data else None
        
        # Parse fields from breakdown to build jd_obj and input data
        skills_breakdown = scoring_breakdown.get("skills", {}).get("details", {})
        must_have_skills = skills_breakdown.get("matched_critical_skills", []) + skills_breakdown.get("missing_critical_skills", [])
        nice_to_have_skills = skills_breakdown.get("matched_nice_skills", []) + skills_breakdown.get("missing_nice_skills", [])

        exp_breakdown = scoring_breakdown.get("experience", {}).get("details", {})
        min_years_experience = int(exp_breakdown.get("required_years", 0))

        edu_breakdown = scoring_breakdown.get("education", {}).get("details", {})
        required_degree = edu_breakdown.get("jd_degree", "none")

        lang_breakdown = scoring_breakdown.get("language", {}).get("details", {}).get("breakdown", [])
        required_languages = {item["language"].lower(): item["required_level"].lower() for item in lang_breakdown if "language" in item and "required_level" in item}

        from extract_cv import JobDescription
        jd_obj = JobDescription(
            job_title=detail.get("jd_name", "Vị trí"),
            job_description=jd_content or "Job description details",
            min_years_experience=min_years_experience,
            required_degree=required_degree,
            must_have_skills=must_have_skills,
            nice_to_have_skills=nice_to_have_skills,
            required_languages=required_languages
        )
        
        # Build resume_data parameter
        exp_history = []
        for job in exp_breakdown.get("job_breakdown", []):
            exp_history.append({
                "title": job.get("Job_title", "N/A"),
                "years": job.get("raw_years", 0.0),
                "relevance_to_jd": job.get("relevance_pct", 0) / 100.0
            })

        edu_history = []
        if resume_obj:
            best_deg = edu_breakdown.get("best_matched_degree", "none")
            best_rel = edu_breakdown.get("major_relevant", 0.0)
            for edu in resume_obj.educations:
                rel = best_rel if edu.degree.lower() == best_deg.lower() else 0.0
                edu_history.append({
                    "degree": edu.degree,
                    "major_relevant": rel
                })
        if not edu_history:
            edu_history = [{"degree": "none", "major_relevant": 0.0}]

        languages = {}
        if resume_obj:
            languages = {lang.name.lower(): lang.level.lower() for lang in resume_obj.languages}

        cv_data_input = {
            "experience_history": exp_history,
            "education_history": edu_history,
            "matched_must_have_skills": skills_breakdown.get("matched_critical_skills", []),
            "matched_nice_to_have_skills": skills_breakdown.get("matched_nice_skills", []),
            "languages": languages
        }

        jd_data_input = {
            "required_experience_years": min_years_experience,
            "required_degree": required_degree,
            "must_have_skills": must_have_skills,
            "nice_to_have_skills": nice_to_have_skills,
            "required_languages": required_languages
        }

        scoring_result_input = {
            "final_score_pct": detail.get("total_score", 0.0),
            "recommendation": detail.get("recommendation", ""),
            "breakdown": scoring_breakdown
        }

        # Initialize chatbot
        bot = InterviewChatbot(
            resume_data=cv_data_input,
            jd_data=jd_data_input,
            scoring_result=scoring_result_input,
            candidate_name=detail.get("candidate_name", "Ứng viên"),
            job_title=detail.get("jd_name", "Vị trí tuyển dụng"),
            resume_detail=resume_data,
            jd_detail=jd_obj.model_dump() if hasattr(jd_obj, "model_dump") else {}
        )
        
        # Generate questions
        bot.generate_questions()
        
        # Save session
        interview_sessions[payload.analysis_id] = bot
        
        # Get first question
        q = bot.get_next_question()
        
        return {
            "status": "success",
            "analysis_id": payload.analysis_id,
            "total_questions": len(bot.questions),
            "current_question": q
        }
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Lỗi khởi tạo chatbot: {e}")


@app.get("/api/interview/{analysis_id}/question", dependencies=[Depends(verify_token)])
def get_current_question(analysis_id: str):
    bot = interview_sessions.get(analysis_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên phỏng vấn. Vui lòng bắt đầu phỏng vấn trước.")
        
    q = bot.get_next_question()
    return {
        "is_finished": bot.is_finished,
        "current_question_index": bot.current_question_index,
        "total_questions": len(bot.questions),
        "question": q
    }


@app.post("/api/interview/{analysis_id}/answer", dependencies=[Depends(verify_token)])
def submit_answer(analysis_id: str, payload: SubmitAnswerRequest):
    bot = interview_sessions.get(analysis_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên phỏng vấn")
        
    if bot.is_finished:
        return {"is_finished": True, "message": "Phỏng vấn đã kết thúc"}
        
    try:
        eval_result = bot.submit_answer(payload.answer.strip())
        next_q = bot.get_next_question()
        
        return {
            "evaluation": eval_result,
            "is_finished": bot.is_finished,
            "current_question_index": bot.current_question_index,
            "total_questions": len(bot.questions),
            "next_question": next_q
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đánh giá câu trả lời: {e}")


@app.post("/api/interview/{analysis_id}/skip", dependencies=[Depends(verify_token)])
def skip_question(analysis_id: str):
    bot = interview_sessions.get(analysis_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên phỏng vấn")
        
    if bot.is_finished:
        return {"is_finished": True, "message": "Phỏng vấn đã kết thúc"}
        
    try:
        eval_result = bot.skip_question()
        next_q = bot.get_next_question()
        
        return {
            "evaluation": eval_result,
            "is_finished": bot.is_finished,
            "current_question_index": bot.current_question_index,
            "total_questions": len(bot.questions),
            "next_question": next_q
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi bỏ qua câu hỏi: {e}")


@app.get("/api/interview/{analysis_id}/summary", dependencies=[Depends(verify_token)])
def get_interview_summary(analysis_id: str):
    bot = interview_sessions.get(analysis_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên phỏng vấn")
        
    if not bot.evaluations:
        raise HTTPException(status_code=400, detail="Chưa có câu trả lời nào được thực hiện")
        
    try:
        summary = bot.generate_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo tổng kết phỏng vấn: {e}")


# ==========================================
#  CV TAILOR / OPTIMIZER API
# ==========================================

@app.post("/api/cv/tailor/{analysis_id}", dependencies=[Depends(verify_token)])
def tailor_cv(analysis_id: str, language: str = "auto"):
    detail = get_analysis_detail(analysis_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Không tìm thấy chi tiết phân tích")
        
    resume_data = detail.get("resume_data", {})
    scoring_breakdown = detail.get("scoring_breakdown", {})
    
    try:
        # Load associated JD content
        jd_id = detail.get("jd_id", "")
        jd_content = ""
        if jd_id and jd_id != "manual":
            jd = get_jd_by_id(jd_id)
            if jd:
                jd_content = jd["content"]
        
        # Build resume_obj
        resume_obj = CandidateResume(**resume_data) if resume_data else None
        
        # Parse fields from breakdown to build jd_obj and missing_skills
        skills_breakdown = scoring_breakdown.get("skills", {}).get("details", {})
        must_have_skills = skills_breakdown.get("matched_critical_skills", []) + skills_breakdown.get("missing_critical_skills", [])
        nice_to_have_skills = skills_breakdown.get("matched_nice_skills", []) + skills_breakdown.get("missing_nice_skills", [])

        exp_breakdown = scoring_breakdown.get("experience", {}).get("details", {})
        min_years_experience = int(exp_breakdown.get("required_years", 0))

        edu_breakdown = scoring_breakdown.get("education", {}).get("details", {})
        required_degree = edu_breakdown.get("jd_degree", "none")

        lang_breakdown = scoring_breakdown.get("language", {}).get("details", {}).get("breakdown", [])
        required_languages = {item["language"].lower(): item["required_level"].lower() for item in lang_breakdown if "language" in item and "required_level" in item}

        jd_obj = JobDescription(
            job_title=detail.get("jd_name", "Vị trí"),
            job_description=jd_content or "Job description details",
            min_years_experience=min_years_experience,
            required_degree=required_degree,
            must_have_skills=must_have_skills,
            nice_to_have_skills=nice_to_have_skills,
            required_languages=required_languages
        )
        
        # Analysis report details
        analysis_report_data = detail.get("analysis_report", {})
        missing_skills = analysis_report_data.get("missing_keywords", []) + analysis_report_data.get("missing_skills_technical", [])
        
        # Detect language
        cv_lang = language
        if language == "auto":
            # Form a text string to detect language
            cv_text = " ".join([
                getattr(resume_obj, "name", ""),
                " ".join(getattr(resume_obj, "skills", [])),
                " ".join([exp.description for exp in getattr(resume_obj, "experiences", []) if exp.description]),
                " ".join([edu.school for edu in getattr(resume_obj, "educations", []) if edu.school])
            ])
            cv_lang = detect_cv_language_by_text(cv_text)
            
        # Run tailoring
        tailored_result = tailor_cv_to_jd(resume_obj, jd_obj, missing_skills, language=cv_lang)
        
        return tailored_result.model_dump() if hasattr(tailored_result, "model_dump") else tailored_result
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Lỗi tối ưu hóa CV: {e}")


# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
