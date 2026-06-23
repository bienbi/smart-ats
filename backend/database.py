"""
Database Layer — MongoDB
Quản lý kết nối và CRUD cho hệ thống ATS.
Collections:
  - jd_profiles: Lưu trữ Job Descriptions
  - cv_analyses: Lưu trữ kết quả phân tích CV
"""

 
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from bson import ObjectId
from pymongo import MongoClient, DESCENDING
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI", os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
MONGO_DB_NAME = os.getenv("MONGODB_DB_NAME", os.getenv("MONGO_DB_NAME", "ats_database"))

_client: Optional[MongoClient] = None
_db = None


def _get_db():
    """Lấy database instance (singleton pattern)."""
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        _db = _client[MONGO_DB_NAME]
    return _db


def init_db():
    """Khởi tạo database và tạo indexes."""
    db = _get_db()
    # Indexes cho JD
    db.jd_profiles.create_index("created_at", background=True)
    # Indexes cho CV analyses
    db.cv_analyses.create_index("jd_id", background=True)
    db.cv_analyses.create_index("total_score", background=True)
    db.cv_analyses.create_index("created_at", background=True)
    db.cv_analyses.create_index("candidate_name", background=True)
    return True


# ========================
#  JD PROFILES — CRUD
# ========================

def save_jd(name: str, content: str, parsed_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Lưu JD mới vào database.
    Returns: ID của JD đã lưu (string).
    """
    db = _get_db()
    doc = {
        "name": name.strip(),
        "content": content.strip(),
        "parsed_data": parsed_data or {},
        "created_at": datetime.now(timezone.utc),
    }
    result = db.jd_profiles.insert_one(doc)
    return str(result.inserted_id)


def get_all_jds() -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả JD, sắp xếp theo ngày tạo mới nhất."""
    db = _get_db()
    jds = []
    for doc in db.jd_profiles.find().sort("created_at", DESCENDING):
        jds.append({
            "id": str(doc["_id"]),
            "name": doc["name"],
            "content": doc["content"],
            "parsed_data": doc.get("parsed_data", {}),
            "created_at": doc["created_at"],
        })
    return jds


def get_jd_by_id(jd_id: str) -> Optional[Dict[str, Any]]:
    """Lấy JD theo ID."""
    db = _get_db()
    try:
        doc = db.jd_profiles.find_one({"_id": ObjectId(jd_id)})
    except Exception:
        return None
    if doc is None:
        return None
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "content": doc["content"],
        "parsed_data": doc.get("parsed_data", {}),
        "created_at": doc["created_at"],
    }


def update_jd_parsed_data(jd_id: str, parsed_data: Dict[str, Any]) -> bool:
    """
    Cập nhật dữ liệu trích xuất cấu trúc của JD.
    """
    db = _get_db()
    try:
        result = db.jd_profiles.update_one(
            {"_id": ObjectId(jd_id)},
            {"$set": {"parsed_data": parsed_data}}
        )
        return result.modified_count > 0
    except Exception:
        return False


def delete_jd(jd_id: str) -> bool:
    """Xóa JD theo ID. Returns True nếu xóa thành công."""
    db = _get_db()
    try:
        result = db.jd_profiles.delete_one({"_id": ObjectId(jd_id)})
        return result.deleted_count > 0
    except Exception:
        return False


# ========================
#  CV ANALYSES — CRUD
# ========================

def save_analysis(
    candidate_name: str,
    email: str,
    filename: str,
    jd_id: str,
    jd_name: str,
    total_score: float,
    recommendation: str,
    scoring_breakdown: Dict[str, Any],
    resume_data: Dict[str, Any],
    analysis_report: Dict[str, Any],
    filter_results: Optional[Dict[str, Any]] = None,
    weights_used: Optional[Dict[str, float]] = None,
    file_hash: Optional[str] = None,
) -> str:
    """
    Lưu kết quả phân tích CV vào database.
    Returns: ID của bản ghi đã lưu (string).
    """
    db = _get_db()
    doc = {
        "candidate_name": candidate_name,
        "email": email or "",
        "filename": filename,
        "jd_id": jd_id,
        "jd_name": jd_name,
        "total_score": total_score,
        "recommendation": recommendation,
        "scoring_breakdown": scoring_breakdown,
        "resume_data": resume_data,
        "analysis_report": analysis_report,
        "filter_results": filter_results or {},
        "weights_used": weights_used or {},
        "file_hash": file_hash or "",
        "created_at": datetime.now(timezone.utc),
    }
    result = db.cv_analyses.insert_one(doc)
    return str(result.inserted_id)


