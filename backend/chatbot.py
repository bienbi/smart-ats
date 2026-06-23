import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from extract_cv import call_llm as _call_llm



class InterviewQuestion(BaseModel):
    question: str = Field(description="Nội dung câu hỏi")
    category: str = Field(description="Loại câu hỏi: technical, behavioral, situational, skill_verification")
    difficulty: str = Field(description="Độ khó: easy, medium, hard")
    related_skill: str = Field(description="Kỹ năng liên quan đến câu hỏi này")
    cv_reference: str = Field(
        description="Tên công ty, dự án, vai trò hoặc đoạn kinh nghiệm cụ thể trong CV mà câu hỏi dựa vào. Bắt buộc với mọi câu không phải situational."
    )
    purpose: str = Field(description="Mục đích của câu hỏi (giúp HR hiểu tại sao hỏi)")
    evaluation_criteria: str = Field(description="Tiêu chí đánh giá câu trả lời tốt vs xấu")


class InterviewQuestionSet(BaseModel):
    questions: List[InterviewQuestion] = Field(description="Danh sách câu hỏi phỏng vấn")


class AnswerEvaluation(BaseModel):
    score: float = Field(description="Điểm đánh giá từ 0.0 đến 10.0")
    strengths: List[str] = Field(description="Những điểm tốt trong câu trả lời")
    weaknesses: List[str] = Field(description="Những điểm yếu hoặc thiếu sót")
    follow_up_question: Optional[str] = Field(
        None, 
        description="Câu hỏi follow-up nếu cần, null nếu không cần"
    )
    reasoning: str = Field(description="Giải thích chi tiết cho điểm số")


class InterviewSummary(BaseModel):
    overall_score: float = Field(description="Điểm tổng phỏng vấn (0-10)")
    technical_competency: str = Field(description="Đánh giá năng lực kỹ thuật: weak, developing, competent, strong, expert")
    communication_quality: str = Field(description="Chất lượng giao tiếp: poor, fair, good, excellent")
    key_strengths: List[str] = Field(description="Điểm mạnh nổi bật")
    areas_of_concern: List[str] = Field(description="Điểm cần lưu ý / rủi ro")
    hiring_recommendation: str = Field(description="Khuyến nghị: strong_hire, hire, maybe, no_hire")
    detailed_assessment: str = Field(description="Đánh giá chi tiết cho HR đọc")



# SYSTEM PROMPTS

QUESTION_GENERATION_PROMPT = """
You are a Senior Technical Interviewer at a top tech company. Based on the candidate's resume analysis and job requirements, generate a tailored set of interview questions.

CRITICAL LANGUAGE & PRONOUN RULES:
- ALL questions MUST be written entirely in Vietnamese (tiếng Việt).
- Always address the candidate as "bạn". Never use "anh/chị", "anh", or "chị" to address the candidate.
- Do NOT mix English words into Vietnamese sentences. 
- Technical terms (e.g., MVVM, RxSwift, API) can remain in English, but the sentence structure must be Vietnamese.

QUESTION GENERATION RULES:
1. PROJECT-BASED QUESTIONS (Priority): Reference the candidate's SPECIFIC projects, companies, and experiences listed in their CV. Ask them to explain what they actually did, challenges they faced, and how they solved them. Example: "Trong dự án LOPIA tại Fujitech, bạn đã xử lý tích hợp RESTful APIs như thế nào? Gặp khó khăn gì?"
2. SKILL VERIFICATION: For skills the candidate claims to have, ask questions that prove real hands-on experience (not just textbook knowledge).
3. MISSING/WEAK SKILLS: For skills identified as missing or weak in the CV scoring, ask questions to assess if the candidate has any hidden experience or potential.
4. SITUATIONAL QUESTIONS: Include hypothetical but realistic scenarios that a person in this role would face. These may or may not relate to projects in the CV. Example: "Nếu ứng dụng bị crash liên tục trên iOS 17 nhưng hoạt động bình thường trên iOS 16, bạn sẽ debug như thế nào?"
5. Mix question types:
   - `technical`: Direct knowledge/coding questions about specific technologies.
   - `behavioral`: Past experience questions (hỏi về kinh nghiệm thực tế đã trải qua).
   - `situational`: Hypothetical scenarios relevant to the job.
   - `skill_verification`: Questions to verify claimed skills via specific project details.
6. Adjust difficulty based on the candidate's experience level (fresher vs senior).
7. Each question must be clear, specific, and answerable in 2-5 minutes.
8. Generate EXACTLY 5 questions total, distributed across categories.
9. At least 3 questions MUST reference specific projects or companies from the candidate's CV.
"""

