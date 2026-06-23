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

import json
import os
import fitz
import docx
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip('"').strip("'")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
_groq_client = None

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip().strip('"').strip("'")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
_deepseek_client = None


def is_groq_configured() -> bool:
    return bool(GROQ_API_KEY) and GROQ_API_KEY not in ("your_groq_api_key_here",)


def _get_groq_client() -> Groq:
    global _groq_client
    if not is_groq_configured():
        raise RuntimeError("GROQ_API_KEY chưa được cấu hình trong file .env")
    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def _get_deepseek_client():
    global _deepseek_client
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY chưa được cấu hình trong file .env")
    if _deepseek_client is None:
        from openai import OpenAI
        _deepseek_client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com"
        )
    return _deepseek_client


def call_llm(
    messages: list,
    response_format=None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
):
    import time
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()

    if provider == "deepseek":
        client = _get_deepseek_client()
        model_name = DEEPSEEK_MODEL
    else:
        client = _get_groq_client()
        model_name = GROQ_MODEL

    msgs = [dict(m) for m in messages]
    kwargs = dict(
        model=model_name,
        messages=msgs,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if response_format is not None:
        kwargs["response_format"] = {"type": "json_object"}
        schema_json = json.dumps(response_format.model_json_schema(), indent=2)
        msgs[0]["content"] += (
            f"\n\nRespond ONLY with valid JSON matching this schema:\n{schema_json}"
        )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content.strip()
            if response_format is not None:
                return response_format.model_validate_json(text)
            return text
        except Exception as e:
            error_str = str(e).lower()
            if "rate_limit" in error_str or "429" in error_str:
                if attempt < max_retries - 1:
                    wait_time = 15 * (attempt + 1)  # 15s, 30s, 45s
                    print(f"[{provider.upper()}] Rate limit hit, đợi {wait_time}s rồi thử lại (lần {attempt + 2}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(
                        f"API của {provider.upper()} đã chạm giới hạn rate limit. "
                        f"Vui lòng đổi sang provider khác trong file .env hoặc đợi thêm thời gian. "
                        f"Chi tiết: {e}"
                    )
            else:
                raise

class CVExtractionError(Exception):
    """Lỗi trong quá trình trích xuất CV."""
    pass

class UnsupportedFormatError(CVExtractionError):
    """Định dạng file không được hỗ trợ."""
    pass

# TRÍCH XUẤT VĂN BẢN THÔ TỪ CV

def extract_text_from_cv(file_path: str) -> str:
    """
    Trích xuất văn bản thô từ file PDF hoặc DOCX.

    Inputs:
        file_path: Đường dẫn tới file CV.

    Outputs:
        Chuỗi văn bản được trích xuất.

    Raises:
        FileNotFoundError: Khi file không tồn tại.
        UnsupportedFormatError: Khi định dạng file không phải PDF/DOCX.
        CVExtractionError: Khi file rỗng hoặc không đọc được.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

    filename = file_path.lower()
    extracted_text = ""

    try:
        if filename.endswith(".pdf"):
            pdf_document = fitz.open(file_path)
            for page in pdf_document:
                extracted_text += page.get_text() + "\n"
            pdf_document.close()
        elif filename.endswith(".docx"):
            doc = docx.Document(file_path)
            extracted_text = "\n".join(p.text for p in doc.paragraphs)
        else:
            raise UnsupportedFormatError(
                "Định dạng file không được hỗ trợ. Vui lòng upload file PDF hoặc DOCX."
            )
    except UnsupportedFormatError:
        raise
    except Exception:
        raise CVExtractionError(
            "CV này là dạng ảnh quét (Scanned PDF) hoặc không chứa nội dung văn bản. Vui lòng sử dụng file PDF hoặc DOCX"
        )

    if not extracted_text.strip():
        raise CVExtractionError(
            "CV này là dạng ảnh quét (Scanned PDF) hoặc không chứa nội dung văn bản. Vui lòng sử dụng file PDF hoặc DOCX"
        )

    return extracted_text


# TRÍCH XUẤT THÔNG TIN CHI TIẾT TỪ CV

# Trích xuất kinh nghiệm làm việc: tên công ty, chức danh, số năm làm việc, mô tả công việc
class Experience(BaseModel):
    company: Optional[str] = Field(None, description="Tên công ty hoặc tổ chức, trả về null nếu không có")
    role: Optional[str] = Field(None, description="Chức danh/vị trí, trả về null nếu không rõ")
    start_date: Optional[str] = Field(None, description="Ngày bắt đầu, định dạng YYYY-MM (e.g., '2023-01'). Trả về null nếu không có")
    end_date: Optional[str] = Field(None, description="Ngày kết thúc, định dạng YYYY-MM (e.g., '2024-05'). Nếu là 'Hiện tại'/'Present'/'Nay', dùng '2026-06'. Trả về null nếu không có")
    years: float = Field(0.0, description="Số năm làm việc tại công ty này (ước tính từ ngày bắt đầu/kết thúc nếu có, làm tròn 1 chữ số thập phân)")
    description: Optional[str] = Field(None, description="Mô tả công việc, trách nhiệm, thành tựu, trả về null nếu không có")

# Trích xuất học vấn: tên trường, cấp bậc bằng cấp, chuyên ngành, GPA nếu có
class Education(BaseModel):
    school: Optional[str] = Field(None, description="Tên trường, trả về null nếu không rõ")
    degree: Optional[str] = Field(None, description="Cấp bậc bằng cấp. Phải là một trong: none, associate (cao đẳng, cao đẳng nghề, vocational college, college), bachelor (cử nhân, kỹ sư, đại học, engineer), master (thạc sĩ), phd (tiến sĩ)")
    major: Optional[str] = Field(None, description="Chuyên ngành học, trả về null nếu không rõ")
    gpa: Optional[str] = Field(
        None,
        description="Điểm GPA hoặc CPA hoặc xếp loại tốt nghiệp, giữ nguyên định dạng của ứng viên (ví dụ: GPA 3.5/4, CPA 3.2, 8.5/10), trả về null nếu không có trong CV"
    )

# Trích xuất dự án: tên dự án, mô tả, công nghệ sử dụng
class Project(BaseModel):
    name: Optional[str] = Field(None, description="Tên dự án")
    description: Optional[str] = Field(None, description="Mô tả dự án")
    tech_stack: List[str] = Field(default_factory=list, description="Công nghệ sử dụng")

# Trích xuất chứng chỉ: tên chứng chỉ
class Certificate(BaseModel):
    name: Optional[str] = Field(None, description="Tên chứng chỉ")

# Trích xuất ngoại ngữ: tên ngôn ngữ, trình độ (none, basic, conversational, fluent, native)
class Language(BaseModel):
    name: Optional[str] = Field(default="Unknown", description="Tên ngôn ngữ, ví dụ: English, Japanese")
    level: Optional[str] = Field(default="basic", description="Trình độ: none, basic, conversational, fluent, native. Mặc định 'basic' nếu không rõ")
    certificate: Optional[str] = Field(
        None,
        description="Chứng chỉ hoặc điểm số cụ thể nếu có đề cập trong CV (ví dụ: TOEIC 650, IELTS 7.0, JLPT N3, HSK 5, hoặc 'Không có')"
    )

# Tổng hợp thông tin ứng viên sau khi trích xuất
class CandidateResume(BaseModel):
    name: Optional[str] = Field(default="Ứng viên", description="Họ tên ứng viên")
    email: Optional[str] = Field(None, description="Email liên hệ")
    skills: List[str] = Field(
        default_factory=list,
        description="Danh sách tất cả kỹ năng được đề cập trong CV"
    )
    experiences: List[Experience] = Field(
        default_factory=list,
        description="Lịch sử làm việc"
    )
    educations: List[Education] = Field(
        default_factory=list,
        description="Lịch sử học vấn"
    )
    projects: List[Project] = Field(
        default_factory=list,
        description="Các dự án cá nhân hoặc công việc"
    )
    certificates: List[Certificate] = Field(
        default_factory=list,
        description="Chứng chỉ"
    )
    languages: List[Language] = Field(
        default_factory=list,
        description="Ngoại ngữ"
    )

# TRÍCH XUẤT THÔNG TIN TỪ JD
class SkillsRequirement(BaseModel):
    core: List[str] = Field(default_factory=list, description="Các ngôn ngữ lập trình chính, các framework chính bắt buộc (e.g., VueJS 3, React Native, NestJS, Spring Boot)")
    supporting: List[str] = Field(default_factory=list, description="Các thư viện phụ trợ, cơ sở dữ liệu, kiến thức nền tảng (e.g., Pinia, WebSocket, Tailwind CSS, JWT, Redux)")
    tools: List[str] = Field(default_factory=list, description="Các công cụ, hệ thống quản lý mã nguồn, quy trình làm việc (e.g., Git, SonarQube, Cursor AI, Docker)")

class JobDescription(BaseModel):
    job_title: Optional[str] = Field(default="Vị trí", description="Tên vị trí tuyển dụng")
    job_description: Optional[str] = Field(default="", description="Mô tả công việc tổng quan")
    min_years_experience: int = Field(
        0,
        description="Số năm kinh nghiệm tối thiểu yêu cầu (lấy giá trị thấp nhất, 0 nếu không nêu rõ)"
    )
    required_degree: str = Field(
        "none",
        description="Bằng cấp tối thiểu yêu cầu: none, associate, bachelor, master, phd"
    )
    must_have_skills: Optional[List[str]] = Field(
        default_factory=list,
        description="Kỹ năng bắt buộc (required, essential, mandatory) - Giữ để tương thích ngược"
    )
    nice_to_have_skills: Optional[List[str]] = Field(
        default_factory=list,
        description="Kỹ năng ưu tiên (preferred, bonus, nice-to-have, a plus) - Giữ để tương thích ngược"
    )
    skills_requirement: Optional[SkillsRequirement] = Field(
        default_factory=SkillsRequirement,
        description="Phân tầng kỹ năng chi tiết: core, supporting, tools"
    )
    required_languages: Dict[str, str] = Field(
        default_factory=dict,
        description="Ngôn ngữ yêu cầu, ví dụ: {'english': 'fluent', 'japanese': 'basic'}. "
                    "Để {} nếu không yêu cầu."
    )


# SO SÁNH CV VỚI JD ĐỂ ĐÁNH GIÁ MỨC ĐỘ LIÊN QUAN CHO TỪNG YẾU TỐ

# Đánh giá mức độ liên quan cho từng công việc của ứng viên với công việc trong JD
class ExperienceRelevance(BaseModel):
    title: Optional[str] = Field(default="N/A", description="Chức danh / vị trí công việc")
    company: Optional[str] = Field(default=None, description="Tên công ty hoặc tổ chức")
    start_date: Optional[str] = Field(default=None, description="Ngày bắt đầu, định dạng YYYY-MM")
    end_date: Optional[str] = Field(default=None, description="Ngày kết thúc, định dạng YYYY-MM. Nếu là Hiện tại, dùng '2026-06'")
    years: float = Field(default=0.0, description="Số năm làm việc")
    relevance_to_jd: float = Field(default=0.0, description="Mức độ liên quan đến JD, từ 0.0 đến 1.0. 1.0 = hoàn toàn phù hợp, 0.0 = không liên quan")

# Đánh giá mức độ liên quan của học vấn với JD dựa trên chuyên ngành và cấp bậc bằng cấp
class EducationRelevance(BaseModel):
    degree: Optional[str] = Field(default="none", description="Cấp bậc bằng: none, associate, bachelor, master, phd")
    major_relevant: float = Field(default=0.0, description="Mức độ liên quan của chuyên ngành với JD, từ 0.0 đến 1.0")

class SkillMatchEvaluation(BaseModel):
    skill_name: str = Field(..., description="Tên kỹ năng từ JD")
    category: str = Field(..., description="Thuộc nhóm kỹ năng nào: core, supporting, tools")
    status: str = Field(..., description="Chỉ nhận một trong 3 giá trị: matched, equivalent, missing")
    equivalent_skill: Optional[str] = Field(None, description="Tên kỹ năng tương đương phát hiện trong CV (nếu có)")
    evidence: Optional[str] = Field(None, description="Dẫn chứng từ CV (ghi rõ kinh nghiệm hoặc dự án thể hiện kỹ năng này)")

class HRQuickEvaluations(BaseModel):
    skills: str = Field(..., description="Đánh giá nhanh kỹ năng, 1 câu ngắn gọn tiếng Việt")
    experience: str = Field(..., description="Đánh giá nhanh kinh nghiệm, 1 câu ngắn gọn tiếng Việt")
    education: str = Field(..., description="Đánh giá nhanh học vấn, 1 câu ngắn gọn tiếng Việt")
    language: str = Field(..., description="Đánh giá nhanh ngoại ngữ, 1 câu ngắn gọn tiếng Việt")
    stability: str = Field(..., description="Đánh giá nhanh mức gắn bó, 1 câu ngắn gọn tiếng Việt")

class InterviewQuestion(BaseModel):
    title: str = Field(..., description="Tiêu đề câu hỏi, ví dụ: 'Câu hỏi Kiểm tra Năng lực Chuyển đổi'")
    question: str = Field(..., description="Nội dung câu hỏi gợi ý chi tiết dạng trích dẫn (quote)")

# Kết quả phân tích mức độ liên quan
class CVMatchAnalysis(BaseModel):
    experience_history: List[ExperienceRelevance] = Field(description="Đánh giá mức độ liên quan (relevance) cho từng kinh nghiệm làm việc")
    education_history: List[EducationRelevance] = Field(description="Đánh giá mức độ liên quan (relevance) cho từng bằng cấp/học vấn")
    skills_match: List[SkillMatchEvaluation] = Field(default_factory=list, description="Đánh giá so khớp cho từng kỹ năng yêu cầu trong JD")
    recruiter_note: Optional[str] = Field(None, description="Nhận xét và khuyến nghị tuyển dụng chi tiết bằng tiếng Việt. Nhận xét về sự lệch tech stack (nếu có) và tiềm năng chuyển đổi công nghệ của ứng viên dựa trên tư duy, kinh nghiệm và công cụ AI sử dụng.")
    hr_evaluations: Optional[HRQuickEvaluations] = None
    strengths: List[str] = Field(default_factory=list, description="Danh sách các điểm mạnh thực chiến sâu sắc")
    risks: List[str] = Field(default_factory=list, description="Danh sách rủi ro tuyển dụng cần lưu ý")
    interview_questions: List[InterviewQuestion] = Field(default_factory=list, description="Danh sách các câu hỏi gợi ý phỏng vấn chuyên nghiệp")
    # Giữ các trường cũ để tránh lỗi tương thích ngược khi load kết quả phân tích cũ từ DB
    matched_must_have_skills: Optional[List[str]] = Field(default_factory=list, description="Kỹ năng bắt buộc (từ JD) mà ứng viên đã có")
    matched_nice_to_have_skills: Optional[List[str]] = Field(default_factory=list, description="Kỹ năng ưu tiên (từ JD) mà ứng viên đã có")


# SYSTEM PROMPTS

RESUME_SYSTEM_PROMPT = """
You are an expert Hiring Assistant. Your task is to carefully analyze the provided Candidate Resume text and extract the candidate's information to strictly populate the provided data schema.

EXTRACTION GUIDELINES:
1. Strict Accuracy: Extract ONLY the information explicitly stated in the resume. Do not infer, hallucinate, or guess any details.
2. Handling Missing Data: If a specific data point (e.g., GPA, certificates, or languages) is not present in the text, leave the field empty by returning `null` or an empty list `[]` depending on the field type.
3. Data Formatting:
   - For `gpa`, extract the GPA, CPA, or graduation classification exactly as written in the CV (e.g. "GPA 3.5/4", "CPA 3.2", "8.5/10", or "Loại Giỏi"). Return null if not stated.
   - For `experiences`, extract `start_date` and `end_date` in YYYY-MM format (e.g., '2023-01'). If the date is ongoing (e.g., "Present", "Nay", "Hiện tại"), use '2026-06'. Calculate `years` based on start/end dates (rounded to 1 decimal). Note: The current date is June 2026. Use June 2026 as the "Present" or "Nay" date for calculating durations of ongoing roles.
   - For `experiences` and `projects`, synthesize the responsibilities and achievements into a clear, concise `description` string.
   - For `degree`, map to one of: none, associate (for cao đẳng, vocational college, or college), bachelor (for cử nhân, kỹ sư, đại học, or engineer), master (for thạc sĩ), phd (for tiến sĩ).
4. Language Levels: Map language proficiency to one of: none, basic, conversational, fluent, native.
   Mapping references:
   - IELTS: 4.0-5.0 → basic, 5.5-6.0 → conversational, 6.5-7.5 → fluent, 8.0+ → native
   - TOEIC: 225-549 → basic, 550-784 → conversational, 785-944 → fluent, 945+ → native
   - JLPT: N5 → basic, N4 → basic, N3 → conversational, N2 → fluent, N1 → native
   - CEFR: A1-A2 → basic, B1 → conversational, B2-C1 → fluent, C2 → native
   - If no specific level/score is mentioned, default to "basic".
   - Also, extract the specific certificate, score, or level mentioned (e.g. TOEIC 650, IELTS 7.0, JLPT N3, HSK 5) into the `certificate` field. Leave as null if no certificate/score is mentioned.
5. Two-column layout: The resume text may come from a PDF with a multi-column layout, causing sections to be interleaved. Use context clues (section headers, dates, company names) to correctly separate and associate information.
"""

JD_SYSTEM_PROMPT = """
You are an expert HR Data Analyst. Your task is to carefully analyze the provided Job Description (JD) text and extract the core job requirements to strictly populate the provided data schema.

EXTRACTION GUIDELINES:
1. Strict Accuracy: Extract ONLY the information explicitly stated in the job description. Do not infer or hallucinate requirements.
2. Experience Parsing: For `min_years_experience`, extract ONLY the lowest integer value. For example, if the JD states "3-5 years" or "At least 3 years", output `3`. If no specific years of experience are mentioned, output `0`.
3. Skill Categorization (skills_requirement):
   - Categorize all required/mandatory/preferred skills into three categories:
     a. `core`: Main programming languages, primary frameworks required for the role (e.g., VueJS 3, React Native, Java for Java Developer, Python for AI Developer).
     b. `supporting`: Secondary frameworks, state management libraries, databases, APIs, basic standards, and relevant concepts (e.g., Pinia, WebSockets, Redux, Zustand, MySQL, RESTful APIs, JWT, WebSocket).
     c. `tools`: Version control, testing tools, build tools, CI/CD tools, AI tools, and minor utilities (e.g., Git, GitHub, SonarQube, Vite, Webpack, Cursor AI).
   - Also populate the old flat fields `must_have_skills` (which should equal `core` + `supporting`) and `nice_to_have_skills` (which should equal `tools`) to maintain backward compatibility.
4. Atomic Skills Extraction: Each extracted skill in the lists (`core`, `supporting`, `tools`, `must_have_skills`, `nice_to_have_skills`) MUST be a single, independent, atomic technology or keyword. Do NOT group multiple alternative or related skills into a single list element (e.g., DO NOT extract "Zustand, Redux Toolkit" or "Pinia/Zustand" as a single string. Instead, split them into separate array elements: "Zustand", "Redux Toolkit", "Pinia"). Strip any parenthetical details or explanations (e.g., extract "React Hooks" instead of "React Hooks (useState, useEffect)").
5. Degree Parsing: For `required_degree`, map to one of: none, associate, bachelor, master, phd. If not specified, use "none".
6. Language Requirements: For `required_languages`, output as a dictionary, e.g., {"english": "fluent"}. Map levels to: none, basic, conversational, fluent, native.
7. Handling Missing Data: If a field is completely missing from the text, return `null` for strings and empty arrays `[]` for lists.
"""

MATCH_ANALYSIS_SYSTEM_PROMPT = """
You are an expert HR Analyst. You are given:
1. A structured Candidate Resume (JSON)
2. A structured Job Description (JSON)

Your task is to COMPARE them and assess the relevance/match for each data point.

ANALYSIS GUIDELINES:
1. `experience_history`: Assess the relevance of each work experience in the CV to the JD. Do NOT guess a random percentage. Look at the core skills used in that job:
   - For each experience item in the candidate resume, create a corresponding ExperienceRelevance object.
   - Copy `title`, `company`, `start_date`, `end_date`, and `years` EXACTLY from the resume experience item.
   - relevance_to_jd = 1.0: The role used the EXACT primary Core skills required by the JD (e.g., VueJS 3, React Native).
   - relevance_to_jd = 0.5: The role used closely RELATED or EQUIVALENT stack at a high level (e.g., candidate used ReactJS for a VueJS position, or used NestJS for a Spring Boot position) AND is highly relevant in role.
   - relevance_to_jd = 0.1 - 0.3: The role used a completely different tech stack but in the same domain (e.g. candidate only did ReactJS for a VueJS/React Native JD, but has zero Vue/RN. This is only partially relevant and must be heavily penalized. Do not give 0.5 or higher if there is a complete core tech mismatch).
   - relevance_to_jd = 0.0: The role did not use any Core or equivalent skills (e.g., different tech stack entirely, like PHP/Java for a Python AI role, or non-technical roles).
   - Use decimal points in between if there are multiple projects with mixed relevance.

2. `education_history`: For each degree, assess how relevant the major/field of study is to the JD. Set `major_relevant` from 0.0 to 1.0:
   - 1.0: Exact match (e.g., CS/IT degree for a software engineer role).
   - 0.5-0.9: Related field (e.g., Electronics, Telecommunication, Math-CS).
   - 0.1-0.4: Loosely related.
   - 0.0: Completely unrelated.

3. `skills_match`: For every required skill listed in the JD (combine all skills from `core`, `supporting`, and `tools`), perform a semantic equivalent check against the CV:
   - If the candidate explicitly has the exact skill (written in skills, experiences, or projects): set status to "matched" and provide evidence. Do not mark as "matched" if it's not explicitly in their CV!
   - If the candidate does NOT have the exact skill, but has a closely equivalent/transferable skill in the same category (e.g., candidate has Redux/Zustand but JD requests Pinia, or candidate has ReactJS but JD requests VueJS, or candidate has SignalR but JD requests WebSocket): set status to "equivalent", write the equivalent skill in `equivalent_skill` (e.g. 'SignalR' for WebSocket), and explain the evidence in `evidence`.
   - If the candidate has no match and no equivalent technology: set status to "missing", leave `equivalent_skill` as null.
   - Note on synonyms vs equivalents: If the CV lists a direct synonym or specific implementation of a general tech (e.g., SignalR is an implementation of WebSocket), it MUST be set to status "equivalent" rather than "matched", so the report clearly shows this distinction.
   - Also, populate the legacy fields `matched_must_have_skills` (list of matched/equivalent must-have skills) and `matched_nice_to_have_skills` (list of matched/equivalent nice-to-have skills) to ensure backward compatibility.

4. `recruiter_note`: Write a detailed, professional recruiting note in Vietnamese.
   - Highlight the candidate's strengths, weaknesses, and overall stack alignment.
   - Analyze the technology gap: If they specialize in a different stack (e.g. React vs Vue), assess if their strong CS foundation, AI-assisted coding skills (like Cursor, Claude), and related experience make them suitable for retraining (technology switch) within 1-2 months.
   - Give a clear recommendation (e.g., "KHUYẾN NGHỊ PHỎNG VẤN (chấp nhận đào tạo lại)", "LOẠI/KHÔNG PHÙ HỢP", "ƯU TIÊN PHỎNG VẤN NGAY").

5. `hr_evaluations`: Provide 1 short, concise Vietnamese sentence (under 15 words) for each evaluation dimension based on the resume vs JD requirements:
   - `skills`: Fast summary of matches and gaps (e.g., "Có kỹ năng React nhưng thiếu VueJS, có khả năng tự học tốt").
   - `experience`: Fast summary of working duration and relevance (e.g., "Có 3 năm kinh nghiệm lập trình Frontend/Mobile").
   - `education`: Summary of school and degree (e.g., "Tốt nghiệp cử nhân CNTT trường Đại học Bách Khoa").
   - `language`: Summary of language certificates or levels (e.g., "Tiếng Anh giao tiếp tốt (IELTS 6.5)").
   - `stability`: Summary of tenure / job hopping risk (e.g., "Mức độ gắn bó trung bình, mỗi công ty làm việc khoảng 1.5 - 2 năm").

6. `strengths`: Provide a list of 2-3 deep technical/practical strengths of the candidate. Keep each point under 25 words in Vietnamese.

7. `risks`: Provide a list of 1-2 potential risks or concerns when hiring/onboarding the candidate (e.g., time to switch technologies, stability risk, side project distraction, potential high salary expectation for short tenure, etc.). Keep each point under 25 words in Vietnamese.

8. `interview_questions`: Provide a list of 2-3 highly customized, sharp interview questions. Each question must target either:
   - A critical technology gap (e.g. asking how they will switch from React to Vue).
   - A potential concern or risk identified (e.g., why they stayed at the last job for only 6 months, or how they handle multi-threading performance).
   Each question item has:
   - `title`: A concise, descriptive title (e.g., "Câu hỏi Kiểm tra Năng lực Chuyển đổi Công nghệ (React -> Vue)").
   - `question`: The actual question text wrapped in a professional, constructive manner.
"""


# HÀM TRÍCH XUẤT THÔNG TIN TỪ CV SỬ DỤNG API

_jd_cache = {}

def extract_information(raw_text: str, schema_class, prompt_type: str):
    """
    Trích xuất thông tin có cấu trúc từ văn bản thô bằng Groq.

    Inputs:
        raw_text: Văn bản thô cần trích xuất.
        schema_class: Pydantic model class dùng làm response_format.
        prompt_type: "resume" hoặc "jd" — quyết định system prompt.

    Outputs:
        Instance của schema_class chứa thông tin đã trích xuất.
    """
    if prompt_type == "jd":
        import hashlib
        text_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        if text_hash in _jd_cache:
            return _jd_cache[text_hash]

    system_prompts = {
        "resume": RESUME_SYSTEM_PROMPT,
        "jd": JD_SYSTEM_PROMPT,
    }

    result = call_llm(
        messages=[
            {"role": "system", "content": system_prompts[prompt_type]},
            {"role": "user", "content": f"Input text:\n{raw_text}"},
        ],
        response_format=schema_class,
        temperature=0.1,
    )

    if prompt_type == "jd":
        import hashlib
        text_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        _jd_cache[text_hash] = result

    return result


def analyze_cv_jd_match(resume: CandidateResume, jd: JobDescription) -> CVMatchAnalysis:
    """
    So sánh CV với JD bằng AI để tính relevance scores.

    Inputs:
        resume: Thông tin CV đã trích xuất.
        jd: Thông tin JD đã trích xuất.

    Outputs:
        CVMatchAnalysis chứa relevance scores và matched skills.
    """
    user_content = (
        f"Candidate Resume\n{resume.model_dump_json(indent=2)}\n\n"
        f"Job Description\n{jd.model_dump_json(indent=2)}"
    )

    return call_llm(
        messages=[
            {"role": "system", "content": MATCH_ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format=CVMatchAnalysis,
        temperature=0.1,
    )


# HÀM CHUYỂN ĐỔI DỮ LIỆU ĐỂ CHUẨN BỊ INPUT CHO HÀM CHẤM ĐIỂM CV
def prepare_scoring_data(resume: CandidateResume, jd: JobDescription, match: CVMatchAnalysis,) -> tuple:
    """
    Chuyển đổi dữ liệu đã trích xuất sang format tương thích với CVScoresAggregator.

    Inputs:
        resume: Thông tin CV gốc.
        jd: Thông tin JD gốc.
        match: Kết quả so khớp CV vs JD từ AI.

    Outputs:
        tuple: (cv_data: dict, jd_data: dict) — sẵn sàng truyền vào score_cv().
    """
    # Xây dựng format cv_data cho cham_diem_cv.py
    cv_data = {
        # ExperienceMatcher và StabilityMatcher cần: [{"title": str, "company": str, "start_date": str, "end_date": str, "years": float, "relevance_to_jd": float}]
        "experience_history": [
            {
                "title": exp.title,
                "company": getattr(exp, "company", None),
                "start_date": getattr(exp, "start_date", None),
                "end_date": getattr(exp, "end_date", None),
                "years": exp.years,
                "relevance_to_jd": exp.relevance_to_jd,
            }
            for exp in match.experience_history
        ],

        # EducationMatcher cần: [{"degree": str, "major_relevant": float}]
        "education_history": [
            {
                "degree": edu.degree,
                "major_relevant": edu.major_relevant,
            }
            for edu in match.education_history
        ],

        # SkillMatcher cần:
        "skills_match": [
            eval_item.model_dump() if hasattr(eval_item, "model_dump") else eval_item
            for eval_item in getattr(match, "skills_match", [])
        ],
        # Trường cũ để tương thích ngược
        "matched_must_have_skills": match.matched_must_have_skills or [],
        "matched_nice_to_have_skills": match.matched_nice_to_have_skills or [],

        # LanguageMatcher cần: {"english": "fluent", "japanese": "basic"}
        "languages": {
            lang.name.lower(): lang.level.lower()
            for lang in resume.languages
        },
        "recruiter_note": getattr(match, "recruiter_note", None),
        "hr_evaluations": match.hr_evaluations.model_dump() if match.hr_evaluations and hasattr(match.hr_evaluations, "model_dump") else (match.hr_evaluations or None),
        "strengths": match.strengths or [],
        "risks": match.risks or [],
        "interview_questions": [
            q.model_dump() if hasattr(q, "model_dump") else q
            for q in (match.interview_questions or [])
        ],
    }

    # Xây dựng format jd_data cho cham_diem_cv.py
    jd_data = {
        "required_experience_years": jd.min_years_experience,
        "required_degree": jd.required_degree,
        "required_languages": jd.required_languages or {},
        # Cấu trúc mới
        "skills_requirement": jd.skills_requirement.model_dump() if jd.skills_requirement and hasattr(jd.skills_requirement, "model_dump") else (jd.skills_requirement or {}),
        # Trường cũ để tương thích ngược
        "must_have_skills": jd.must_have_skills or [],
        "nice_to_have_skills": jd.nice_to_have_skills or [],
    }

    return cv_data, jd_data


# PIPELINE

def process_cv_and_jd(cv_file_path: str, jd_text: str, jd_id: str = None) -> tuple:
    """
    Pipeline hoàn chỉnh: Đọc file CV và JD -> Trích xuất -> So khớp -> Chuẩn bị data chấm điểm.

    Inputs:
        cv_file_path: Đường dẫn tới file CV (PDF/DOCX).
        jd_text: Văn bản JD dạng raw text.
        jd_id: ID của JD trong MongoDB (nếu có) để tìm kiếm cache.

    Outputs:
        tuple: (cv_data, jd_data, resume_obj, jd_obj)
            - cv_data, jd_data: Dict sẵn sàng truyền vào CVScoresAggregator.score_cv()
            - resume_obj, jd_obj: Pydantic object gốc để tham khảo thêm nếu cần.
    """
    # B1: Trích xuất text thô từ file CV
    raw_resume_text = extract_text_from_cv(cv_file_path)

    # B2: AI trích xuất thông tin có cấu trúc 
    resume = extract_information(raw_resume_text, CandidateResume, "resume")
    
    # Kiểm tra xem JD đã được phân tích cấu trúc trong DB chưa
    jd = None
    if jd_id and jd_id != "manual":
        try:
            from database import get_jd_by_id, update_jd_parsed_data
            jd_doc = get_jd_by_id(jd_id)
            if jd_doc and jd_doc.get("parsed_data"):
                parsed_data = jd_doc["parsed_data"]
                if parsed_data.get("skills_requirement") and (parsed_data["skills_requirement"].get("core") or parsed_data["skills_requirement"].get("supporting") or parsed_data["skills_requirement"].get("tools")):
                    jd = JobDescription(**parsed_data)
                    print(f"[Cache Hit] Đã tải cấu trúc JD từ database cho JD: {jd_doc['name']}")
            
            if jd is None:
                # Lazy load: phân tích lần đầu rồi lưu lại
                jd = extract_information(jd_text, JobDescription, "jd")
                if jd_doc:
                    parsed_dict = jd.model_dump() if hasattr(jd, "model_dump") else jd
                    update_jd_parsed_data(jd_id, parsed_dict)
                    print(f"[Lazy Load] Đã phân tích và lưu cấu trúc JD vào database cho JD: {jd_doc['name']}")
        except Exception as cache_err:
            print(f"⚠️ Lỗi cache JD: {cache_err}. Sử dụng phân tích trực tiếp...")
            jd = None

    if jd is None:
        jd = extract_information(jd_text, JobDescription, "jd")

    # B3: AI so khớp CV với JD -> tính relevance scores
    match_analysis = analyze_cv_jd_match(resume, jd)

    # B4: Chuyển đổi sang format cho CVScoresAggregator
    cv_data, jd_data = prepare_scoring_data(resume, jd, match_analysis)

    return cv_data, jd_data, resume, jd



# if __name__ == "__main__":
#     from extract_cv import CVScoresAggregator
    
#     JD_TEXT = """ [HÀ NỘI] TUYỂN DỤNG Senior Mobile App Developer (iOS & Android). 
#     Yêu cầu: 
#     * Có ít nhất 5 năm kinh nghiệm phát triển các ứng dụng iOS (Swift /Objective C) và Android (Java, Kotlin)
#     * Nắm vững kiến thức về Swift/Objective C và Java/Kotlin
#     * Nắm vững kiến thức về Lập trình hướng đối tượng (OOP) và các nguyên tắc SOLID.
#     * Có kiến thức về cấu trúc dữ liệu, clean code, design patterns, refactoring, hiệu suất code, bộ nhớ, bộ nhớ đệm (caching), đa luồng (multi-threading), phát triển hướng kiểm thử (TDD) và phân tích hiệu suất ứng dụng (application profiling).
#     Công việc: 
#     * Làm việc với các Bộ phận Sản phẩm và các bên liên quan về tính năng, kỹ thuật để xây dựng, thiết kế, đề xuất các giải pháp mobile và kế hoạch bàn giao.
#     * Phát triển các ứng dụng Android/iOS hướng tới số lượng lớn các thiết bị Android/iOS đa dạng (500K-1M users)
#     * Thiết kế, phát triển và tối ưu hóa Kiến Trúc và Hiệu Suất của Ứng dụng Di động.
#     * Tích hợp với các dịch vụ back-end services
#     Lương: 28.000.000 - 35.000.000
#     Địa điểm làm việc: Trung tâm Nghiên cứu và phát triển sản phẩm Công ty CP Lumi Việt Nam - Tầng 6, tòa New Skyline Văn Quán, Đường 19/5, Hà Đông, Hà Nội
#     Thời gian làm việc: Từ Thứ 2 - Thứ 6, Thứ 7 làm việc và nghỉ xem kẽ (nghỉ 2 thứ 7/ tháng).
#     Giờ làm việc linh hoạt, áp dụng Ngày làm remote cho nhân viên chính thức."""

#     cv_data, jd_data, resume, jd = process_cv_and_jd(
#         cv_file_path="E:\ĐANC 20262\CV mẫu\son_do_hoang.pdf",
#         jd_text=JD_TEXT
#     )
    
#     aggregator = CVScoresAggregator()
#     result = aggregator.score_cv(cv_data, jd_data)
#     print(f"Điểm: {result['final_score_pct']}%")
#     print(f"Recommendation: {result['recommendation']}")
#     pass