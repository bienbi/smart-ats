import os
import uuid
from datetime import datetime, timezone
from fastapi import Header, HTTPException, Depends, APIRouter
from pydantic import BaseModel
from database import _get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

def get_current_session_token() -> str:
    try:
        db = _get_db()
        session = db.active_sessions.find_one({"_id": "global_session"})
        if session:
            return session.get("token", "")
    except Exception as e:
        print(f"Lỗi truy vấn active_sessions: {e}")
    return ""

def set_current_session_token(token: str):
    try:
        db = _get_db()
        db.active_sessions.update_one(
            {"_id": "global_session"},
            {"$set": {"token": token, "updated_at": datetime.now(timezone.utc)}},
            upsert=True
        )
    except Exception as e:
        print(f"Lỗi cập nhật active_sessions: {e}")
        raise HTTPException(status_code=500, detail="Không thể lưu phiên làm việc vào cơ sở dữ liệu")

from fastapi import Header, Query, HTTPException, Depends, APIRouter

def verify_token(authorization: str = Header(None), token: str = Query(None)):
    req_token = None
    if authorization:
        parts = authorization.split(" ")
        if len(parts) == 2 and parts[0].lower() == "bearer":
            req_token = parts[1]
    
    if not req_token and token:
        req_token = token

    if not req_token:
        raise HTTPException(
            status_code=401,
            detail="Thiếu mã xác thực (Authorization Header hoặc token query parameter)"
        )
    
    current_token = get_current_session_token()
    
    if not current_token or req_token != current_token:
        raise HTTPException(
            status_code=401,
            detail="Tài khoản đã được đăng nhập ở thiết bị khác hoặc phiên làm việc hết hạn!"
        )
    return req_token

@router.post("/login")
def login(payload: LoginRequest):
    admin_password = os.getenv("ADMIN_PASSWORD", "atsadmin2026")
    # Clean inputs
    username = payload.username.strip()
    password = payload.password.strip()
    
    if username != "admin" or password != admin_password:
        raise HTTPException(
            status_code=400,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác!"
        )
    
    # Tạo token mới và ghi đè phiên cũ
    new_token = str(uuid.uuid4())
    set_current_session_token(new_token)
    
    return {"token": new_token, "username": "admin"}

@router.get("/check")
def check_session(token: str = Depends(verify_token)):
    return {"status": "valid", "username": "admin"}
