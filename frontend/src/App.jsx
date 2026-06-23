import React, { useState, useEffect } from 'react';
import HrDashboard from './hr/HrDashboard';
import CvAnalysis from './hr/CvAnalysis';
import JdManager from './hr/JdManager';
import AnalysisHistory from './hr/AnalysisHistory';
import InterviewChatbot from './candidate/InterviewChatbot';
import CvTailor from './candidate/CvTailor';
import Login from './Login';
import { api } from './lib/api';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('ats_token'));
  const [role, setRole] = useState('HR'); // HR, Candidate
  const [activeTab, setActiveTab] = useState('hr_dashboard'); // hr_dashboard, analysis, jd, history, interview, tailor

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('ats_token');
      if (token) {
        try {
          await api.checkSession();
          setIsAuthenticated(true);
        } catch (err) {
          console.error("Phiên làm việc hết hạn hoặc không hợp lệ:", err);
          localStorage.removeItem('ats_token');
          localStorage.removeItem('ats_user');
          setIsAuthenticated(false);
        }
      }
    };
    checkAuth();
  }, []);

  const handleRoleChange = (newRole) => {
    setRole(newRole);
    if (newRole === 'HR') {
      setActiveTab('hr_dashboard');
    } else {
      setActiveTab('interview');
    }
  };

  // Guide texts depending on active tab
  const getGuideText = () => {
    switch (activeTab) {
      case 'hr_dashboard':
        return (
          <>

          </>
        );
      case 'analysis':
        return (
          <>
            1. Tạo hoặc chọn JD ở tab "Quản lý JD"<br />
            2. Sang tab "Phân tích & Chấm điểm CV"<br />
            3. Upload CV (tối đa 10 file)<br />
            4. Tùy chỉnh trọng số / bộ lọc (nếu cần)<br />
            5. Bấm "Phân tích CV" & Xem kết quả
          </>
        );
      case 'jd':
        return (
          <>
            1. Nhập tên vị trí tuyển dụng mới<br />
            2. Dán nội dung chi tiết Job Description<br />
            3. Bấm "Lưu JD" để lưu vào cơ sở dữ liệu và phân tích cấu trúc bằng AI
          </>
        );
      case 'history':
        return (
          <>
            1. Xem danh sách CV đã phân tích từ trước<br />
            2. Sử dụng bộ lọc nâng cao để lọc theo trường ĐH, điểm số, kỹ năng, bằng cấp, ngoại ngữ hoặc mức gắn bó<br />
            3. Bấm xem chi tiết hoặc xóa bản ghi
          </>
        );
      case 'interview':
        return (
          <>
            1. Tải lên CV của bạn hoặc chọn kết quả phân tích cũ<br />
            2. Chọn vị trí công việc ứng tuyển (JD)<br />
            3. Bấm "Bắt đầu phỏng vấn"<br />
            4. Trả lời chi tiết từng câu hỏi do AI tạo ra để được đánh giá real-time
          </>
        );
      case 'tailor':
        return (
          <>
            1. Tải lên CV của bạn hoặc chọn kết quả phân tích cũ<br />
            2. Chọn vị trí công việc ứng tuyển (JD)<br />
            3. Bấm "Tiếp tục" để xem độ tương thích và kỹ năng thiếu<br />
            4. Bấm "Tối ưu CV ngay" để AI viết lại CV và sinh Thư xin việc
          </>
        );
      default:
        return '';
    }
  };

  const getPageHeader = () => {
    switch (activeTab) {
      case 'hr_dashboard':
        return {
          title: 'Tổng quan Dashboard',
          // desc: 'Số liệu thống kê nhanh và phân tích tổng hợp các CV ứng viên ứng tuyển'
        };
      case 'analysis':
        return {
          title: 'Phân tích & chấm điểm CV',
          // desc: 'Thực hiện phân tích độ tương thích và chấm điểm hàng loạt hồ sơ ứng viên'
        };
      case 'jd':
        return {
          title: 'Quản lý JD',
          // desc: 'Nhập và quản lý các mô tả công việc của các vị trí tuyển dụng trong hệ thống'
        };
      case 'history':
        return {
          title: 'Lịch sử phân tích',
          // desc: 'Xem lại kết quả đánh giá và bộ lọc nâng cao của các CV đã lưu trong hệ thống'
        };
      case 'interview':
        return {
          title: 'Luyện tập phỏng vấn với AI',
          // desc: 'Mô phỏng buổi phỏng vấn tuyển dụng thực tế dựa trên thông tin CV và JD của bạn'
        };
      case 'tailor':
        return {
          title: 'Tối ưu hóa CV',
          // desc: 'Tối ưu cấu trúc, từ khóa và cách diễn đạt trong CV để gia tăng điểm số vượt qua vòng lọc CV'
        };
      default:
        return { title: 'Hệ thống ATS', desc: 'Hệ thống tuyển dụng thông minh' };
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('ats_token');
    localStorage.removeItem('ats_user');
    setIsAuthenticated(false);
  };

  if (!isAuthenticated) {
    return <Login onLoginSuccess={() => setIsAuthenticated(true)} />;
  }

  const header = getPageHeader();

  return (
    <div className={`app-container ${role === 'HR' ? 'theme-hr' : 'theme-candidate'}`} style={{ flexDirection: 'column' }}>
      
      {/* Top Level Roles Tab Bar */}
      <div className="top-tab-bar">
        <div 
          className={`top-tab-item ${role === 'Candidate' ? 'active-candidate' : ''}`}
          onClick={() => handleRoleChange('Candidate')}
        >
          Ứng viên
        </div>
        <div 
          className={`top-tab-item ${role === 'HR' ? 'active-hr' : ''}`}
          onClick={() => handleRoleChange('HR')}
        >
          HR - Nhà tuyển dụng
        </div>
        <div 
          className="top-tab-item logout-btn"
          style={{ marginLeft: 'auto', color: '#dc2626', fontWeight: '500' }}
          onClick={handleLogout}
        >
          Đăng xuất
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, width: '100%' }}>
        {/* Sidebar Navigation */}
        <aside className="sidebar" style={{ top: '60px', height: 'calc(100vh - 60px)' }}>
          <div className="sidebar-brand">
            <span className="sidebar-logo">ATS Platform</span>
            <span className="sidebar-subtitle">
              {role === 'HR' ? 'Chế độ nhà tuyển dụng (HR)' : 'Chế độ Ứng viên'}
            </span>
          </div>

          <div className="sidebar-divider"></div>

          <div className="sidebar-group">
            <div className="sidebar-section-title">Chức năng</div>
            <nav className="sidebar-nav">
              {role === 'HR' ? (
                <>
                  <div 
                    className={`nav-item ${activeTab === 'hr_dashboard' ? 'active' : ''}`}
                    onClick={() => setActiveTab('hr_dashboard')}
                  >
                    <span className="nav-item-icon"></span>
                    <span>Tổng quan Dashboard</span>
                  </div>
                  <div 
                    className={`nav-item ${activeTab === 'analysis' ? 'active' : ''}`}
                    onClick={() => setActiveTab('analysis')}
                  >
                    <span className="nav-item-icon"></span>
                    <span>Phân tích & Chấm điểm</span>
                  </div>
                  <div 
                    className={`nav-item ${activeTab === 'jd' ? 'active' : ''}`}
                    onClick={() => setActiveTab('jd')}
                  >
                    <span className="nav-item-icon"></span>
                    <span>Quản lý JD</span>
                  </div>
                  <div 
                    className={`nav-item ${activeTab === 'history' ? 'active' : ''}`}
                    onClick={() => setActiveTab('history')}
                  >
                    <span className="nav-item-icon"></span>
                    <span>Lịch sử Phân tích</span>
                  </div>
                </>
              ) : (
                <>
                  <div 
                    className={`nav-item ${activeTab === 'interview' ? 'active' : ''}`}
                    onClick={() => setActiveTab('interview')}
                  >
                    <span className="nav-item-icon"></span>
                    <span>Luyện tập phỏng vấn</span>
                  </div>
                  <div 
                    className={`nav-item ${activeTab === 'tailor' ? 'active' : ''}`}
                    onClick={() => setActiveTab('tailor')}
                  >
                    <span className="nav-item-icon"></span>
                    <span>Tối ưu CV & Cover Letter</span>
                  </div>
                </>
              )}
            </nav>
          </div>

          {/* Guides section */}
          {/* <div className="glass-card" style={{ marginTop: '30px', padding: '15px', borderRadius: '10px', background: 'rgba(255,255,255,0.01)', border: '1px dashed var(--border-glass)' }}>
            <div style={{ fontWeight: '600', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-primary-light)', marginBottom: '8px' }}>💡 Hướng dẫn nhanh</div>
            <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', lineHeight: '1.6' }}>
              {getGuideText()}
            </div>
          </div> */}

          {/* <div className="sidebar-footer">
            ĐANC 20262 — Đồ án tốt nghiệp
          </div> */}
        </aside>

        {/* Main Content Pane */}
        <main className="main-content" style={{ marginTop: '20px' }}>
          <header className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h2 className="page-title">{header.title}</h2>
              <p className="page-description">{header.desc}</p>
            </div>
            
            <div className="badge badge-pass" style={{ 
              fontSize: '12px', 
              padding: '8px 16px', 
              borderRadius: '20px',
              background: role === 'HR' ? 'rgba(124, 58, 237, 0.1)' : 'rgba(37, 99, 235, 0.1)',
              color: role === 'HR' ? '#9061f3' : '#3b82f6',
              borderColor: role === 'HR' ? 'rgba(124, 58, 237, 0.2)' : 'rgba(37, 99, 235, 0.2)'
            }}>
              {/* {role === 'HR' ? '💼 HR Portal' : '👤 Candidate Portal'} */}
            </div>
          </header>

          {/* Active Page View Rendering */}
          {activeTab === 'hr_dashboard' && <HrDashboard navigateToAnalyze={() => setActiveTab('analysis')} />}
          {activeTab === 'analysis' && <CvAnalysis />}
          {activeTab === 'jd' && <JdManager />}
          {activeTab === 'history' && <AnalysisHistory />}
          {activeTab === 'interview' && <InterviewChatbot />}
          {activeTab === 'tailor' && <CvTailor />}
        </main>
      </div>
    </div>
  );
}
