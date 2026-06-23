"""
UI_analysis_cv.py — Giao diện Phân tích & Chấm điểm CV (HR)
Hỗ trợ:
  - Upload tối đa 10 CV cùng lúc
  - Chọn JD từ database
  - Tùy chỉnh trọng số chấm điểm
  - Bộ lọc nâng cao (trường ĐH, kinh nghiệm, ngoại ngữ, kỹ năng, bằng cấp, gắn bó)
  - Bảng điểm chi tiết 5 yếu tố
  - Lưu kết quả vào MongoDB
"""
import os, json, tempfile
import streamlit as st
from extract_cv import (
    process_cv_and_jd, extract_text_from_cv, is_groq_configured,
    CandidateResume, JobDescription, Experience, Education, Language,
)
from scoring_cv import CVScoresAggregator, AdvancedFilter
from cv_tailor import (
    tailor_cv_to_jd, TailoredResume, AnalysisReport,
    analyze_cv_detailed, generate_markdown_report, generate_html_report,
    translate_school_name, build_detail_text_rich,
)
from database import save_analysis, get_all_jds
# ========================
#  HELPER: Mock data
# ========================
def _mock_data():
    cv = {"experience_history":[{"title":"iOS Developer","years":3.0,"relevance_to_jd":1.0},{"title":"Mobile Developer","years":2.0,"relevance_to_jd":0.8}],
          "education_history":[{"degree":"bachelor","major_relevant":1.0}],
          "matched_must_have_skills":["Swift","SwiftUI","RESTful APIs"],
          "matched_nice_to_have_skills":["CI/CD"],
          "languages":{"english":"fluent","japanese":"basic"}}
    jd = {"required_experience_years":5,"required_degree":"bachelor",
          "must_have_skills":["Swift","SwiftUI","Combine","RESTful APIs"],
          "nice_to_have_skills":["CI/CD","StoreKit","Flutter"],
          "required_languages":{"english":"fluent","japanese":"conversational"}}
    r = CandidateResume(name="Sơn Đỗ Hoàng",email="son.do@example.com",
        skills=["Swift","SwiftUI","RESTful APIs","CI/CD"],
        experiences=[Experience(company="Tech Corp",role="iOS Developer",years=3.0,description="Developed iOS apps."),
                     Experience(company="Startup Inc",role="Mobile Developer",years=2.0,description="Built mobile apps.")],
        educations=[Education(school="HUST",degree="bachelor",major="Computer Science",gpa=3.5)],
        projects=[],certificates=[],
        languages=[Language(name="English",level="fluent"),Language(name="Japanese",level="basic")])
    j = JobDescription(job_title="Senior iOS Developer",job_description="Looking for senior iOS dev.",
        min_years_experience=5,required_degree="bachelor",
        must_have_skills=["Swift","SwiftUI","Combine","RESTful APIs"],
        nice_to_have_skills=["CI/CD","StoreKit","Flutter"],
        required_languages={"english":"fluent","japanese":"conversational"})
    return cv, jd, r, j
def _is_mock():
    return not is_groq_configured()
