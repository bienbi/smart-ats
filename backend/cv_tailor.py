from typing import List, Optional
from pydantic import BaseModel, Field
from extract_cv import CandidateResume, JobDescription, call_llm, InterviewQuestion

class TailoredResume(BaseModel):
    markdown_content: str = Field(description="Nội dung CV đã được tối ưu hóa dưới dạng Markdown, sẵn sàng để ứng viên copy và sử dụng.")
    changes_summary: str = Field(description="Tóm tắt những thay đổi chính mà AI đã thực hiện bằng tiếng Việt (ví dụ: thêm keyword, viết lại kinh nghiệm, sử dụng động từ mạnh).")
    keywords_added: List[str] = Field(default_factory=list, description="Danh sách các từ khóa đã được thêm vào CV từ JD.")
    improvements_made: List[str] = Field(default_factory=list, description="Danh sách cải tiến đã thực hiện bằng tiếng Việt.")
    cover_letter: str = Field(default="", description="Cover letter được tạo tự động phù hợp với JD, dạng Markdown.")


class AnalysisReport(BaseModel):
    """Báo cáo phân tích CV chi tiết."""
    compatibility_score: float = Field(description="Điểm tương thích (0-100)")
    score_message: str = Field(description="Thông điệp đánh giá dựa trên điểm")
    missing_keywords: List[str] = Field(default_factory=list, description="Từ khóa từ JD không tìm thấy trong CV")
    missing_skills_technical: List[str] = Field(default_factory=list, description="Kỹ năng kỹ thuật thiếu")
    missing_skills_soft: List[str] = Field(default_factory=list, description="Kỹ năng mềm thiếu")
    strengths: List[str] = Field(default_factory=list, description="Điểm mạnh của CV so với JD")
    suggestions: List[str] = Field(default_factory=list, description="Gợi ý cải thiện cụ thể")
    areas_for_improvement: List[str] = Field(default_factory=list, description="Các lĩnh vực cần cải thiện")
    next_steps: List[str] = Field(default_factory=list, description="Các bước tiếp theo")
    recruiter_note: Optional[str] = Field(None, description="Nhận xét và khuyến nghị tuyển dụng chi tiết")
    risks: List[str] = Field(default_factory=list, description="Các rủi ro tuyển dụng cần lưu ý")
    interview_questions: List[InterviewQuestion] = Field(default_factory=list, description="Các câu hỏi phỏng vấn gợi ý")
    missing_skills_core: List[str] = Field(default_factory=list, description="Kỹ năng cốt lõi bắt buộc còn thiếu")
    missing_skills_supporting: List[str] = Field(default_factory=list, description="Kỹ năng phụ trợ còn thiếu")
    missing_skills_tools: List[str] = Field(default_factory=list, description="Công cụ/DevOps còn thiếu")


