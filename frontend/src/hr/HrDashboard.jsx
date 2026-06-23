import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';

export default function HrDashboard({ navigateToAnalyze }) {
  const [jdsCount, setJdsCount] = useState(0);
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const jdData = await api.getJds();
      setJdsCount(jdData.length);

      const recData = await api.getAnalyses();
      setRecords(recData);
    } catch (err) {
      console.error("Lỗi khi tải thông số tổng quan:", err);
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 80) return '#22c55e'; // Green
    if (score >= 65) return '#3b82f6'; // Blue
    if (score >= 50) return '#f59e0b'; // Amber
    return '#ef4444'; // Red
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString("vi-VN", {
        day: "2-digit",
        month: "2-digit",
      });
    } catch (e) {
      return dateStr;
    }
  };

  // Top 5 candidates for bar chart
  const topCandidates = [...records]
    .sort((a, b) => b.total_score - a.total_score)
    .slice(0, 5);

  const avgScore = records.length > 0
    ? Math.round(records.reduce((acc, r) => acc + r.total_score, 0) / records.length)
    : 0;

  const potentialCount = records.filter(r => r.total_score >= 65).length;

  if (loading) {
    return (
      <div className="glass-card" style={{ textAlign: 'center', padding: '50px 20px' }}>
        <div className="spinner"></div>
        <p className="upload-subtext" style={{ marginTop: '10px' }}>Đang tải số liệu thống kê...</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Quick Metrics Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '20px'
      }}>
        {/* Metric 1 */}
        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '15px', padding: '20px', marginBottom: 0 }}>
          {/* <div style={{ background: 'rgba(124, 58, 237, 0.1)', padding: '12px', borderRadius: '10px', fontSize: '24px' }}></div> */}
          <div>
            <div className="upload-subtext" style={{ fontSize: '12px', fontWeight: '600' }}>Vị trí tuyển dụng (JD)</div>
            <div style={{ fontSize: '24px', fontWeight: '800', marginTop: '2px' }}>{jdsCount}</div>
          </div>
        </div>

        {/* Metric 2 */}
        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '15px', padding: '20px', marginBottom: 0 }}>
          {/* <div style={{ background: 'rgba(6, 182, 212, 0.1)', padding: '12px', borderRadius: '10px', fontSize: '24px' }}></div> */}
          <div>
            <div className="upload-subtext" style={{ fontSize: '12px', fontWeight: '600' }}>Hồ sơ CV đã chấm</div>
            <div style={{ fontSize: '24px', fontWeight: '800', marginTop: '2px' }}>{records.length} CV</div>
          </div>
        </div>

        {/* Metric 3 */}
        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '15px', padding: '20px', marginBottom: 0 }}>
          {/* <div style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '12px', borderRadius: '10px', fontSize: '24px' }}></div> */}
          <div>
            <div className="upload-subtext" style={{ fontSize: '12px', fontWeight: '600' }}>Điểm tương thích TB</div>
            <div style={{ fontSize: '24px', fontWeight: '800', color: '#10b981', marginTop: '2px' }}>{avgScore}%</div>
          </div>
        </div>

        {/* Metric 4 */}
        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '15px', padding: '20px', marginBottom: 0 }}>
          {/* <div style={{ background: 'rgba(245, 158, 11, 0.1)', padding: '12px', borderRadius: '10px', fontSize: '24px' }}></div> */}
          <div>
            <div className="upload-subtext" style={{ fontSize: '12px', fontWeight: '600' }}>Ứng viên tiềm năng</div>
            <div style={{ fontSize: '24px', fontWeight: '800', marginTop: '2px' }}>{potentialCount}</div>
          </div>
        </div>
      </div>

      {/* Main Charts & Activity layout */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))',
        gap: '20px'
      }}>
        {/* Top 5 Candidates CSS Bar Chart */}
        <div className="glass-card" style={{ marginBottom: 0 }}>
          <h4 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-muted)', marginBottom: '25px' }}>
            Top 5 ứng viên tương thích cao nhất
          </h4>
          {topCandidates.length > 0 ? (
            <div style={{
              display: 'flex',
              justifyContent: 'space-around',
              alignItems: 'flex-end',
              height: '220px',
              paddingTop: '20px',
              borderBottom: '1px solid var(--border-glass)'
            }}>
              {topCandidates.map((c, idx) => (
                <div key={idx} style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  width: '60px',
                  position: 'relative'
                }}>
                  {/* Score tooltip above the bar */}
                  <span style={{
                    fontSize: '11px',
                    fontWeight: '700',
                    color: getScoreColor(c.total_score),
                    marginBottom: '8px'
                  }}>
                    {c.total_score}%
                  </span>
                  {/* Visual Bar */}
                  <div style={{
                    width: '32px',
                    height: `${c.total_score * 1.5}px`,
                    background: `linear-gradient(180deg, ${getScoreColor(c.total_score)} 0%, rgba(124, 58, 237, 0.1) 100%)`,
                    borderRadius: '6px 6px 0 0',
                    boxShadow: `0 0 10px ${getScoreColor(c.total_score)}22`,
                    transition: 'height 0.8s ease'
                  }}></div>
                  {/* Name below the bar */}
                  <span style={{
                    fontSize: '10px',
                    fontWeight: '600',
                    color: 'var(--color-text-muted)',
                    marginTop: '10px',
                    textAlign: 'center',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    width: '100%'
                  }} title={c.candidate_name}>
                    {c.candidate_name.split(' ').pop()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ height: '220px', display: 'flex', justifyContent: 'center', alignItems: 'center', color: 'var(--color-text-muted)', fontSize: '14px' }}>
              Chưa có dữ liệu phân tích nào được thực hiện.
            </div>
          )}
        </div>

        {/* Recent Activities List */}
        <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', marginBottom: 0 }}>
          <div>
            <h4 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-muted)', marginBottom: '20px' }}>
              Hoạt động gần đây
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '180px', overflowY: 'auto' }}>
              {records.slice(0, 3).map((r, index) => (
                <div key={index} style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--border-glass)',
                  borderRadius: '10px',
                  padding: '12px'
                }}>
                  <div style={{ overflow: 'hidden', marginRight: '10px' }}>
                    <span style={{ fontSize: '13px', fontWeight: '600', display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.candidate_name}</span>
                    <span style={{ fontSize: '10px', color: 'var(--color-text-muted)', display: 'block', marginTop: '2px' }}>
                      {formatDate(r.created_at)} | {r.jd_name}
                    </span>
                  </div>
                  <span style={{ fontSize: '14px', fontWeight: '800', color: getScoreColor(r.total_score) }}>
                    {r.total_score}%
                  </span>
                </div>
              ))}
              {records.length === 0 && (
                <div style={{ textAlign: 'center', padding: '20px', color: 'var(--color-text-muted)', fontSize: '12px' }}>Không có hoạt động gần đây</div>
              )}
            </div>
          </div>

          <button
            className="btn btn-primary"
            onClick={navigateToAnalyze}
            style={{ width: '100%', marginTop: '20px', padding: '10px' }}
          >
            Tiến hành chấm CV mới
          </button>
        </div>
      </div>
    </div>
  );
}