ANSWER_EVALUATION_PROMPT = """
You are a Senior Technical Interviewer evaluating a candidate's answer.

CRITICAL: All your feedback (strengths, weaknesses, reasoning, follow_up_question) MUST be written entirely in Vietnamese.

EVALUATION CRITERIA:
1. Technical accuracy (câu trả lời có chính xác về mặt kỹ thuật không?)
2. Depth of knowledge (hiểu biết bề mặt hay hiểu sâu?)
3. Practical experience (có đưa ra ví dụ thực tế từ dự án đã làm không?)
4. Communication clarity (câu trả lời có mạch lạc, rõ ràng không?)
5. Problem-solving approach (cách tiếp cận giải quyết vấn đề)

SCORING GUIDE:
- 9-10: Xuất sắc — kiến thức chuyên sâu, có insight thực tế
- 7-8: Tốt — hiểu biết vững chắc, có ví dụ thuyết phục
- 5-6: Trung bình — hiểu cơ bản nhưng thiếu chiều sâu
- 3-4: Yếu — hiểu biết hời hợt, nhiều lỗ hổng
- 1-2: Kém — câu trả lời sai hoặc không liên quan
- 0: Không trả lời

Be fair but rigorous. Give specific, actionable feedback in Vietnamese.
"""

INTERVIEW_SUMMARY_PROMPT = """
You are a Senior HR Consultant writing a final interview assessment report.

CRITICAL: The entire report (key_strengths, areas_of_concern, detailed_assessment) MUST be written in Vietnamese.

ASSESSMENT GUIDELINES:
1. Consider the overall pattern of answers, not just individual scores.
2. Weight technical questions more heavily for technical roles.
3. Factor in communication quality and enthusiasm.
4. Be honest and specific — avoid generic praise or criticism.
5. The hiring recommendation should consider both the CV score and interview performance.
6. In detailed_assessment, mention specific examples from the candidate's answers.
"""



