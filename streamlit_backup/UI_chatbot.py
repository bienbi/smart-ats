import json
import os
import re
import tempfile
import streamlit as st
from chatbot import InterviewChatbot
from database import get_all_jds, find_analysis_by_hash_or_filename, save_analysis
from extract_cv import process_cv_and_jd, CandidateResume, JobDescription, extract_text_from_cv
from scoring_cv import CVScoresAggregator
from cv_tailor import tailor_cv_to_jd, analyze_cv_detailed, AnalysisReport


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _has_cv_analysis(prefix: str = "") -> bool:
    """Kiểm tra xem đã có dữ liệu phân tích CV trong session chưa."""
    required = (f"{prefix}cv_data", f"{prefix}jd_data", f"{prefix}result")
    return all(k in st.session_state for k in required)


def _get_bot() -> InterviewChatbot | None:
    data = st.session_state.get("interview_bot")
    if not data:
        return None
    return InterviewChatbot.from_dict(data)


def _save_bot(bot: InterviewChatbot) -> None:
    st.session_state["interview_bot"] = bot.to_dict()


def _render_summary(summary: dict) -> None:
    st.markdown("## Kết quả phỏng vấn")

    c1, c2, c3 = st.columns(3)
    c1.metric("Điểm CV", f"{summary.get('cv_score_pct', 0)}%")
    c2.metric("Điểm phỏng vấn", f"{summary.get('interview_score', 0)}/10")
    c3.metric("Khuyến nghị", summary.get("hiring_recommendation", "N/A"))

    st.markdown(f"**Ứng viên:** {summary.get('candidate_name', 'N/A')}")
    st.markdown(f"**Vị trí:** {summary.get('job_title', 'N/A')}")
    st.markdown(f"**Năng lực kỹ thuật:** {summary.get('technical_competency', 'N/A')}")
    st.markdown(f"**Giao tiếp:** {summary.get('communication_quality', 'N/A')}")

    if summary.get("key_strengths"):
        st.markdown("### Điểm mạnh")
        for item in summary["key_strengths"]:
            st.markdown(f"- {item}")

    if summary.get("areas_of_concern"):
        st.markdown("### Cần lưu ý")
        for item in summary["areas_of_concern"]:
            st.markdown(f"- {item}")

    st.markdown("### Đánh giá chi tiết")
    st.write(summary.get("detailed_assessment", ""))

    with st.expander("Chi tiết từng câu hỏi", expanded=False):
        for ev in summary.get("question_evaluations", []):
            st.markdown(f"**Câu {ev['question_number']}** ({ev['category']} | {ev['related_skill']})")
            st.markdown(f"> {ev['question']}")
            st.markdown(f"**Trả lời:** {ev['candidate_answer']}")
            st.markdown(f"**Điểm:** {ev['score']}/10")
            if ev.get("strengths"):
                st.markdown("Điểm mạnh: " + ", ".join(ev["strengths"]))
            if ev.get("weaknesses"):
                st.markdown("Cần cải thiện: " + ", ".join(ev["weaknesses"]))
            st.divider()

    st.download_button(
        "Tải kết quả JSON",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "ket_qua_phong_van.json",
        "application/json",
        use_container_width=True,
    )


def _detect_language(text: str) -> str:
    """Phát hiện ngôn ngữ CV: 'vi' nếu tiếng Việt, 'en' nếu tiếng Anh."""
    vietnamese_chars = re.findall(
        r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]',
        text.lower(),
    )
    ratio = len(vietnamese_chars) / max(len(text), 1)
    return "vi" if ratio > 0.02 else "en"


def _save_uploaded_cv(uploaded_file) -> str:
    """Lưu file upload tạm thời và trả về đường dẫn."""
    suffix = os.path.splitext(uploaded_file.name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.getvalue())
    tmp.close()
    return tmp.name


