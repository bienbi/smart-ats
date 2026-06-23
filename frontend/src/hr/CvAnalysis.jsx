import React, { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';

export default function CvAnalysis() {
  const [jds, setJds] = useState([]);
  const [selectedJdId, setSelectedJdId] = useState('');
  const [manualJdContent, setManualJdContent] = useState('');
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [weights, setWeights] = useState({
    skills: 40,
    experience: 30,
    education: 10,
    language: 10,
    stability: 10
  });
  const [showWeightsConfig, setShowWeightsConfig] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progressText, setProgressText] = useState('');
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');
  const [expandedResultIdx, setExpandedResultIdx] = useState(null);
  const fileInputRef = useRef(null);
  const folderInputRef = useRef(null);

  useEffect(() => {
    fetchJds();
  }, []);

  const fetchJds = async () => {
    try {
      const data = await api.getJds();
      setJds(data);
      if (data.length > 0) {
        setSelectedJdId(data[0].id);
      } else {
        setSelectedJdId('manual');
      }
    } catch (err) {
      console.error('Không thể tải JD:', err);
    }
  };

  const handleWeightChange = (key, val) => {
    const numericVal = Math.min(100, Math.max(0, parseInt(val) || 0));
    setWeights(prev => ({
      ...prev,
      [key]: numericVal
    }));
  };

  const resetWeights = () => {
    setWeights({
      skills: 40,
      experience: 30,
      education: 10,
      language: 10,
      stability: 10
    });
  };

  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);

  // File drag and drop
  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files) {
      addFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files) {
      addFiles(Array.from(e.target.files));
    }
  };

  const handleFolderChange = (e) => {
    if (e.target.files) {
      addFiles(Array.from(e.target.files));
    }
  };

  const addFiles = (newFiles) => {
    const validFiles = newFiles.filter(f => 
      f.name.toLowerCase().endsWith('.pdf') || 
      f.name.toLowerCase().endsWith('.docx')
    );
    if (validFiles.length === 0) {
      setError('Không tìm thấy tệp CV định dạng .pdf hoặc .docx hợp lệ nào.');
      return;
    }
    setError('');
    setFiles(prev => {
      const combined = [...prev, ...validFiles];
      const unique = combined.filter((file, index, self) =>
        index === self.findIndex((t) => t.name === file.name && t.size === file.size)
      );
      return unique.slice(0, 50); // Hỗ trợ tối đa 50 files
    });
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleAnalyze = async () => {
    if (files.length === 0) {
      setError('Vui lòng tải lên ít nhất một CV');
      return;
    }
    if (totalWeight !== 100) {
      setError('Tổng trọng số phải bằng 100%');
      return;
    }
    if (selectedJdId === 'manual' && !manualJdContent.trim()) {
      setError('Vui lòng nhập nội dung JD thủ công');
      return;
    }

    setLoading(true);
    setError('');
    setResults(null);
    setProgressText('Đang chuẩn bị phân tích CV');

    const formData = new FormData();
    formData.append('jd_id', selectedJdId);
    if (selectedJdId === 'manual') {
      formData.append('jd_content_manual', manualJdContent);
    }
    formData.append('w_skills', weights.skills);
    formData.append('w_exp', weights.experience);
    formData.append('w_edu', weights.education);
    formData.append('w_lang', weights.language);
    formData.append('w_stab', weights.stability);
    
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      setProgressText(`Đang tải file và phân tích ${files.length} CV...`);
      const response = await api.analyzeCvs(formData);
      setResults(response);
    } catch (err) {
      setError('Lỗi khi phân tích CV: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 85) return '#22c55e'; // Green
    if (score >= 70) return '#3b82f6'; // Blue
    if (score >= 50) return '#f59e0b'; // Orange
    return '#ef4444'; // Red
  };

  const getRecLabel = (rec) => {
    if (rec.includes('Strong') || rec.includes('Rất phù hợp')) return 'Rất phù hợp';
    if (rec.includes('Partial') || rec.includes('một phần')) return 'Phù hợp một phần';
    if (rec.includes('Good') || rec.includes('Phù hợp')) return 'Phù hợp';
    return 'Không phù hợp';
  };

  return (
    <div className="cv-analysis-container">
      {/* Step 1: Configurations */}
      {!results && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          <div className="analysis-grid-layout" style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', 
            gap: '20px', 
            alignItems: 'start' 
          }}>
            
            {/* Left Column: JD & Upload */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              
              {/* JD Selection */}
              <div className="glass-card">
                <h3>Chọn JD tuyển dụng</h3>
                <div className="form-group" style={{ marginTop: '20px' }}>
                  <label className="form-label">Chọn mô tả công việc (JD) để phân tích CV</label>
                  <select 
                    className="form-select"
                    value={selectedJdId}
                    onChange={(e) => setSelectedJdId(e.target.value)}
                  >
                    {jds.map(jd => (
                      <option key={jd.id} value={jd.id}>{jd.name}</option>
                    ))}
                    <option value="manual">— Nhập JD thủ công —</option>
                  </select>
                </div>

                {selectedJdId === 'manual' && (
                  <div className="form-group">
                    <label className="form-label">Nội dung mô tả công việc (JD) thủ công</label>
                    <textarea
                      className="form-textarea"
                      placeholder="Dán toàn bộ nội dung mô tả công việc, yêu cầu tuyển dụng ở đây..."
                      value={manualJdContent}
                      onChange={(e) => setManualJdContent(e.target.value)}
                    />
                  </div>
                )}
                
                {selectedJdId !== 'manual' && jds.find(j => j.id === selectedJdId) && (
                  <div className="expander-container" style={{ marginTop: '15px' }}>
                    <div 
                      className="expander-header" 
                      onClick={() => setShowWeightsConfig(!showWeightsConfig)}
                      style={{ fontSize: '14px', background: 'rgba(255,255,255,0.01)' }}
                    >
                      <span>Xem nội dung JD đang chọn</span>
                      <span>{showWeightsConfig ? '▼' : '▶'}</span>
                    </div>
                    {showWeightsConfig && (
                      <div className="expander-content" style={{ maxHeight: '200px', overflowY: 'auto' }}>
                        <pre style={{ whiteSpace: 'pre-wrap', fontSize: '14px', fontFamily: 'var(--font-family-body)', lineHeight: '1.5' }}>
                          {jds.find(j => j.id === selectedJdId)?.content}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Upload Files */}
              <div className="glass-card">
                <h3>Upload CV</h3>
                <div style={{ marginTop: '20px' }}>
                  <div 
                    className={`upload-zone ${isDragging ? 'dragging' : ''}`}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    style={{ cursor: 'default' }}
                  >
                    {/* <div className="upload-icon" style={{ fontSize: '36px', marginBottom: '8px' }}>📤</div> */}
                    <div className="upload-text" style={{ fontSize: '15px', fontWeight: '600' }}>Kéo thả file hoặc thư mục CV vào đây</div>
                    
                    <div style={{ display: 'flex', gap: '12px', marginTop: '10px', marginBottom: '5px' }}>
                      <button 
                        type="button" 
                        className="btn btn-secondary" 
                        style={{ padding: '8px 16px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}
                        onClick={() => fileInputRef.current.click()}
                      >
                        Chọn tệp CV
                      </button>
                      <button 
                        type="button" 
                        className="btn btn-secondary" 
                        style={{ padding: '8px 16px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}
                        onClick={() => folderInputRef.current.click()}
                      >
                        Chọn thư mục
                      </button>
                    </div>

                    {/* <div className="upload-subtext">Chấp nhận tệp PDF, DOCX </div> */}
                    
                    <input 
                      type="file" 
                      ref={fileInputRef} 
                      style={{ display: 'none' }} 
                      onChange={handleFileChange}
                      multiple 
                      accept=".pdf,.docx" 
                    />
                    <input 
                      type="file" 
                      ref={folderInputRef} 
                      style={{ display: 'none' }} 
                      onChange={handleFolderChange}
                      multiple
                      webkitdirectory=""
                      directory=""
                    />
                  </div>

                  {files.length > 0 && (
                    <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <div className="badge badge-pass" style={{ marginBottom: '10px' }}>Đã nhận {files.length} file CV</div>
                      <div className="file-list" style={{ maxHeight: '250px', overflowY: 'auto' }}>
                        {files.map((file, idx) => (
                          <div key={idx} className="file-item">
                            <span className="file-name" title={file.name}>{file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
                            <span className="remove-file" onClick={(e) => { e.stopPropagation(); removeFile(idx); }}>X</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

            </div>

            {/* Right Column: Weight settings */}
            <div className="glass-card" style={{ height: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3>Tùy chỉnh trọng số chấm điểm</h3>
                <span className="badge badge-warning" style={{ fontSize: '12px', padding: '6px 12px' }}>Tổng: {totalWeight}%</span>
              </div>
              
              <p className="upload-subtext" style={{ marginBottom: '20px' }}>Điều chỉnh tỷ trọng cho 5 khía cạnh cốt lõi (Tổng bắt buộc phải bằng 100%):</p>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                
                {/* Skills weight slider */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: '600', fontSize: '14px', color: 'var(--color-text-main)' }}>Kỹ năng chuyên môn</span>
                    <span style={{ fontWeight: '700', color: 'var(--color-primary)' }}>{weights.skills}%</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <input 
                      type="range" 
                      min="0" 
                      max="100" 
                      step="5"
                      value={weights.skills}
                      onChange={(e) => handleWeightChange('skills', e.target.value)}
                      style={{ flex: 1, accentColor: 'var(--color-primary)', cursor: 'pointer' }}
                    />
                    <input 
                      type="number" 
                      className="form-input" 
                      style={{ width: '70px', padding: '6px 10px', textAlign: 'center' }}
                      value={weights.skills} 
                      onChange={(e) => handleWeightChange('skills', e.target.value)} 
                    />
                  </div>
                </div>

                {/* Experience weight slider */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: '600', fontSize: '14px', color: 'var(--color-text-main)' }}>Kinh nghiệm làm việc</span>
                    <span style={{ fontWeight: '700', color: 'var(--color-primary)' }}>{weights.experience}%</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <input 
                      type="range" 
                      min="0" 
                      max="100" 
                      step="5"
                      value={weights.experience}
                      onChange={(e) => handleWeightChange('experience', e.target.value)}
                      style={{ flex: 1, accentColor: 'var(--color-primary)', cursor: 'pointer' }}
                    />
                    <input 
                      type="number" 
                      className="form-input" 
                      style={{ width: '70px', padding: '6px 10px', textAlign: 'center' }}
                      value={weights.experience} 
                      onChange={(e) => handleWeightChange('experience', e.target.value)} 
                    />
                  </div>
                </div>

                {/* Education weight slider */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: '600', fontSize: '14px', color: 'var(--color-text-main)' }}>Học vấn & Bằng cấp</span>
                    <span style={{ fontWeight: '700', color: 'var(--color-primary)' }}>{weights.education}%</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <input 
                      type="range" 
                      min="0" 
                      max="100" 
                      step="5"
                      value={weights.education}
                      onChange={(e) => handleWeightChange('education', e.target.value)}
                      style={{ flex: 1, accentColor: 'var(--color-primary)', cursor: 'pointer' }}
                    />
                    <input 
                      type="number" 
                      className="form-input" 
                      style={{ width: '70px', padding: '6px 10px', textAlign: 'center' }}
                      value={weights.education} 
                      onChange={(e) => handleWeightChange('education', e.target.value)} 
                    />
                  </div>
                </div>

                {/* Language weight slider */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: '600', fontSize: '14px', color: 'var(--color-text-main)' }}>Trình độ Ngoại ngữ</span>
                    <span style={{ fontWeight: '700', color: 'var(--color-primary)' }}>{weights.language}%</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <input 
                      type="range" 
                      min="0" 
                      max="100" 
                      step="5"
                      value={weights.language}
                      onChange={(e) => handleWeightChange('language', e.target.value)}
                      style={{ flex: 1, accentColor: 'var(--color-primary)', cursor: 'pointer' }}
                    />
                    <input 
                      type="number" 
                      className="form-input" 
                      style={{ width: '70px', padding: '6px 10px', textAlign: 'center' }}
                      value={weights.language} 
                      onChange={(e) => handleWeightChange('language', e.target.value)} 
                    />
                  </div>
                </div>

                {/* Stability weight slider */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: '600', fontSize: '14px', color: 'var(--color-text-main)' }}>Mức độ gắn bó/Ổn định</span>
                    <span style={{ fontWeight: '700', color: 'var(--color-primary)' }}>{weights.stability}%</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <input 
                      type="range" 
                      min="0" 
                      max="100" 
                      step="5"
                      value={weights.stability}
                      onChange={(e) => handleWeightChange('stability', e.target.value)}
                      style={{ flex: 1, accentColor: 'var(--color-primary)', cursor: 'pointer' }}
                    />
                    <input 
                      type="number" 
                      className="form-input" 
                      style={{ width: '70px', padding: '6px 10px', textAlign: 'center' }}
                      value={weights.stability} 
                      onChange={(e) => handleWeightChange('stability', e.target.value)} 
                    />
                  </div>
                </div>

              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '22px', borderTop: '1px solid var(--border-glass)', paddingTop: '20px' }}>
                {totalWeight !== 100 ? (
                  <div className="badge badge-fail" style={{ fontSize: '12px' }}>Tổng trọng số hiện tại là {totalWeight}% (yêu cầu 100%)</div>
                ) : (
                  <div className="badge badge-pass" style={{ fontSize: '12px' }}>Hợp lệ: Tổng đạt 100%</div>
                )}
                <button type="button" className="btn btn-secondary" onClick={resetWeights} style={{ padding: '8px 16px', fontSize: '12px' }}>Đặt lại mặc định</button>
              </div>
            </div>

          </div>

          {error && <div className="badge badge-fail" style={{ padding: '15px', display: 'block', textAlign: 'center', fontSize: '14px' }}>{error}</div>}

          <button 
            className="btn btn-primary" 
            style={{ width: '100%', padding: '15px', fontSize: '16px', fontWeight: '700'}}
            disabled={files.length === 0 || totalWeight !== 100}
            onClick={handleAnalyze}
          >
            Bắt đầu Phân tích & Chấm điểm CV
          </button>
        </div>
      )}

      {/* Loading Screen */}
      {loading && (
        <div className="glass-card" style={{ textAlign: 'center', padding: '50px 20px' }}>
          <div className="spinner"></div>
          <h4 style={{ marginTop: '20px' }}>Đang thực hiện phân tích</h4>
          <p className="upload-subtext" style={{ marginTop: '10px' }}>{progressText}</p>
        </div>
      )}

      {/* Step 2: Show Results */}
      {results && (
        <div>
          <div className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>Kết quả Phân tích</h3>
            <button className="btn btn-secondary" onClick={() => { setResults(null); setFiles([]); }}>Phân tích lại</button>
          </div>

          {/* Aggregated Table */}
          <div className="glass-card">
            <h4>Bảng Tổng hợp</h4>
            <div className="table-container" style={{ marginTop: '15px' }}>
              <table className="modern-table">
                <thead>
                  <tr>
                    <th style={{ textAlign: 'center', width: '50px' }}>STT</th>
                    <th>Tên ứng viên</th>
                    <th>File CV</th>
                    <th style={{ textAlign: 'center', width: '100px' }}>Điểm số</th>
                    <th style={{ textAlign: 'center', width: '150px' }}>Khuyến nghị</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, idx) => {
                    const isError = !r.scoring_result;
                    return (
                      <tr key={idx} style={{ cursor: isError ? 'default' : 'pointer' }} onClick={() => !isError && setExpandedResultIdx(expandedResultIdx === idx ? null : idx)}>
                        <td style={{ textAlign: 'center' }}>{idx + 1}</td>
                        <td style={{ fontWeight: '600' }}>{r.name}</td>
                        <td style={{ fontSize: '13px', color: '#9ca3af' }}>{r.filename}</td>
                        <td style={{ textAlign: 'center', fontWeight: 'bold', color: isError ? '#ef4444' : getScoreColor(r.score) }}>
                          {isError ? 'Lỗi' : `${r.score}%`}
                        </td>
                        <td>
                          {isError ? (
                            <span className="badge badge-fail">Không thể phân tích</span>
                          ) : (
                            <span className={`badge ${r.score >= 70 ? 'badge-pass' : r.score >= 50 ? 'badge-warning' : 'badge-fail'}`}>
                              {getRecLabel(r.recommendation)}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Details sections */}
          <h4 style={{ margin: '30px 0 15px 0' }}>Chi tiết từng CV</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            {results.map((r, idx) => {
              if (r.error_detail) {
                return (
                  <div key={idx} className="glass-card" style={{ borderColor: '#dcd9d9', background: 'rgba(239, 68, 68, 0.05)' }}>
                    <div style={{ color: '#ef4444', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span>Lỗi khi phân tích CV: {r.filename}</span>
                    </div>
                    {r.is_user_error ? (
                      <div style={{ marginTop: '12px', fontSize: '14px', lineHeight: '1.6', padding: '12px 16px', borderRadius: '8px', borderLeft: '4px solid #ef4444' }}>
                        {r.error_detail}
                      </div>
                    ) : (
                      <pre style={{ background: '#0a0a16', padding: '15px', borderRadius: '8px', overflowX: 'auto', marginTop: '10px', fontSize: '12px', color: '#9ca3af' }}>
                        {r.error_detail}
                      </pre>
                    )}
                  </div>
                );
              }

              const isExpanded = expandedResultIdx === idx;
              const breakdown = r.scoring_result.breakdown;
              const analysis = r.analysis;

              return (
                <div key={idx} className="expander-container">
                  <div className="expander-header" onClick={() => setExpandedResultIdx(isExpanded ? null : idx)}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                      <span style={{ fontWeight: '700', fontSize: '16px' }}>{r.name}</span>
                      <span className="upload-subtext">{r.filename}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                      <span style={{ fontWeight: '800', color: getScoreColor(r.score) }}>{r.score}%</span>
                      <span>{isExpanded ? '▼' : '▶'}</span>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="expander-content" style={{ background: 'var(--bg-secondary)', padding: '25px' }}>
                      {/* Metainfo */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '20px' }}>
                        <div><strong>Ứng viên:</strong> {r.name}</div>
                        <div><strong>Email:</strong> {r.email || 'Không có'}</div>
                        <div><strong>Vị trí tuyển dụng (JD):</strong> {r.jd_name}</div>
                      </div>

                      {/* Summary score card */}
                      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '25px' }}>
                        <div className="score-circle-container" style={{ width: '100%', maxWidth: '400px', border: '1px solid var(--border-glass)', borderRadius: '14px' }}>
                          <div className="score-circle" style={{ borderColor: getScoreColor(r.score) }}>
                            <span className="score-number" style={{ color: getScoreColor(r.score) }}>
                              {r.score}
                            </span>
                            {/* <span className="score-text" style={{ fontSize: '11px', marginTop: 1 }}>/100</span> */}
                          </div>
                          <div style={{ textAlign: 'center', fontWeight: '500' }}>{r.recommendation}</div>
                        </div>
                      </div>

                      {/* Thẻ tag/badge kỹ năng */}
                      <div className="glass-card" style={{ marginTop: '20px', padding: '20px' }}>
                        <h5 style={{ color: 'var(--color-primary)', marginBottom: '15px', fontWeight: '700' }}>
                          Đánh giá nhanh kỹ năng của ứng viên
                        </h5>
                        
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                          {/* Đã đạt */}
                          <div>
                            <div style={{ fontWeight: '600', fontSize: '13px', color: '#10b981', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={{ fontSize: '10px' }}></span> Kỹ năng đã đạt:
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                              {[...(breakdown.skills?.details?.matched_critical_skills || []), ...(breakdown.skills?.details?.matched_nice_skills || [])].map((s, idx) => (
                                <span key={idx} className="badge badge-pass" style={{ fontSize: '12px', padding: '4px 8px', margin: 0 }}>{s}</span>
                              ))}
                              {[...(breakdown.skills?.details?.equivalent_critical_skills || []), ...(breakdown.skills?.details?.equivalent_nice_skills || [])].map((s, idx) => (
                                <span key={idx} className="badge badge-warning" style={{ fontSize: '12px', padding: '4px 8px', margin: 0 }}>{s}</span>
                              ))}
                              {!(breakdown.skills?.details?.matched_critical_skills?.length) && !(breakdown.skills?.details?.matched_nice_skills?.length) && (
                                <span style={{ fontSize: '12px', color: '#9ca3af', fontStyle: 'italic' }}>Không có</span>
                              )}
                            </div>
                          </div>

                          {/* Tương đương
                          <div>
                            <div style={{ fontWeight: '600', fontSize: '13px', color: '#f59e0b', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={{ fontSize: '10px' }}></span> Kỹ năng tương đương:
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                              {[...(breakdown.skills?.details?.equivalent_critical_skills || []), ...(breakdown.skills?.details?.equivalent_nice_skills || [])].map((s, idx) => (
                                <span key={idx} className="badge badge-warning" style={{ fontSize: '12px', padding: '4px 8px', margin: 0 }}>{s}</span>
                              ))}
                              {!(breakdown.skills?.details?.equivalent_critical_skills?.length) && !(breakdown.skills?.details?.equivalent_nice_skills?.length) && (
                                <span style={{ fontSize: '12px', color: '#9ca3af', fontStyle: 'italic' }}>Không có</span>
                              )}
                            </div>
                          </div> */}

                          {/* Còn thiếu */}
                          <div>
                            <div style={{ fontWeight: '600', fontSize: '13px', color: '#ef4444', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={{ fontSize: '10px' }}></span> Kỹ năng còn thiếu:
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                              {[...(breakdown.skills?.details?.missing_critical_skills || []), ...(breakdown.skills?.details?.missing_nice_skills || [])].map((s, idx) => (
                                <span key={idx} className="badge badge-fail" style={{ fontSize: '12px', padding: '4px 8px', margin: 0 }}>{s}</span>
                              ))}
                              {!(breakdown.skills?.details?.missing_critical_skills?.length) && !(breakdown.skills?.details?.missing_nice_skills?.length) && (
                                <span style={{ fontSize: '12px', color: '#9ca3af', fontStyle: 'italic' }}>Không có</span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>


                      {/* Detailed Scoring Table */}
                      <h4 style={{ marginBottom: '15px' }}>Bảng điểm chi tiết</h4>
                      <div className="table-container" style={{ marginBottom: '20px' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', margin: '16px 0', border: '1px solid #e0e0e0', borderRadius: '8px', overflow: 'hidden', fontSize: '13px' }}>
                          <thead>
                            <tr style={{ background: '#7c3aed', color: 'white' }}>
                              <th style={{ padding: '10px', textAlign: 'left', color: 'white', fontWeight: '600' }}>Tiêu chí</th>
                              <th style={{ padding: '10px', textAlign: 'center', color: 'white', fontWeight: '600', width: '90px' }}>Trọng số</th>
                              <th style={{ padding: '10px', textAlign: 'center', color: 'white', fontWeight: '600', width: '110px' }}>Điểm (thang 100)</th>
                              <th style={{ padding: '10px', textAlign: 'center', color: 'white', fontWeight: '600', width: '110px' }}>Điểm thành phần</th>
                              <th style={{ padding: '10px', textAlign: 'left', color: 'white', fontWeight: '600' }}>Chi tiết</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries({
                              skills: 'Kỹ năng chuyên môn',
                              experience: 'Kinh nghiệm',
                              education: 'Học vấn',
                              language: 'Ngoại ngữ',
                              stability: 'Mức gắn bó'
                            }).map(([key, label], idx) => {
                              const info = breakdown[key] || {};
                              const scVal = (info.score || 0) * 100;
                              const weightPct = (info.weight || 0) * 100;
                              const weightedVal = (info.weighted_score || 0) * 100;

                              const getHtmlReportScoreColor = (val) => {
                                if (val >= 80) return '#22c55e';
                                if (val >= 60) return '#3b82f6';
                                if (val >= 40) return '#f59e0b';
                                return '#ef4444';
                              };

                              const rowBg = idx % 2 === 1 ? '#f8f8ff' : '#ffffff';

                              return (
                                <tr key={key} style={{ background: rowBg }}>
                                  <td style={{ padding: '10px', fontWeight: '600', borderBottom: '1px solid #e0e0e0', color: '#333' }}>{label}</td>
                                  <td style={{ padding: '10px', textAlign: 'center', borderBottom: '1px solid #e0e0e0', color: '#333' }}>{weightPct.toFixed(0)}%</td>
                                  <td style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold', color: getHtmlReportScoreColor(scVal), borderBottom: '1px solid #e0e0e0' }}>{scVal.toFixed(1)}</td>
                                  <td style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold', borderBottom: '1px solid #e0e0e0', color: '#333' }}>{weightedVal.toFixed(1)}</td>
                                  <td style={{ padding: '10px', fontSize: '0.95em', borderBottom: '1px solid #e0e0e0', color: '#333', lineHeight: '1.5' }} dangerouslySetInnerHTML={{ __html: info.details?.reasoning || 'N/A' }}></td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                        <p style={{ fontSize: '0.85em', color: '#666', marginTop: '8px', lineHeight: '1.5' }}>
                          <strong>Ghi chú giải thích cách tính điểm:</strong><br />
                          - <strong>Điểm (thang 100):</strong> Điểm đánh giá độc lập của tiêu chí đó (thang 0-100, không mang ký tự %).<br />
                          - <strong>Điểm thành phần:</strong> Điểm đóng góp của tiêu chí sau khi nhân trọng số (Điểm thành phần = Điểm (thang 100) x Trọng số). Tổng 5 điểm thành phần chính là Điểm Tương thích cuối cùng.
                        </p>
                      </div>

                      {/* Download Buttons */}
                      <div style={{ display: 'flex', gap: '15px', marginTop: '20px' }}>
                        <a 
                          href={api.getHtmlReportUrl(r.id)} 
                          download
                          className="btn btn-secondary" 
                          style={{ flex: 1, textDecoration: 'none', color: 'var(--color-text-main)', textAlign: 'center' }}
                        >
                          Tải báo cáo HTML
                        </a>
                        <a 
                          href={api.getMdReportUrl(r.id)} 
                          download
                          className="btn btn-secondary" 
                          style={{ flex: 1, textDecoration: 'none', color: 'var(--color-text-main)', textAlign: 'center' }}
                        >
                          Tải báo cáo MD
                        </a>
                      </div>

                      {/* Notice */}
                      <div style={{ fontSize: '12px', color: '#9ca3af', textAlign: 'center', marginTop: '15px', fontStyle: 'italic', lineHeight: '1.4' }}>
                        * Tải báo cáo HTML hoặc MD để xem đầy đủ nhận xét tuyển dụng chuyên sâu, rủi ro onboard và bộ câu hỏi phỏng vấn gợi ý (Interview Guide).
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
