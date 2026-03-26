import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API_BASE = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health & Status
export const getHealth = () => api.get('/health');
export const getStatus = () => api.get('/status');

// Tools
export const getTools = (params) => api.get('/tools', { params });
export const getTool = (id) => api.get(`/tools/${id}`);
export const createTool = (data) => api.post('/tools', data);
export const updateTool = (id, data) => api.put(`/tools/${id}`, data);
export const deleteTool = (id) => api.delete(`/tools/${id}`);
export const searchTools = (query) => api.get(`/tools/search/${query}`);

// Executions
export const getExecutions = (params) => api.get('/executions', { params });
export const getExecution = (id) => api.get(`/executions/${id}`);
export const createExecution = (data) => api.post('/executions', data);
export const executeToolNow = (id) => api.post(`/executions/${id}/execute`);
export const cancelExecution = (id) => api.post(`/executions/${id}/cancel`);

// Approvals
export const getApprovals = (params) => api.get('/approvals', { params });
export const getPendingApprovals = (params) => api.get('/approvals/pending', { params });
export const getApproval = (id) => api.get(`/approvals/${id}`);
export const respondToApproval = (id, data) => api.post(`/approvals/${id}/respond`, data);

// Logs
export const getLogs = (params) => api.get('/logs', { params });
export const getRecentLogs = (params) => api.get('/logs/recent', { params });

// Monitor
export const getMonitorStatus = () => api.get('/monitor/status');
export const startMonitor = () => api.post('/monitor/start');
export const stopMonitor = () => api.post('/monitor/stop');
export const analyzeText = (data) => api.post('/monitor/analyze', data);

export default api;