def _run_analysis_pipeline(uploaded_file, jd_content: str, jd_id: str, jd_name: str, prefix: str = ""):
    """
    Pipeline phân tích CV: upload -> extract → score.
    Lưu kết quả vào session_state với prefix cho mỗi trang.
    Trả về True nếu thành công.
    Tích hợp cache lookup trên MongoDB để tránh gọi API nhiều lần.
    """
    try:
        # Tính SHA-256 hash của CV
        import hashlib
        file_bytes = uploaded_file.getvalue()
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Kiểm tra xem CV đã được phân tích cho JD này chưa
        analysis_doc = None
        if jd_id and jd_id != "manual":
            with st.spinner("Đang tìm kiếm kết quả phân tích cũ trong database..."):
                try:
                    analysis_doc = find_analysis_by_hash_or_filename(file_hash, uploaded_file.name, jd_id)
                except Exception as db_err:
                    st.warning(f"⚠️ Lỗi khi tìm cache trong database: {db_err}")

        if analysis_doc:
            st.info("Đã tìm thấy kết quả phân tích trùng khớp trong database. Đang tải dữ liệu...")
            
            # Tái dựng resume_obj
            resume_data = analysis_doc.get("resume_data", {})
            resume_obj = CandidateResume(**resume_data) if resume_data else None

            # Tái dựng scoring_result (result)
            scoring_result = {
                "final_score_pct": analysis_doc.get("total_score", 0.0),
                "recommendation": analysis_doc.get("recommendation", ""),
                "weights_used": analysis_doc.get("weights_used", {}),
                "breakdown": analysis_doc.get("scoring_breakdown", {})
            }

            # Trích xuất dữ liệu từ scoring_breakdown để dựng jd_obj và cv_data/jd_data
            breakdown = scoring_result["breakdown"]
            skills_breakdown = breakdown.get("skills", {}).get("details", {})
            must_have_skills = skills_breakdown.get("matched_critical_skills", []) + skills_breakdown.get("missing_critical_skills", [])
            nice_to_have_skills = skills_breakdown.get("matched_nice_skills", []) + skills_breakdown.get("missing_nice_skills", [])

            exp_breakdown = breakdown.get("experience", {}).get("details", {})
            min_years_experience = int(exp_breakdown.get("required_years", 0))

            edu_breakdown = breakdown.get("education", {}).get("details", {})
            required_degree = edu_breakdown.get("jd_degree", "none")

            lang_breakdown = breakdown.get("language", {}).get("details", {}).get("breakdown", [])
            required_languages = {item["language"].lower(): item["required_level"].lower() for item in lang_breakdown if "language" in item and "required_level" in item}

            # Tái dựng jd_obj
            jd_obj = JobDescription(
                job_title=analysis_doc.get("jd_name", "Vị trí"),
                job_description=jd_content,
                min_years_experience=min_years_experience,
                required_degree=required_degree,
                must_have_skills=must_have_skills,
                nice_to_have_skills=nice_to_have_skills,
                required_languages=required_languages
            )

            # Tái dựng cv_data
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

            cv_data = {
                "experience_history": exp_history,
                "education_history": edu_history,
                "matched_must_have_skills": skills_breakdown.get("matched_critical_skills", []),
                "matched_nice_to_have_skills": skills_breakdown.get("matched_nice_skills", []),
                "languages": languages
            }

            # Tái dựng jd_data
            jd_data = {
                "required_experience_years": min_years_experience,
                "required_degree": required_degree,
                "must_have_skills": must_have_skills,
                "nice_to_have_skills": nice_to_have_skills,
                "required_languages": required_languages
            }

            # Lưu vào session
            st.session_state[f"{prefix}cv_data"] = cv_data
            st.session_state[f"{prefix}jd_data"] = jd_data
            st.session_state[f"{prefix}result"] = scoring_result
            st.session_state[f"{prefix}resume_obj"] = resume_obj
            st.session_state[f"{prefix}jd_obj"] = jd_obj
            st.session_state[f"{prefix}cv_filename"] = uploaded_file.name
            st.session_state[f"{prefix}raw_cv_text"] = file_bytes

            # Tạo cv_raw_text cho việc phát hiện ngôn ngữ
            cv_text_for_lang = " ".join([
                getattr(resume_obj, "name", ""),
                " ".join(getattr(resume_obj, "skills", [])),
                " ".join([exp.description for exp in getattr(resume_obj, "experiences", [])]),
                " ".join([edu.school for edu in getattr(resume_obj, "educations", [])])
            ])
            st.session_state[f"{prefix}cv_raw_text"] = cv_text_for_lang
            return True

        # Nếu không có cache trong database: Chạy pipeline phân tích qua API
        file_path = _save_uploaded_cv(uploaded_file)

        with st.spinner("Đang trích xuất và phân tích CV từ API"):
            cv_data, jd_data, resume_obj, jd_obj = process_cv_and_jd(file_path, jd_content, jd_id)

        with st.spinner("Đang chấm điểm CV"):
            aggregator = CVScoresAggregator()
            result = aggregator.score_cv(cv_data, jd_data)

        # Lưu vào session
        st.session_state[f"{prefix}cv_data"] = cv_data
        st.session_state[f"{prefix}jd_data"] = jd_data
        st.session_state[f"{prefix}result"] = result
        st.session_state[f"{prefix}resume_obj"] = resume_obj
        st.session_state[f"{prefix}jd_obj"] = jd_obj
        st.session_state[f"{prefix}cv_filename"] = uploaded_file.name
        st.session_state[f"{prefix}raw_cv_text"] = file_bytes

        # Đọc raw text để detect language
        raw_text = extract_text_from_cv(file_path)
        st.session_state[f"{prefix}cv_raw_text"] = raw_text

        # Cleanup temp file
        try:
            os.unlink(file_path)
        except OSError:
            pass

        # Lưu bản ghi mới vào MongoDB để làm cache cho lần sau
        if jd_id and jd_id != "manual":
            with st.spinner("Đang lưu kết quả phân tích vào database"):
                try:
                    # Tạo AnalysisReport cho save_analysis
                    try:
                        analysis = analyze_cv_detailed(resume_obj, jd_obj, result)
                    except Exception:
                        sk = result["breakdown"].get("skills", {}).get("details", {})
                        analysis = AnalysisReport(
                            compatibility_score=result["final_score_pct"],
                            score_message=result["recommendation"],
                            missing_keywords=sk.get("missing_critical_skills", []) + sk.get("missing_nice_skills", []),
                            missing_skills_technical=sk.get("missing_critical_skills", []),
                            missing_skills_soft=[], strengths=[], suggestions=[],
                            areas_for_improvement=[], next_steps=[],
                        )

                    save_analysis(
                        candidate_name=getattr(resume_obj, "name", "N/A"),
                        email=getattr(resume_obj, "email", "") or "",
                        filename=uploaded_file.name,
                        jd_id=jd_id,
                        jd_name=jd_name,
                        total_score=result["final_score_pct"],
                        recommendation=result["recommendation"],
                        scoring_breakdown=result["breakdown"],
                        resume_data=resume_obj.model_dump() if hasattr(resume_obj, "model_dump") else {},
                        analysis_report=analysis.model_dump() if hasattr(analysis, "model_dump") else {},
                        filter_results={},
                        weights_used=aggregator.weights,
                        file_hash=file_hash,
                    )
                except Exception as db_err:
                    st.warning(f"Không thể lưu kết quả phân tích vào database: {db_err}")

        return True
    except Exception as e:
        import traceback
        st.error(f"Lỗi khi phân tích CV: {e}")
        st.code(traceback.format_exc())
        return False


