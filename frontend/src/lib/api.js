const API_BASE_URL = (window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')) && 
  (window.location.port !== '8080' && window.location.port !== '80' && window.location.port !== '')
  ? 'http://localhost:8000/api'
  : '/api';

/**
 * Helper for fetch requests
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  
  // Set CORS headers
  const defaultHeaders = {
    'Accept': 'application/json',
  };

  const token = localStorage.getItem('ats_token');
  if (token) {
    defaultHeaders['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData) && options.body && typeof options.body === 'object') {
    defaultHeaders['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }

  options.headers = {
    ...defaultHeaders,
    ...options.headers,
  };

  const response = await fetch(url, options);
  
  if (!response.ok) {
    let errorDetail = 'API Request failed';
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorJson.message || errorDetail;
    } catch (e) {
      errorDetail = await response.text() || errorDetail;
    }
    throw new Error(errorDetail);
  }

  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

export const api = {
  // JDs CRUD
  getJds: () => request('/jds'),
  getJd: (id) => request(`/jds/${id}`),
  createJd: (name, content) => request('/jds', {
    method: 'POST',
    body: { name, content }
  }),
  deleteJd: (id) => request(`/jds/${id}`, { method: 'DELETE' }),

  // CV Analysis
  analyzeCvs: (formData) => request('/analyses', {
    method: 'POST',
    body: formData // Form data with file(s) and weights
  }),

  // History
  getAnalyses: (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        query.append(key, val);
      }
    });
    const queryString = query.toString();
    return request(`/analyses${queryString ? `?${queryString}` : ''}`);
  },
  getAnalysis: (id) => request(`/analyses/${id}`),
  deleteAnalysis: (id) => request(`/analyses/${id}`, { method: 'DELETE' }),
  clearAllAnalyses: (confirmText) => {
    const form = new FormData();
    form.append('confirm', confirmText);
    return request('/analyses/clear', {
      method: 'POST',
      body: form
    });
  },

  // Auth
  login: (username, password) => request('/auth/login', {
    method: 'POST',
    body: { username, password }
  }),
  checkSession: () => request('/auth/check'),

  // Report URLs
  getHtmlReportUrl: (analysisId) => {
    const token = localStorage.getItem('ats_token') || '';
    return `${API_BASE_URL}/analyses/${analysisId}/report/html?token=${encodeURIComponent(token)}`;
  },
  getMdReportUrl: (analysisId) => {
    const token = localStorage.getItem('ats_token') || '';
    return `${API_BASE_URL}/analyses/${analysisId}/report/md?token=${encodeURIComponent(token)}`;
  },

  // Interview Bot
  startInterview: (analysisId) => request('/interview/start', {
    method: 'POST',
    body: { analysis_id: analysisId }
  }),
  getInterviewQuestion: (analysisId) => request(`/interview/${analysisId}/question`),
  submitInterviewAnswer: (analysisId, answer) => request(`/interview/${analysisId}/answer`, {
    method: 'POST',
    body: { answer }
  }),
  skipInterviewQuestion: (analysisId) => request(`/interview/${analysisId}/skip`, {
    method: 'POST'
  }),
  getInterviewSummary: (analysisId) => request(`/interview/${analysisId}/summary`),

  // CV Tailoring
  tailorCv: (analysisId, language = 'auto') => request(`/cv/tailor/${analysisId}?language=${language}`, {
    method: 'POST'
  })
};
