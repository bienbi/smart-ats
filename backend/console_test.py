import json

from extract_cv import process_cv_and_jd, CVExtractionError
from scoring_cv import CVScoresAggregator


def score_candidate(cv_file_path: str, jd_text: str) -> dict:
    print("\n[1/2] Đang trích xuất và phân tích CV + JD...")
    try:
        cv_data, jd_data, resume, jd = process_cv_and_jd(
            cv_file_path=cv_file_path,
            jd_text=jd_text,
        )
    except CVExtractionError as e:
        print(f"Lỗi đọc file CV: {e}")
        return None
    except Exception as e:
        print(f"Lỗi khi gọi AI: {e}")
        return None

    print(f"Ứng viên: {resume.name}")
    print(f"Vị trí JD: {jd.job_title}")

    print("\n[2/2] Đang chấm điểm...")
    aggregator = CVScoresAggregator()
    result = aggregator.score_cv(cv_data, jd_data)

    return result


def print_result(result: dict, candidate_name: str = "Ứng viên"):
    """In kết quả chấm điểm ra console theo định dạng dễ đọc."""
    if result is None:
        print("Không có kết quả do xảy ra lỗi.")
        return

    print(f"KẾT QUẢ CHẤM ĐIỂM: {candidate_name}")

    score = result["final_score_pct"]
    recommendation = result["recommendation"]

    print(f"Điểm tổng: {score}")
    print(f"Đánh giá: {recommendation}")

    print("Chi tiết từng tiêu chí")
    label_map = {
        "experience": "Kinh nghiệm",
        "skills":     "Kỹ năng",
        "education":  "Học vấn",
        "language":   "Ngoại ngữ",
        "stability":  "Sự gắn bó",
    }
    for key, label in label_map.items():
        item = result["breakdown"].get(key, {})
        raw_score = item.get("score", 0)
        weight = item.get("weight", 0)
        weighted = item.get("weighted_score", 0)
        reasoning = item.get("details", {}).get("reasoning", "")
        print(
            f"  {label:<12} {int(raw_score * 100):>3}%  "
            f"(trọng số {int(weight * 100)}% -> đóng góp {int(weighted * 100)}%) "
            f"| {reasoning}"
        )

    print("\nKỹ năng còn thiếu")
    skills_details = result["breakdown"].get("skills", {}).get("details", {})
    missing_must = skills_details.get("missing_critical_skills", [])
    missing_nice = skills_details.get("missing_nice_skills", [])

    if missing_must:
        print(f"Bắt buộc còn thiếu : {', '.join(missing_must)}")
    else:
        print("Bắt buộc còn thiếu : (không thiếu kỹ năng nào)")

    if missing_nice:
        print(f"Ưu tiên còn thiếu  : {', '.join(missing_nice)}")

    print("=" * 60)