def _render_cv_upload_section(prefix: str = "", key_suffix: str = ""):
    """
    Render phần upload CV + chọn JD chung cho cả 2 trang.
    Trả về True nếu đã có dữ liệu phân tích sẵn sàng.
    """
    if _has_cv_analysis(prefix):
        # Đã phân tích rồi — show tóm tắt
        result = st.session_state[f"{prefix}result"]
        resume_obj = st.session_state.get(f"{prefix}resume_obj")
        jd_obj = st.session_state.get(f"{prefix}jd_obj")
        candidate_name = getattr(resume_obj, "name", "Ứng viên") if resume_obj else "Ứng viên"
        job_title = getattr(jd_obj, "job_title", "Vị trí") if jd_obj else "Vị trí"

        col1, col2, col3 = st.columns(3)
        col1.metric("Ứng viên", candidate_name)
        col2.metric("Vị trí", job_title)
        col3.metric("Điểm CV", f"{result.get('final_score_pct', 0)}%")

        if st.button("Phân tích CV khác", key=f"reset_{key_suffix}", use_container_width=True):
            for k in list(st.session_state.keys()):
                if prefix and k.startswith(prefix):
                    del st.session_state[k]
            # Cũng xoá state phỏng vấn và tối ưu CV của ứng viên
            for k in ("interview_bot", "interview_summary", "last_eval", "tailor_result", "tailor_analysis"):
                st.session_state.pop(k, None)
            st.rerun()

        st.divider()
        return True

    # Chưa có dữ liệu — show form upload
    st.markdown(
        '<div style="background:linear-gradient(135deg,#ede9fe,#f5f3ff);padding:20px;border-radius:12px;'
        'border-left:4px solid #7c3aed;margin-bottom:20px">'
        '<h4 style="color:#7c3aed;margin:0 0 8px 0">📄 Tải lên CV và chọn JD</h4>'
        '<p style="color:#666;margin:0;font-size:14px">Upload CV (PDF/DOCX) và chọn mô tả công việc để bắt đầu</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Tải lên CV (PDF hoặc DOCX)",
        type=["pdf", "docx"],
        key=f"cv_upload_{key_suffix}",
    )

    # Lấy danh sách JD từ database
    try:
        jds = get_all_jds()
    except Exception:
        jds = []

    selected_jd_content = ""
    selected_jd_name = ""
    selected_jd_id = ""

    if not jds:
        st.warning("Chưa có JD nào trong hệ thống. Vui lòng liên hệ HR để thêm JD hoặc nhập JD thủ công.")
        jd_text_manual = st.text_area(
            "Hoặc nhập JD thủ công:",
            height=200,
            key=f"jd_manual_{key_suffix}",
            placeholder="Dán nội dung mô tả công việc (Job Description) vào đây...",
        )
        selected_jd_content = jd_text_manual.strip() if jd_text_manual else ""
        selected_jd_name = "JD thủ công"
        selected_jd_id = "manual"
    else:
        jd_options = {f"{jd['name']}": jd for jd in jds}
        selected_name = st.selectbox(
            "Chọn mô tả công việc (JD)",
            options=list(jd_options.keys()),
            key=f"jd_select_{key_suffix}",
        )
        if selected_name:
            selected_jd = jd_options[selected_name]
            selected_jd_content = selected_jd["content"]
            selected_jd_name = selected_jd["name"]
            selected_jd_id = selected_jd["id"]
            with st.expander("Xem nội dung JD", expanded=False):
                st.text(selected_jd_content)
        else:
            selected_jd_content = ""
            selected_jd_name = ""
            selected_jd_id = ""

    # Nút phân tích
    if st.button("Phân tích CV", type="primary", use_container_width=True, key=f"analyze_{key_suffix}"):
        if not uploaded_file:
            st.warning("Vui lòng tải lên file CV.")
            return False
        if not selected_jd_content:
            st.warning("Vui lòng chọn hoặc nhập JD.")
            return False

        success = _run_analysis_pipeline(
            uploaded_file=uploaded_file,
            jd_content=selected_jd_content,
            jd_id=selected_jd_id,
            jd_name=selected_jd_name,
            prefix=prefix
        )
        if success:
            st.success("Phân tích CV thành công!")
            st.rerun()

    return False


