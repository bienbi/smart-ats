import React, { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';

export default function InterviewChatbot() {
  const [jds, setJds] = useState([]);
  const [pastAnalyses, setPastAnalyses] = useState([]);
  const [selectedJdId, setSelectedJdId] = useState('');
  const [manualJdContent, setManualJdContent] = useState('');
  const [uploadedFile, setUploadedFile] = useState(null);
  
  // Setup source type: 'past' or 'new'
  const [sourceType, setSourceType] = useState('new');
  const [selectedAnalysisId, setSelectedAnalysisId] = useState('');

  // Interview state
  const [analysisId, setAnalysisId] = useState(null);
  const [interviewStarted, setInterviewStarted] = useState(false);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [answer, setAnswer] = useState('');
  const [evaluationFeedback, setEvaluationFeedback] = useState(null);
  const [chatHistory, setChatHistory] = useState([]); // Array of { role: 'bot'|'user', content: string, eval?: object, meta?: object }
  
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState('');
  const [error, setError] = useState('');
  const [summary, setSummary] = useState(null);
  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    fetchJds();
    fetchPastAnalyses();
  }, []);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatHistory]);

  const fetchJds = async () => {
    try {
      const data = await api.getJds();
      setJds(data);
      if (data.length > 0) setSelectedJdId(data[0].id);
      else setSelectedJdId('manual');
    } catch (err) {
      console.error(err);
    }
  };

  const fetchPastAnalyses = async () => {
    try {
      const data = await api.getAnalyses();
      setPastAnalyses(data);
      if (data.length > 0) setSelectedAnalysisId(data[0].id);
    } catch (err) {
      console.error(err);
    }
  };

  const handleStartInterview = async () => {
    setLoading(true);
    setError('');
    setSummary(null);
    setChatHistory([]);
    setEvaluationFeedback(null);

    let activeId = '';
    
    try {
      if (sourceType === 'past') {
        if (!selectedAnalysisId) {
          setError('Vui lòng chọn một kết quả phân tích CV từ danh sách');
          setLoading(false);
          return;
        }
        activeId = selectedAnalysisId;
      } else {
        // Upload & Analyze first
        if (!uploadedFile) {
          setError('Vui lòng tải lên CV của bạn');
          setLoading(false);
          return;
        }
        if (selectedJdId === 'manual' && !manualJdContent.trim()) {
          setError('Vui lòng nhập nội dung JD');
          setLoading(false);
          return;
        }

        setLoadingText('Đang phân tích CV của bạn');
        const formData = new FormData();
        formData.append('jd_id', selectedJdId);
        if (selectedJdId === 'manual') {
          formData.append('jd_content_manual', manualJdContent);
        }
        // Add default weights
        formData.append('w_skills', 40);
        formData.append('w_exp', 30);
        formData.append('w_edu', 10);
        formData.append('w_lang', 10);
        formData.append('w_stab', 10);
        formData.append('files', uploadedFile);

        const results = await api.analyzeCvs(formData);
        if (results && results.length > 0) {
          if (results[0].error_detail) {
            throw new Error(results[0].recommendation);
          }
          activeId = results[0].id;
        } else {
          throw new Error('Phân tích CV thất bại');
        }
      }

      setLoadingText('Đang khởi tạo chatbot phỏng vấn và tạo câu hỏi');
      const response = await api.startInterview(activeId);
      
      setAnalysisId(activeId);
      setTotalQuestions(response.total_questions);
      setCurrentQuestion(response.current_question);
      setInterviewStarted(true);
      
      // Add first question to chat
      setChatHistory([
        { 
          role: 'bot', 
          content: response.current_question.question,
          meta: response.current_question
        }
      ]);
    } catch (err) {
      setError('Không thể bắt đầu phỏng vấn: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitAnswer = async () => {
    if (!answer.trim()) return;

    setLoading(true);
    setLoadingText('AI đang đánh giá câu trả lời của bạn...');
    setError('');
    
    const submittedAnswer = answer;
    setAnswer('');
    
    // Add user answer to chat history
    setChatHistory(prev => [...prev, { role: 'user', content: submittedAnswer }]);

    try {
      const response = await api.submitInterviewAnswer(analysisId, submittedAnswer);
      
      // Update the user bubble with the evaluation feedback
      setChatHistory(prev => {
        const updated = [...prev];
        // find the last user bubble and attach evaluation feedback
        const lastUserIdx = updated.map(c => c.role).lastIndexOf('user');
        if (lastUserIdx !== -1) {
          updated[lastUserIdx].eval = response.evaluation;
        }
        return updated;
      });

      setEvaluationFeedback(response.evaluation);

      if (response.is_finished) {
        setInterviewStarted(false);
        setCurrentQuestion(null);
        handleFetchSummary();
      } else {
        setCurrentQuestion(response.next_question);
        // Add next question to chat history
        setChatHistory(prev => [...prev, { 
          role: 'bot', 
          content: response.next_question.question,
          meta: response.next_question
        }]);
      }
    } catch (err) {
      setError('Lỗi gửi câu trả lời: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSkipQuestion = async () => {
    setLoading(true);
    setLoadingText('Đang bỏ qua câu hỏi...');
    setError('');

    // Add user answer indicator
    setChatHistory(prev => [...prev, { role: 'user', content: '[Bỏ qua câu hỏi này]' }]);

    try {
      const response = await api.skipInterviewQuestion(analysisId);
      
      setChatHistory(prev => {
        const updated = [...prev];
        const lastUserIdx = updated.map(c => c.role).lastIndexOf('user');
        if (lastUserIdx !== -1) {
          updated[lastUserIdx].eval = response.evaluation;
        }
        return updated;
      });

      setEvaluationFeedback(response.evaluation);

      if (response.is_finished) {
        setInterviewStarted(false);
        setCurrentQuestion(null);
        handleFetchSummary();
      } else {
        setCurrentQuestion(response.next_question);
        setChatHistory(prev => [...prev, { 
          role: 'bot', 
          content: response.next_question.question,
          meta: response.next_question
        }]);
      }
    } catch (err) {
      setError('Lỗi bỏ qua câu hỏi: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFetchSummary = async () => {
    setLoading(true);
    setLoadingText('Đang tổng hợp đánh giá phỏng vấn...');
    try {
      const summaryData = await api.getInterviewSummary(analysisId);
      setSummary(summaryData);
    } catch (err) {
      setError('Lỗi tổng hợp phỏng vấn: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setAnalysisId(null);
    setInterviewStarted(false);
    setCurrentQuestion(null);
    setChatHistory([]);
    setSummary(null);
    setEvaluationFeedback(null);
  };

  const downloadJson = () => {
    if (!summary) return;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(summary, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `ket_qua_phong_van_${summary.candidate_name.replace(' ', '_')}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const getHiringBadgeClass = (rec) => {
    if (rec === 'strong_hire') return 'badge-pass';
    if (rec === 'hire') return 'badge-pass';
    if (rec === 'maybe') return 'badge-warning';
    return 'badge-fail';
  };

  const getHiringLabel = (rec) => {
    const map = {
      'strong_hire': 'Rất nên tuyển (Strong Hire)',
      'hire': 'Tuyển dụng (Hire)',
      'maybe': 'Cân nhắc (Maybe)',
      'no_hire': 'Không tuyển (No Hire)'
    };
    return map[rec] || rec;
  };

  return (
    <div className="interview-practice-container">
      {/* Loading overlay */}
      {loading && (
        <div className="glass-card" style={{ textAlign: 'center', padding: '50px 20px' }}>
          <div className="spinner"></div>
          <h4 style={{ marginTop: '20px' }}>{loadingText}</h4>
        </div>
      )}

      {/* Step 1: Initial upload/select screen */}
      {!interviewStarted && !summary && !loading && (
        <div className="glass-card">
          <h3>Bắt đầu Luyện tập phỏng vấn</h3>
          
          <div className="tab-container" style={{ marginTop: '20px' }}>
            <div className={`tab-btn ${sourceType === 'new' ? 'active' : ''}`} onClick={() => setSourceType('new')}>Upload CV mới</div>
            <div className={`tab-btn ${sourceType === 'past' ? 'active' : ''}`} onClick={() => setSourceType('past')}>Chọn từ kết quả đã phân tích</div>
          </div>

          {sourceType === 'new' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div className="form-group">
                <label className="form-label">Tải lên CV của bạn (PDF/DOCX)</label>
                <div 
                  className="upload-zone"
                  onClick={() => fileInputRef.current.click()}
                  style={{ padding: '30px 20px' }}
                >
                  {/* <div className="upload-icon" style={{ fontSize: '30px' }}>📤</div> */}
                  <div className="upload-text" style={{ fontSize: '14px' }}>Upload CV</div>
                  <input 
                    type="file" 
                    ref={fileInputRef} 
                    style={{ display: 'none' }} 
                    onChange={e => setUploadedFile(e.target.files[0])} 
                    accept=".pdf,.docx" 
                  />
                </div>
                {uploadedFile && <div className="badge badge-pass" style={{ marginTop: '10px', display: 'inline-block' }}>📎 {uploadedFile.name}</div>}
              </div>

              <div className="form-group">
                <label className="form-label">Chọn vị trí tuyển dụng (JD)</label>
                <select className="form-select" value={selectedJdId} onChange={e => setSelectedJdId(e.target.value)}>
                  {jds.map(jd => <option key={jd.id} value={jd.id}>{jd.name}</option>)}
                  <option value="manual">— Nhập JD thủ công —</option>
                </select>
              </div>

              {selectedJdId === 'manual' && (
                <div className="form-group">
                  <label className="form-label">Nội dung mô tả công việc (JD)</label>
                  <textarea 
                    className="form-textarea" 
                    placeholder="Dán nội dung JD tuyển dụng..."
                    value={manualJdContent}
                    onChange={e => setManualJdContent(e.target.value)}
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="form-group" style={{ marginTop: '20px' }}>
              <label className="form-label">Chọn ứng viên & CV</label>
              <select className="form-select" value={selectedAnalysisId} onChange={e => setSelectedAnalysisId(e.target.value)}>
                {pastAnalyses.length === 0 ? (
                  <option value="">Chưa có phân tích nào, vui lòng upload CV mới</option>
                ) : (
                  pastAnalyses.map(a => (
                    <option key={a.id} value={a.id}>{a.candidate_name} — Vị trí: {a.jd_name} ({a.total_score}%)</option>
                  ))
                )}
              </select>
            </div>
          )}

          {error && <div className="badge badge-fail" style={{ display: 'block', padding: '12px', margin: '20px 0', textAlign: 'center' }}>{error}</div>}

          <button 
            className="btn btn-primary" 
            style={{ width: '100%', marginTop: '10px', padding: '14px' }}
            onClick={handleStartInterview}
          >
            Bắt đầu phỏng vấn
          </button>
        </div>
      )}

      {/* Step 2: Chat Interface */}
      {interviewStarted && currentQuestion && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '25px' }}>
          {/* Question Metadata Card */}
          <div className="glass-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
              <h4>Câu hỏi {currentQuestion.question_number} / {totalQuestions}</h4>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span className="badge badge-pass" style={{ fontSize: '10px' }}>{currentQuestion.category}</span>
                <span className="badge badge-warning" style={{ fontSize: '10px' }}>Độ khó: {currentQuestion.difficulty}</span>
              </div>
            </div>
            <div style={{ fontSize: '14px', marginBottom: '10px', color: 'var(--color-text-muted)' }}>
              <strong>Kỹ năng kiểm tra:</strong> {currentQuestion.related_skill}
            </div>
            {currentQuestion.cv_reference && currentQuestion.cv_reference !== 'N/A - tình huống giả định' && (
              <div style={{ fontSize: '13px', fontStyle: 'italic', color: 'var(--color-primary-light)', marginBottom: '10px' }}>
                Dựa trên CV: {currentQuestion.cv_reference}
              </div>
            )}
            <div style={{ background: '#f8fafc', padding: '15px', borderRadius: '8px', borderLeft: '3px solid var(--color-primary)', fontSize: '16px', fontWeight: '600', lineHeight: '1.5', color: '#0f172a' }}>
              {currentQuestion.question}
            </div>
            {currentQuestion.purpose && (
              <span className="upload-subtext" style={{ display: 'block', marginTop: '10px', fontSize: '12px' }}>Mục đích: {currentQuestion.purpose}</span>
            )}
          </div>

          {/* Interactive Chat Log */}
          <div className="chat-container">
            <div className="chat-history">
              {chatHistory.map((chat, idx) => (
                <div key={idx} style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
                  <div className={`chat-bubble ${chat.role}`}>
                    <div>{chat.content}</div>
                    {chat.meta && (
                      <div className="chat-metadata">
                        <span>[{chat.meta.category}]</span>
                        <span>{chat.meta.related_skill}</span>
                      </div>
                    )}
                  </div>
                  
                  {/* Realtime evaluation shown right below candidate's response bubble */}
                  {chat.role === 'user' && chat.eval && (
                    <div className="glass-card" style={{ 
                      alignSelf: 'flex-end', 
                      maxWidth: '75%', 
                      marginTop: '8px',
                      background: '#faf5ff',
                      borderColor: '#e9d5ff',
                      padding: '15px',
                      color: '#0f172a'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                        <span style={{ fontWeight: '600', fontSize: '13px', color: 'var(--color-primary-light)' }}>AI Đánh giá câu trả lời</span>
                        <span className="badge badge-pass" style={{ fontSize: '11px', color: '#10b981' }}>{chat.eval.score} / 10 điểm</span>
                      </div>
                      
                      {chat.eval.strengths && chat.eval.strengths.length > 0 && (
                        <div style={{ fontSize: '12px', marginBottom: '5px' }}>
                          <strong style={{ color: '#10b981' }}>Điểm mạnh:</strong> {chat.eval.strengths.join(', ')}
                        </div>
                      )}
                      {chat.eval.weaknesses && chat.eval.weaknesses.length > 0 && (
                        <div style={{ fontSize: '12px', marginBottom: '5px' }}>
                          <strong style={{ color: '#ef4444' }}>Cần cải thiện:</strong> {chat.eval.weaknesses.join(', ')}
                        </div>
                      )}
                      {chat.eval.reasoning && (
                        <div className="upload-subtext" style={{ fontSize: '11px', marginTop: '8px', borderTop: '1px solid rgba(0,0,0,0.08)', paddingTop: '8px' }}>
                          {chat.eval.reasoning}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>

            {/* Input area */}
            <div className="chat-input-area">
              <textarea 
                className="form-input" 
                placeholder="Nhập câu trả lời chi tiết của bạn vào đây" 
                value={answer}
                onChange={e => setAnswer(e.target.value)}
                style={{ flex: 1, minHeight: '60px', height: '60px', resize: 'none' }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmitAnswer();
                  }
                }}
              />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <button className="btn btn-primary" onClick={handleSubmitAnswer} disabled={!answer.trim()} style={{ height: '35px', padding: '0 15px' }}>Gửi câu trả lời</button>
                <button className="btn btn-secondary" onClick={handleSkipQuestion} style={{ height: '25px', padding: '0 15px', fontSize: '11px' }}>Bỏ qua</button>
              </div>
            </div>
          </div>
          
          {error && <div className="badge badge-fail" style={{ display: 'block', padding: '12px', textAlign: 'center' }}>{error}</div>}
        </div>
      )}

      {/* Step 3: Summary screen */}
      {summary && !interviewStarted && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
          {/* Main metrics */}
          <div className="glass-card" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px', textAlign: 'center' }}>
            <div className="score-circle-container">
              <div className="score-circle" style={{ borderColor: '#22c55e' }}>
                <span className="score-number" style={{ color: '#22c55e' }}>{summary.cv_score_pct}</span>
                <span className="score-text" style={{ fontSize: '10px', marginTop: 0 }}>/100</span>
              </div>
              <span className="score-text">Điểm tương thích CV</span>
            </div>

            <div className="score-circle-container">
              <div className="score-circle" style={{ borderColor: 'var(--color-primary-light)' }}>
                <span className="score-number" style={{ color: 'var(--color-primary-light)' }}>{summary.interview_score}</span>
                <span className="score-text" style={{ fontSize: '10px', marginTop: 0 }}>/10</span>
              </div>
              <span className="score-text">Điểm phỏng vấn</span>
            </div>

            <div className="score-circle-container" style={{ justifyContent: 'center' }}>
              <span className="score-text">Đánh giá chung</span>
              <span className={`badge ${getHiringBadgeClass(summary.hiring_recommendation)}`} style={{ padding: '8px 16px', fontSize: '12px', marginBottom: '15px' }}>
                {getHiringLabel(summary.hiring_recommendation)}
              </span>
            </div>
          </div>

          {/* Details assessment text */}
          <div className="glass-card">
            <h4>Đánh giá chi tiết</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', margin: '20px 0' }}>
              <div><strong>Ứng viên:</strong> {summary.candidate_name}</div>
              <div><strong>Vị trí phỏng vấn:</strong> {summary.job_title}</div>
              <div><strong>Năng lực kỹ thuật:</strong> <span className="badge badge-warning" style={{ textTransform: 'capitalize' }}>{summary.technical_competency}</span></div>
              <div><strong>Chất lượng giao tiếp:</strong> <span className="badge badge-pass" style={{ textTransform: 'capitalize' }}>{summary.communication_quality}</span></div>
            </div>
            
            <div style={{ background: 'rgba(255,255,255,0.02)', padding: '20px', borderRadius: '10px', borderLeft: '4px solid var(--color-accent)', fontSize: '14px', lineHeight: '1.6', whiteSpace: 'pre-wrap' }}>
              {summary.detailed_assessment}
            </div>
          </div>

          {/* Strengths & concerns */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '25px' }}>
            <div className="glass-card" style={{ borderColor: 'rgba(16, 185, 129, 0.2)' }}>
              <h5 style={{ color: '#10b981', marginBottom: '15px', fontSize: '14px'}}>Điểm mạnh nổi bật</h5>
              <ul style={{ paddingLeft: '20px', fontSize: '14px' }}>
                {summary.key_strengths && summary.key_strengths.map((s, idx) => <li key={idx} style={{ marginBottom: '8px' }}>{s}</li>)}
              </ul>
            </div>

            <div className="glass-card" style={{ borderColor: 'rgba(239, 68, 68, 0.2)' }}>
              <h5 style={{ color: '#ef4444', marginBottom: '15px', fontSize: '14px'}}>Điểm cần lưu ý</h5>
              <ul style={{ paddingLeft: '20px', fontSize: '14px' }}>
                {summary.areas_of_concern && summary.areas_of_concern.map((a, idx) => <li key={idx} style={{ marginBottom: '8px' }}>{a}</li>)}
              </ul>
            </div>
          </div>

          {/* Questions breakdown */}
          <div className="glass-card">
            <h4>Tổng hợp kết quả phỏng vấn</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', marginTop: '20px' }}>
              {summary.question_evaluations && summary.question_evaluations.map((ev, idx) => (
                <div key={idx} className="glass-card" style={{ background: 'rgba(255,255,255,0.01)', padding: '20px', marginBottom: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <span style={{ fontWeight: '600' }}>Câu {ev.question_number}: {ev.category} ({ev.related_skill})</span>
                    <span className="badge badge-pass" style={{ color: '#10b981' }}>{ev.score} / 10 điểm</span>
                  </div>
                  <div style={{ fontSize: '14px', fontWeight: '500', color: 'var(--color-text-main)', marginBottom: '10px', fontStyle: 'italic' }}>
                    &ldquo;{ev.question}&rdquo;
                  </div>
                  <div style={{ fontSize: '13px', color: '#6b6d6f', marginBottom: '10px', background: 'rgba(147, 144, 144, 0.2)', padding: '10px', borderRadius: '6px' }}>
                    <strong>Trả lời:</strong> {ev.candidate_answer}
                  </div>
                  
                  {ev.strengths && ev.strengths.length > 0 && (
                    <div style={{ fontSize: '12px', color: '#10b981', marginBottom: '4px' }}>
                      <strong>Điểm tốt:</strong> {ev.strengths.join(', ')}
                    </div>
                  )}
                  {ev.weaknesses && ev.weaknesses.length > 0 && (
                    <div style={{ fontSize: '12px', color: '#ef4444', marginBottom: '4px' }}>
                      <strong>Cần cải thiện:</strong> {ev.weaknesses.join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Download JSON and Restart */}
          <div style={{ display: 'flex', gap: '20px' }}>
            <button className="btn btn-secondary" style={{ flex: 1, border: '2px solid #d0d2d3'}} onClick={downloadJson}>Tải kết quả (JSON)</button>
            <button className="btn btn-secondary" style={{ flex: 1, border: '2px solid #d0d2d3'}} onClick={handleReset}>Luyện tập lại</button>
          </div>
        </div>
      )}
    </div>
  );
}
