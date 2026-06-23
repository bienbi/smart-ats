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

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional

def parse_date_to_months(date_str: Any) -> Optional[int]:
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    import re
    # Match YYYY-MM
    match = re.match(r"^(\d{4})-(\d{2})$", date_str)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        return year * 12 + month
    # Match YYYY
    match_year = re.match(r"^(\d{4})$", date_str)
    if match_year:
        year = int(match_year.group(1))
        return year * 12 + 1
    return None

def calculate_experience_totals(experience_history: list) -> Tuple[float, float, float]:
    """
    Tính toán (raw_total_years, relevant_total_years, max_relevance) có xử lý trùng lặp thời gian (overlap).
    Sử dụng phương pháp chia lưới theo tháng để gộp các khoảng thời gian song song.
    """
    if not experience_history:
        return 0.0, 0.0, 0.0

    mapped_months = {} # month_index -> max_relevance_for_this_month
    unmappable_raw_years = 0.0
    unmappable_weighted_years = 0.0
    max_relevance = 0.0

    for job in experience_history:
        relevance = float(job.get("relevance_to_jd", 0.0))
        max_relevance = max(max_relevance, relevance)
        
        start_date = job.get("start_date")
        end_date = job.get("end_date")
        years = float(job.get("years", 0.0))

        start_month = parse_date_to_months(start_date)
        end_month = parse_date_to_months(end_date)

        if start_month is not None and end_month is not None:
            # Sắp xếp đúng thứ tự nếu start_month > end_month
            if start_month > end_month:
                start_month, end_month = end_month, start_month
            for m in range(start_month, end_month + 1):
                mapped_months[m] = max(mapped_months.get(m, 0.0), relevance)
        else:
            # Fallback nếu không có ngày bắt đầu/kết thúc cụ thể
            unmappable_raw_years += years
            unmappable_weighted_years += years * relevance

    mapped_raw_years = len(mapped_months) / 12.0
    mapped_weighted_years = sum(mapped_months.values()) / 12.0

    total_raw_years = round(mapped_raw_years + unmappable_raw_years, 2)
    total_relevant_years = round(mapped_weighted_years + unmappable_weighted_years, 2)

    return total_raw_years, total_relevant_years, max_relevance

