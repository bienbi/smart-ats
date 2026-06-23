"""
UI_jd_manager.py — Giao diện Quản lý Job Description (JD)
Cho phép HR nhập JD mới, lưu vào MongoDB, và chọn JD để phân tích CV.
"""

import streamlit as st
from database import save_jd, get_all_jds, delete_jd, get_jd_by_id


def render_jd_manager_page(show_header=True):
    if show_header:
        st.markdown(
            '<h1 style="text-align:center;color:#7c3aed;">Quản lý Job Description</h1>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p style="text-align:center;color:#666;">Nhập và quản lý các vị trí tuyển dụng</p>',
            unsafe_allow_html=True,
        )
        st.divider()

    # ========================
    #  NHẬP JD MỚI
    # ========================
    st.markdown("### Nhập JD mới")

    # Xóa input nếu vừa lưu thành công (flag từ lần rerun trước)
    if st.session_state.pop("_jd_saved", False):
        st.session_state["jd_name"] = ""
        st.session_state["jd_content"] = ""

    try:
        container = st.container(border=True)
    except TypeError:
        container = st.container()

    with container:
        name_key = "jd_name"
        content_key = "jd_content"

        jd_name = st.text_input(
            "Tên vị trí tuyển dụng",
            placeholder="VD: Senior iOS Developer, Data Analyst, Product Manager...",
            key=name_key,
        )
        jd_content = st.text_area(
            "Nội dung mô tả công việc (JD)",
            placeholder="Dán toàn bộ nội dung mô tả công việc, yêu cầu tuyển dụng ở đây...",
            height=250,
            key=content_key,
        )

        if jd_content:
            st.caption(f"{len(jd_content)} ký tự")

        if st.button("Lưu JD", key="save_jd_btn", type="primary", use_container_width=True):
            if not jd_name or not jd_name.strip():
                st.error("Vui lòng nhập tên vị trí tuyển dụng!")
            elif not jd_content or not jd_content.strip():
                st.error("Vui lòng nhập nội dung JD!")
            else:
                try:
                    parsed_data = {}
                    try:
                        from extract_cv import extract_information, JobDescription
                        with st.spinner("Đang phân tích cấu trúc JD bằng AI..."):
                            parsed_jd_obj = extract_information(jd_content.strip(), JobDescription, "jd")
                            parsed_data = parsed_jd_obj.model_dump() if hasattr(parsed_jd_obj, "model_dump") else {}
                    except Exception as parse_err:
                        st.warning(f"Không thể phân tích cấu trúc JD bằng AI: {parse_err}. JD vẫn được lưu dưới dạng thô.")
                    
                    jd_id = save_jd(jd_name.strip(), jd_content.strip(), parsed_data)
                    st.success(f"Đã lưu JD \"{jd_name.strip()}\" thành công!")
                    # Đánh dấu để xóa input ở lần rerun tiếp theo
                    st.session_state["_jd_saved"] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi khi lưu: {e}")

    st.divider()

    # ========================
    #  DANH SÁCH JD ĐÃ LƯU
    # ========================
    st.markdown("### Danh sách JD đã lưu")

    try:
        jds = get_all_jds()
    except Exception as e:
        st.error(f"Không thể tải danh sách JD: {e}")
        return

    if not jds:
        st.info("Chưa có JD nào được lưu. Hãy nhập JD ở phần trên!")
        return

    # Bảng danh sách JD
    # st.markdown("#### 📋 Tất cả JD")

    for idx, jd in enumerate(jds):
        with st.expander(
            f"📄 {jd['name']} — {jd['created_at'].strftime('%d/%m/%Y %H:%M') if jd.get('created_at') else 'N/A'}",
            expanded=False,
        ):
            st.markdown(f"**ID:** `{jd['id']}`")
            st.markdown(f"**Tên vị trí:** {jd['name']}")
            st.markdown(f"**Ngày tạo:** {jd['created_at'].strftime('%d/%m/%Y %H:%M UTC') if jd.get('created_at') else 'N/A'}")
            st.markdown(f"**Độ dài:** {len(jd['content'])} ký tự")

            st.text_area(
                "Nội dung JD",
                jd["content"],
                height=200,
                disabled=True,
                key=f"jd_view_{jd['id']}",
            )

            if st.button(
                "Xóa JD này",
                key=f"del_jd_{jd['id']}",
                use_container_width=True,
            ):
                try:
                    delete_jd(jd["id"])
                    st.success(f"Đã xóa JD \"{jd['name']}\"")
                    # Nếu JD đang được chọn bị xóa, xóa selection
                    if st.session_state.get("selected_jd", {}).get("id") == jd["id"]:
                        st.session_state.pop("selected_jd", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")