def analyze_cv_detailed(resume: CandidateResume, jd: JobDescription, scoring_result: dict) -> AnalysisReport:
    """ 
    Phân tích CV chi tiết so với JD không sử dụng AI, lấy kết quả từ extract_test.py và scoring_cv.py. 
    Tạo báo cáo đầy đủ bao gồm missing keywords, missing skills, strengths, suggestions. 
    """

    breakdown = scoring_result.get("breakdown", {})
    score = scoring_result.get("final_score_pct", 0)

    # Missing Keywords & Skills 
    skills_details = breakdown.get("skills", {}).get("details", {})
    missing_must = skills_details.get("missing_critical_skills", [])
    missing_nice = skills_details.get("missing_nice_skills", [])
    missing_keywords = missing_must + missing_nice
    
    # Strengths, trích từ các tiêu chí đạt >= 70% 
    strengths = []
    
    exp_score = breakdown.get("experience", {}).get("score", 0)
    if exp_score >= 0.7:
        exp_details = breakdown.get("experience", {}).get("details", {})
        strengths.append(
            f"Kinh nghiệm làm việc tốt: {exp_details.get('relevant_total_years', 0)} năm liên quan đến vị trí"
        )

    skill_score = breakdown.get("skills", {}).get("score", 0)
    if skill_score >= 0.7:
        strengths.append("Kỹ năng chuyên môn phù hợp tốt với yêu cầu công việc")
    elif skills_details.get("must_have_score", 0) >= 0.5:
        matched_count = len(resume.skills) - len(missing_must)
        strengths.append(f"Có nền tảng kỹ năng cốt lõi ({matched_count} kỹ năng bắt buộc đã có)")

    edu_score = breakdown.get("education", {}).get("score", 0)
    if edu_score >= 0.8:
        strengths.append("Trình độ học vấn đáp ứng tốt yêu cầu")
    
    lang_info = breakdown.get("language", {})
    lang_weight = lang_info.get("weight", 0.0)
    lang_score = lang_info.get("score", 0.0)
    if lang_weight > 0.0 and lang_score >= 0.7:
        strengths.append("Trình độ ngoại ngữ đáp ứng yêu cầu")

    stab_score = breakdown.get("stability", {}).get("score", 0)
    if stab_score >= 0.7:
        strengths.append("Mức độ gắn bó công việc tốt, ít rủi ro nhảy việc")

    if not strengths:
        strengths.append("Ứng viên có kinh nghiệm trong lĩnh vực liên quan")

    # Suggestions
    suggestions = []
    
    if missing_must:
        suggestions.append(
            f"Bổ sung các kỹ năng bắt buộc còn thiếu vào CV: {', '.join(missing_must)}"
        )
    if missing_nice:
        suggestions.append(
            f"Cân nhắc bổ sung các kỹ năng ưu tiên: {', '.join(missing_nice[:3])}"
        )
    if exp_score < 0.7:
        suggestions.append("Nhấn mạnh hơn các kinh nghiệm liên quan trực tiếp đến vị trí ứng tuyển")
    if lang_weight > 0.0 and lang_score < 0.7:
        lang_details = breakdown.get("language", {}).get("details", {})
        lang_breakdown = lang_details.get("breakdown", [])
        for lb in lang_breakdown:
            if lb.get("score", 1) < 0.7:
                suggestions.append(
                    f"Cải thiện trình độ {lb['language'].title()}: hiện tại {lb['candidate_level']}, yêu cầu {lb['required_level']}"
                )
    if stab_score < 0.5:
        suggestions.append("Giải thích lý do thay đổi công việc trong CV để giảm lo ngại về tính ổn định")
    
    if not suggestions:
        suggestions.append("CV đã khá tốt, hãy sử dụng Action Verbs để tăng sức hấp dẫn")

    # Các yếu tố cần lưu ý cải thiện
    areas = []
    if skill_score < 0.7:
        areas.append("Kỹ năng chuyên môn cần được bổ sung")
    if exp_score < 0.7:
        areas.append("Kinh nghiệm liên quan chưa đủ so với yêu cầu")
    if lang_weight > 0.0 and lang_score < 0.7:
        areas.append("Trình độ ngoại ngữ chưa đạt mức yêu cầu")
    if stab_score < 0.5:
        areas.append("Lịch sử làm việc cho thấy rủi ro nhảy việc")

    next_steps = []
    recruiter_note = scoring_result.get("recruiter_note", "N/A")

    # ── Phân loại Kỹ năng thiếu theo nhóm ──
    missing_skills_core = []
    missing_skills_supporting = []
    missing_skills_tools = []
    
    req_core = []
    req_supp = []
    req_tool = []
    
    if jd and getattr(jd, "skills_requirement", None):
        req_core = [s.lower() for s in getattr(jd.skills_requirement, "core", [])]
        req_supp = [s.lower() for s in getattr(jd.skills_requirement, "supporting", [])]
        req_tool = [s.lower() for s in getattr(jd.skills_requirement, "tools", [])]
        
    for skill in missing_must:
        skill_lower = skill.lower()
        if skill_lower in req_core:
            missing_skills_core.append(skill)
        elif skill_lower in req_supp:
            missing_skills_supporting.append(skill)
        elif skill_lower in req_tool:
            missing_skills_tools.append(skill)
        else:
            missing_skills_core.append(skill)
            
    for skill in missing_nice:
        skill_lower = skill.lower()
        if skill_lower in req_core:
            missing_skills_core.append(skill)
        elif skill_lower in req_supp:
            missing_skills_supporting.append(skill)
        elif skill_lower in req_tool:
            missing_skills_tools.append(skill)
        else:
            missing_skills_tools.append(skill)

    # ── Map thông tin từ scoring_result ──
    ai_strengths = scoring_result.get("strengths", [])
    if ai_strengths:
        strengths = ai_strengths

    risks = scoring_result.get("risks", [])
    interview_questions = scoring_result.get("interview_questions", [])
    
    validated_questions = []
    for q in interview_questions:
        if isinstance(q, dict):
            validated_questions.append(InterviewQuestion(title=q.get("title", "Câu hỏi"), question=q.get("question", "")))
        elif isinstance(q, InterviewQuestion):
            validated_questions.append(q)
        else:
            validated_questions.append(InterviewQuestion(title="Câu hỏi phỏng vấn", question=str(q)))

    # Score Message (tiếng Việt)
    if score >= 85:
        score_message = "Rất phù hợp! CV phù hợp tốt với yêu cầu công việc."
    elif score >= 70:
        score_message = "Phù hợp! CV đáp ứng tốt, có một số điểm cần cải thiện."
    elif score >= 50:
        score_message = "Phù hợp một phần. Cần cải thiện CV để phù hợp hơn với vị trí này."
    else:
        score_message = "Chưa phù hợp. Cần cải thiện đáng kể để đáp ứng yêu cầu."

    return AnalysisReport(
        compatibility_score=score,
        score_message=score_message,
        missing_keywords=missing_keywords,
        missing_skills_technical=missing_must,
        missing_skills_soft=[],
        strengths=strengths,
        suggestions=suggestions,
        areas_for_improvement=areas,
        next_steps=next_steps,
        recruiter_note=recruiter_note,
        risks=risks,
        interview_questions=validated_questions,
        missing_skills_core=missing_skills_core,
        missing_skills_supporting=missing_skills_supporting,
        missing_skills_tools=missing_skills_tools
    )
    # """
    # Phân tích CV chi tiết so với JD sử dụng AI.
    # Tạo báo cáo đầy đủ bao gồm missing keywords, missing skills, strengths, suggestions.
    # """
    # system_prompt = """
    # You are an expert ATS (Applicant Tracking System) Analyst and Career Coach. 
    # Your task is to perform a detailed analysis of the candidate's resume against the job description.
    
    # You will receive:
    # 1. The candidate's structured resume data
    # 2. The job description
    # 3. A preliminary scoring result
    
    # Based on this, you need to provide:
    # 1. Missing Keywords: Important keywords/phrases from the JD that are not present in the resume
    # 2. Missing Skills (Technical & Soft): Skills required by the JD that the candidate lacks
    # 3. Strengths: Areas where the resume already aligns well with the JD
    # 4. Suggestions: Specific, actionable ways to improve the resume for this position
    # 5. Areas for Improvement: Brief list of improvement areas
    # 6. Next Steps: Actionable next steps for the candidate
    
    # Be specific, practical, and constructive in your analysis.
    # """
    
    # user_prompt = f"""
    # === CANDIDATE'S RESUME ===
    # {resume.model_dump_json(indent=2)}
    
    # === JOB DESCRIPTION ===
    # {jd.model_dump_json(indent=2)}
    
    # === PRELIMINARY SCORING ===
    # Final Score: {scoring_result.get('final_score_pct', 0)}%
    # Recommendation: {scoring_result.get('recommendation', 'N/A')}
    # Skills breakdown: {scoring_result.get('breakdown', {}).get('skills', {}).get('details', {})}
    
    # Please provide a comprehensive analysis report.
    # """
    
    # parsed = _call_llm(
    #     messages=[
    #         {"role": "system", "content": system_prompt},
    #         {"role": "user", "content": user_prompt},
    #     ],
    #     response_format=AnalysisReport,
    # )
    
    # # Override score with our calculated score
    # parsed.compatibility_score = scoring_result.get('final_score_pct', 0)
        
    # score = parsed.compatibility_score
    # if score >= 85:
    #     parsed.score_message = "Excellent match! Your resume aligns very well with the job requirements."
    # elif score >= 70:
    #     parsed.score_message = "Good match! Your resume is well-suited with some areas for improvement."
    # elif score >= 50:
    #     parsed.score_message = "Partial match. Consider enhancing your resume to better align with this role."
    # else:
    #     parsed.score_message = "Low match. Significant improvements are needed to align with this role."
    
    # return parsed

# Phát hiện ngôn ngữ CV
def detect_cv_language(text: str) -> str:
    """Phát hiện ngôn ngữ CV: 'vi' (tiếng Việt) hoặc 'en' (tiếng Anh)."""
    import re
    vietnamese_chars = re.findall(
        r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]',
        text.lower()
    )
    ratio = len(vietnamese_chars) / max(len(text), 1)
    return 'vi' if ratio > 0.02 else 'en'