class BaseMatcher(ABC):
    def __init__(self, config: Dict[str, float] = None):
        self.config = config or {}

    @abstractmethod
    def calculate_match(self, cv_data: Dict[str, Any], jd_data: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """
        Tính điểm % phù hợp giữa CV và JD.
        Trả về Tuple: (Điểm số từ 0 -> 1, Bảng giải thích chi tiết)
        """
        pass

# TÍNH ĐIỂM KINH NGHIỆM LÀM VIỆC

class ExperienceMatcher(BaseMatcher):
    def calculate_match(self, cv_data: Dict[str, Any], jd_data: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        jd_required_years = jd_data.get("required_experience_years", 0.0)
        experience_history = cv_data.get("experience_history") or []

        total_raw_years, total_relevant_years, max_relevance = calculate_experience_totals(experience_history)

        breakdown = []
        for job in experience_history:
            years = job.get("years", 0.0)
            relevance = job.get("relevance_to_jd", 0.0)
            breakdown.append({
                "Job_title": job.get("title", "N/A"),
                "raw_years": years,
                "relevance_pct": int(relevance * 100),
                "contributed_years": round(years * relevance, 2)
            })

        # Chấm điểm số năm kinh nghiệm trước
        if jd_required_years == 0:
            years_fit_score = 1.0
            years_reasoning = "JD không yêu cầu kinh nghiệm"
        else:
            years_fit_score = min(1.0, total_relevant_years / jd_required_years)
            if years_fit_score >= 1.0:
                years_reasoning = "Ứng viên có đủ kinh nghiệm liên quan đến JD"
            else:
                years_reasoning = f"Ứng viên đi làm {total_raw_years} năm thực tế (không tính trùng lặp), trong đó có {total_relevant_years} năm liên quan đến JD (yêu cầu {jd_required_years} năm)."

        # Sửa lỗi kinh nghiệm ảo: nhân điểm số năm với mức độ công nghệ tương thích cao nhất
        if jd_required_years > 0:
            score = years_fit_score * max_relevance
            if max_relevance <= 0.3:
                reasoning = f"Chưa đạt. {years_reasoning} Tuy nhiên, điểm kinh nghiệm bị giảm trừ sâu do công nghệ làm việc trong quá khứ lệch hoàn toàn với tech stack cốt lõi của JD (độ tương thích stack lớn nhất chỉ đạt {int(max_relevance*100)}%)."
            elif max_relevance <= 0.5:
                reasoning = f"Cân nhắc. {years_reasoning} Điểm kinh nghiệm bị giảm bớt do tech stack lệch một phần và cần đào tạo lại (độ tương thích stack lớn nhất đạt {int(max_relevance*100)}%)."
            else:
                reasoning = years_reasoning
        else:
            score = 1.0
            reasoning = "JD không yêu cầu kinh nghiệm."

        hr_evals = cv_data.get("hr_evaluations")
        if hr_evals and isinstance(hr_evals, dict) and hr_evals.get("experience"):
            reasoning = hr_evals["experience"]

        return score, {
            "required_years": jd_required_years,
            "raw_total_years": total_raw_years,
            "relevant_total_years": total_relevant_years,
            "max_relevance": max_relevance,
            "job_breakdown": breakdown,
            "reasoning": reasoning
        }

# TÍNH ĐIỂM HỌC VẤN 
class EducationMatcher(BaseMatcher):
    degree_level = {
        "none": 0,
        "associate": 1,  # cao đẳng
        "bachelor": 2,
        "master": 3,
        "phd": 4,
    }

    def calculate_match(self, cv_data: Dict[str, Any], jd_data: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        jd_degree = str(jd_data.get("required_degree") or "none").lower()
        jd_level = self.degree_level.get(jd_degree, 0)

        # Lấy danh sách bằng cấp. VD: [{"degree": "bachelor", "major_relevant": 0.2}, {"degree": "master", "major_relevant": 0.9}]
        education_history = cv_data.get("education_history", [])
        
        if not education_history and cv_data.get("highest_degree"):
            education_history = [{
                "degree": cv_data.get("highest_degree"),
                "major_relevant": cv_data.get("major_relevant", 1.0)
            }]
        elif not education_history:
            education_history = [{"degree": "none", "major_relevant": 0.0}]

        best_score = 0.0
        best_edu = None
        best_reasoning = ""

        for edu in education_history:
            cv_degree = str(edu.get("degree") or "none").lower()
            cv_level = self.degree_level.get(cv_degree, 0)
            major_relevant = edu.get("major_relevant", 0.0)

            if jd_level == 0:
                if major_relevant >= 0.8:
                    edu_score = 1.0
                    reason = f"Chuyên ngành phù hợp tốt ({cv_degree.title()})"
                elif major_relevant >= 0.5:
                    edu_score = 0.75
                    reason = f"Chuyên ngành phù hợp một phần ({cv_degree.title()})"
                else:
                    edu_score = 0.4
                    reason = f"Chuyên ngành không liên quan ({cv_degree.title()})"
            else:
                if cv_level >= jd_level:
                    level_score = 1.0
                    level_reason = f"Đạt yêu cầu cấp bậc ({cv_degree.title()} vs {jd_degree.title()})"
                else:
                    penalty = (jd_level - cv_level) / jd_level
                    level_score = 1.0 - penalty
                    level_reason = f"Chưa đạt yêu cầu cấp bậc ({cv_degree.title()} vs {jd_degree.title()})"
                
                edu_score = level_score * max(major_relevant, 0.1)
                
                if major_relevant < 0.5:
                    major_reason = "Chuyên ngành học không liên quan đến JD"
                elif major_relevant < 0.8:
                    major_reason = "Chuyên ngành học có liên quan một phần đến JD"
                else:
                    major_reason = "Chuyên ngành học phù hợp với JD"
                reason = f"{level_reason}, {major_reason}"

            if edu_score >= best_score:
                best_score = round(edu_score, 2)
                best_edu = edu
                best_reasoning = reason

        if best_edu is None:
            best_edu = education_history[0] if education_history else {"degree": "none", "major_relevant": 0.0}

        if jd_level == 0:
            full_reasoning = f"JD không yêu cầu bằng cấp cụ thể. {best_reasoning}."
        else:
            full_reasoning = f"Dựa trên bằng cấp phù hợp nhất: {best_reasoning}"

        hr_evals = cv_data.get("hr_evaluations")
        if hr_evals and isinstance(hr_evals, dict) and hr_evals.get("education"):
            full_reasoning = hr_evals["education"]

        return best_score, {
            "jd_degree": jd_degree,
            "best_matched_degree": best_edu.get("degree", "none"),
            "major_relevant": best_edu.get("major_relevant", 0.0),
            "reasoning": full_reasoning
        }
    
# TÍNH ĐIỂM KỸ NĂNG CHUYÊN MÔN

class SkillMatcher(BaseMatcher):
    def calculate_match(self, cv_data: Dict[str, Any], jd_data: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        skills_match = cv_data.get("skills_match")
        
        # Nếu có dữ liệu so khớp phân tầng (Cách 3 mới)
        if skills_match is not None:
            # Nhóm các kết quả theo tầng (core, supporting, tools)
            core_evals = [s for s in skills_match if s.get("category") == "core"]
            supp_evals = [s for s in skills_match if s.get("category") == "supporting"]
            tool_evals = [s for s in skills_match if s.get("category") == "tools"]

            # Hàm tính điểm của một tầng
            def calculate_layer_score(evals) -> float:
                if not evals:
                    return 1.0 # Tầng này không yêu cầu kỹ năng nào
                total_val = 0.0
                for item in evals:
                    status = item.get("status", "missing")
                    if status == "matched":
                        total_val += 1.0
                    elif status == "equivalent":
                        total_val += 0.7
                    else:
                        total_val += 0.0
                return min(1.0, total_val / len(evals))

            core_score = calculate_layer_score(core_evals)
            supp_score = calculate_layer_score(supp_evals)
            tool_score = calculate_layer_score(tool_evals)

            # Tính điểm kỹ năng theo trọng số phân tầng 60% Core, 30% Supporting, 10% Tools
            # Nếu một số tầng không có yêu cầu nào, ta tái phân bổ trọng số cho các tầng còn lại
            w_core, w_supp, w_tool = 0.6, 0.3, 0.1
            if not core_evals and not supp_evals and not tool_evals:
                final_skill_score = 1.0
            else:
                active_weights = []
                active_scores = []
                if core_evals:
                    active_weights.append(w_core)
                    active_scores.append(core_score)
                if supp_evals:
                    active_weights.append(w_supp)
                    active_scores.append(supp_score)
                if tool_evals:
                    active_weights.append(w_tool)
                    active_scores.append(tool_score)
                
                sum_weights = sum(active_weights)
                if sum_weights > 0:
                    final_skill_score = sum(s * (w / sum_weights) for s, w in zip(active_scores, active_weights))
                else:
                    final_skill_score = 1.0

            matched_critical = []
            matched_nice = []
            equivalent_critical = []
            equivalent_nice = []
            missing_critical = []
            missing_nice = []
            equivalent_details = []

            for item in skills_match:
                name = item.get("skill_name")
                cat = item.get("category")
                status = item.get("status")
                eq = item.get("equivalent_skill")
                ev = item.get("evidence")

                if status == "matched":
                    if cat in ("core", "supporting"):
                        matched_critical.append(name)
                    else:
                        matched_nice.append(name)
                elif status == "equivalent":
                    if cat in ("core", "supporting"):
                        equivalent_critical.append(name)
                    else:
                        equivalent_nice.append(name)
                    equivalent_details.append(f"• <b>{name}</b>: Tương đương với <i>{eq}</i> trong CV ({ev})")
                else:
                    if cat in ("core", "supporting"):
                        missing_critical.append(name)
                    else:
                        missing_nice.append(name)

            reasoning_parts = []
            # Kỹ năng đã đạt
            all_exact_matched = matched_critical + matched_nice
            if all_exact_matched:
                reasoning_parts.append(f"<b>Kỹ năng ĐÃ ĐẠT:</b> {', '.join(all_exact_matched)}")
            else:
                reasoning_parts.append("<b>Kỹ năng ĐÃ ĐẠT:</b> Không có")

            # Kỹ năng tương đương
            all_equivalent = equivalent_critical + equivalent_nice
            if all_equivalent:
                reasoning_parts.append(f"<b>Kỹ năng TƯƠNG ĐƯƠNG:</b> {', '.join(all_equivalent)}")
                if equivalent_details:
                    reasoning_parts.append("<b>Chi tiết tương đương:</b><br/>" + "<br/>".join(equivalent_details))
            else:
                reasoning_parts.append("<b>Kỹ năng TƯƠNG ĐƯƠNG:</b> Không có")

            # Kỹ năng còn thiếu
            all_missing = missing_critical + missing_nice
            if all_missing:
                reasoning_parts.append(f"<b>Kỹ năng CÒN THIẾU:</b> <span style='color:#ef4444;'>{', '.join(all_missing)}</span>")
            else:
                reasoning_parts.append("<b>Kỹ năng CÒN THIẾU:</b> Không có")

            html_reasoning = "<br/><br/>".join(reasoning_parts)

            hr_evals = cv_data.get("hr_evaluations")
            if hr_evals and isinstance(hr_evals, dict) and hr_evals.get("skills"):
                html_reasoning = hr_evals["skills"]

            return final_skill_score, {
                "must_have_score": round(core_score * 0.7 + supp_score * 0.3, 2), # Cho qualification check
                "nice_to_have_score": round(tool_score, 2),
                "matched_critical_skills": matched_critical,
                "matched_nice_skills": matched_nice,
                "equivalent_critical_skills": equivalent_critical,
                "equivalent_nice_skills": equivalent_nice,
                "missing_critical_skills": missing_critical,
                "missing_nice_skills": missing_nice,
                "reasoning": html_reasoning
            }

        # FALLBACK: Chạy logic chấm điểm thô cũ nếu không có dữ liệu phân tầng (cho các bản ghi cũ từ DB)
        must_have_req = set(jd_data.get("must_have_skills", []))
        must_have_cv = set(cv_data.get("matched_must_have_skills", []))

        must_score = 0.0
        if not must_have_req:
            must_score = 1.0 
        else:
            must_score = min(1.0, len(must_have_cv) / len(must_have_req))

        nice_to_have_req = set(jd_data.get("nice_to_have_skills", []))
        nice_to_have_cv = set(cv_data.get("matched_nice_to_have_skills", []))

        nice_score = 0.0
        if not nice_to_have_req:
            nice_score = 1.0 
        else:
            nice_score = min(1.0, len(nice_to_have_cv) / len(nice_to_have_req))

        # Trọng số kỹ năng bắt buộc và kỹ năng ưu tiên
        weight_must = 0.8
        weight_nice = 0.2

        if not nice_to_have_req:
            weight_must = 1.0 
            weight_nice = 0.0
        elif not must_have_req:  # Bổ sung case JD chỉ có Nice to have
            weight_must = 0.0
            weight_nice = 1.0

        final_skill_score = (must_score * weight_must) + (nice_score * weight_nice)

        # Lấy danh sách kỹ năng thiếu để gợi ý cho câu hỏi phỏng vấn
        missing_must = list(must_have_req - must_have_cv)
        missing_nice = list(nice_to_have_req - nice_to_have_cv) # Thêm cái này rất hữu ích

        # Format lại Reasoning 
        reasoning_parts = []
        if must_have_cv:
            reasoning_parts.append(f"<b>Kỹ năng ĐÃ ĐẠT:</b> {', '.join(must_have_cv)}")
        if nice_to_have_cv:
            reasoning_parts.append(f"<b>Công cụ đã đạt:</b> {', '.join(nice_to_have_cv)}")
        if missing_must or missing_nice:
            reasoning_parts.append(f"<b>Kỹ năng CÒN THIẾU:</b> <span style='color:#ef4444;'>{', '.join(missing_must + missing_nice)}</span>")
            
        reasoning = "<br/><br/>".join(reasoning_parts) if reasoning_parts else "JD không yêu cầu kỹ năng nào."

        hr_evals = cv_data.get("hr_evaluations")
        if hr_evals and isinstance(hr_evals, dict) and hr_evals.get("skills"):
            reasoning = hr_evals["skills"]

        return final_skill_score, {
            "must_have_score": round(must_score, 2),
            "nice_to_have_score": round(nice_score, 2),
            "matched_critical_skills": list(must_have_cv),
            "matched_nice_skills": list(nice_to_have_cv),
            "equivalent_critical_skills": [],
            "equivalent_nice_skills": [],
            "missing_critical_skills": missing_must,
            "missing_nice_skills": missing_nice,
            "reasoning": reasoning
        }

# TÍNH ĐIỂM NGOẠI NGỮ

class LanguageMatcher(BaseMatcher):
    language_levels = {
        "none": 0,
        "basic": 1,          # Sơ cấp
        "conversational": 2, # Giao tiếp
        "fluent": 3,         # Thông thạo
        "native": 4          # Bản ngữ
    }
    
    def calculate_match(self, cv_data: Dict[str, Any], jd_data: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        # Lấy danh sách ngoại ngữ yêu cầu từ JD, VD: {"english": "fluent", "japanese": "basic"}
        req_langs = jd_data.get("required_languages", {})
        
        if not req_langs:
            reasoning = "JD không yêu cầu ngoại ngữ."
            hr_evals = cv_data.get("hr_evaluations")
            if hr_evals and isinstance(hr_evals, dict) and hr_evals.get("language"):
                reasoning = hr_evals["language"]
            return 1.0, {"reasoning": reasoning}
            
        cv_langs = {k.lower(): str(v).lower() for k, v in cv_data.get("languages", {}).items()}
        total_score = 0.0
        breakdown = []
        
        for lang, req_level_str in req_langs.items():
            lang_lower = lang.lower()
            req_level = self.language_levels.get(str(req_level_str).lower(), 1)
            
            cv_level_str = cv_langs.get(lang_lower, "none")
            cv_level = self.language_levels.get(cv_level_str, 0)
            
            if cv_level >= req_level:
                score = 1.0
            else:
                score = cv_level / req_level 
                
            total_score += score
            breakdown.append({
                "language": lang,
                "required_level": req_level_str,
                "candidate_level": cv_level_str,
                "score": round(score, 2)
            })
            
        final_score = total_score / len(req_langs)
        
        reasoning = f"Đáp ứng trung bình {round(final_score * 100)}% yêu cầu ngoại ngữ."
        hr_evals = cv_data.get("hr_evaluations")
        if hr_evals and isinstance(hr_evals, dict) and hr_evals.get("language"):
            reasoning = hr_evals["language"]

        return round(final_score, 2), {
            "breakdown": breakdown,
            "reasoning": reasoning
        }

# ĐÁNH GIÁ MỨC ĐỘ GẮN BÓ/NHẢY VIỆC 
class StabilityMatcher(BaseMatcher):
    def calculate_match(self, cv_data: Dict[str, Any], jd_data: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        experience_history = cv_data.get("experience_history") or []
        
        hr_evals = cv_data.get("hr_evaluations")
        has_override = hr_evals and isinstance(hr_evals, dict) and hr_evals.get("stability")
        
        if not experience_history:
            reasoning = hr_evals["stability"] if has_override else "Chưa có đủ dữ liệu lịch sử làm việc để đánh giá mức độ gắn bó."
            return 1.0, {"reasoning": reasoning}
            
        # Loại bỏ các công việc tạm thời (Freelance, Intern, Collaborator, v.v.) khỏi tính toán nhảy việc
        stable_jobs = []
        for job in experience_history:
            title = str(job.get("title") or "").lower()
            is_temporary = any(kw in title for kw in ["intern", "freelance", "collaborator", "cộng tác viên", "thực tập", "part-time", "contract", "dự án", "collaborate"])
            if not is_temporary:
                stable_jobs.append(job)

        if not stable_jobs:
            reasoning = hr_evals["stability"] if has_override else "Ứng viên chủ yếu làm Freelance hoặc Thực tập, không tính rủi ro nhảy việc."
            return 1.0, {"reasoning": reasoning}

        num_jobs = len(stable_jobs)
        total_years = sum(job.get("years", 0.0) for job in stable_jobs)
        
        if num_jobs <= 1 or total_years < 1.0:
            reasoning = hr_evals["stability"] if has_override else "Ứng viên có ít công ty chính thức hoặc là Fresher, không có dấu hiệu nhảy việc."
            return 1.0, {"reasoning": reasoning}
            
        avg_tenure = total_years / num_jobs
        
        score = min(1.0, max(0.2, avg_tenure / 2.0))
        
        if score >= 0.9:
            reasoning = f"Gắn bó rất tốt (trung bình {round(avg_tenure, 1)} năm/công ty chính thức)."
        elif score >= 0.7:
            reasoning = f"Gắn bó khá tốt (trung bình {round(avg_tenure, 1)} năm/công ty chính thức)."
        elif score >= 0.5:
            reasoning = f"Có dấu hiệu thay đổi công việc hơi nhanh (trung bình {round(avg_tenure, 1)} năm/công ty chính thức)."
        else:
            reasoning = f"Rủi ro nhảy việc cao (trung bình chỉ {round(avg_tenure, 1)} năm/công ty chính thức)."
            
        if has_override:
            reasoning = hr_evals["stability"]

        return score, {
            "total_companies": num_jobs,
            "total_years": round(total_years, 2),
            "average_tenure_years": round(avg_tenure, 2),
            "reasoning": reasoning
        }

# TỔNG HỢP ĐIỂM CV

class CVScoresAggregator:
    def __init__(self, weights: Dict[str, float] = None):
        # Trọng số điểm cho từng yếu tố
        self.weights = weights or {
            "experience": 0.30, # 30% cho Kinh nghiệm
            "skills": 0.40,     # 40% cho Kỹ năng chuyên môn
            "education": 0.10,  # 10% cho Bằng cấp
            "language": 0.10,   # 10% cho Ngoại ngữ
            "stability": 0.10   # 10% cho Sự gắn bó (ít nhảy việc)
        }
        
        total_weight = sum(self.weights.values())
        if round(total_weight, 2) != 1.0:
            raise ValueError(f"Tổng trọng số phải bằng 1.0, hiện tại đang là {total_weight}")

        self.matchers = {
            "experience": ExperienceMatcher(),
            "skills": SkillMatcher(),
            "education": EducationMatcher(),
            "language": LanguageMatcher(),
            "stability": StabilityMatcher()
        }
        
    def score_cv(self, cv_data: Dict[str, Any], jd_data: Dict[str, Any]) -> Dict[str, Any]:
        # Sao chép weights gốc
        current_weights = self.weights.copy()
        
        # 1. Kiểm tra xem JD có yêu cầu Ngoại ngữ không
        req_langs = jd_data.get("required_languages", {})
        has_lang_req = bool(req_langs)
        
        # 2. Áp dụng Trọng số động nếu không yêu cầu Ngoại ngữ
        if not has_lang_req:
            lang_weight = current_weights.get("language", 0.0)
            if lang_weight > 0.0:
                current_weights["language"] = 0.0
                # San phẳng 10% trọng số của Ngoại ngữ sang cho phần Kỹ năng chuyên môn
                current_weights["skills"] = current_weights.get("skills", 0.40) + lang_weight

        total_score = 0.0
        breakdown = {}
        
        for key, matcher in self.matchers.items():
            try:
                score, details = matcher.calculate_match(cv_data, jd_data)
            except Exception as e:
                score = 0.0
                details = {"error": str(e), "reasoning": f"Lỗi khi phân tích tiêu chí '{key}'"}
            
            weight = current_weights.get(key, 0.0)
            
            # Nếu Ngoại ngữ không có yêu cầu, gán điểm 0 thay vì 1.0 free và giải thích rõ
            if key == "language" and not has_lang_req:
                score = 0.0
                details = {
                    "reasoning": "JD không yêu cầu ngoại ngữ. Trọng số 10% được phân bổ lại cho Kỹ năng chuyên môn.",
                    "breakdown": []
                }
                
            weighted_score = score * weight
            total_score += weighted_score
            
            # Lưu lại vào báo cáo chi tiết
            breakdown[key] = {
                "score": round(score, 2),
                "weight": weight,
                "weighted_score": round(weighted_score, 2),
                "details": details
            }
            
        final_score_pct = round(total_score * 100, 2)
        
        # Nếu ứng viên thiếu > 70% kỹ năng bắt buộc -> Loại trực tiếp
        # Tránh trường hợp ứng viên không có skill gì nhưng vẫn nhận "Cân nhắc" (recommendation) 
        skills_details = breakdown.get("skills", {}).get("details", {})
        must_have_score = skills_details.get("must_have_score", 1.0)
        is_disqualified = must_have_score < 0.3  
        
        if is_disqualified:
            recommendation = "Not Match (Không phù hợp) -> Loại (thiếu kỹ năng bắt buộc quan trọng)"
        elif final_score_pct >= 80:
            recommendation = "Strong Match (Rất phù hợp) -> Ưu tiên phỏng vấn ngay"
        elif final_score_pct >= 65:
            recommendation = "Good Match (Phù hợp) -> Đưa vào danh sách xem xét"
        elif final_score_pct >= 50:
            recommendation = "Partial Match (Phù hợp một phần) -> Cân nhắc nếu thiếu ứng viên"
        else:
            recommendation = "Not Match (Không phù hợp) -> Loại"

        return {
            "final_score_pct": final_score_pct,
            "final_score_raw": round(total_score, 4),
            "is_disqualified": is_disqualified,
            "recommendation": recommendation,
            "weights_used": current_weights,
            "breakdown": breakdown,
            "recruiter_note": cv_data.get("recruiter_note", None),
            "hr_evaluations": cv_data.get("hr_evaluations", None),
            "strengths": cv_data.get("strengths", []),
            "risks": cv_data.get("risks", []),
            "interview_questions": cv_data.get("interview_questions", [])
        }


# BỘ LỌC NÂNG CAO — ÁP DỤNG SAU KHI CHẤM ĐIỂM

class AdvancedFilter:
    """
    Bộ lọc nâng cao cho phép HR lọc CV theo nhiều yếu tố tùy chọn.
    Áp dụng SAU khi chấm điểm, chỉ đánh dấu ✅/⚠️, KHÔNG tự động loại.
    """

    # Mapping cấp bậc bằng cấp (dùng lại từ EducationMatcher)
    degree_levels = {
        "none": 0, "associate": 1, "bachelor": 2, "master": 3, "phd": 4,
    }
    degree_labels_vi = {
        "none": "Không yêu cầu", "associate": "Cao đẳng", 
        "bachelor": "Cử nhân", "master": "Thạc sĩ", "phd": "Tiến sĩ",
    }
    
    # Mapping trình độ ngoại ngữ
    language_levels = {
        "none": 0, "basic": 1, "conversational": 2, "fluent": 3, "native": 4,
    }
    language_labels_vi = {
        "none": "Không có", "basic": "Sơ cấp",
        "conversational": "Giao tiếp", "fluent": "Thông thạo", "native": "Bản ngữ",
    }

    @staticmethod
    def apply_filters(
        cv_data: Dict[str, Any],
        resume_obj,  # CandidateResume pydantic object
        scoring_result: Dict[str, Any],
        filter_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Áp dụng bộ lọc nâng cao lên kết quả phân tích CV.

        Args:
            cv_data: Dict dữ liệu CV đã chuẩn bị cho scoring
            resume_obj: CandidateResume pydantic object (chứa thông tin đầy đủ)
            scoring_result: Kết quả từ CVScoresAggregator.score_cv()
            filter_config: Dict cấu hình bộ lọc từ UI, VD:
                {
                    "universities": ["Bách Khoa", "FPT"],
                    "min_experience_years": 4,
                    "language": {"name": "english", "min_level": "fluent"},
                    "required_skills": ["Python", "SQL"],
                    "min_degree": "bachelor",
                    "min_stability_pct": 50,
                }

        Returns:
            {
                "passed": True/False (đạt TẤT CẢ bộ lọc),
                "details": [
                    {"filter": "Trường ĐH", "passed": True, "reason": "..."},
                    ...
                ]
            }
        """
        details = []
        all_passed = True

        # --- 1. LỌC TRƯỜNG ĐẠI HỌC ---
        universities = filter_config.get("universities", [])
        if universities:
            from cv_tailor import translate_school_name
            # Lấy danh sách trường từ resume_obj (gồm cả raw và translated)
            candidate_schools = []
            candidate_schools_display = []
            if resume_obj and hasattr(resume_obj, "educations"):
                for edu in resume_obj.educations:
                    raw = edu.school.lower().strip()
                    vi = translate_school_name(edu.school).lower().strip()
                    candidate_schools.append((raw, vi, edu.school))
                    candidate_schools_display.append(translate_school_name(edu.school))

            # So sánh fuzzy: kiểm tra xem tên trường yêu cầu có xuất hiện trong tên trường của ứng viên (raw hoặc vi)
            matched = False
            matched_school = ""
            for req_school in universities:
                req_lower = req_school.lower().strip()
                for raw, vi, original in candidate_schools:
                    if req_lower in raw or raw in req_lower or req_lower in vi or vi in req_lower:
                        matched = True
                        matched_school = original
                        break
                if matched:
                    break

            if matched:
                details.append({
                    "filter": "Trường ĐH",
                    "passed": True,
                    "reason": f"Ứng viên tốt nghiệp từ: {translate_school_name(matched_school)}",
                })
            else:
                all_passed = False
                schools_str = ", ".join(candidate_schools_display) if candidate_schools_display else "Không rõ"
                details.append({
                    "filter": "Trường ĐH",
                    "passed": False,
                    "reason": f"Trường của ứng viên ({schools_str}) không nằm trong danh sách yêu cầu ({', '.join(universities)})",
                })

        # --- 2. LỌC KINH NGHIỆM TỐI THIỂU ---
        min_exp = filter_config.get("min_experience_years")
        if min_exp is not None and min_exp > 0:
            exp_details = scoring_result.get("breakdown", {}).get("experience", {}).get("details", {})
            relevant_years = exp_details.get("relevant_total_years", 0)
            raw_years = exp_details.get("raw_total_years", 0)

            if relevant_years >= min_exp:
                details.append({
                    "filter": "Kinh nghiệm tối thiểu",
                    "passed": True,
                    "reason": f"{relevant_years} năm kinh nghiệm liên quan (yêu cầu ≥ {min_exp} năm)",
                })
            else:
                all_passed = False
                details.append({
                    "filter": "Kinh nghiệm tối thiểu",
                    "passed": False,
                    "reason": f"Chỉ có {relevant_years} năm kinh nghiệm liên quan (tổng {raw_years} năm), yêu cầu ≥ {min_exp} năm",
                })

        # --- 3. LỌC TRÌNH ĐỘ NGOẠI NGỮ ---
        lang_filter = filter_config.get("language", {})
        if lang_filter and lang_filter.get("name") and lang_filter.get("min_level"):
            lang_name = lang_filter["name"].lower()
            min_level = lang_filter["min_level"].lower()
            min_level_num = AdvancedFilter.language_levels.get(min_level, 0)

            # Lấy trình độ ngoại ngữ của ứng viên
            cv_langs = cv_data.get("languages", {})
            cv_level_str = cv_langs.get(lang_name, "none")
            cv_level_num = AdvancedFilter.language_levels.get(cv_level_str, 0)

            min_label = AdvancedFilter.language_labels_vi.get(min_level, min_level)
            cv_label = AdvancedFilter.language_labels_vi.get(cv_level_str, cv_level_str)

            if cv_level_num >= min_level_num:
                details.append({
                    "filter": f"Ngoại ngữ ({lang_name.title()})",
                    "passed": True,
                    "reason": f"Trình độ {lang_name.title()}: {cv_label} (yêu cầu ≥ {min_label})",
                })
            else:
                all_passed = False
                details.append({
                    "filter": f"Ngoại ngữ ({lang_name.title()})",
                    "passed": False,
                    "reason": f"Trình độ {lang_name.title()}: {cv_label} — chưa đạt (yêu cầu ≥ {min_label})",
                })

        # --- 4. LỌC KỸ NĂNG BẮT BUỘC ---
        required_skills = filter_config.get("required_skills", [])
        if required_skills:
            # Lấy tất cả kỹ năng ứng viên (bao gồm matched skills)
            candidate_skills_lower = set()
            if resume_obj and hasattr(resume_obj, "skills"):
                for s in resume_obj.skills:
                    candidate_skills_lower.add(s.lower().strip())
            # Cũng thêm matched skills
            for s in cv_data.get("matched_must_have_skills", []):
                candidate_skills_lower.add(s.lower().strip())
            for s in cv_data.get("matched_nice_to_have_skills", []):
                candidate_skills_lower.add(s.lower().strip())

            matched_skills = []
            missing_skills = []
            for skill in required_skills:
                skill_lower = skill.lower().strip()
                if skill_lower in candidate_skills_lower:
                    matched_skills.append(skill)
                else:
                    # Fuzzy check: kiểm tra nếu skill là substring
                    found = any(skill_lower in cs for cs in candidate_skills_lower)
                    if found:
                        matched_skills.append(skill)
                    else:
                        missing_skills.append(skill)

            if not missing_skills:
                details.append({
                    "filter": "Kỹ năng bắt buộc",
                    "passed": True,
                    "reason": f"Có đủ tất cả kỹ năng yêu cầu: {', '.join(matched_skills)}",
                })
            else:
                all_passed = False
                details.append({
                    "filter": "Kỹ năng bắt buộc",
                    "passed": False,
                    "reason": f"Thiếu kỹ năng: {', '.join(missing_skills)} (Có: {', '.join(matched_skills) if matched_skills else 'Không có'})",
                })

        # --- 5. LỌC BẰNG CẤP TỐI THIỂU ---
        min_degree = filter_config.get("min_degree", "")
        if min_degree and min_degree != "none":
            min_degree_num = AdvancedFilter.degree_levels.get(min_degree.lower(), 0)
            min_degree_label = AdvancedFilter.degree_labels_vi.get(min_degree.lower(), min_degree)

            # Tìm bằng cấp cao nhất của ứng viên
            max_cv_degree = "none"
            max_cv_degree_num = 0
            if resume_obj and hasattr(resume_obj, "educations"):
                for edu in resume_obj.educations:
                    d = edu.degree.lower().strip()
                    d_num = AdvancedFilter.degree_levels.get(d, 0)
                    if d_num > max_cv_degree_num:
                        max_cv_degree_num = d_num
                        max_cv_degree = d

            cv_degree_label = AdvancedFilter.degree_labels_vi.get(max_cv_degree, max_cv_degree)

            if max_cv_degree_num >= min_degree_num:
                details.append({
                    "filter": "Bằng cấp tối thiểu",
                    "passed": True,
                    "reason": f"Bằng cấp: {cv_degree_label} (yêu cầu ≥ {min_degree_label})",
                })
            else:
                all_passed = False
                details.append({
                    "filter": "Bằng cấp tối thiểu",
                    "passed": False,
                    "reason": f"Bằng cấp: {cv_degree_label} — chưa đạt (yêu cầu ≥ {min_degree_label})",
                })

        # --- 6. LỌC MỨC GẮN BÓ ---
        min_stability = filter_config.get("min_stability_pct")
        if min_stability is not None and min_stability > 0:
            stab_score = scoring_result.get("breakdown", {}).get("stability", {}).get("score", 1.0)
            stab_pct = round(stab_score * 100, 1)

            stab_details = scoring_result.get("breakdown", {}).get("stability", {}).get("details", {})
            avg_tenure = stab_details.get("average_tenure_years", 0)

            if stab_pct >= min_stability:
                details.append({
                    "filter": "Mức gắn bó",
                    "passed": True,
                    "reason": f"Mức gắn bó: {stab_pct}% (TB {avg_tenure} năm/công ty, yêu cầu ≥ {min_stability}%)",
                })
            else:
                all_passed = False
                details.append({
                    "filter": "Mức gắn bó",
                    "passed": False,
                    "reason": f"Mức gắn bó: {stab_pct}% (TB {avg_tenure} năm/công ty) — chưa đạt (yêu cầu ≥ {min_stability}%)",
                })

        return {
            "passed": all_passed,
            "details": details,
        }


# if __name__ == "__main__":
#     import json
#     import os

#     # Đọc dữ liệu từ file JSON đã được trích xuất ở bước trước
#     try:
#         with open("ket_qua_trich_xuat.json", "r", encoding="utf-8") as f:
#             data = json.load(f)
#             cv_data = data["cv_data"]
#             jd_data = data["jd_data"]
#     except FileNotFoundError:
#         print("Không tìm thấy file 'ket_qua_trich_xuat.json'. Hãy chạy file trich_xuat_cv.py trước để tạo data!")
#         exit(1)

#     print("=" * 60)
#     print("  TEST CHẤM ĐIỂM CV")
#     print("=" * 60)

#     # Khởi tạo bộ chấm điểm
#     aggregator = CVScoresAggregator()
    
#     # Thực hiện chấm điểm
#     result = aggregator.score_cv(cv_data, jd_data)

#     # --- IN KẾT QUẢ ---
#     print(f"\nĐIỂM TỔNG HỢP: {result['final_score_pct']}%")
#     print(f"KHUYẾN NGHỊ : {result['recommendation']}")
    
#     print("\n--- CHI TIẾT TỪNG TIÊU CHÍ ---")
    
#     # 1. Kỹ năng (Skills) - 40%
#     skills = result['breakdown']['skills']
#     print(f"1. Kỹ năng chuyên môn (Trọng số 40%): {int(skills['score']*100)}%")
#     print(f"Lý do: {skills['details']['reasoning']}")
    
#     # 2. Kinh nghiệm (Experience) - 30%
#     exp = result['breakdown']['experience']
#     print(f"\n2. Kinh nghiệm làm việc (Trọng số 30%): {int(exp['score']*100)}%")
#     print(f"Lý do: {exp['details']['reasoning']}")
    
#     # 3. Học vấn (Education) - 10%
#     edu = result['breakdown']['education']
#     print(f"\n3. Bằng cấp/Học vấn (Trọng số 10%): {int(edu['score']*100)}%")
#     print(f"Lý do: {edu['details']['reasoning']}")
    
#     # 4. Ngoại ngữ (Language) - 10%
#     lang = result['breakdown']['language']
#     print(f"\n4. Trình độ ngoại ngữ (Trọng số 10%): {int(lang['score']*100)}%")
#     print(f"   Lý do: {lang['details']['reasoning']}")
    
#     # 5. Mức độ gắn bó (Stability) - 10%
#     stab = result['breakdown']['stability']
#     print(f"\n5. Mức độ gắn bó (Trọng số 10%): {int(stab['score']*100)}%")
#     print(f"Lý do: {stab['details']['reasoning']}")

#     # Lưu kết quả đầy đủ ra file
#     with open("ket_qua_cham_diem.json", "w", encoding="utf-8") as f:
#         json.dump(result, f, ensure_ascii=False, indent=2)
#     print("\nĐã lưu toàn bộ thông tin chi tiết vào: ket_qua_cham_diem.json")