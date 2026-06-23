import os, json
import streamlit as st

# Page Config 
st.set_page_config(
    page_title="ATS — Hệ thống Tuyển dụng Thông minh",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS 
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp {font-family: 'Segoe UI', sans-serif;}

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    [data-testid="stSidebar"] * {
        color: #e0e0ff !important;
    }
    [data-testid="stSidebar"] .stRadio label {
        font-size: 0.95rem;
    }

    /* Chat message styles */
    .chat-msg-user {
        background: #e3f2fd; border-radius: 12px; padding: 0.8rem 1rem;
        margin: 0.5rem 0; border-left: 4px solid #1976d2;
    }
    .chat-msg-bot {
        background: #f3e5f5; border-radius: 12px; padding: 0.8rem 1rem;
        margin: 0.5rem 0; border-left: 4px solid #7b1fa2;
    }

    /* Score colors */
    .score-excellent { color: #22c55e; }
    .score-good { color: #3b82f6; }
    .score-partial { color: #f59e0b; }
    .score-low { color: #ef4444; }

    /* Filter status badges */
    .badge-pass {
        background: #d4edda; color: #155724; padding: 4px 12px;
        border-radius: 20px; font-size: 0.85rem; font-weight: 600;
    }
    .badge-fail {
        background: #f8d7da; color: #721c24; padding: 4px 12px;
        border-radius: 20px; font-size: 0.85rem; font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Khởi tạo database
try:
    from database import init_db
    init_db()
except Exception as e:
    st.sidebar.error(f"Không thể kết nối MongoDB: {e}")

# ========================
#  SIDEBAR NAVIGATION
# ========================
with st.sidebar:
    st.markdown("## ATS")
    st.markdown("**Hệ thống Tuyển dụng Thông minh**")
    st.markdown("---")

    # Chọn vai trò
    role = st.radio(
        "Chọn vai trò:",
        ["HR — Nhà tuyển dụng", "Ứng viên"],
        index=0,
    )

    st.markdown("---")

    if "HR" in role:
        page = st.radio(
            "Chức năng:",
            [
                "Phân tích & Chấm điểm CV",
                "Lịch sử Phân tích",
            ],
            index=0,
        )
    else:
        page = st.radio(
            "Chức năng:",
            [
                "Luyện tập phỏng vấn",
                "Tối ưu CV",
            ],
            index=0,
        )

    st.markdown("---")
    st.markdown("#### Hướng dẫn")

    if "Phân tích" in page and "Lịch sử" not in page:
        st.info("1. Tạo hoặc chọn JD ở tab 'Quản lý JD'\n2. Sang tab 'Phân tích & Chấm điểm CV'\n3. Upload CV (tối đa 10 file)\n4. Tùy chỉnh trọng số / bộ lọc (nếu cần)\n5. Bấm 'Phân tích CV' & Xem kết quả")
    elif "Lịch sử" in page:
        st.info("1. Xem danh sách CV đã phân tích\n2. Lọc theo JD, điểm số\n3. Bấm xem chi tiết từng CV")
    elif "phỏng vấn" in page or "Phỏng vấn" in page:
        st.info("1. Upload CV của bạn\n2. Chọn JD ứng tuyển\n3. Bấm 'Bắt đầu phỏng vấn'\n4. Trả lời từng câu hỏi")
    elif "Tối ưu" in page:
        st.info("1. Upload CV của bạn\n2. Chọn JD ứng tuyển\n3. Bấm 'Tối ưu CV'\n4. Tải CV đã tối ưu")

    st.markdown("---")
    st.caption("ĐANC 20262 — Đồ án tốt nghiệp")

# ========================
#  PAGE ROUTING
# ========================
if "Phân tích" in page and "Lịch sử" not in page:
    from UI_analysis_cv import render_analysis_page
    render_analysis_page()

elif "Lịch sử" in page:
    from UI_history import render_history_page
    render_history_page()

elif "phỏng vấn" in page or "Phỏng vấn" in page:
    from UI_chatbot import render_interview_page
    render_interview_page()

elif "Tối ưu" in page:
    from UI_chatbot import render_tailor_page
    render_tailor_page()