# Tối ưu lại CV theo JD, tạo thêm cover letter
def tailor_cv_to_jd(resume: CandidateResume, jd: JobDescription, missing_skills: list, language: str = "auto", raw_cv_text: str = "") -> TailoredResume:
    """
    Tự động tối ưu hoá CV để phù hợp hơn với JD (Tailor Resume).
    Sử dụng AI để viết lại bullet points, thêm từ khóa một cách tự nhiên.
    
    Args:
        language: 'en', 'vi', hoặc 'auto' (tự phát hiện từ raw_cv_text)
        raw_cv_text: Văn bản CV gốc (dùng để phát hiện ngôn ngữ nếu language='auto')
    """
    # Phát hiện ngôn ngữ
    if language == "auto" and raw_cv_text:
        language = detect_cv_language(raw_cv_text)
    elif language == "auto":
        language = "en"  # Mặc định tiếng Anh

    lang_instruction = ""
    if language == "vi":
        lang_instruction = "\n\nIMPORTANT: The original CV is in Vietnamese. Write the entire optimized resume AND cover letter in Vietnamese. Use professional Vietnamese language."
    else:
        lang_instruction = "\n\nIMPORTANT: The original CV is in English. Write the entire optimized resume AND cover letter in English."

    system_prompt = f"""
    You are an expert Career Coach and ATS Optimizer. Your task is to rewrite the candidate's resume to better align with the provided Job Description (JD).
    
    GUIDELINES:
    1. Output Format: Return a highly professional, well-formatted Markdown resume.
    2. ATS Optimization: Naturally integrate the missing keywords/skills (provided in the prompt) into the resume's experience descriptions, summary, or skills section ONLY IF it makes sense based on the candidate's existing background.
    3. Action Verbs & Impact: Rewrite the bullet points in the experience section to be more impactful, using strong action verbs and quantifying results where possible.
    4. Honesty: Do not invent completely new work experiences, companies, or degrees. Only rephrase and emphasize existing experiences to highlight their relevance to the target job.
    5. Summary: Add a strong professional summary at the top if missing, tailored specifically for the target job title.
    6. Cover Letter: Also generate a professional cover letter tailored to the job description.
    7. Keywords Added: List all the keywords from the JD that you integrated into the resume.
    8. Improvements Made: List specific improvements you made (MUST be written in Vietnamese).
    9. Changes Summary: Summarize the changes you made (MUST be written in Vietnamese).
    10. No Emojis or Icons: DO NOT include any emojis, icons, or graphic symbols (such as 📧, 📍, 📞, 💼, 🎓, 📱, 🔗, 🌐, etc.) anywhere in the generated Markdown resume or Cover Letter. Use clean, professional text formatting only.
    {lang_instruction}
    """
    
    user_prompt = f"""
    === CANDIDATE'S ORIGINAL RESUME ===
    {resume.model_dump_json(indent=2)}
    
    === TARGET JOB DESCRIPTION ===
    {jd.model_dump_json(indent=2)}
    
    === MISSING SKILLS TO INTEGRATE (If Applicable) ===
    {missing_skills}
    
    Please provide:
    1. The optimized resume in Markdown format
    2. A cover letter in Markdown format
    3. A summary of the changes made
    4. A list of keywords added
    5. A list of improvements made
    """
    
    return call_llm(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format=TailoredResume,
        max_tokens=8192,
        temperature=0.5,
    )

# Translate university names
UNIVERSITY_TRANSLATIONS = {
    "hanoi university of science and technology": "Đại học Bách Khoa Hà Nội",
    "hust": "Đại học Bách Khoa Hà Nội",
    "vietnam national university": "Đại học Quốc gia Hà Nội",
    "vietnam national university hanoi": "Đại học Quốc gia Hà Nội",
    "vnu": "Đại học Quốc gia Hà Nội",
    "vietnam national university ho chi minh city": "Đại học Quốc gia TP.HCM",
    "vietnam national university, ho chi minh city": "Đại học Quốc gia TP.HCM",
    "vnu-hcm": "Đại học Quốc gia TP.HCM",
    "national economics university": "Đại học Kinh tế Quốc dân",
    "neu": "Đại học Kinh tế Quốc dân",
    "posts and telecommunications institute of technology": "Học viện Công nghệ Bưu chính Viễn thông",
    "posts & telecommunications institute of technology": "Học viện Công nghệ Bưu chính Viễn thông",
    "ptit": "Học viện Công nghệ Bưu chính Viễn thông",
    "foreign trade university": "Đại học Ngoại thương",
    "ftu": "Đại học Ngoại thương",
    "Royal Melbourne Institute of Technology": "Đại học RMIT",
    "rmit": "Đại học RMIT",
    "fpt university": "Đại học FPT",
    "fpt": "Đại học FPT",
    "hanoi university of industry": "Đại học Công nghiệp Hà Nội",
    "haui": "Đại học Công nghiệp Hà Nội",
    "hanoi university": "Đại học Hà Nội",
    "hanu": "Đại học Hà Nội",
    "ho chi minh university of technology": "Đại học Bách khoa TP.HCM",
    "hcmut": "Đại học Bách khoa TP.HCM",
    "hanoi vocational college of technology": "Cao đẳng Nghề Bách Khoa Hà Nội",
    "hactech": "Cao đẳng Nghề Bách Khoa Hà Nội",
    "ho chi minh city university of technology and education": "Đại học Sư phạm Kỹ thuật TP.HCM",
    "hcmute": "Đại học Sư phạm Kỹ thuật TP.HCM",
    "university of technology and education": "Đại học Sư phạm Kỹ thuật",
    "ute": "Đại học Sư phạm Kỹ thuật",
    "university of engineering and technology": "Đại học Công nghệ (ĐHQGHN)",
    "vnu university of engineering and technology": "Đại học Công nghệ (ĐHQGHN)",
    "uet": "Đại học Công nghệ (ĐHQGHN)",
    "vnu-uet": "Đại học Công nghệ (ĐHQGHN)",
    "university of science": "Đại học Khoa học Tự nhiên",
    "vnu university of science": "Đại học Khoa học Tự nhiên (ĐHQGHN)",
    "hus": "Đại học Khoa học Tự nhiên",
    "vnu-hus": "Đại học Khoa học Tự nhiên (ĐHQGHN)",
    "ho chi minh city university of science": "Đại học Khoa học Tự nhiên TP.HCM",
    "hcmus": "Đại học Khoa học Tự nhiên TP.HCM",
    "academy of finance": "Học viện Tài chính",
    "aof": "Học viện Tài chính",
    "banking academy": "Học viện Ngân hàng",
    "ba": "Học viện Ngân hàng",
    "thuyloi university": "Đại học Thủy lợi",
    "tlu": "Đại học Thủy lợi",
    "transport university": "Đại học Giao thông Vận tải",
    "utc": "Đại học Giao thông Vận tải",
    "university of commerce": "Đại học Thương mại",
    "vietnam university of commerce": "Đại học Thương mại",
    "tmu": "Đại học Thương mại",
    "hanoi university of civil engineering": "Đại học Xây dựng Hà Nội",
    "huce": "Đại học Xây dựng Hà Nội",
    "nuce": "Đại học Xây dựng Hà Nội",
    "hanoi university of mining and geology": "Đại học Mỏ - Địa chất",
    "humg": "Đại học Mỏ - Địa chất",
    "electric power university": "Đại học Điện lực",
    "epu": "Đại học Điện lực",
    "military technical academy": "Học viện Kỹ thuật Quân sự",
    "mta": "Học viện Kỹ thuật Quân sự",
    "le quy don technical university": "Học viện Kỹ thuật Quân sự",
    "vietnam national university of agriculture": "Học viện Nông nghiệp Việt Nam",
    "vnua": "Học viện Nông nghiệp Việt Nam",
    "ton duc thang university": "Đại học Tôn Đức Thắng",
    "tdtu": "Đại học Tôn Đức Thắng",
    "industrial university of ho chi minh city": "Đại học Công nghiệp TP.HCM",
    "iuh": "Đại học Công nghiệp TP.HCM",
    "hanoi university of business and technology": "Đại học Kinh doanh và Công nghệ Hà Nội",
    "hubt": "Đại học Kinh doanh và Công nghệ Hà Nội",
    "hanoi open university": "Đại học Mở Hà Nội",
    "hou": "Đại học Mở Hà Nội",
}