# ──────────────────────────────────────────────
#  TRANG 1: Phỏng vấn AI
# ──────────────────────────────────────────────

def render_interview_page() -> None:
    st.markdown(
        '<h1 style="text-align:center;color:#7c3aed;">🎤 Luyện tập phỏng vấn</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="text-align:center;color:#666;">Mô phỏng buổi phỏng vấn dựa trên kết quả phân tích CV</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    # Phần upload CV + chọn JD (dùng prefix chung candidate_ để chia sẻ dữ liệu)
    PREFIX = "candidate_"
    if not _render_cv_upload_section(prefix=PREFIX, key_suffix="interview"):
        return

    # ── Từ đây trở đi, đã có dữ liệu phân tích ──
    result = st.session_state[f"{PREFIX}result"]
    resume_obj = st.session_state.get(f"{PREFIX}resume_obj")
    jd_obj = st.session_state.get(f"{PREFIX}jd_obj")
    candidate_name = getattr(resume_obj, "name", "Ứng viên") if resume_obj else "Ứng viên"
    job_title = getattr(jd_obj, "job_title", "Vị trí tuyển dụng") if jd_obj else "Vị trí tuyển dụng"

    # Nếu đã có kết quả phỏng vấn
    if "interview_summary" in st.session_state:
        _render_summary(st.session_state["interview_summary"])
        st.divider()
        if st.button("Phỏng vấn lại", use_container_width=True):
            for k in ("interview_bot", "interview_summary", "last_eval"):
                st.session_state.pop(k, None)
            st.rerun()
        return

    bot = _get_bot()

    if bot is None:
        if st.button("Bắt đầu phỏng vấn", type="primary", use_container_width=True):
            with st.spinner("Đang tạo câu hỏi phỏng vấn..."):
                try:
                    resume_detail = resume_obj.model_dump() if resume_obj else None
                    jd_detail = jd_obj.model_dump() if jd_obj else None
                    bot = InterviewChatbot(
                        resume_data=st.session_state[f"{PREFIX}cv_data"],
                        jd_data=st.session_state[f"{PREFIX}jd_data"],
                        scoring_result=result,
                        candidate_name=candidate_name,
                        job_title=job_title,
                        resume_detail=resume_detail,
                        jd_detail=jd_detail,
                    )
                    bot.generate_questions()
                    _save_bot(bot)
                except Exception as e:
                    st.error(f"Lỗi: {e}")
                    return
            st.rerun()
        return

    # ── Luồng hỏi-đáp ──
    q_info = bot.get_next_question()
    if q_info is None:
        with st.spinner("Đang tổng kết buổi phỏng vấn"):
            try:
                summary = bot.generate_summary()
                st.session_state["interview_summary"] = summary
                _save_bot(bot)
            except Exception as e:
                st.error(f"Lỗi tổng kết: {e}")
                return
        st.rerun()

    if "last_eval" in st.session_state:
        ev = st.session_state.pop("last_eval")
        st.success(f"Đã chấm câu {ev['question_number']}: {ev['score']}/10")
        if ev.get("strengths"):
            st.markdown("**Điểm mạnh:** " + ", ".join(ev["strengths"]))
        if ev.get("weaknesses"):
            st.markdown("**Cần cải thiện:** " + ", ".join(ev["weaknesses"]))
        if ev.get("reasoning"):
            st.caption(ev["reasoning"])
        st.divider()

    st.markdown(
        f"### Câu {q_info['question_number']}/{q_info['total_questions']}"
    )
    st.caption(f"Loại: {q_info['category']} | Độ khó: {q_info['difficulty']} | Kỹ năng: {q_info['related_skill']}")
    if q_info.get("cv_reference") and q_info["cv_reference"] != "N/A - tình huống giả định":
        st.caption(f"Dựa trên CV: {q_info['cv_reference']}")
    st.markdown(f"**{q_info['question']}**")
    if q_info.get("purpose"):
        st.caption(f"Mục đích: {q_info['purpose']}")

    answer = st.text_area("Câu trả lời của bạn", height=150, key=f"answer_{q_info['question_number']}")

    c1, c2 = st.columns(2)
    with c1:
        submit = st.button("Gửi câu trả lời", type="primary", use_container_width=True)
    with c2:
        skip = st.button("Bỏ qua", use_container_width=True)

    if submit:
        if not answer.strip():
            st.warning("Vui lòng nhập câu trả lời hoặc bấm Bỏ qua.")
            return
        with st.spinner("AI đang đánh giá câu trả lời"):
            try:
                eval_result = bot.submit_answer(answer.strip())
                _save_bot(bot)
                st.session_state["last_eval"] = eval_result
            except Exception as e:
                st.error(f"Lỗi: {e}")
                return
        st.rerun()

    if skip:
        with st.spinner("Đang bỏ qua câu hỏi"):
            try:
                eval_result = bot.skip_question()
                _save_bot(bot)
                st.session_state["last_eval"] = eval_result
            except Exception as e:
                st.error(f"Lỗi: {e}")
                return
        st.rerun()


# ──────────────────────────────────────────────
#  TRANG 2: Tối ưu CV
# ──────────────────────────────────────────────

def render_tailor_page() -> None:
    st.markdown(
        '<h1 style="text-align:center;color:#7c3aed;">Tối ưu CV</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="text-align:center;color:#666;">Tối ưu hóa CV của bạn để phù hợp hơn với mô tả công việc</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    # Phần upload CV + chọn JD
    PREFIX = "candidate_"
    if not _render_cv_upload_section(prefix=PREFIX, key_suffix="tailor"):
        return

    # ── Đã có dữ liệu phân tích — hiển thị tóm tắt ──
    result = st.session_state[f"{PREFIX}result"]
    resume_obj = st.session_state.get(f"{PREFIX}resume_obj")
    jd_obj = st.session_state.get(f"{PREFIX}jd_obj")
    candidate_name = getattr(resume_obj, "name", "Ứng viên") if resume_obj else "Ứng viên"
    job_title = getattr(jd_obj, "job_title", "Vị trí") if jd_obj else "Vị trí"

    # Hiện kết quả phân tích ngắn gọn
    with st.expander("Kết quả phân tích CV", expanded=True):
        score_pct = result.get("final_score_pct", 0)
        recommendation = result.get("recommendation", "N/A")

        # Thanh điểm
        if score_pct >= 80:
            bar_color = "#22c55e"
        elif score_pct >= 65:
            bar_color = "#3b82f6"
        elif score_pct >= 50:
            bar_color = "#f59e0b"
        else:
            bar_color = "#ef4444"

        st.markdown(
            f'<div style="background:#f8f9fa;padding:16px;border-radius:10px;margin-bottom:12px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
            f'<span style="font-weight:600;color:#333">Điểm tương thích</span>'
            f'<span style="font-size:24px;font-weight:bold;color:{bar_color}">{score_pct}%</span></div>'
            f'<div style="background:#e5e7eb;border-radius:8px;height:10px;overflow:hidden">'
            f'<div style="background:{bar_color};height:100%;width:{min(score_pct, 100)}%;border-radius:8px"></div>'
            f'</div>'
            f'<p style="color:#666;font-size:13px;margin-top:8px">{recommendation}</p></div>',
            unsafe_allow_html=True,
        )

        # Kỹ năng thiếu
        breakdown = result.get("breakdown", {})
        skills_details = breakdown.get("skills", {}).get("details", {})
        missing_critical = skills_details.get("missing_critical_skills", [])
        missing_nice = skills_details.get("missing_nice_skills", [])

        if missing_critical:
            st.markdown("**Kỹ năng bắt buộc còn thiếu:**")
            st.markdown(", ".join(f"`{s}`" for s in missing_critical))
        if missing_nice:
            st.markdown("**Kỹ năng ưu tiên còn thiếu:**")
            st.markdown(", ".join(f"`{s}`" for s in missing_nice))
        if not missing_critical and not missing_nice:
            st.success("CV đã đáp ứng tất cả kỹ năng yêu cầu!")

    st.divider()

    # ── Nút Tối ưu CV ──
    if "tailor_result" not in st.session_state:
        st.markdown(
            '<div style="background:#fef3c7;padding:16px;border-radius:10px;border-left:4px solid #f59e0b;margin-bottom:16px">'
            '<p style="margin:0;color:#92400e;font-size:14px">'
            '<strong>AI sẽ tối ưu CV</strong> của bạn bằng cách thêm từ khóa phù hợp, '
            'viết lại các mục kinh nghiệm với động từ mạnh hơn, và tạo thư xin việc tự động. '
            'Nội dung gốc sẽ được giữ nguyên — chỉ tối ưu cách trình bày.</p></div>',
            unsafe_allow_html=True,
        )

        if st.button("Tối ưu CV ngay", type="primary", use_container_width=True, key="btn_tailor"):
            with st.spinner("AI đang tối ưu hóa CV"):
                try:
                    # Phân tích chi tiết
                    analysis = analyze_cv_detailed(resume_obj, jd_obj, result)
                    all_missing = analysis.missing_keywords + analysis.missing_skills_technical

                    # Detect language
                    raw_text = st.session_state.get(f"{PREFIX}cv_raw_text", "")
                    cv_lang = _detect_language(raw_text)

                    # Tối ưu CV — truyền language hint qua monkey-patching user prompt
                    # Chúng ta tạo một wrapper để thêm language instruction
                    lang_instruction = (
                        "IMPORTANT: The candidate's CV is written in Vietnamese. "
                        "You MUST write the optimized resume AND cover letter entirely in Vietnamese (tiếng Việt). "
                        "Keep technical terms in English but all other content must be in Vietnamese."
                        if cv_lang == "vi"
                        else "IMPORTANT: The candidate's CV is written in English. "
                        "Write the optimized resume AND cover letter in English."
                    )

                    # Gọi tailor_cv_to_jd với thông tin ngôn ngữ được thêm vào missing_skills
                    missing_with_lang = all_missing.copy()
                    # Thêm language hint vào cuối list (sẽ xuất hiện trong prompt)
                    tailored = _tailor_with_language(resume_obj, jd_obj, all_missing, cv_lang)

                    st.session_state["tailor_result"] = tailored
                    st.session_state["tailor_analysis"] = analysis
                    st.success("Tối ưu CV thành công!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi khi tối ưu CV: {e}")
        return

    # ── Hiển thị kết quả tối ưu ──
    tailored = st.session_state["tailor_result"]

    # Tabs
    tab_cv, tab_cover = st.tabs(["CV Đã Tối ưu", "Thư Xin Việc"])

    with tab_cv:
        # Tóm tắt thay đổi
        if tailored.changes_summary:
            st.info(f"**Tóm tắt thay đổi:** {tailored.changes_summary}")

        if tailored.keywords_added:
            with st.expander("Từ khóa đã thêm", expanded=False):
                st.markdown(", ".join(f"`{kw}`" for kw in tailored.keywords_added))

        if tailored.improvements_made:
            with st.expander("Các cải tiến đã thực hiện", expanded=False):
                for imp in tailored.improvements_made:
                    st.markdown(f"- {imp}")

        st.divider()

        # Nội dung CV
        st.markdown(tailored.markdown_content)

        # Download
        st.download_button(
            "Tải CV đã tối ưu (.md)",
            data=tailored.markdown_content,
            file_name="CV_Da_Toi_Uu.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with tab_cover:
        if tailored.cover_letter:
            st.markdown(tailored.cover_letter)

            st.download_button(
                "Tải Thư Xin Việc (.md)",
                data=tailored.cover_letter,
                file_name="Thu_Xin_Viec.md",
                mime="text/markdown",
                use_container_width=True,
            )
        else:
            st.info("Không có thư xin việc được tạo.")

    st.divider()
    if st.button("Tối ưu lại", use_container_width=True, key="btn_retailor"):
        st.session_state.pop("tailor_result", None)
        st.session_state.pop("tailor_analysis", None)
        st.rerun()


def _tailor_with_language(resume_obj, jd_obj, missing_skills: list, cv_lang: str):
    """
    Wrapper quanh tailor_cv_to_jd để thêm language instruction.
    Thêm ngôn ngữ vào prompt thông qua missing_skills context.
    """
    from extract_cv import call_llm
    from cv_tailor import TailoredResume

    lang_note = (
        "[LANGUAGE INSTRUCTION] The candidate's CV is written in Vietnamese. "
        "You MUST write the optimized resume AND cover letter entirely in Vietnamese (tiếng Việt). "
        "Keep technical terms (e.g., Python, API, MVVM) in English, but all descriptions, "
        "summaries, bullet points, and the cover letter must be in Vietnamese."
        if cv_lang == "vi"
        else "[LANGUAGE INSTRUCTION] The candidate's CV is written in English. "
        "Write the optimized resume AND cover letter entirely in English."
    )

    system_prompt = f"""
    You are an expert Career Coach and ATS Optimizer. Your task is to rewrite the candidate's resume to better align with the provided Job Description (JD).
    
    {lang_note}
    
    GUIDELINES:
    1. Output Format: Return a highly professional, well-formatted Markdown resume.
    2. ATS Optimization: Naturally integrate the missing keywords/skills (provided in the prompt) into the resume's experience descriptions, summary, or skills section ONLY IF it makes sense based on the candidate's existing background.
    3. Action Verbs & Impact: Rewrite the bullet points in the experience section to be more impactful, using strong action verbs (e.g., Spearheaded, Orchestrated) and quantifying results where possible.
    4. Honesty: Do not invent completely new work experiences, companies, or degrees. Only rephrase and emphasize existing experiences to highlight their relevance to the target job.
    5. Summary: Add a strong professional summary at the top if missing, tailored specifically for the target job title.
    6. Cover Letter: Also generate a professional cover letter tailored to the job description.
    7. Keywords Added: List all the keywords from the JD that you integrated into the resume.
    8. Improvements Made: List specific improvements you made (e.g., "Integrated X relevant keywords", "Enhanced with Y strong action verbs", "Added Z quantifiable achievements").
    """

    user_prompt = f"""
    === CANDIDATE'S ORIGINAL RESUME ===
    {resume_obj.model_dump_json(indent=2)}
    
    === TARGET JOB DESCRIPTION ===
    {jd_obj.model_dump_json(indent=2)}
    
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
