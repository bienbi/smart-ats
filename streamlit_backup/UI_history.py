"""
UI_history.py — Giao diện Lịch sử Phân tích CV (HR)
Hiển thị danh sách tất cả CV đã phân tích từ MongoDB,
cho phép lọc, xem chi tiết, và xóa bản ghi.
"""

import streamlit as st
from database import (
    get_all_analyses, get_analyses_by_jd, get_analysis_detail,
    delete_analysis, get_all_jds,
)
from cv_tailor import translate_school_name, build_detail_text_rich
from scoring_cv import AdvancedFilter
from extract_cv import CandidateResume


# Mapping nhãn tiếng Việt
DEGREE_VI = {"none": "Không có", "associate": "Cao đẳng", "bachelor": "Cử nhân", "master": "Thạc sĩ", "phd": "Tiến sĩ"}
LANG_LEVEL_VI = {"none": "Không có", "basic": "Sơ cấp", "conversational": "Giao tiếp", "fluent": "Thông thạo", "native": "Bản ngữ"}


def _render_scoring_table(scoring_breakdown, resume_data):
    """Render bảng điểm chi tiết 5 yếu tố từ dữ liệu đã lưu."""
    criteria_map = {
        "skills": "Kỹ năng chuyên môn",
        "experience": "Kinh nghiệm",
        "education": "Học vấn",
        "language": "Ngoại ngữ",
        "stability": "Mức gắn bó với công việc",
    }

    table_html = """<table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
    <tr style="background:#7c3aed;color:white;">
        <th style="padding:10px;text-align:left;">Tiêu chí</th>
        <th style="padding:10px;text-align:center;">Trọng số</th>
        <th style="padding:10px;text-align:center;">Điểm thành phần (thang 100)</th>
        <th style="padding:10px;text-align:center;">Tổng điểm (bằng Điểm thành phần * Trọng số)</th>
        <th style="padding:10px;text-align:left;">Chi tiết</th>
    </tr>"""

    for key in ["skills", "experience", "education", "language", "stability"]:
        info = scoring_breakdown.get(key, {})
        label = criteria_map.get(key, key)
        raw_score = info.get("score", 0)
        weight = info.get("weight", 0)
        weighted = info.get("weighted_score", 0)
        details = info.get("details", {})

        score_val = round(raw_score * 100, 1)
        weight_pct = round(weight * 100)
        weighted_val = round(weighted * 100, 1)

        # Sử dụng rich detail text của cv_tailor
        detail_text = build_detail_text_rich(key, details, resume_data, format_type="html")
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

    # st.markdown("""
    # <p style='font-size:0.8rem;color:#666;margin-top:8px;'>
    #     <b>Giải thích cột:</b><br>
    #     - <b>Điểm (thang 100):</b> Điểm đánh giá độc lập của riêng tiêu chí đó (thang điểm từ 0 đến 100, không mang ký tự %).<br>
    #     - <b>Điểm thành phần:</b> Điểm đóng góp vào điểm tổng (bằng Điểm (thang 100)  Trọng số). Tổng điểm thành phần của 5 tiêu chí chính là Điểm Tương thích cuối cùng.
    # </p>
    # """, unsafe_allow_html=True)