class InterviewChatbot:
    """
    Chatbot phỏng vấn AI tích hợp với hệ thống chấm điểm CV.

    1. Nhận kết quả chấm điểm CV (scoring_result) + thông tin resume/jd
    2. Tạo bộ câu hỏi phỏng vấn phù hợp
    3. Hỏi từng câu -> ứng viên trả lời -> AI đánh giá real-time
    4. Tổng kết buổi phỏng vấn
    """

    def __init__(
        self,
        resume_data: Dict[str, Any],
        jd_data: Dict[str, Any],
        scoring_result: Dict[str, Any],
        candidate_name: str = "Ứng viên",
        job_title: str = "Vị trí tuyển dụng",
        resume_detail: Optional[Dict[str, Any]] = None,
        jd_detail: Optional[Dict[str, Any]] = None,
    ):
        self.resume_data = resume_data
        self.jd_data = jd_data
        self.scoring_result = scoring_result
        self.candidate_name = candidate_name
        self.job_title = job_title
        self.resume_detail = resume_detail or {}
        self.jd_detail = jd_detail or {}

        self.questions: List[InterviewQuestion] = []
        self.current_question_index: int = 0
        self.conversation_history: List[Dict[str, str]] = []
        self.evaluations: List[Dict[str, Any]] = []
        self.is_finished: bool = False

    # Tạo câu hỏi phỏng vấn dựa trên kết quả chấm điểm CV

    def generate_questions(self) -> List[InterviewQuestion]:
        """Tạo bộ câu hỏi phỏng vấn dựa trên CV scoring result."""
        context = self._build_context_for_question_generation()
        question_set = _call_llm(
            messages=[
                {"role": "system", "content": QUESTION_GENERATION_PROMPT},
                {"role": "user", "content": context},
            ],
            response_format=InterviewQuestionSet,
            max_tokens=8192,
            temperature=0.5,
        )
        self.questions = question_set.questions
        return self.questions

    def _build_context_for_question_generation(self) -> str:
        breakdown = self.scoring_result.get("breakdown", {})
        skills_details = breakdown.get("skills", {}).get("details", {})
        rd = self.resume_detail
        jd = self.jd_detail
        return f"""
        === CANDIDATE INFORMATION ===
        Name: {self.candidate_name}
        Applying for: {self.job_title}
        CV Score: {self.scoring_result.get('final_score_pct', 0)}%
        Recommendation: {self.scoring_result.get('recommendation', 'N/A')}

        === FULL CV — WORK EXPERIENCE (company, role, years, description) ===
        {json.dumps(rd.get('experiences', []), indent=2, ensure_ascii=False)}

        === FULL CV — PROJECTS (name, description, tech_stack) ===
        {json.dumps(rd.get('projects', []), indent=2, ensure_ascii=False)}

        === FULL CV — SKILLS ===
        {json.dumps(rd.get('skills', []), indent=2, ensure_ascii=False)}

        === FULL CV — EDUCATION ===
        {json.dumps(rd.get('educations', []), indent=2, ensure_ascii=False)}

        === FULL CV — CERTIFICATES & LANGUAGES ===
        Certificates: {json.dumps(rd.get('certificates', []), ensure_ascii=False)}
        Languages: {json.dumps(rd.get('languages', []), ensure_ascii=False)}

        === CV SCORING BREAKDOWN ===
        - Experience: {breakdown.get('experience', {}).get('score', 0) * 100:.0f}%
        -> {breakdown.get('experience', {}).get('details', {}).get('reasoning', '')}
        - Skills: {breakdown.get('skills', {}).get('score', 0) * 100:.0f}%
        -> {breakdown.get('skills', {}).get('details', {}).get('reasoning', '')}
        - Education: {breakdown.get('education', {}).get('score', 0) * 100:.0f}%
        -> {breakdown.get('education', {}).get('details', {}).get('reasoning', '')}

        === SKILLS GAP ANALYSIS ===
        - Missing CRITICAL skills: {skills_details.get('missing_critical_skills', [])}
        - Missing nice-to-have: {skills_details.get('missing_nice_skills', [])}
        - Must-have match: {skills_details.get('must_have_score', 0) * 100:.0f}%

        === JOB DESCRIPTION ===
        Title: {jd.get('job_title', self.job_title)}
        Description: {jd.get('job_description', 'N/A')}
        - Must-have skills: {self.jd_data.get('must_have_skills', [])}
        - Nice-to-have skills: {self.jd_data.get('nice_to_have_skills', [])}
        - Required experience: {self.jd_data.get('required_experience_years', 0)} years

        === EXPERIENCE RELEVANCE (from CV-JD matching) ===
        {json.dumps(self.resume_data.get('experience_history', []), indent=2, ensure_ascii=False)}

        INSTRUCTION: Generate EXACTLY 5 interview questions. Most questions MUST cite specific companies, projects, or tasks from the FULL CV sections above. Do NOT ask generic questions.
        """

    # Lấy câu hỏi tiếp theo để hỏi ứng viên, trả về None nếu đã hết câu hỏi hoặc phỏng vấn đã kết thúc

    def get_next_question(self) -> Optional[Dict[str, Any]]:
        if self.current_question_index >= len(self.questions):
            self.is_finished = True
            return None
        question = self.questions[self.current_question_index]
        return {
            "question_number": self.current_question_index + 1,
            "total_questions": len(self.questions),
            "question": question.question,
            "category": question.category,
            "difficulty": question.difficulty,
            "related_skill": question.related_skill,
            "cv_reference": question.cv_reference,
            "purpose": question.purpose,
        }

    # Nhận câu trả lời của ứng viên, đánh giá và lưu kết quả

    def submit_answer(self, answer: str) -> Dict[str, Any]:
        if self.current_question_index >= len(self.questions):
            return {"error": "Phỏng vấn đã kết thúc."}
        question = self.questions[self.current_question_index]
        self.conversation_history.append({"role": "interviewer", "content": question.question})
        self.conversation_history.append({"role": "candidate", "content": answer})
        evaluation = self._evaluate_answer(question, answer)
        eval_result = {
            "question_number": self.current_question_index + 1,
            "question": question.question,
            "category": question.category,
            "related_skill": question.related_skill,
            "candidate_answer": answer,
            "score": evaluation.score,
            "strengths": evaluation.strengths,
            "weaknesses": evaluation.weaknesses,
            "follow_up_question": evaluation.follow_up_question,
            "reasoning": evaluation.reasoning,
        }
        self.evaluations.append(eval_result)
        self.current_question_index += 1
        return eval_result

    def _evaluate_answer(self, question: InterviewQuestion, answer: str) -> AnswerEvaluation:
        user_content = f"""
        === INTERVIEW CONTEXT ===
        Position: {self.job_title}
        Candidate: {self.candidate_name}
        CV Score: {self.scoring_result.get('final_score_pct', 0)}%

        === QUESTION ===
        Category: {question.category} | Difficulty: {question.difficulty}
        Related Skill: {question.related_skill}
        Question: {question.question}
        Evaluation Criteria: {question.evaluation_criteria}

        === CANDIDATE'S ANSWER ===
        {answer}

        Please evaluate this answer.
        """
        return _call_llm(
            messages=[
                {"role": "system", "content": ANSWER_EVALUATION_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format=AnswerEvaluation,
        )

    # Tổng kết buổi phỏng vấn 

    def generate_summary(self) -> Dict[str, Any]:
        if not self.evaluations:
            return {"error": "Chưa có câu trả lời nào để tổng kết."}
        transcript = self._build_transcript()
        user_content = f"""
        === CANDIDATE INFO ===
        Name: {self.candidate_name}
        Position: {self.job_title}
        CV Score: {self.scoring_result.get('final_score_pct', 0)}%
        CV Recommendation: {self.scoring_result.get('recommendation', 'N/A')}

        === INTERVIEW TRANSCRIPT & EVALUATIONS ===
        {transcript}

        === SCORE SUMMARY ===
        Average Interview Score: {self._average_score():.1f}/10
        Total Questions: {len(self.evaluations)}

        Please provide a comprehensive interview summary and hiring recommendation.
        """
        summary = _call_llm(
            messages=[
                {"role": "system", "content": INTERVIEW_SUMMARY_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format=InterviewSummary,
        )
        return {
            "candidate_name": self.candidate_name,
            "job_title": self.job_title,
            "cv_score_pct": self.scoring_result.get("final_score_pct", 0),
            "interview_score": summary.overall_score,
            "technical_competency": summary.technical_competency,
            "communication_quality": summary.communication_quality,
            "key_strengths": summary.key_strengths,
            "areas_of_concern": summary.areas_of_concern,
            "hiring_recommendation": summary.hiring_recommendation,
            "detailed_assessment": summary.detailed_assessment,
            "question_evaluations": self.evaluations,
            "total_questions_asked": len(self.evaluations),
            "average_answer_score": round(self._average_score(), 2),
        }

    def _build_transcript(self) -> str:
        parts = []
        for i, ev in enumerate(self.evaluations, 1):
            parts.append(f"""
            Question {i} ({ev['category']} | {ev['related_skill']}) ---
            Q: {ev['question']}
            A: {ev['candidate_answer']}
            Score: {ev['score']}/10
            Strengths: {', '.join(ev['strengths'])}
            Weaknesses: {', '.join(ev['weaknesses'])}
            """)
        return "\n".join(parts)

    def _average_score(self) -> float:
        if not self.evaluations:
            return 0.0
        return sum(ev["score"] for ev in self.evaluations) / len(self.evaluations)

    def skip_question(self) -> Dict[str, Any]:
        return self.submit_answer("[Ứng viên bỏ qua / không trả lời câu hỏi này]")

    # Serialization methods để lưu trạng thái chatbot vào session hoặc file

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resume_data": self.resume_data,
            "jd_data": self.jd_data,
            "scoring_result": self.scoring_result,
            "candidate_name": self.candidate_name,
            "job_title": self.job_title,
            "resume_detail": self.resume_detail,
            "jd_detail": self.jd_detail,
            "questions": [q.model_dump() for q in self.questions],
            "current_question_index": self.current_question_index,
            "conversation_history": self.conversation_history,
            "evaluations": self.evaluations,
            "is_finished": self.is_finished,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterviewChatbot":
        """Khôi phục state từ dict."""
        bot = cls(
            resume_data=data["resume_data"],
            jd_data=data["jd_data"],
            scoring_result=data["scoring_result"],
            candidate_name=data["candidate_name"],
            job_title=data["job_title"],
            resume_detail=data.get("resume_detail"),
            jd_detail=data.get("jd_detail"),
        )
        bot.questions = [InterviewQuestion(**q) for q in data.get("questions", [])]
        bot.current_question_index = data.get("current_question_index", 0)
        bot.conversation_history = data.get("conversation_history", [])
        bot.evaluations = data.get("evaluations", [])
        bot.is_finished = data.get("is_finished", False)
        return bot
