import axios from 'axios';

const API_BASE_URL = '/api';

export const api = axios.create({
  baseURL: API_BASE_URL,
});

// ── Auth token interceptor ──
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.dispatchEvent(new Event('auth:logout'));
    }
    return Promise.reject(err);
  }
);

// ── Auth API ──
export const login = async (username, password) => {
  const res = await api.post('/auth/login', { username, password });
  const { token, user } = res.data;
  localStorage.setItem('token', token);
  localStorage.setItem('user', JSON.stringify(user));
  return user;
};

export const logout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
};

export const getMe = async () => {
  const res = await api.get('/auth/me');
  return res.data;
};

export const changePassword = async (oldPassword, newPassword) => {
  return api.post('/auth/change-password', { old_password: oldPassword, new_password: newPassword });
};

export const getStoredUser = () => {
  try {
    return JSON.parse(localStorage.getItem('user'));
  } catch {
    return null;
  }
};

export const isLoggedIn = () => !!localStorage.getItem('token');

// ── Admin API ──
export const getUsers = async () => {
  const res = await api.get('/admin/users');
  return res.data.users || [];
};

export const createUser = async (data) => api.post('/admin/users', data);
export const updateUser = async (id, data) => api.put(`/admin/users/${id}`, data);
export const deleteUser = async (id) => api.delete(`/admin/users/${id}`);

// ── Fund API (shared, some public) ──
export const searchFunds = async (query) => {
  try {
    const response = await api.get('/search', { params: { q: query } });
    return response.data;
  } catch (error) {
    console.error("Search failed", error);
    return [];
  }
};

export const getFundDetail = async (fundId) => {
  const response = await api.get(`/fund/${fundId}`);
  return response.data;
};

export const getFundHistory = async (fundId, limit = 30, accountId = null) => {
  try {
    const params = { limit };
    if (accountId) params.account_id = accountId;
    const response = await api.get(`/fund/${fundId}/history`, { params });
    return response.data;
  } catch (error) {
    console.error("Get history failed", error);
    return { history: [], transactions: [] };
  }
};

export const subscribeFund = async (fundId, data) => api.post(`/fund/${fundId}/subscribe`, data);

export const getFundCategories = async () => {
  try {
    const response = await api.get('/categories');
    return response.data.categories || [];
  } catch (error) {
    console.error("Get categories failed", error);
    return [];
  }
};

// ── Account API ──
export const getAccounts = async () => {
  try {
    const response = await api.get('/accounts');
    return response.data.accounts || [];
  } catch (error) {
    console.error("Get accounts failed", error);
    return [];
  }
};

export const createAccount = async (data) => api.post('/accounts', data);
export const updateAccount = async (accountId, data) => api.put(`/accounts/${accountId}`, data);
export const deleteAccount = async (accountId) => api.delete(`/accounts/${accountId}`);

// ── Position API ──
export const getAccountPositions = async (accountId = 1) => {
  const response = await api.get('/account/positions', { params: { account_id: accountId } });
  return response.data;
};

export const updatePosition = async (data, accountId = 1) => {
  return api.post('/account/positions', data, { params: { account_id: accountId } });
};

export const deletePosition = async (code, accountId = 1) => {
  return api.delete(`/account/positions/${code}`, { params: { account_id: accountId } });
};

export const addPositionTrade = async (code, data, accountId = 1) => {
  const response = await api.post(`/account/positions/${code}/add`, data, { params: { account_id: accountId } });
  return response.data;
};

export const reducePositionTrade = async (code, data, accountId = 1) => {
  const response = await api.post(`/account/positions/${code}/reduce`, data, { params: { account_id: accountId } });
  return response.data;
};

export const getTransactions = async (accountId = 1, code = null, limit = 100) => {
  const params = { account_id: accountId, limit };
  if (code) params.code = code;
  const response = await api.get('/account/transactions', { params });
  return response.data.transactions || [];
};

export const updatePositionsNav = async (accountId = 1) => {
  return api.post('/account/positions/update-nav', null, { params: { account_id: accountId } });
};

// ── AI Prompts ──
export const getPrompts = async () => {
  try {
    const response = await api.get('/ai/prompts');
    return response.data.prompts || [];
  } catch (error) {
    console.error("Get prompts failed", error);
    return [];
  }
};

export const createPrompt = async (data) => api.post('/ai/prompts', data);
export const updatePrompt = async (id, data) => api.put(`/ai/prompts/${id}`, data);
export const deletePrompt = async (id) => api.delete(`/ai/prompts/${id}`);

// ── Data import/export ──
export const exportData = async (modules) => {
  try {
    const modulesParam = modules.join(',');
    const response = await api.get(`/data/export?modules=${modulesParam}`, { responseType: 'blob' });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    const contentDisposition = response.headers['content-disposition'];
    let filename = 'fundval_export.json';
    if (contentDisposition) {
      const m = contentDisposition.match(/filename="?(.+)"?/);
      if (m) filename = m[1];
    }
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    return { success: true };
  } catch (error) {
    console.error('Export failed', error);
    throw error;
  }
};

export const importData = async (data, modules, mode) => {
  return api.post('/data/import', { data, modules, mode });
};

// ── Preferences ──
export const getPreferences = async () => {
  try {
    const response = await api.get('/preferences');
    return response.data;
  } catch (error) {
    console.error('Get preferences failed', error);
    return { watchlist: '[]', currentAccount: 1, sortOption: null };
  }
};

export const updatePreferences = async (data) => api.post('/preferences', data);