def render_history_page():
    st.markdown(
        '<h1 style="text-align:center;color:#7c3aed;">Lịch sử Phân tích</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="text-align:center;color:#666;">Xem lại kết quả phân tích CV đã lưu trong hệ thống</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    # ========================
    #  BỘ LỌC
    # ========================
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        try:
            jds = get_all_jds()
        except Exception:
            jds = []
        jd_options = {"— Tất cả JD —": None}
        for jd in jds:
            jd_options[f"{jd['name']} ({jd['id'][:8]}...)"] = jd["id"]
        selected_jd_filter = st.selectbox("Lọc theo JD:", options=list(jd_options.keys()), key="hist_jd_filter")

    with col_f2:
        min_score_filter = st.number_input("Điểm tối thiểu:", min_value=0.0, max_value=100.0, value=0.0, step=5.0, key="hist_min_score")

    with col_f3:
        filter_passed = st.selectbox(
            "Trạng thái bộ lọc:",
            ["— Tất cả —", "Đạt bộ lọc", "Không đạt"],
            key="hist_filter_status",
        )

    # --- Bộ lọc Nâng cao (Dynamic) ---
    with st.expander("Bộ lọc Nâng cao (tùy chọn)", expanded=False):
        st.caption("Nhập các tiêu chí để lọc nhanh danh sách CV ở dưới.")
        fc1, fc2 = st.columns(2)
        with fc1:
            filter_uni = st.text_input(
                "Trường ĐH (nhiều trường cách nhau bằng dấu phẩy)",
                placeholder="VD: Bách Khoa, FPT, RMIT",
                key="hist_filter_uni",
            )
            filter_min_exp = st.number_input(
                "Kinh nghiệm tối thiểu (năm)",
                min_value=0.0, max_value=50.0, value=0.0, step=0.5,
                key="hist_filter_min_exp",
            )
            filter_skills = st.text_input(
                "Kỹ năng bắt buộc (cách nhau bằng dấu phẩy)",
                placeholder="VD: Python, SQL, AWS",
                key="hist_filter_skills",
            )
        with fc2:
            lang_col1, lang_col2 = st.columns(2)
            with lang_col1:
                filter_lang_name = st.selectbox(
                    "Ngoại ngữ",
                    ["", "English", "Japanese", "Chinese", "Korean", "French", "German"],
                    key="hist_filter_lang_name",
                )
            with lang_col2:
                filter_lang_level = st.selectbox(
                    "Trình độ tối thiểu",
                    ["", "basic", "conversational", "fluent", "native"],
                    format_func=lambda x: {"": "— Chọn —", "basic": "Sơ cấp", "conversational": "Giao tiếp", "fluent": "Thông thạo", "native": "Bản ngữ"}.get(x, x),
                    key="hist_filter_lang_level",
                )
            filter_min_degree = st.selectbox(
                "🎓 Bằng cấp tối thiểu",
                ["none", "associate", "bachelor", "master", "phd"],
                format_func=lambda x: {"none": "— Không lọc —", "associate": "Cao đẳng", "bachelor": "Cử nhân", "master": "Thạc sĩ", "phd": "Tiến sĩ"}.get(x, x),
                key="hist_filter_min_degree",
            )
            filter_min_stab = st.slider(
                "Mức gắn bó tối thiểu (%)",
                min_value=0, max_value=100, value=0, step=5,
                key="hist_filter_min_stab",
            )

    # Chuẩn bị filter config
    filter_config = {}
    if filter_uni and filter_uni.strip():
        filter_config["universities"] = [u.strip() for u in filter_uni.split(",") if u.strip()]
    if filter_min_exp > 0:
        filter_config["min_experience_years"] = filter_min_exp
    if filter_lang_name and filter_lang_level:
        filter_config["language"] = {"name": filter_lang_name.lower(), "min_level": filter_lang_level}
    if filter_skills and filter_skills.strip():
        filter_config["required_skills"] = [s.strip() for s in filter_skills.split(",") if s.strip()]
    if filter_min_degree and filter_min_degree != "none":
        filter_config["min_degree"] = filter_min_degree
    if filter_min_stab > 0:
        filter_config["min_stability_pct"] = filter_min_stab

    # ========================
    #  LẤY DỮ LIỆU
    # ========================
    try:
        selected_jd_id = jd_options.get(selected_jd_filter)
        if selected_jd_id:
            analyses = get_analyses_by_jd(selected_jd_id)
        else:
            analyses = get_all_analyses()
    except Exception as e:
        st.error(f"Không thể tải dữ liệu: {e}")
        return

    # Áp dụng bộ lọc điểm số và bộ lọc nâng cao động
    filtered_analyses = []
    for a in analyses:
        score = a.get("total_score", 0)
        passed_score = score >= min_score_filter if min_score_filter > 0 else True
        if not passed_score:
            continue

        # Dynamic Advanced Filter evaluation
        resume_data = a.get("resume_data", {})
        resume_obj = None
        if resume_data:
            try:
                resume_obj = CandidateResume(**resume_data)
            except Exception:
                pass

        # Reconstruct cv_data for AdvancedFilter
        cv_data = {}
        if resume_obj:
            cv_data["languages"] = {lang.name.lower(): lang.level.lower() for lang in resume_obj.languages}
            skills_details = a.get("scoring_breakdown", {}).get("skills", {}).get("details", {})
            cv_data["matched_must_have_skills"] = skills_details.get("matched_critical_skills", [])
            cv_data["matched_nice_to_have_skills"] = skills_details.get("matched_nice_skills", [])

        # Apply Advanced Filter if filter_config is not empty
        dynamic_filter_results = {}
        if filter_config and resume_obj:
            dynamic_filter_results = AdvancedFilter.apply_filters(
                cv_data, resume_obj, {"breakdown": a.get("scoring_breakdown", {})}, filter_config
            )
        
        # Save dynamic filter results back to the item for rendering/displaying
        a["filter_results"] = dynamic_filter_results

        # Evaluate filtering logic
        has_advanced_filter = bool(dynamic_filter_results and dynamic_filter_results.get("details"))
        passed_advanced = dynamic_filter_results.get("passed", True) if has_advanced_filter else True

        if filter_passed == "Đạt bộ lọc":
            if passed_advanced:
                filtered_analyses.append(a)
        elif filter_passed == "Không đạt":
            if not passed_advanced:
                filtered_analyses.append(a)
        else:  # — Tất cả —
            filtered_analyses.append(a)
                
    analyses = filtered_analyses

    if not analyses:
        st.info("Không có dữ liệu phân tích nào phù hợp với bộ lọc.")
        return

    # ========================
    #  BẢNG TỔNG HỢP
    # ========================
    st.markdown(f"### Danh sách ({len(analyses)} kết quả)")

    table_html = """<table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
    <tr style="background:#7c3aed;color:white;">
        <th style="padding:8px;text-align:center;">STT</th>
        <th style="padding:8px;text-align:left;">Tên ứng viên</th>
        <th style="padding:8px;text-align:left;">File CV</th>
        <th style="padding:8px;text-align:left;">Vị trí (JD)</th>
        <th style="padding:8px;text-align:center;">Điểm</th>
        <th style="padding:8px;text-align:center;">Bộ lọc</th>
        <th style="padding:8px;text-align:left;">Ngày</th>
    </tr>"""

    for idx, a in enumerate(analyses, 1):
        score = a.get("total_score", 0)
        sc = "#22c55e" if score >= 85 else "#3b82f6" if score >= 70 else "#f59e0b" if score >= 50 else "#ef4444"

        fr = a.get("filter_results", {})
        if fr and fr.get("details"):
            if fr.get("passed"):
                filter_badge = "<span style='background:#d4edda;color:#155724;padding:2px 8px;border-radius:10px;font-size:0.8rem;'>✅ Đạt</span>"
            else:
                filter_badge = "<span style='background:#f8d7da;color:#721c24;padding:2px 8px;border-radius:10px;font-size:0.8rem;'>⚠️ Không đạt</span>"
        else:
            filter_badge = "<span style='color:#999;'>—</span>"

        date_str = a.get("created_at").strftime("%d/%m/%Y %H:%M") if a.get("created_at") else "N/A"

        table_html += f"""<tr style="border-bottom:1px solid #eee;">
            <td style="padding:8px;text-align:center;">{idx}</td>
            <td style="padding:8px;">{a.get('candidate_name', 'N/A')}</td>
            <td style="padding:8px;font-size:0.8rem;">{a.get('filename', '')}</td>
            <td style="padding:8px;">{a.get('jd_name', 'N/A')}</td>
            <td style="padding:8px;text-align:center;font-weight:bold;color:{sc};">{score}%</td>
            <td style="padding:8px;text-align:center;">{filter_badge}</td>
            <td style="padding:8px;font-size:0.8rem;">{date_str}</td>
        </tr>"""

    table_html += "</table>"
    st.markdown(table_html, unsafe_allow_html=True)

    # ========================
    #  CHI TIẾT TỪNG CV
    # ========================
    st.markdown("### Chi tiết từng CV")

    for idx, a in enumerate(analyses, 1):
        score = a.get("total_score", 0)
        name = a.get("candidate_name", "N/A")

        with st.expander(f" {name} — {score}% — {a.get('filename', '')}", expanded=False):
            try:
                detail = get_analysis_detail(a["id"])
                if detail:
                    detail["filter_results"] = a.get("filter_results", {})
            except Exception as e:
                st.error(f"Lỗi tải chi tiết: {e}")
                continue

            if not detail:
                st.warning("Không tìm thấy dữ liệu chi tiết.")
                continue

            st.markdown(f"**Ứng viên:** {detail.get('candidate_name', 'N/A')}")
            st.markdown(f"**Email:** {detail.get('email', 'Không có') or 'Không có'}")

            # Trường ĐH (dịch tên trường, GPA/CPA)
            resume_data = detail.get("resume_data", {})
            schools = []
            if resume_data and "educations" in resume_data:
                for edu in resume_data["educations"]:
                    school_raw = edu.get("school", "N/A")
                    school_vi = translate_school_name(school_raw)
                    degree = edu.get("degree", "none")
                    major = edu.get("major", "N/A")
                    gpa = edu.get("gpa")
                    gpa_str = f" - GPA/CPA: {gpa}" if gpa and str(gpa).lower() not in ("none", "null", "") else ""
                    schools.append(f"{school_vi} ({degree.title()} — Chuyên ngành: {major}{gpa_str})")
            if schools:
                st.markdown(f"**🎓 Học vấn:** {' | '.join(schools)}")

            st.markdown(f"**File:** {detail.get('filename', '')}")
            st.markdown(f"**Vị trí:** {detail.get('jd_name', 'N/A')}")

            sc_color = "#22c55e" if score >= 85 else "#3b82f6" if score >= 70 else "#f59e0b" if score >= 50 else "#ef4444"
            st.markdown(f"""<div style="border:2px solid #e0e0ff;border-radius:12px;padding:16px;text-align:center;margin:12px 0;">
                <h4 style="margin:0;">Điểm Tương thích</h4>
                <div style="font-size:36px;font-weight:bold;color:{sc_color};">{score}%</div>
                <p style="color:#666;margin:0;">{detail.get('recommendation', '')}</p></div>""", unsafe_allow_html=True)

            scoring_breakdown = detail.get("scoring_breakdown", {})
            resume_data = detail.get("resume_data", {})
            if scoring_breakdown:
                st.markdown("#### Bảng điểm Chi tiết")
                _render_scoring_table(scoring_breakdown, resume_data)

            filter_results = detail.get("filter_results", {})
            if filter_results and filter_results.get("details"):
                st.markdown("#### Kết quả Bộ lọc")
                for fd in filter_results["details"]:
                    if fd["passed"]:
                        st.success(fd["reason"])
                    else:
                        st.warning(fd["reason"])

            analysis_report = detail.get("analysis_report", {})
            if analysis_report:
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    strengths = analysis_report.get("strengths", [])
                    if strengths:
                        st.markdown("**Điểm mạnh:**")
                        for s in strengths:
                            st.markdown(f"- {s}")
                with col2:
                    suggestions = analysis_report.get("suggestions", [])
                    if suggestions:
                        st.markdown("**Gợi ý cải thiện:**")
                        for s in suggestions:
                            st.markdown(f"- {s}")

                areas = analysis_report.get("areas_for_improvement", [])
                if areas:
                    st.markdown("**Cần lưu ý:**")
                    for a_item in areas:
                        st.markdown(f"- {a_item}")

            weights = detail.get("weights_used", {})
            if weights:
                w_text = " | ".join([f"{k}: {round(v*100)}%" for k, v in weights.items()])
                st.caption(f"Trọng số đã dùng: {w_text}")

            st.markdown("---")
            if st.button(f"Xóa bản ghi này", key=f"del_analysis_{a['id']}", use_container_width=True):
                try:
                    delete_analysis(a["id"])
                    st.success("Đã xóa bản ghi.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")

    # ========================
    #  XÓA TẤT CẢ
    # ========================
    st.divider()
    with st.expander("Xóa tất cả bản ghi", expanded=False):
        st.warning("Hành động này sẽ xóa **tất cả** kết quả phân tích CV đã lưu. Không thể hoàn tác!")
        confirm = st.text_input("Nhập 'XOA TAT CA' để xác nhận:", key="confirm_delete_all")
        if st.button("Xóa tất cả", type="primary", use_container_width=True, key="btn_delete_all"):
            if confirm == "XOA TAT CA":
                try:
                    count = 0
                    all_a = get_all_analyses()
                    for a_item in all_a:
                        delete_analysis(a_item["id"])
                        count += 1
                    st.success(f"Đã xóa {count} bản ghi.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")
            else:
                st.error("Nhập sai mã xác nhận!")
