import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';

export default function AnalysisHistory() {
  const [jds, setJds] = useState([]);
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [detailsCache, setDetailsCache] = useState({});

  // Filters State
  const [jdFilter, setJdFilter] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [filterStatus, setFilterStatus] = useState('all');
  
  // Advanced filters state
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [uniFilter, setUniFilter] = useState('');
  const [minExp, setMinExp] = useState(0);
  const [skillsFilter, setSkillsFilter] = useState('');
  const [minDegree, setMinDegree] = useState('none');
  const [minStability, setMinStability] = useState(0);
  const [langName, setLangName] = useState('');
  const [langLevel, setLangLevel] = useState('');

  useEffect(() => {
    fetchJds();
    fetchAnalyses();
  }, []);

  // Fetch when filters change
  useEffect(() => {
    fetchAnalyses();
  }, [jdFilter, minScore, filterStatus, uniFilter, minExp, skillsFilter, minDegree, minStability, langName, langLevel]);

  const fetchJds = async () => {
    try {
      const data = await api.getJds();
      setJds(data);
    } catch (err) {
      console.error('Lỗi tải JDs:', err);
    }
  };

  const fetchAnalyses = async () => {
    setLoading(true);
    try {
      const params = {
        jd_id: jdFilter || undefined,
        min_score: minScore > 0 ? minScore : undefined,
        filter_status: filterStatus,
        uni_filter: uniFilter || undefined,
        min_exp: minExp > 0 ? minExp : undefined,
        required_skills: skillsFilter || undefined,
        min_degree: minDegree !== 'none' ? minDegree : undefined,
        min_stability: minStability > 0 ? minStability : undefined,
        lang_name: langName || undefined,
        lang_level: langLevel || undefined
      };
      const data = await api.getAnalyses(params);
      setAnalyses(data);
    } catch (err) {
      setError('Lỗi tải lịch sử phân tích: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFetchDetail = async (id) => {
    if (detailsCache[id]) {
      setExpandedId(expandedId === id ? null : id);
      return;
    }

    try {
      const detail = await api.getAnalysis(id);
      setDetailsCache(prev => ({
        ...prev,
        [id]: detail
      }));
      setExpandedId(id);
    } catch (err) {
      setError('Lỗi tải chi tiết CV: ' + err.message);
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa bản ghi của "${name}"?`)) {
      return;
    }

    try {
      await api.deleteAnalysis(id);
      setSuccess(`Đã xóa bản ghi của "${name}" thành công!`);
      // Remove from lists
      setAnalyses(prev => prev.filter(a => a.id !== id));
      if (expandedId === id) setExpandedId(null);
    } catch (err) {
      setError('Lỗi khi xóa bản ghi: ' + err.message);
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm("Bạn có chắc chắn muốn xóa vĩnh viễn toàn bộ kết quả phân tích CV đã lưu trong hệ thống? Hành động này không thể hoàn tác.")) {
      return;
    }

    try {
      const res = await api.clearAllAnalyses('XOA TAT CA');
      setSuccess(res.message);
      setAnalyses([]);
      setDetailsCache({});
      setExpandedId(null);
    } catch (err) {
      setError('Lỗi khi xóa toàn bộ: ' + err.message);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 85) return '#22c55e';
    if (score >= 70) return '#3b82f6';
    if (score >= 50) return '#f59e0b';
    return '#ef4444';
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      const d = new Date(dateString);
      return d.toLocaleString('vi-VN', { hour12: false });
    } catch (e) {
      return dateString;
    }
  };

  return (
    <div className="analysis-history-container">
      {/* Filters Form */}
      <div className="glass-card">
        <h3>Bộ lọc Tìm kiếm</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px', marginTop: '20px' }}>
          <div className="form-group">
            <label className="form-label">Lọc theo JD</label>
            <select className="form-select" value={jdFilter} onChange={e => setJdFilter(e.target.value)}>
              <option value="">— Tất cả JD —</option>
              {jds.map(jd => <option key={jd.id} value={jd.id}>{jd.name}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Điểm số tối thiểu</label>
            <input 
              type="number" 
              className="form-input" 
              value={minScore} 
              onChange={e => setMinScore(parseInt(e.target.value) || 0)} 
              min="0" 
              max="100" 
            />
          </div>

          <div className="form-group">
            <label className="form-label">Trạng thái bộ lọc</label>
            <select className="form-select" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
              <option value="all">— Tất cả —</option>
              <option value="pass">Đạt bộ lọc</option>
              <option value="fail">Không đạt bộ lọc</option>
            </select>
          </div>
        </div>

        {/* Advanced Filters Accordion */}
        <div className="expander-container" style={{ marginTop: '15px' }}>
          <div 
            className="expander-header" 
            onClick={() => setShowAdvanced(!showAdvanced)}
            style={{ background: 'rgba(255,255,255,0.01)', border: '2px solid var(--border-glass)' }}
          >
            <span>Bộ lọc Nâng cao (Tùy chọn)</span>
            <span>{showAdvanced ? '▼' : '▶'}</span>
          </div>
          
          {showAdvanced && (
            <div className="expander-content" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', backgroundColor: '#f2f1f1', padding: '20px'}}>
              <div>
                <div className="form-group">
                  <label className="form-label">Trường ĐH (phân tách bằng dấu phẩy)</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    placeholder="VD: Bách Khoa, FPT, RMIT" 
                    value={uniFilter} 
                    onChange={e => setUniFilter(e.target.value)} 
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Kinh nghiệm tối thiểu (năm)</label>
                  <input 
                    type="number" 
                    className="form-input" 
                    step="0.5" 
                    value={minExp} 
                    onChange={e => setMinExp(parseFloat(e.target.value) || 0)} 
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Kỹ năng bắt buộc (phân tách bằng dấu phẩy)</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    placeholder="VD: Python, SQL, AWS" 
                    value={skillsFilter} 
                    onChange={e => setSkillsFilter(e.target.value)} 
                  />
                </div>
              </div>

              <div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                  <div className="form-group">
                    <label className="form-label">Ngoại ngữ</label>
                    <select className="form-select" value={langName} onChange={e => setLangName(e.target.value)}>
                      <option value="">— Chọn ngoại ngữ —</option>
                      {['English', 'Japanese', 'Chinese', 'Korean', 'French', 'German'].map(l => <option key={l} value={l}>{l}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Trình độ tối thiểu</label>
                    <select className="form-select" value={langLevel} onChange={e => setLangLevel(e.target.value)}>
                      <option value="">— Chọn trình độ —</option>
                      <option value="basic">Sơ cấp</option>
                      <option value="conversational">Giao tiếp</option>
                      <option value="fluent">Thông thạo</option>
                      <option value="native">Bản ngữ</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Bằng cấp tối thiểu</label>
                  <select className="form-select" value={minDegree} onChange={e => setMinDegree(e.target.value)}>
                    <option value="none">— Không lọc bằng cấp —</option>
                    <option value="associate">Cao đẳng</option>
                    <option value="bachelor">Cử nhân</option>
                    <option value="master">Thạc sĩ</option>
                    <option value="phd">Tiến sĩ</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Mức gắn bó tối thiểu: {minStability}%</label>
                  <input 
                    type="range" 
                    min="0" 
                    max="100" 
                    step="5" 
                    style={{ width: '100%', accentColor: 'var(--color-primary-light)' }} 
                    value={minStability} 
                    onChange={e => setMinStability(parseInt(e.target.value))} 
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {error && <div className="badge badge-fail" style={{ width: '100%', padding: '10px', margin: '20px 0' }}>{error}</div>}
      {success && <div className="badge badge-pass" style={{ width: '100%', padding: '10px', margin: '20px 0' }}>{success}</div>}

      {/* Results List */}
      <div className="glass-card" style={{ marginTop: '30px' }}>
        <h3>Danh sách ({analyses.length} kết quả)</h3>
        
        {loading && <div className="spinner" style={{ margin: '30px auto' }}></div>}
        
        {!loading && analyses.length === 0 ? (
          <div className="upload-subtext" style={{ textAlign: 'center', padding: '30px' }}>Không có dữ liệu phân tích nào phù hợp với bộ lọc.</div>
        ) : (
          <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '15px' }}>
            {analyses.map((a, idx) => {
              const isExpanded = expandedId === a.id;
              const detail = detailsCache[a.id];
              const filterPassResult = a.filter_results && a.filter_results.details;

              return (
                <div key={a.id} className="expander-container">
                  <div className="expander-header" onClick={() => handleFetchDetail(a.id)}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                      <span style={{ fontWeight: '700', fontSize: '15px' }}>{a.candidate_name}</span>
                      <span className="upload-subtext" style={{ fontSize: '12px' }}>{a.filename}</span>
                      <span className="badge badge-warning" style={{ fontSize: '10px' }}>{a.jd_name}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                      {filterPassResult && (
                        <span className={`badge ${a.filter_results.passed ? 'badge-pass' : 'badge-fail'}`} style={{ fontSize: '10px' }}>
                          {a.filter_results.passed ? 'Đạt lọc' : 'Không đạt'}
                        </span>
                      )}
                      <span style={{ fontWeight: '800', color: getScoreColor(a.total_score) }}>{a.total_score}%</span>
                      <span>{isExpanded ? '▼' : '▶'}</span>
                    </div>
                  </div>

                  {isExpanded && detail && (
                    <div className="expander-content" style={{ background: 'var(--bg-secondary)', padding: '20px' }}>
                      {/* Meta elements */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '14px', marginBottom: '20px' }}>
                        <div><strong>Ứng viên:</strong> {detail.candidate_name}</div>
                        <div><strong>Email:</strong> {detail.email || 'Không có'}</div>
                        <div><strong>Ngày phân tích:</strong> {formatDate(detail.created_at)}</div>
                        <div><strong>File:</strong> {detail.filename}</div>
                        <div style={{ gridColumn: 'span 2' }}>
                          <strong>Học vấn:</strong> {
                            (detail.resume_data?.educations || []).map(edu => 
                              `${edu.school || 'N/A'} (${edu.degree || 'none'} - ${edu.major || 'N/A'}${edu.gpa ? `, GPA: ${edu.gpa}` : ''})`
                            ).join(' | ') || 'N/A'
                          }
                        </div>
                      </div>

                      {/* Display Score box */}
                      <div style={{ display: 'flex', justifyContent: 'center', margin: '20px 0' }}>
                        <div className="score-circle-container" style={{ width: '100%', maxWidth: '350px', border: '1px solid var(--border-glass)', borderRadius: '12px' }}>
                          <div className="score-circle" style={{ width: '120px', height: '120px', borderColor: getScoreColor(detail.total_score) }}>
                            <span className="score-number" style={{ fontSize: '32px', color: getScoreColor(detail.total_score) }}>
                              {detail.total_score}
                            </span>
                          </div>
                          <div style={{ textAlign: 'center', fontWeight: '500', fontSize: '14px' }}>{detail.recommendation}</div>
                        </div>
                      </div>

                      {/* Thẻ tag/badge kỹ năng */}
                      <h5 style={{ marginBottom: '10px', fontSize: '14px'}}>Đánh giá nhanh kỹ năng của ứng viên</h5>
                      <div className="glass-card" style={{ marginTop: '15px', padding: '15px', marginBottom: '15px' }}>                        
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                          {/* Đã đạt */}
                          <div>
                            <div style={{ fontWeight: '600', fontSize: '12px', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <span style={{ fontSize: '9px' }}></span> Kỹ năng đã đạt:
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                              {[...(detail.scoring_breakdown.skills?.details?.matched_critical_skills || []), ...(detail.scoring_breakdown.skills?.details?.matched_nice_skills || [])].map((s, idx) => (
                                <span key={idx} className="badge badge-pass" style={{ fontSize: '11px', padding: '3px 6px', margin: 0 }}>{s}</span>
                              ))}
                              {[...(detail.scoring_breakdown.skills?.details?.equivalent_critical_skills || []), ...(detail.scoring_breakdown.skills?.details?.equivalent_nice_skills || [])].map((s, idx) => (
                                <span key={idx} className="badge badge-pass" style={{ fontSize: '11px', padding: '3px 6px', margin: 0 }}>{s}</span>
                              ))}
                              {!(detail.scoring_breakdown.skills?.details?.matched_critical_skills?.length) && !(detail.scoring_breakdown.skills?.details?.matched_nice_skills?.length) && (
                                <span style={{ fontSize: '11px', color: '#9ca3af', fontStyle: 'italic' }}>Không có</span>
                              )}
                            </div>
                          </div>

                          {/* Tương đương
                          <div>
                            <div style={{ fontWeight: '600', fontSize: '12px', color: '#10b981', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <span style={{ fontSize: '9px' }}></span> Kỹ năng tương đương:
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                              {[...(detail.scoring_breakdown.skills?.details?.equivalent_critical_skills || []), ...(detail.scoring_breakdown.skills?.details?.equivalent_nice_skills || [])].map((s, idx) => (
                                <span key={idx} className="badge badge-pass" style={{ fontSize: '11px', padding: '3px 6px', margin: 0 }}>{s}</span>
                              ))}
                              {!(detail.scoring_breakdown.skills?.details?.equivalent_critical_skills?.length) && !(detail.scoring_breakdown.skills?.details?.equivalent_nice_skills?.length) && (
                                <span style={{ fontSize: '11px', color: '#9ca3af', fontStyle: 'italic' }}>Không có</span>
                              )}
                            </div>
                          </div> */}

                          {/* Còn thiếu */}
                          <div>
                            <div style={{ fontWeight: '600', fontSize: '12px', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <span style={{ fontSize: '9px' }}></span> Kỹ năng còn thiếu:
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                              {[...(detail.scoring_breakdown.skills?.details?.missing_critical_skills || []), ...(detail.scoring_breakdown.skills?.details?.missing_nice_skills || [])].map((s, idx) => (
                                <span key={idx} className="badge badge-fail" style={{ fontSize: '11px', padding: '3px 6px', margin: 0 }}>{s}</span>
                              ))}
                              {!(detail.scoring_breakdown.skills?.details?.missing_critical_skills?.length) && !(detail.scoring_breakdown.skills?.details?.missing_nice_skills?.length) && (
                                <span style={{ fontSize: '11px', color: '#9ca3af', fontStyle: 'italic' }}>Không có</span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>


                      {/* Score table */}
                      <h5 style={{ marginBottom: '10px', fontSize: '14px'}}>Bảng điểm chi tiết</h5>
                      <div className="table-container" style={{ marginBottom: '20px' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', margin: '16px 0', border: '1px solid #e0e0e0', borderRadius: '8px', overflow: 'hidden', fontSize: '13px' }}>
                          <thead>
                            <tr style={{ background: '#7c3aed', color: 'white' }}>
                              <th style={{ padding: '10px', textAlign: 'left', color: 'white', fontWeight: '600' }}>Tiêu chí</th>
                              <th style={{ padding: '10px', textAlign: 'center', color: 'white', fontWeight: '600', width: '80px' }}>Trọng số</th>
                              <th style={{ padding: '10px', textAlign: 'center', color: 'white', fontWeight: '600', width: '90px' }}>Điểm (thang 100)</th>
                              <th style={{ padding: '10px', textAlign: 'center', color: 'white', fontWeight: '600', width: '90px' }}>Điểm thành phần</th>
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
                              const info = detail.scoring_breakdown[key] || {};
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

                      {/* Advanced filters feedback details */}
                      {detail.filter_results && detail.filter_results.details && (
                        <div style={{ marginBottom: '20px' }}>
                          <h5 style={{ marginBottom: '10px' }}>Kết quả Bộ lọc Nâng cao</h5>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {detail.filter_results.details.map((fd, fIdx) => (
                              <div key={fIdx} className={`badge ${fd.passed ? 'badge-pass' : 'badge-fail'}`} style={{ display: 'inline-block', width: 'fit-content', textTransform: 'none' }}>
                                {fd.reason}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Download and actions */}
                      <div style={{ display: 'flex', gap: '15px', marginTop: '15px' }}>
                        <a href={api.getHtmlReportUrl(detail.id)} download className="btn btn-secondary" style={{ flex: 1, textDecoration: 'none', color: '#000000', fontSize: '13px', textAlign: 'center' }}>Tải báo cáo HTML</a>
                        <a href={api.getMdReportUrl(detail.id)} download className="btn btn-secondary" style={{ flex: 1, textDecoration: 'none', color: '#000000', fontSize: '13px', textAlign: 'center' }}>Tải báo cáo MD</a>
                        <button className="btn btn-danger" style={{ flex: 1, fontSize: '13px' }} onClick={() => handleDelete(detail.id, detail.candidate_name)}>Xóa bản ghi này</button>
                      </div>

                      {/* Notice */}
                      <div style={{ fontSize: '11px', color: '#77787b', textAlign: 'center', marginTop: '12px', fontStyle: 'italic', lineHeight: '1.4' }}>
                        Tải báo cáo HTML hoặc MD để xem đầy đủ nhận xét tuyển dụng chuyên sâu, rủi ro onboard và bộ câu hỏi phỏng vấn gợi ý (Interview Guide).
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Clear All Data Section */}
      <div className="glass-card" style={{ marginTop: '40px', borderColor: 'rgba(239, 68, 68, 0.2)', padding: '25px' }}>
        <p className="upload-subtext" style={{ margin: '0 0 15px 0', fontSize: '14px', color: '#e53e3e', fontWeight: '500' }}>
          Lưu ý: Hành động này sẽ xóa vĩnh viễn toàn bộ kết quả phân tích CV đã lưu trong hệ thống. Không thể khôi phục!
        </p>
        <button type="button" className="btn btn-danger" onClick={handleClearAll}>
          Xóa tất cả bản ghi
        </button>
      </div>
    </div>
  );
}