def translate_school_name(school_name: str) -> str:
    if not school_name:
        return "N/A"
    cleaned = school_name.strip().lower().replace(".", "").replace(",", "")
    if cleaned in UNIVERSITY_TRANSLATIONS:
        return UNIVERSITY_TRANSLATIONS[cleaned]
        
    words = cleaned.split()
    for eng_name, vi_name in UNIVERSITY_TRANSLATIONS.items():
        if eng_name in words:
            return vi_name
        if len(eng_name) > 3 and eng_name in cleaned:
            return vi_name
            
    return school_name.title()

def build_detail_text_rich(key: str, details: dict, resume_data, format_type: str = "html") -> str:
    def get_safe(obj, attr, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    DEGREE_VI = {"none": "Không có", "associate": "Cao đẳng", "bachelor": "Cử nhân", "master": "Thạc sĩ", "phd": "Tiến sĩ"}
    LANG_LEVEL_VI = {"none": "Không có", "basic": "Sơ cấp", "conversational": "Giao tiếp", "fluent": "Thông thạo", "native": "Bản ngữ"}

    is_html = format_type == "html"
    br = "<br>" if is_html else "\n"
    b_start = "<b>" if is_html else "**"
    b_end = "</b>" if is_html else "**"
    red_start = "<span style='color:#ef4444;'>" if is_html else ""
    red_end = "</span>" if is_html else ""
    green_start = "<span style='color:#22c55e;'>" if is_html else ""
    green_end = "</span>" if is_html else ""

    if key == "skills":
        matched_must = details.get("matched_critical_skills", [])
        matched_nice = details.get("matched_nice_skills", [])
        eq_must = details.get("equivalent_critical_skills", [])
        eq_nice = details.get("equivalent_nice_skills", [])
        missing_must = details.get("missing_critical_skills", [])
        missing_nice = details.get("missing_nice_skills", [])

        # Fallback for older records
        if not matched_must and not matched_nice and not eq_must and not eq_nice and resume_data:
            cv_skills = get_safe(resume_data, "skills", [])
            if not isinstance(cv_skills, list) and hasattr(cv_skills, "__iter__"):
                cv_skills = list(cv_skills)
            matched_must = [s for s in cv_skills if s in missing_must]

        parts = []
        # Kỹ năng đã đạt
        parts.append(f"{b_start}Kỹ năng ĐÃ ĐẠT:{b_end}")
        if matched_must or matched_nice:
            if matched_must:
                parts.append(f"• Bắt buộc/Bổ trợ: {green_start}{', '.join(matched_must)}{green_end}")
            if matched_nice:
                parts.append(f"• Công cụ/Ưu tiên: {green_start}{', '.join(matched_nice)}{green_end}")
        else:
            parts.append("• Không có")

        # Kỹ năng tương đương
        parts.append(f"{b_start}Kỹ năng TƯƠNG ĐƯƠNG:{b_end}")
        if eq_must or eq_nice:
            if eq_must:
                parts.append(f"• Bắt buộc/Bổ trợ: {green_start}{', '.join(eq_must)}{green_end}")
            if eq_nice:
                parts.append(f"• Công cụ/Ưu tiên: {green_start}{', '.join(eq_nice)}{green_end}")
        else:
            parts.append("• Không có")

        # Kỹ năng còn thiếu
        parts.append(f"{b_start}Kỹ năng CÒN THIẾU:{b_end}")
        if missing_must or missing_nice:
            if missing_must:
                parts.append(f"• Bắt buộc/Bổ trợ: {red_start}{', '.join(missing_must)}{red_end}")
            if missing_nice:
                parts.append(f"• Công cụ/Ưu tiên: {red_start}{', '.join(missing_nice)}{red_end}")
        else:
            parts.append("• Không có")

        return br.join(parts)

    elif key == "experience":
        raw_years = details.get("raw_total_years", 0)
        rel_years = details.get("relevant_total_years", 0)
        req_years = details.get("required_years", 0)
        
        parts = [f"Tổng kinh nghiệm: {raw_years} năm. Liên quan: {rel_years}/{req_years} năm yêu cầu."]
        job_breakdown = details.get("job_breakdown", [])
        if job_breakdown:
            parts.append(f"{b_start}Chi tiết vị trí:{b_end}")
            for job in job_breakdown[:3]:
                parts.append(f"• {job.get('Job_title', 'N/A')}: {job.get('raw_years', 0)} năm ({job.get('relevance_pct', 0)}% liên quan)")
        return br.join(parts)

    elif key == "education":
        best_degree = details.get("best_matched_degree", "none")
        jd_degree = details.get("jd_degree", "none")
        major_rel = details.get("major_relevant", 0)

        schools = []
        educations = get_safe(resume_data, "educations") or []
        for edu in educations:
            school_raw = get_safe(edu, "school", "N/A")
            school_vi = translate_school_name(school_raw)
            major = get_safe(edu, "major", "N/A")
            gpa = get_safe(edu, "gpa")
            gpa_str = f" (GPA/CPA: {gpa})" if gpa and str(gpa).lower() not in ("none", "null", "") else ""
            schools.append(f"• {school_vi} - Ngành: {major}{gpa_str}")

        parts = [f"{b_start}Lịch sử học vấn:{b_end}"]
        if schools:
            parts.extend(schools)
        else:
            parts.append("• Không có thông tin trường học")
        parts.append(f"• Cấp bậc: {DEGREE_VI.get(best_degree, best_degree)} (Yêu cầu: {DEGREE_VI.get(jd_degree, jd_degree)})")
        parts.append(f"• Độ phù hợp chuyên ngành: {round(major_rel * 100)}%")
        return br.join(parts)

    elif key == "language":
        languages_list = []
        cv_languages = get_safe(resume_data, "languages") or []
        for lang in cv_languages:
            name = get_safe(lang, "name", "")
            level = get_safe(lang, "level", "")
            cert = get_safe(lang, "certificate")
            cert_str = f" ({cert})" if cert and str(cert).lower() not in ("none", "null", "không có", "") else ""
            languages_list.append(f"• {name.title()}: {LANG_LEVEL_VI.get(level.lower(), level)}{cert_str}")
        
        parts = []
        if languages_list:
            parts.append(f"{b_start}Ngoại ngữ hiện có trong CV:{b_end}")
            parts.extend(languages_list)
        else:
            parts.append("• Không có ngoại ngữ nào trong CV")
        
        lang_breakdown = details.get("breakdown", [])
        if lang_breakdown:
            parts.append(f"{b_start}Đối sánh yêu cầu:{b_end}")
            for lb in lang_breakdown:
                req_l = LANG_LEVEL_VI.get(lb.get("required_level", ""), lb.get("required_level", ""))
                cv_l = LANG_LEVEL_VI.get(lb.get("candidate_level", ""), lb.get("candidate_level", ""))
                status = "Đạt" if lb.get("score", 0) >= 1.0 else "Chưa đạt"
                parts.append(f"• {lb.get('language', '').title()}: {cv_l} (yêu cầu: {req_l}) - {status}")
        else:
            parts.append(details.get("reasoning", "JD không yêu cầu ngoại ngữ"))
            
        return br.join(parts)

    elif key == "stability":
        total_comp = details.get("total_companies", 0)
        total_yrs = details.get("total_years", 0)
        avg_tenure = details.get("average_tenure_years", 0)
        reasoning = details.get("reasoning", "")
        if total_comp:
            return f"{total_comp} công ty trong {total_yrs} năm. TB {avg_tenure} năm/công ty.{br}Phân tích: {reasoning}"
        return reasoning

    return details.get("reasoning", "")

def generate_markdown_report(analysis: AnalysisReport, resume_name: str = "Resume", position: str = "Position", scoring_result: dict = None, resume_obj = None, created_at = None) -> str:
    from datetime import datetime, timezone, timedelta
    tz_vn = timezone(timedelta(hours=7))
    
    if not created_at:
        created_at = datetime.now(timezone.utc)
    elif isinstance(created_at, str):
        try:
            if created_at.endswith('Z'):
                created_at = created_at[:-1] + '+00:00'
            created_at = datetime.fromisoformat(created_at)
        except Exception:
            created_at = datetime.now(timezone.utc)
            
    if hasattr(created_at, "tzinfo") and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
        
    local_time = created_at.astimezone(tz_vn)
    local_time_str = local_time.strftime('%d/%m/%Y lúc %H:%M')
    
    score = analysis.compatibility_score
    score_msg = analysis.score_message
    
    raw_note = analysis.recruiter_note or "Không có nhận xét."
    # Bold the phrase starting with "KHUYẾN NGHỊ" or "Khuyến nghị"
    import re
    pattern = r'\*?\*?((?:KHUYẾN NGHỊ|Khuyến nghị)[^*.]+)\*?\*?'
    formatted_note = re.sub(pattern, r'**\1**', raw_note)
    
    # ── 1. Kết quả Đánh giá Tổng quan ──
    report = f"""# Báo cáo Thẩm định Hồ sơ Ứng viên (ATS Plus)

**Ngày tạo:** {local_time_str}
**Ứng viên:** {resume_name}
**Vị trí ứng tuyển:** {position}

## 1. Kết quả Đánh giá Tổng quan

### **Điểm Tương thích: {score} / 100** — {score_msg}

### **Nhận xét & Khuyến nghị tuyển dụng (Recruiter's Note)**
> {formatted_note}

---

## 2. Bảng điểm Chi tiết (Scoring Dashboard)

| Tiêu chí | Trọng số | Điểm số (thang 100) | Điểm thành phần | Đánh giá nhanh của HR |
| :--- | :--- | :--- | :--- | :--- |
"""

    if scoring_result and scoring_result.get("breakdown"):
        criteria_names = {
            "skills": "Kỹ năng chuyên môn",
            "experience": "Kinh nghiệm thực chiến",
            "education": "Học vấn & Nền tảng",
            "language": "Trình độ Ngoại ngữ",
            "stability": "Mức độ gắn bó",
        }
        breakdown = scoring_result["breakdown"]
        for key in ["skills", "experience", "education", "language", "stability"]:
            info = breakdown.get(key, {})
            name = criteria_names.get(key, key)
            score_val = round(info.get("score", 0) * 100, 1)
            weight_pct = round(info.get("weight", 0) * 100)
            weighted_val = round(info.get("weighted_score", 0) * 100, 1)
            
            details = info.get("details", {})
            reasoning = details.get("reasoning", "N/A")
            # Clear HTML tags in reasoning for Markdown table compatibility
            import re
            clean_reasoning = re.sub(r'<[^>]*>', '', reasoning).replace("\n", " ").strip()
            
            report += f"| **{name}** | {weight_pct}% | {score_val} | {weighted_val} | {clean_reasoning} |\n"
    else:
        report += "| N/A | N/A | N/A | N/A | N/A |\n"
        
    report += "\n---\n\n## 3. Phân tích Chi tiết Lỗ hổng & Điểm mạnh\n\n"
    
    # ── Điểm mạnh ──
    report += "### Điểm mạnh Nổi bật (Core Competencies)\n"
    if analysis.strengths:
        for s in analysis.strengths:
            report += f"*   {s}\n"
    else:
        report += "*   Không có điểm mạnh nổi bật nào được ghi nhận.\n"
        
    # ── Lỗ hổng công nghệ ──
    report += "\n### Lỗ hổng Công nghệ (Kỹ năng & Từ khóa Thiếu)\n"
    core_skills_str = ", ".join(f"`{s}`" for s in analysis.missing_skills_core) if getattr(analysis, "missing_skills_core", None) else ""
    supp_skills_str = ", ".join(f"`{s}`" for s in analysis.missing_skills_supporting) if getattr(analysis, "missing_skills_supporting", None) else ""
    tool_skills_str = ", ".join(f"`{s}`" for s in analysis.missing_skills_tools) if getattr(analysis, "missing_skills_tools", None) else ""
    
    # Fallback for old records
    if not core_skills_str and not supp_skills_str and not tool_skills_str:
        all_missing = analysis.missing_keywords or analysis.missing_skills_technical
        core_skills_str = ", ".join(f"`{s}`" for s in all_missing) if all_missing else ""
        
    report += f"*   **Core Frameworks (Bắt buộc):** {core_skills_str if core_skills_str else 'Đã đáp ứng đầy đủ / Không có'}\n"
    report += f"*   **Hệ sinh thái & Phụ trợ:** {supp_skills_str if supp_skills_str else 'Đã đáp ứng đầy đủ / Không có'}\n"
    report += f"*   **Công cụ Build & DevOps:** {tool_skills_str if tool_skills_str else 'Đã đáp ứng đầy đủ / Không có'}\n"

    # ── Rủi ro tuyển dụng ──
    report += "\n### Rủi ro Tuyển dụng (Cần Lưu ý)\n"
    if getattr(analysis, "risks", None):
        for r in analysis.risks:
            report += f"*   {r}\n"
    else:
        # Fallback for old records
        if analysis.areas_for_improvement:
            for a in analysis.areas_for_improvement:
                report += f"*   {a}\n"
        else:
            report += "*   Không có rủi ro tuyển dụng nào đáng kể.\n"
            
    report += "\n---\n\n## 4. Bộ câu hỏi Gợi ý cho Vòng Phỏng vấn (Interview Guide)\n\n"
    report += "Do ứng viên có thể lệch Stack công nghệ hoặc có điểm cần làm rõ, người phỏng vấn kỹ thuật (Technical Interviewer) nên tập trung vào khả năng chuyển đổi và tư duy nền tảng:\n\n"
    
    if getattr(analysis, "interview_questions", None):
        for i, q in enumerate(analysis.interview_questions, 1):
            title = q.title if hasattr(q, "title") else q.get("title", "Câu hỏi gợi ý")
            question = q.question if hasattr(q, "question") else q.get("question", "")
            report += f"{i}.  **{title}:**\n"
            report += f"    > *\"{question}\"*\n"
    else:
        # Fallback for old records
        report += "1.  **Câu hỏi Kiểm tra Kỹ năng:**\n"
        report += f"    > *\"Bạn đã tích lũy kinh nghiệm thiết kế hệ thống như thế nào để bù đắp các công nghệ còn thiếu?\"*\n"

    return report

# Tạo báo cáo phân tích CV dạng HTML (tiếng Việt)

def generate_html_report(analysis: AnalysisReport, resume_name: str = "Resume", position: str = "Position", scoring_result: dict = None, resume_obj = None, created_at = None) -> str:
    from datetime import datetime, timezone, timedelta
    tz_vn = timezone(timedelta(hours=7))
    
    if not created_at:
        created_at = datetime.now(timezone.utc)
    elif isinstance(created_at, str):
        try:
            if created_at.endswith('Z'):
                created_at = created_at[:-1] + '+00:00'
            created_at = datetime.fromisoformat(created_at)
        except Exception:
            created_at = datetime.now(timezone.utc)
            
    if hasattr(created_at, "tzinfo") and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
        
    local_time = created_at.astimezone(tz_vn)
    local_time_str = local_time.strftime('%d/%m/%Y lúc %H:%M')
    
    score = analysis.compatibility_score
    
    raw_note = analysis.recruiter_note or "Không có nhận xét tuyển dụng chi tiết."
    clean_note = raw_note.replace("**", "")
    import re
    formatted_note_html = re.sub(r'((?:KHUYẾN NGHỊ|Khuyến nghị)[^.]+)', r'<b>\1</b>', clean_note)
    
    if score >= 85:
        score_color = "#22c55e"
    elif score >= 70:
        score_color = "#3b82f6"
    elif score >= 50:
        score_color = "#f59e0b"
    else:
        score_color = "#ef4444"
        
    # Phân loại Kỹ năng thiếu
    core_skills_html = "".join(f"<span class='badge core'>{s}</span>" for s in analysis.missing_skills_core) if getattr(analysis, "missing_skills_core", None) else ""
    supp_skills_html = "".join(f"<span class='badge supp'>{s}</span>" for s in analysis.missing_skills_supporting) if getattr(analysis, "missing_skills_supporting", None) else ""
    tool_skills_html = "".join(f"<span class='badge tool'>{s}</span>" for s in analysis.missing_skills_tools) if getattr(analysis, "missing_skills_tools", None) else ""
    
    # Fallback cho bản ghi cũ
    if not core_skills_html and not supp_skills_html and not tool_skills_html:
        all_missing = analysis.missing_keywords or analysis.missing_skills_technical
        core_skills_html = "".join(f"<span class='badge core'>{s}</span>" for s in all_missing) if all_missing else "Không có"
        
    strengths_html = "".join(f"<li>{s}</li>" for s in analysis.strengths) or "<li>Không có điểm mạnh nổi bật nào được ghi nhận.</li>"
    
    risks_list = getattr(analysis, "risks", None)
    if not risks_list:
        risks_list = analysis.areas_for_improvement
    risks_html = "".join(f"<li>{r}</li>" for r in risks_list) or "<li>Không có rủi ro tuyển dụng nào đáng kể.</li>"
    
    # Câu hỏi phỏng vấn
    questions_html = ""
    if getattr(analysis, "interview_questions", None):
        for i, q in enumerate(analysis.interview_questions, 1):
            title = q.title if hasattr(q, "title") else q.get("title", "Câu hỏi gợi ý")
            question = q.question if hasattr(q, "question") else q.get("question", "")
            questions_html += f"""
            <div class="question-card">
                <div class="question-title">{i}. {title}</div>
                <div class="question-body">"{question}"</div>
            </div>"""
    else:
        questions_html = """
        <div class="question-card">
            <div class="question-title">1. Câu hỏi Kiểm tra Kỹ năng</div>
            <div class="question-body">"Bạn đã tích lũy kinh nghiệm thiết kế hệ thống như thế nào để bù đắp các công nghệ còn thiếu?"</div>
        </div>"""

    # Bảng điểm chi tiết
    rows_html = ""
    if scoring_result and scoring_result.get("breakdown"):
        criteria_names = {
            "skills": "Kỹ năng chuyên môn",
            "experience": "Kinh nghiệm thực chiến",
            "education": "Học vấn & Nền tảng",
            "language": "Trình độ Ngoại ngữ",
            "stability": "Mức độ gắn bó",
        }
        breakdown = scoring_result["breakdown"]
        for key in ["skills", "experience", "education", "language", "stability"]:
            info = breakdown.get(key, {})
            name = criteria_names.get(key, key)
            score_val = round(info.get("score", 0) * 100, 1)
            weight_pct = round(info.get("weight", 0) * 100)
            weighted_val = round(info.get("weighted_score", 0) * 100, 1)
            
            details = info.get("details", {})
            reasoning = details.get("reasoning", "N/A")
            import re
            clean_reasoning = re.sub(r'<[^>]*>', '', reasoning).replace("\n", " ").strip()
            
            s_color = "#22c55e" if score_val >= 80 else "#3b82f6" if score_val >= 60 else "#f59e0b" if score_val >= 40 else "#ef4444"
            rows_html += f"""
            <tr>
                <td style="padding:12px;font-weight:600;">{name}</td>
                <td style="padding:12px;text-align:center;">{weight_pct}%</td>
                <td style="padding:12px;text-align:center;color:{s_color};font-weight:bold;">{score_val}</td>
                <td style="padding:12px;text-align:center;font-weight:bold;">{weighted_val}</td>
                <td style="padding:12px;font-size:0.9em;color:#4a5568;">{clean_reasoning}</td>
            </tr>"""
    else:
        rows_html = "<tr><td colspan='5' style='text-align:center;padding:12px;'>Không có dữ liệu bảng điểm</td></tr>"
        
    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Báo cáo đánh giá chi tiết</title>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html {{ zoom: 90%; }}
    body {{ font-family: 'Inter', sans-serif; max-width: 900px; margin: 0 auto; padding: 30px; color: #1e293b; background: #f8fafc; line-height: 1.6; }}
    .header-card {{ background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); color: white; padding: 24px 30px; border-radius: 16px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(99, 102, 241, 0.15); }}
    .header-card h1 {{ margin: 0; font-size: 28px; font-weight: 700; }}
    .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px; font-size: 14px; opacity: 0.9; }}
    
    .section-card {{ background: white; border-radius: 16px; padding: 24px 30px; margin-bottom: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); border: 1px solid #f1f5f9; }}
    .section-title {{ font-size: 20px; font-weight: 600; color: #0f172a; margin-top: 0; margin-bottom: 20px; border-left: 4px solid #4f46e5; padding-left: 12px; }}
    
    .score-container {{ display: flex; align-items: center; justify-content: center; flex-direction: column; margin-bottom: 20px; }}
    .score-circle {{ width: 100px; height: 100px; border-radius: 50%; border: 6px solid #e2e8f0; display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 700; color: {score_color}; margin-bottom: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
    .score-message {{ font-size: 16px; font-weight: 600; color: #334155; }}
    
    .recruiter-note {{ background: #f0fdfa; border-left: 4px solid #14b8a6; padding: 16px 20px; border-radius: 0 12px 12px 0; margin-top: 15px; font-style: italic; color: #0f766e; }}
    
    table {{ width: 100%; border-collapse: collapse; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; font-size: 14px;}}
    th {{ background: #f1f5f9; color: #475569; padding: 12px; font-weight: 600; text-align: left; border-bottom: 2px solid #e2e8f0; }}
    td {{ border-bottom: 1px solid #e2e8f0; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:nth-child(even) {{ background: #f8fafc; }}
    
    ul.checklist {{ list-style-type: disc; padding-left: 20px; margin: 0; }}
    ul.checklist li {{ margin-bottom: 10px; font-size: 15px; }}
    
    .tech-grid {{ display: grid; gap: 15px; margin-top: 15px; }}
    .tech-item {{ background: #f8fafc; padding: 12px 16px; border-radius: 8px; border: 1px solid #e2e8f0; }}
    .tech-label {{ font-weight: 600; color: #475569; font-size: 14px; margin-bottom: 6px; }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: 500; margin-right: 6px; margin-bottom: 6px; }}
    .badge.core {{ background: #fee2e2; color: #ef4444; border: 1px solid #fca5a5; }}
    .badge.supp {{ background: #ffedd5; color: #f97316; border: 1px solid #fdba74; }}
    .badge.tool {{ background: #f3e8ff; color: #a855f7; border: 1px solid #d8b4fe; }}
    
    .question-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; margin-bottom: 15px; }}
    .question-title {{ font-weight: 600; color: #4f46e5; margin-bottom: 8px; font-size: 15px; }}
    .question-body {{ font-style: italic; color: #475569; border-left: 3px solid #cbd5e1; padding-left: 12px; }}
    
    footer {{ text-align: center; color: #94a3b8; font-size: 13px; margin-top: 40px; border-top: 1px solid #e2e8f0; padding-top: 20px; }}
</style>
</head>
<body>

<div class="header-card">
    <h1>Báo cáo đánh giá chi tiết</h1>
    <div class="meta-grid">
        <div><strong>Ứng viên:</strong> {resume_name}</div>
        <div><strong>Ngày tạo:</strong> {local_time_str}</div>
        <div><strong>Vị trí ứng tuyển:</strong> {position}</div>
    </div>
</div>

<div class="section-card">
    <h2 class="section-title">1. Đánh giá tổng quan</h2>
    <div class="score-container">
        <div class="score-circle">{score}</div>
        <div class="score-message">{analysis.score_message}</div>
    </div>
    
    <div style="font-weight: 600; color: #0f172a; margin-top: 20px;">Nhận xét & khuyến nghị tuyển dụng</div>
    <div class="recruiter-note">
        {formatted_note_html}
    </div>
</div>

<div class="section-card">
    <h2 class="section-title">2. Bảng điểm chi tiết</h2>
    <table style="width:100%; margin-top: 10px;">
        <thead>
            <tr>
                <th style="padding:12px;text-align:left;">Tiêu chí</th>
                <th style="padding:12px;text-align:center;width:100px;">Trọng số</th>
                <th style="padding:12px;text-align:center;width:120px;">Điểm số (100)</th>
                <th style="padding:12px;text-align:center;width:130px;">Điểm thành phần</th>
                <th style="padding:12px;text-align:left;">Đánh giá nhanh</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    <p style="font-size:0.85em;color:#64748b;margin-top:12px;">
        <strong>Ghi chú giải thích cách tính điểm:</strong><br>
        - <strong>Điểm số (thang 100):</strong> Điểm đánh giá độc lập của tiêu chí đó (thang 0-100).<br>
        - <strong>Điểm thành phần:</strong> Điểm đóng góp của tiêu chí sau khi nhân trọng số (Điểm thành phần = Điểm số x Trọng số). Tổng 5 điểm thành phần chính là Điểm Tương thích cuối cùng.
    </p>
</div>

<div class="section-card">
    <h2 class="section-title">3. Phân tích Chi tiết Lỗ hổng & Điểm mạnh</h2>
    
    <h3 style="font-size:16px;font-weight:600;color:#0f172a;margin-top:15px;margin-bottom:10px;">Điểm mạnh</h3>
    <ul class="checklist">
        {strengths_html}
    </ul>
    
    <h3 style="font-size:16px;font-weight:600;color:#0f172a;margin-top:25px;margin-bottom:10px;">Kỹ năng & từ khóa còn thiếu</h3>
    <div class="tech-grid">
        <div class="tech-item">
            <div class="tech-label">Core Frameworks (Bắt buộc)</div>
            <div>{core_skills_html if core_skills_html else "<span style='color:#64748b;font-size:13px;'>Đã đáp ứng đầy đủ / Không có</span>"}</div>
        </div>
        <div class="tech-item">
            <div class="tech-label">Hệ sinh thái & Phụ trợ</div>
            <div>{supp_skills_html if supp_skills_html else "<span style='color:#64748b;font-size:13px;'>Đã đáp ứng đầy đủ / Không có</span>"}</div>
        </div>
        <div class="tech-item">
            <div class="tech-label">Công cụ Build & DevOps</div>
            <div>{tool_skills_html if tool_skills_html else "<span style='color:#64748b;font-size:13px;'>Đã đáp ứng đầy đủ / Không có</span>"}</div>
        </div>
    </div>
    
    <h3 style="font-size:16px;font-weight:600;color:#0f172a;margin-top:25px;margin-bottom:10px;">Rủi ro tuyển dụng</h3>
    <ul class="checklist">
        {risks_html}
    </ul>
</div>

</body>
</html>"""
    
    return html
    
    return html


if __name__ == "__main__":
    from extract_test import process_cv_and_jd
    from scoring_cv import CVScoresAggregator
    
    # ── 1. ĐẦU VÀO ──
    CV_FILE_PATH = r"E:\ĐANC 20262\CV mẫu\son_do_hoang.pdf"
    JD_TEXT = """
    Senior iOS Developer

    We are looking for a Senior iOS Developer with at least 5 years of experience.

    Requirements:
    - Proficient in Swift and SwiftUI
    - Experience with RxSwift or Combine
    - Familiar with MVVM or Clean Architecture
    - Experience with RESTful APIs
    - Proficient English communication (working with foreign clients)

    Nice to have:
    - Experience with CI/CD (Fastlane, Jenkins, Github Actions)
    - Knowledge of StoreKit or In-App Purchase
    - JLPT N3 or above (Japanese)
    - Experience with Flutter or React Native
    """

    print("=" * 60)
    print("  TEST TỐI ƯU VÀ VIẾT LẠI CV BẰNG AI")
    print("=" * 60)

    try:
        # Bước 1: Trích xuất & Chấm điểm (Lấy context)
        print("\n[1/4] Đang đọc và chấm điểm CV gốc...")
        cv_data, jd_data, resume_obj, jd_obj = process_cv_and_jd(CV_FILE_PATH, JD_TEXT)
        aggregator = CVScoresAggregator()
        score_result = aggregator.score_cv(cv_data, jd_data)
        
        print(f"Điểm CV gốc: {score_result['final_score_pct']}%")

        # Bước 2: AI Phân tích chi tiết điểm yếu
        print("\n[2/4] AI đang phân tích lỗi sai và kỹ năng còn thiếu...")
        analysis = analyze_cv_detailed(resume_obj, jd_obj, score_result)
        all_missing = analysis.missing_keywords + analysis.missing_skills_technical
        
        print(f"Các từ khóa bị thiếu: {', '.join(all_missing) if all_missing else 'Không có'}")
        print("Gợi ý cải thiện:")
        for s in analysis.suggestions[:2]: # In 2 gợi ý đầu
            print(f"     - {s}")

        # Bước 3: AI Tối ưu và viết lại CV
        print("\n[3/4] AI đang viết lại CV (Tailoring)... (Quá trình này có thể mất 15-30 giây)")
        tailored = tailor_cv_to_jd(resume_obj, jd_obj, all_missing)
        
        print(f"Đã chèn thêm các từ khóa: {', '.join(tailored.keywords_added)}")
        print("Các cải tiến đã làm:")
        for imp in tailored.improvements_made:
            print(f"     - {imp}")

        # Bước 4: Xuất file báo cáo
        print("\n[4/4] Đang lưu kết quả ra file...")
        
        # 4.1 Lưu CV mới (Markdown)
        with open("CV_Da_Toi_Uu.md", "w", encoding="utf-8") as f:
            f.write(tailored.markdown_content)
            
        # 4.2 Lưu Cover Letter (Markdown)
        with open("Thu_Xin_Viec.md", "w", encoding="utf-8") as f:
            f.write(tailored.cover_letter)
            
        # 4.3 Lưu Báo cáo phân tích (HTML)
        html_report = generate_html_report(analysis, resume_name="Sơn Đỗ Hoàng", position="Senior iOS Developer")
        with open("Bao_Cao_ATS.html", "w", encoding="utf-8") as f:
            f.write(html_report)

        print("\nHOÀN TẤT! Bạn hãy mở các file sau để kiểm tra:")
        print("   1. CV_Da_Toi_Uu.md  (Bản CV đã được AI xào nấu lại)")
        print("   2. Thu_Xin_Viec.md  (Thư ứng tuyển AI viết sẵn)")
        print("   3. Bao_Cao_ATS.html (Báo cáo lỗi đẹp mắt)")

    except Exception as e:
        print(f"\nĐã xảy ra lỗi: {e}")