def find_analysis_by_hash_or_filename(file_hash: str, filename: str, jd_id: str) -> Optional[Dict[str, Any]]:
    """
    Tìm kiếm kết quả phân tích CV đã có trong MongoDB để tái sử dụng.
    """
    db = _get_db()
    try:
        # 1. Tìm bằng hash trước (chính xác 100%)
        if file_hash:
            doc = db.cv_analyses.find_one({"file_hash": file_hash, "jd_id": jd_id})
            if doc:
                return get_analysis_detail(str(doc["_id"]))
        
        # 2. Tìm fallback bằng filename và jd_id (chỉ áp dụng nếu filename không quá chung chung)
        generic_names = {"cv.pdf", "cv.docx", "resume.pdf", "resume.docx", "cv_tieng_anh.pdf", "cv_tieng_viet.pdf", "cv_en.pdf", "cv_vi.pdf"}
        if filename and filename.lower().strip() not in generic_names:
            doc = db.cv_analyses.find_one({"filename": filename, "jd_id": jd_id})
            if doc:
                return get_analysis_detail(str(doc["_id"]))
    except Exception:
        return None
    return None


def get_all_analyses() -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả phân tích CV (tóm tắt), sắp xếp theo ngày mới nhất."""
    db = _get_db()
    analyses = []
    for doc in db.cv_analyses.find(
        {},
        {
            "candidate_name": 1, "email": 1, "filename": 1,
            "jd_id": 1, "jd_name": 1, "total_score": 1,
            "recommendation": 1, "filter_results": 1,
            "resume_data": 1, "scoring_breakdown": 1,
            "created_at": 1, "weights_used": 1,
        }
    ).sort("created_at", DESCENDING):
        analyses.append({
            "id": str(doc["_id"]),
            "candidate_name": doc.get("candidate_name", ""),
            "email": doc.get("email", ""),
            "filename": doc.get("filename", ""),
            "jd_id": doc.get("jd_id", ""),
            "jd_name": doc.get("jd_name", ""),
            "total_score": doc.get("total_score", 0),
            "recommendation": doc.get("recommendation", ""),
            "filter_results": doc.get("filter_results", {}),
            "resume_data": doc.get("resume_data", {}),
            "scoring_breakdown": doc.get("scoring_breakdown", {}),
            "created_at": doc.get("created_at"),
            "weights_used": doc.get("weights_used", {}),
        })
    return analyses


def get_analyses_by_jd(jd_id: str) -> List[Dict[str, Any]]:
    """Lấy danh sách phân tích CV theo JD ID."""
    db = _get_db()
    analyses = []
    for doc in db.cv_analyses.find(
        {"jd_id": jd_id}
    ).sort("total_score", DESCENDING):
        analyses.append({
            "id": str(doc["_id"]),
            "candidate_name": doc.get("candidate_name", ""),
            "email": doc.get("email", ""),
            "filename": doc.get("filename", ""),
            "jd_name": doc.get("jd_name", ""),
            "total_score": doc.get("total_score", 0),
            "recommendation": doc.get("recommendation", ""),
            "filter_results": doc.get("filter_results", {}),
            "resume_data": doc.get("resume_data", {}),
            "scoring_breakdown": doc.get("scoring_breakdown", {}),
            "created_at": doc.get("created_at"),
        })
    return analyses


def get_analysis_detail(analysis_id: str) -> Optional[Dict[str, Any]]:
    """Lấy chi tiết đầy đủ của một bản phân tích CV."""
    db = _get_db()
    try:
        doc = db.cv_analyses.find_one({"_id": ObjectId(analysis_id)})
    except Exception:
        return None
    if doc is None:
        return None
    return {
        "id": str(doc["_id"]),
        "candidate_name": doc.get("candidate_name", ""),
        "email": doc.get("email", ""),
        "filename": doc.get("filename", ""),
        "jd_id": doc.get("jd_id", ""),
        "jd_name": doc.get("jd_name", ""),
        "total_score": doc.get("total_score", 0),
        "recommendation": doc.get("recommendation", ""),
        "scoring_breakdown": doc.get("scoring_breakdown", {}),
        "resume_data": doc.get("resume_data", {}),
        "analysis_report": doc.get("analysis_report", {}),
        "filter_results": doc.get("filter_results", {}),
        "weights_used": doc.get("weights_used", {}),
        "created_at": doc.get("created_at"),
    }


def delete_analysis(analysis_id: str) -> bool:
    """Xóa bản ghi phân tích CV. Returns True nếu xóa thành công."""
    db = _get_db()
    try:
        result = db.cv_analyses.delete_one({"_id": ObjectId(analysis_id)})
        return result.deleted_count > 0
    except Exception:
        return False


def delete_analyses_by_jd(jd_id: str) -> int:
    """Xóa tất cả phân tích CV liên quan đến JD. Returns số bản ghi đã xóa."""
    db = _get_db()
    try:
        result = db.cv_analyses.delete_many({"jd_id": jd_id})
        return result.deleted_count
    except Exception:
        return 0