# ========================
#  RENDER: Bảng điểm chi tiết 1 CV
# ========================
def _render_detailed_scoring(result, resume_obj, cv_data, filter_results=None):
    """Hiển thị bảng điểm chi tiết 5 yếu tố cho 1 CV."""
    breakdown = result.get("breakdown", {})
    # --- Thông tin ứng viên ---
    st.markdown(f"**Ứng viên:** {getattr(resume_obj, 'name', 'N/A')}")
    st.markdown(f"**Email:** {getattr(resume_obj, 'email', 'N/A') or 'Không có'}")
    # Trường ĐH (dịch tên trường, GPA/CPA)
    schools = []
    if hasattr(resume_obj, "educations"):
        for edu in resume_obj.educations:
            school_vi = translate_school_name(edu.school)
            gpa_str = f" - GPA/CPA: {edu.gpa}" if edu.gpa is not None else ""
            schools.append(f"{school_vi} ({edu.degree.title()} — Chuyên ngành: {edu.major}{gpa_str})")
    if schools:
        st.markdown(f"**Học vấn:** {' | '.join(schools)}")
    st.markdown("")
    # --- Điểm tổng ---
    score = result.get("final_score_pct", 0)
    color = "#22c55e" if score >= 85 else "#3b82f6" if score >= 70 else "#f59e0b" if score >= 50 else "#ef4444"
    st.markdown(f"""<div style="border:2px solid #e0e0ff;border-radius:16px;padding:20px;text-align:center;margin-bottom:16px;">
        <h4 style="margin:0;">Điểm Tương thích</h4>
        <div style="font-size:42px;font-weight:bold;color:{color};">{score}%</div>
        <p style="color:#666;margin:0;">{result.get('recommendation', '')}</p></div>""", unsafe_allow_html=True)
    # --- Bảng điểm chi tiết ---
    st.markdown("#### Bảng điểm chi tiết")
    criteria_map = {
        "skills": "Kỹ năng chuyên môn",
        "experience": "Kinh nghiệm làm việc",
        "education": "Học vấn",
        "language": "Ngoại ngữ",
        "stability": "Mức độ gắn bó",
    }
    # Tạo bảng HTML chi tiết
    table_html = """<table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
    <tr style="background:#7c3aed;color:white;">
        <th style="padding:10px;text-align:left;border-radius:8px 0 0 0;">Tiêu chí</th>
        <th style="padding:10px;text-align:center;">Trọng số</th>
        <th style="padding:10px;text-align:center;">Điểm (thang 100)</th>
        <th style="padding:10px;text-align:center;">Điểm thành phần</th>
        <th style="padding:10px;text-align:left;border-radius:0 8px 0 0;">Chi tiết</th>
    </tr>"""
    for key in ["skills", "experience", "education", "language", "stability"]:
        info = breakdown.get(key, {})
        label = criteria_map.get(key, key)
        raw_score = info.get("score", 0)
        weight = info.get("weight", 0)
        weighted = info.get("weighted_score", 0)
        details = info.get("details", {})
        score_val = round(raw_score * 100, 1)
        weight_pct = round(weight * 100)
        weighted_val = round(weighted * 100, 1)
        # Sử dụng rich detail text của cv_tailor
        detail_text = build_detail_text_rich(key, details, resume_obj, format_type="html")
        # Màu điểm
        sc = "#22c55e" if score_val >= 80 else "#3b82f6" if score_val >= 60 else "#f59e0b" if score_val >= 40 else "#ef4444"
        table_html += f"""<tr style="border-bottom:1px solid #eee;">
            <td style="padding:10px;font-weight:600;">{label}</td>
            <td style="padding:10px;text-align:center;">{weight_pct}%</td>
            <td style="padding:10px;text-align:center;color:{sc};font-weight:bold;">{score_val}</td>
            <td style="padding:10px;text-align:center;font-weight:bold;">{weighted_val}</td>
            <td style="padding:10px;font-size:0.85rem;">{detail_text}</td>
        </tr>"""
    table_html += "</table>"
    st.markdown(table_html, unsafe_allow_html=True)
    st.markdown("""
    <p style='font-size:0.8rem;color:#666;margin-top:8px;'>
        <b>Giải thích cột:</b><br>
        - <b>Điểm (thang 100):</b> Điểm đánh giá độc lập của riêng tiêu chí đó (thang điểm từ 0 đến 100, không mang ký tự %).<br>
        - <b>Điểm thành phần:</b> Điểm đóng góp vào điểm tổng (bằng Điểm (thang 100) x Trọng số). Tổng điểm thành phần của 5 tiêu chí chính là Điểm Tương thích cuối cùng.
    </p>
    """, unsafe_allow_html=True)
    # --- Kết quả bộ lọc nâng cao ---
    if filter_results and filter_results.get("details"):
        st.markdown("#### Kết quả Bộ lọc Nâng cao")
        for fd in filter_results["details"]:
            if fd["passed"]:
                st.markdown(f"<span class='badge-pass'>{fd['reason']}</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"<span class='badge-fail'>{fd['reason']}</span>", unsafe_allow_html=True)
# ========================
#  RENDER: Kết quả batch
# ========================
def _render_batch_results(all_results):
    """Hiển thị bảng so sánh kết quả nhiều CV."""
    st.markdown("## Kết quả Phân tích")
    # Bảng tổng hợp
    st.markdown("### Bảng Tổng hợp")
    table_html = """<table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
    <tr style="background:#7c3aed;color:white;">
        <th style="padding:10px;text-align:center;">STT</th>
        <th style="padding:10px;text-align:left;">Tên ứng viên</th>
        <th style="padding:10px;text-align:left;">File</th>
        <th style="padding:10px;text-align:center;">Điểm</th>
        <th style="padding:10px;text-align:center;">Bộ lọc</th>
        <th style="padding:10px;text-align:left;">Khuyến nghị</th>
    </tr>"""
    # Sắp xếp theo điểm giảm dần
    sorted_results = sorted(all_results, key=lambda x: x.get("score", 0), reverse=True)
    for idx, r in enumerate(sorted_results, 1):
        score = r.get("score", 0)
        sc = "#22c55e" if score >= 85 else "#3b82f6" if score >= 70 else "#f59e0b" if score >= 50 else "#ef4444"
        filter_status = ""
        fr = r.get("filter_results", {})
        if fr and fr.get("details"):
            if fr.get("passed"):
                filter_status = "<span style='background:#d4edda;color:#155724;padding:2px 8px;border-radius:10px;'>✅ Đạt</span>"
            else:
                failed_filters = [d["filter"] for d in fr["details"] if not d["passed"]]
                filter_status = f"<span style='background:#f8d7da;color:#721c24;padding:2px 8px;border-radius:10px;'>⚠️ {', '.join(failed_filters)}</span>"
        else:
            filter_status = "<span style='color:#999;'>—</span>"
        # Rút gọn recommendation
        rec = r.get("recommendation", "")
        if "Not Match" in rec or "Không phù hợp" in rec:
            rec_short = "Không phù hợp"
        elif "Strong" in rec or "Rất phù hợp" in rec:
            rec_short = "Rất phù hợp"
        elif "Partial" in rec or "một phần" in rec:
            rec_short = "Phù hợp một phần"
        elif "Good" in rec or "Phù hợp" in rec:
            rec_short = "Phù hợp"
        else:
            rec_short = "Không phù hợp"
        table_html += f"""<tr style="border-bottom:1px solid #eee;">
            <td style="padding:8px;text-align:center;">{idx}</td>
            <td style="padding:8px;">{r.get('name', 'N/A')}</td>
            <td style="padding:8px;font-size:0.8rem;">{r.get('filename', '')}</td>
            <td style="padding:8px;text-align:center;font-weight:bold;color:{sc};">{score}%</td>
            <td style="padding:8px;text-align:center;">{filter_status}</td>
            <td style="padding:8px;">{rec_short}</td>
        </tr>"""
    table_html += "</table>"
    st.markdown(table_html, unsafe_allow_html=True)
    # Chi tiết từng CV
    st.markdown("### Chi tiết từng CV")
    for idx, r in enumerate(sorted_results, 1):
        with st.expander(f"{r.get('name', 'N/A')} — {r.get('score', 0)}% — {r.get('filename', '')}", expanded=False):
            # Nếu CV bị lỗi, hiện lỗi chi tiết
            if r.get("error_detail"):
                st.error(f"**Lỗi khi phân tích:** {r.get('recommendation', '')}")
                st.code(r["error_detail"], language="python")
                continue
            _render_detailed_scoring(
                r.get("scoring_result", {}),
                r.get("resume_obj"),
                r.get("cv_data", {}),
                r.get("filter_results"),
            )
            # Phân tích chi tiết (strengths, suggestions)
            analysis = r.get("analysis")
            if analysis:
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Điểm mạnh:**")
                    for s in analysis.strengths:
                        st.markdown(f"- {s}")
                with col2:
                    st.markdown("**Gợi ý cải thiện:**")
                    for s in analysis.suggestions:
                        st.markdown(f"- {s}")
                if analysis.areas_for_improvement:
                    st.markdown("**Cần lưu ý:**")
                    for a in analysis.areas_for_improvement:
                        st.markdown(f"- {a}")
            # Nút tải báo cáo
            st.markdown("---")
            resume_name = r.get("name", "Resume")
            position = r.get("jd_name", "Position")
            if analysis:
                dc1, dc2 = st.columns(2)
                with dc1:
                    html_report = generate_html_report(analysis, resume_name, position, r.get("scoring_result"), resume_obj=r.get("resume_obj"))
                    st.download_button(
                        "Tải báo cáo HTML",
                        html_report,
                        f"Bao_Cao_{resume_name.replace(' ', '_')}.html",
                        "text/html",
                        use_container_width=True,
                        key=f"dl_html_{idx}",
                    )
                with dc2:
                    md_report = generate_markdown_report(analysis, resume_name, position, r.get("scoring_result"), resume_obj=r.get("resume_obj"))
                    st.download_button(
                        "Tải báo cáo MD",
                        md_report,
                        f"Bao_Cao_{resume_name.replace(' ', '_')}.md",
                        "text/markdown",
                        use_container_width=True,
                        key=f"dl_md_{idx}",
                    )
# ========================
#  MAIN PAGE RENDER
# ========================
def render_analysis_page():
    st.markdown(
        '<h1 style="text-align:center;color:#7c3aed;">Quản lý JD & Phân tích CV</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="text-align:center;color:#666;">Quản lý các vị trí tuyển dụng (JD) và thực hiện phân tích, chấm điểm CV ứng viên</p>',
        unsafe_allow_html=True,
    )
    st.divider()
    tab_analysis, tab_jd = st.tabs(["Phân tích & Chấm điểm CV", "Quản lý JD"])
    with tab_jd:
        from UI_jd_manager import render_jd_manager_page
        render_jd_manager_page(show_header=False)
    with tab_analysis:
        _render_analysis_tab_content()
def _render_analysis_tab_content():
    # ========================
    #  B1: CHỌN JD
    # ========================
    st.markdown("### Chọn JD tuyển dụng")
    try:
        jds = get_all_jds()
    except Exception:
        jds = []
    if not jds:
        st.warning("⚠️ Chưa có JD nào trong hệ thống. Vui lòng sang tab **📋 Quản lý JD** để thêm JD trước.")
        return
    # Map options
    jd_options = {f"{jd['name']}": jd for jd in jds}
    
    # Tìm index mặc định của JD đang chọn trước đó
    selected_jd = st.session_state.get("selected_jd")
    default_index = 0
    # if selected_jd:
    #     st.success(f"JD đang dùng: **{selected_jd['name']}**")
    #     for idx, jd in enumerate(jds):
    #         if jd["id"] == selected_jd["id"]:
    #             default_index = idx
    #             break

    selected_name = st.selectbox(
        "Chọn mô tả công việc (JD) để phân tích CV:",
        options=list(jd_options.keys()),
        index=default_index,
        key="analysis_jd_select",
    )
    if selected_name:
        selected_jd = jd_options[selected_name]
        st.session_state["selected_jd"] = selected_jd
        st.success(f"JD đang dùng: **{selected_jd['name']}**")
        with st.expander("Xem nội dung JD", expanded=False):
            st.text_area("Nội dung JD", selected_jd["content"], height=150, disabled=True, key="jd_preview")
    else:
        st.warning("Chưa chọn JD! Vui lòng sang tab **Quản lý JD** bên cạnh để tạo hoặc chọn một JD trước.")
        return
    # ========================
    #  B2: UPLOAD NHIỀU CV
    # ========================
    st.markdown("### Upload CV")
    uploaded_files = st.file_uploader(
        "Kéo thả thư mục (folder) hoặc chọn nhiều file CV (PDF/DOCX)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="cv_upload",
    )
    if uploaded_files:
        st.info(f"📎 Đã nhận {len(uploaded_files)} file CV")
    # ========================
    #  B3: TÙY CHỈNH TRỌNG SỐ
    # ========================
    with st.expander("⚙️ Tùy chỉnh Trọng số chấm điểm", expanded=False):
        st.caption("Điều chỉnh trọng số cho từng tiêu chí (tổng phải = 100%)")
        col_w1, col_w2, col_w3, col_w4, col_w5 = st.columns(5)
        with col_w1:
            w_skills = st.number_input("Kỹ năng (%)", min_value=0, max_value=100, value=40, step=5, key="w_skills")
        with col_w2:
            w_exp = st.number_input("Kinh nghiệm (%)", min_value=0, max_value=100, value=30, step=5, key="w_exp")
        with col_w3:
            w_edu = st.number_input("Học vấn (%)", min_value=0, max_value=100, value=10, step=5, key="w_edu")
        with col_w4:
            w_lang = st.number_input("Ngoại ngữ (%)", min_value=0, max_value=100, value=10, step=5, key="w_lang")
        with col_w5:
            w_stab = st.number_input("Gắn bó (%)", min_value=0, max_value=100, value=10, step=5, key="w_stab")
        total_weight = w_skills + w_exp + w_edu + w_lang + w_stab
        if total_weight != 100:
            st.error(f"Tổng trọng số = {total_weight}% (phải = 100%)")
        else:
            st.success(f"Tổng trọng số = {total_weight}%")
        def reset_weights():
            st.session_state["w_skills"] = 40
            st.session_state["w_exp"] = 30
            st.session_state["w_edu"] = 10
            st.session_state["w_lang"] = 10
            st.session_state["w_stab"] = 10
        st.button("Đặt lại mặc định", key="reset_weights", on_click=reset_weights)

    # ========================
    #  B5: NÚT PHÂN TÍCH
    # ========================
    analyze_btn = st.button(
        "Phân tích CV",
        type="primary",
        use_container_width=True,
        disabled=(not uploaded_files or total_weight != 100),
    )
    if analyze_btn and uploaded_files and total_weight == 100:
        # Chuẩn bị weights
        weights = {
            "skills": w_skills / 100,
            "experience": w_exp / 100,
            "education": w_edu / 100,
            "language": w_lang / 100,
            "stability": w_stab / 100,
        }
        # Xử lý batch
        all_results = []
        progress = st.progress(0, text="Đang phân tích CV")
        total = len(uploaded_files)
        for i, uploaded in enumerate(uploaded_files):
            progress.progress((i) / total, text=f"Đang phân tích CV {i + 1}/{total}: {uploaded.name}...")
            tmp_path = None
            
            # Tính file_hash để lưu vào database
            import hashlib
            file_bytes = uploaded.getvalue()
            file_hash = hashlib.sha256(file_bytes).hexdigest()
            try:
                # B5.1: Trích xuất & so khớp
                if _is_mock():
                    cv_data, jd_data, resume_obj, jd_obj = _mock_data()
                else:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded.name.split('.')[-1]}") as tmp:
                        tmp.write(uploaded.getvalue())
                        tmp_path = tmp.name
                    cv_data, jd_data, resume_obj, jd_obj = process_cv_and_jd(tmp_path, selected_jd["content"], selected_jd.get("id"))
                # B5.2: Chấm điểm
                agg = CVScoresAggregator(weights=weights)
                scoring_result = agg.score_cv(cv_data, jd_data)
                # B5.3: Phân tích chi tiết
                try:
                    analysis = analyze_cv_detailed(resume_obj, jd_obj, scoring_result)
                except Exception:
                    sk = scoring_result["breakdown"].get("skills", {}).get("details", {})
                    analysis = AnalysisReport(
                        compatibility_score=scoring_result["final_score_pct"],
                        score_message=scoring_result["recommendation"],
                        missing_keywords=sk.get("missing_critical_skills", []) + sk.get("missing_nice_skills", []),
                        missing_skills_technical=sk.get("missing_critical_skills", []),
                        missing_skills_soft=[], strengths=[], suggestions=[],
                        areas_for_improvement=[], next_steps=[],
                    )
                # B5.4: Bộ lọc nâng cao được chuyển sang trang Lịch sử phân tích
                filter_results = {}
                # B5.5: Lưu vào MongoDB
                try:
                    save_analysis(
                        candidate_name=getattr(resume_obj, "name", "N/A"),
                        email=getattr(resume_obj, "email", "") or "",
                        filename=uploaded.name,
                        jd_id=selected_jd.get("id", ""),
                        jd_name=selected_jd.get("name", ""),
                        total_score=scoring_result["final_score_pct"],
                        recommendation=scoring_result["recommendation"],
                        scoring_breakdown=scoring_result["breakdown"],
                        resume_data=resume_obj.model_dump() if hasattr(resume_obj, "model_dump") else {},
                        analysis_report=analysis.model_dump() if hasattr(analysis, "model_dump") else {},
                        filter_results=filter_results,
                        weights_used=weights,
                        file_hash=file_hash,
                    )
                except Exception as db_err:
                    st.warning(f"Không thể lưu vào database: {db_err}")
                # Lưu kết quả
                all_results.append({
                    "name": getattr(resume_obj, "name", "N/A"),
                    "email": getattr(resume_obj, "email", ""),
                    "filename": uploaded.name,
                    "score": scoring_result["final_score_pct"],
                    "recommendation": scoring_result["recommendation"],
                    "scoring_result": scoring_result,
                    "cv_data": cv_data,
                    "resume_obj": resume_obj,
                    "jd_obj": jd_obj,
                    "analysis": analysis,
                    "filter_results": filter_results,
                    "jd_name": selected_jd.get("name", ""),
                })
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                all_results.append({
                    "name": "Lỗi",
                    "filename": uploaded.name,
                    "score": 0,
                    "recommendation": f"Lỗi: {e}",
                    "error_detail": error_detail,
                    "scoring_result": {},
                    "cv_data": {},
                    "resume_obj": None,
                    "analysis": None,
                    "filter_results": {},
                })
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
        progress.progress(1.0, text="Hoàn tất phân tích!")
        # Hiện lỗi chi tiết nếu có
        errors = [r for r in all_results if r.get("error_detail")]
        if errors:
            with st.expander(f"{len(errors)} CV gặp lỗi — bấm để xem chi tiết", expanded=True):
                for err in errors:
                    st.error(f"**{err['filename']}**: {err['recommendation']}")
                    st.code(err["error_detail"], language="python")
        st.session_state["batch_results"] = all_results
        st.rerun()
    # ========================
    #  B6: HIỂN THỊ KẾT QUẢ
    # ========================
    if "batch_results" in st.session_state and st.session_state["batch_results"]:
        _render_batch_results(st.session_state["batch_results"])
        st.divider()
        if st.button("Phân tích lại", use_container_width=True):
            st.session_state.pop("batch_results", None)
            st.rerun()