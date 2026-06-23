import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';

export default function JdManager() {
  const [jds, setJds] = useState([]);
  const [name, setName] = useState('');
  const [content, setContent] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    fetchJds();
  }, []);

  const fetchJds = async () => {
    try {
      const data = await api.getJds();
      setJds(data);
    } catch (err) {
      setError('Không thể tải danh sách JD: ' + err.message);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!name.trim() || !content.trim()) {
      setError('Vui lòng điền đầy đủ tên vị trí và nội dung JD');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      await api.createJd(name, content);
      setSuccess(`Đã lưu JD "${name}" thành công!`);
      setName('');
      setContent('');
      fetchJds();
    } catch (err) {
      setError('Lỗi khi lưu JD: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id, jdName) => {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa JD "${jdName}"?`)) {
      return;
    }

    try {
      await api.deleteJd(id);
      setSuccess(`Đã xóa JD "${jdName}"`);
      fetchJds();
    } catch (err) {
      setError('Lỗi khi xóa JD: ' + err.message);
    }
  };

  const toggleExpand = (id) => {
    setExpandedId(expandedId === id ? null : id);
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
    <div className="jd-manager-container">
      <div className="glass-card">
        <h3>Nhập JD mới</h3>
        <form onSubmit={handleSave} style={{ marginTop: '20px' }}>
          {error && <div className="badge badge-fail" style={{ width: '100%', padding: '10px', marginBottom: '15px' }}>{error}</div>}
          {success && <div className="badge badge-pass" style={{ width: '100%', padding: '10px', marginBottom: '15px' }}>{success}</div>}
          
          <div className="form-group">
            <label className="form-label" htmlFor="jd-name">Tên vị trí tuyển dụng</label>
            <input
              id="jd-name"
              type="text"
              className="form-input"
              placeholder="VD: Senior iOS Developer, Data Analyst, Product Manager..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={loading}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="jd-content">Nội dung mô tả công việc (JD)</label>
            <textarea
              id="jd-content"
              className="form-textarea"
              placeholder="Dán toàn bộ nội dung mô tả công việc, yêu cầu tuyển dụng ở đây..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              disabled={loading}
              required
            />
            {content && <span className="upload-subtext" style={{ display: 'block', marginTop: '5px', textAlign: 'right' }}>{content.length} ký tự</span>}
          </div>

          <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={loading}>
            {loading ? 'Đang phân tích và lưu...' : 'Lưu JD'}
          </button>
        </form>
      </div>

      <div className="glass-card" style={{ marginTop: '30px' }}>
        <h3>Danh sách JD đã lưu</h3>
        <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '15px' }}>
          {jds.length === 0 ? (
            <div className="upload-subtext" style={{ textAlign: 'center', padding: '20px' }}>Chưa có JD nào được lưu. Hãy nhập JD ở phần trên!</div>
          ) : (
            jds.map((jd) => (
              <div key={jd.id} className="expander-container">
                <div className="expander-header" onClick={() => toggleExpand(jd.id)}>
                  <span style={{ fontWeight: '600' }}>{jd.name}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <span className="upload-subtext">{formatDate(jd.created_at)}</span>
                    <span>{expandedId === jd.id ? '▼' : '▶'}</span>
                  </div>
                </div>
                {expandedId === jd.id && (
                  <div className="expander-content">
                    <div style={{ marginBottom: '15px', display: 'flex', gap: '10px', fontSize: '12px' }}>
                      <span className="badge badge-warning">ID: {jd.id.substring(0, 8)}...</span>
                      <span className="badge badge-pass">Độ dài: {jd.content.length} ký tự</span>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Nội dung JD</label>
                      <pre style={{
                        background: '#ffffff',
                        padding: '15px',
                        borderRadius: '8px',
                        overflowX: 'auto',
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'var(--font-family-body)',
                        fontSize: '14px',
                        lineHeight: '1.5',
                        maxHeight: '300px',
                        border: '1px solid var(--border-glass)'
                      }}>{jd.content}</pre>
                    </div>
                    <button
                      className="btn btn-danger"
                      style={{ width: '100%', marginTop: '10px' }}
                      onClick={() => handleDelete(jd.id, jd.name)}
                    >
                      Xóa JD này
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
