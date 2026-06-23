import React, { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';

export default function CvTailor() {
  const [jds, setJds] = useState([]);
  const [pastAnalyses, setPastAnalyses] = useState([]);
  const [selectedJdId, setSelectedJdId] = useState('');
  const [manualJdContent, setManualJdContent] = useState('');
  const [uploadedFile, setUploadedFile] = useState(null);
  
  // Setup source type: 'past' or 'new'
  const [sourceType, setSourceType] = useState('new');
  const [selectedAnalysisId, setSelectedAnalysisId] = useState('');

  // CV analysis state before tailoring
  const [analysis, setAnalysis] = useState(null);
  const [analysisId, setAnalysisId] = useState(null);

  // Tailoring state
  const [tailorResult, setTailorResult] = useState(null);
  const [activeTab, setActiveTab] = useState('cv'); // cv, cover
  const [copiedText, setCopiedText] = useState('');

  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState('');
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchJds();
    fetchPastAnalyses();
  }, []);

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

  const handleAnalyze = async () => {
    setLoading(true);
    setError('');
    setAnalysis(null);
    setTailorResult(null);

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

        setLoadingText('Đang phân tích độ tương thích CV ban đầu');
        const formData = new FormData();
        formData.append('jd_id', selectedJdId);
        if (selectedJdId === 'manual') {
          formData.append('jd_content_manual', manualJdContent);
        }
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

      setLoadingText('Đang tải kết quả chi tiết...');
      const fullDetail = await api.getAnalysis(activeId);
      
      setAnalysisId(activeId);
      setAnalysis(fullDetail);
    } catch (err) {
      setError('Không thể phân tích CV: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleTailorCv = async () => {
    if (!analysisId) return;

    setLoading(true);
    setLoadingText('AI đang tối ưu hóa CV và tạo Thư xin việc (Quá trình này có thể mất 20-30s)...');
    setError('');

    try {
      const result = await api.tailorCv(analysisId, 'auto');
      setTailorResult(result);
      setActiveTab('cv');
    } catch (err) {
      setError('Lỗi khi tối ưu hóa CV: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text, type) => {
    navigator.clipboard.writeText(text);
    setCopiedText(type);
    setTimeout(() => setCopiedText(''), 2000);
  };

  const downloadMd = (content, filename) => {
    const element = document.createElement("a");
    const file = new Blob([content], {type: 'text/markdown'});
    element.href = URL.createObjectURL(file);
    element.download = filename;
    document.body.appendChild(element);
    element.click();
    element.remove();
  };

  const handleReset = () => {
    setAnalysis(null);
    setAnalysisId(null);
    setTailorResult(null);
    setUploadedFile(null);
    setManualJdContent('');
  };

  const getScoreColor = (score) => {
    if (score >= 85) return '#22c55e';
    if (score >= 70) return '#3b82f6';
    if (score >= 50) return '#f59e0b';
    return '#ef4444';
  };

  // Extract missing skills from analysis report
  const getMissingSkills = () => {
    if (!analysis) return [];
    const breakdown = analysis.scoring_breakdown || {};
    const skillsDetails = breakdown.skills?.details || {};
    const missingMust = skillsDetails.matched_critical_skills ? skillsDetails.missing_critical_skills || [] : [];
    const missingNice = skillsDetails.matched_nice_skills ? skillsDetails.missing_nice_skills || [] : [];
    return [...missingMust, ...missingNice];
  };

  return (
    <div className="cv-tailor-container">
      {/* Loading overlay */}
      {loading && (
        <div className="glass-card" style={{ textAlign: 'center', padding: '50px 20px' }}>
          <div className="spinner"></div>
          <h4 style={{ marginTop: '20px' }}>{loadingText}</h4>
        </div>
      )}

      {/* Step 1: initial screen */}
      {!analysis && !tailorResult && !loading && (
        <div className="glass-card">
          <h3>Tối ưu CV theo JD</h3>
          <p className="upload-subtext" style={{ margin: '8px 0 20px 0' }}>Tối ưu hóa các mục trong CV của bạn để đáp ứng tốt nhất các yêu cầu từ JD tuyển dụng</p>
          
          <div className="tab-container">
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
                    placeholder="Dán nội dung JD tuyển dụng"
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
            onClick={handleAnalyze}
          >
            Tiếp tục
          </button>
        </div>
      )}

      {/* Step 2: Show Initial analysis compatibility & Button to tailor */}
      {analysis && !tailorResult && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
          <div className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>Độ tương thích CV hiện tại</h3>
            <button className="btn btn-secondary" onClick={handleReset}>Chọn CV khác</button>
          </div>

          <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div className="score-circle-container" style={{ width: '100%', maxWidth: '350px' }}>
              <div className="score-circle" style={{ borderColor: getScoreColor(analysis.total_score) }}>
                <span className="score-number" style={{ color: getScoreColor(analysis.total_score) }}>{analysis.total_score}</span>
                <span className="score-text" style={{ fontSize: '11px', marginTop: 1 }}>/100</span>
              </div>
              <div style={{ fontWeight: '600', fontSize: '15px' }}>{analysis.recommendation}</div>
            </div>

            {/* Missing keywords/skills display */}
            <div style={{ width: '100%', marginTop: '20px' }}>
              {getMissingSkills().length > 0 ? (
                <div>
                  <h5 style={{ color: '#ef4444', marginBottom: '10px', fontSize: '14px'}}>Các kỹ năng còn thiếu:</h5>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {getMissingSkills().map((skill, idx) => (
                      <span key={idx} className="badge badge-fail" style={{ fontSize: '12px', textTransform: 'none' }}>{skill}</span>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="badge badge-pass" style={{ width: '100%', padding: '12px', textAlign: 'center' }}>
                  Tuyệt vời! CV của bạn đã đáp ứng đủ các kỹ năng cốt lõi được mô tả trong JD.
                </div>
              )}
            </div>
          </div>

          <div className="glass-card" style={{ background: 'rgba(245, 158, 11, 0.02)', borderColor: 'rgba(245, 158, 11, 0.1)', fontSize: '16px'}}>
            <h5>AI sẽ tối ưu CV của bạn như thế nào?</h5>
            <ul style={{ paddingLeft: '20px', marginTop: '10px', fontSize: '14px', lineHeight: '1.6', color: 'var(--color-text-muted)' }}>
              <li><strong>Tự nhiên chèn từ khóa:</strong> Đưa các từ khóa kỹ năng quan trọng còn thiếu vào CV một cách logic.</li>
              <li><strong>Sử dụng Action Verbs:</strong> Viết lại các dòng mô tả kinh nghiệm bằng động từ hành động mạnh mẽ, chuyên nghiệp.</li>
              <li><strong>Giữ nguyên tính trung thực:</strong> Không bịa đặt kinh nghiệm, dự án hay học vấn, chỉ thay đổi cách trình bày để đạt điểm ATS tốt nhất.</li>
              <li><strong>Tự động tạo Thư xin việc (Cover Letter):</strong> Viết một bức thư xin việc cá nhân hóa, làm nổi bật điểm mạnh phù hợp với JD.</li>
            </ul>
          </div>

          {error && <div className="badge badge-fail" style={{ display: 'block', padding: '12px', textAlign: 'center' }}>{error}</div>}

          <button className="btn btn-primary" style={{ width: '100%', padding: '15px' }} onClick={handleTailorCv}>
            Tối ưu CV
          </button>
        </div>
      )}

      {/* Step 3: Show optimized CV and cover letter */}
      {tailorResult && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
          <div className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>Kết quả tối ưu CV bằng AI</h3>
            <button className="btn btn-secondary" onClick={handleReset}>Tối ưu CV khác</button>
          </div>

          {/* Changes summary */}
          <div className="glass-card" style={{ background: 'rgba(16, 185, 129, 0.02)', borderColor: 'rgba(16, 185, 129, 0.1)' }}>
            <h5 style={{ color: '#10b981' }}>Tóm tắt các thay đổi đã thực hiện</h5>
            <p style={{ fontSize: '14px', marginTop: '8px', lineHeight: '1.5' }}>{tailorResult.changes_summary}</p>
            
            {tailorResult.keywords_added && tailorResult.keywords_added.length > 0 && (
              <div style={{ marginTop: '15px' }}>
                <strong>Từ khóa đã chèn thêm:</strong>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
                  {tailorResult.keywords_added.map((kw, i) => (
                    <span key={i} className="badge badge-pass" style={{ fontSize: '11px', textTransform: 'none' }}>{kw}</span>
                  ))}
                </div>
              </div>
            )}

            {tailorResult.improvements_made && tailorResult.improvements_made.length > 0 && (
              <div style={{ marginTop: '15px' }}>
                <strong>Cải tiến cụ thể:</strong>
                <ul style={{ paddingLeft: '20px', fontSize: '13px', marginTop: '5px' }}>
                  {tailorResult.improvements_made.map((imp, i) => <li key={i}>{imp}</li>)}
                </ul>
              </div>
            )}
          </div>

          {/* Results Tab navigation */}
          <div>
            <div className="tab-container">
              <div className={`tab-btn ${activeTab === 'cv' ? 'active' : ''}`} onClick={() => setActiveTab('cv')}>CV Đã Tối ưu</div>
              <div className={`tab-btn ${activeTab === 'cover' ? 'active' : ''}`} onClick={() => setActiveTab('cover')}>Thư Xin Việc (Cover Letter)</div>
            </div>

            {activeTab === 'cv' ? (
              <div className="glass-card">
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginBottom: '15px' }}>
                  <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '12px' }} onClick={() => copyToClipboard(tailorResult.markdown_content, 'cv')}>
                    {copiedText === 'cv' ? 'Đã Copy' : 'Copy Markdown'}
                  </button>
                  <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '12px' }} onClick={() => downloadMd(tailorResult.markdown_content, 'CV_Da_Toi_Uu.md')}>
                    Tải xuống (.md)
                  </button>
                </div>
                <div className="markdown-body" style={{ background: '#ffffff', color: '#000000', padding: '25px', borderRadius: '10px', border: '1px solid var(--border-glass)', overflowX: 'auto' }}>
                  <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'var(--font-family-body)', fontSize: '15px', lineHeight: '1.6', background: '#ffffff', color: '#000000', border: 'none', margin: 0, padding: 0 }}>
                    {tailorResult.markdown_content}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="glass-card">
                {tailorResult.cover_letter ? (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginBottom: '15px' }}>
                      <button className="btn" style={{ padding: '6px 12px', fontSize: '12px' }} onClick={() => copyToClipboard(tailorResult.cover_letter, 'cover')}>
                        {copiedText === 'cover' ? 'Đã Copy' : 'Copy Markdown'}
                      </button>
                      <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '12px' }} onClick={() => downloadMd(tailorResult.cover_letter, 'Thu_Xin_Viec.md')}>
                        Tải xuống (.md)
                      </button>
                    </div>
                    <div className="markdown-body" style={{ background: '#ffffff', color: '#000000', padding: '25px', borderRadius: '10px', border: '1px solid var(--border-glass)', overflowX: 'auto' }}>
                      <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'var(--font-family-body)', fontSize: '15px', lineHeight: '1.6', background: '#ffffff', color: '#000000', border: 'none', margin: 0, padding: 0 }}>
                        {tailorResult.cover_letter}
                      </pre>
                    </div>
                  </>
                ) : (
                  <div className="upload-subtext" style={{ textAlign: 'center', padding: '20px' }}>Không có thư xin việc được tạo.</div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
