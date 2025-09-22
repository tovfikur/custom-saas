import axios, { AxiosResponse } from 'axios';
import toast from 'react-hot-toast';
import type {
  ApiResponse,
  LoginRequest,
  TokenResponse,
  AdminProfile,
  VPSHost,
  VPSOnboardRequest,
  VPSHealthResponse,
  NginxConfig,
  NginxConfigCreateRequest,
  NginxConfigPreviewRequest,
  ValidationResponse,
  NginxConfigApplyRequest,
  NginxConfigRevertRequest,
  NginxTemplate,
  SystemMetrics,
  AlertRequest,
  AuditLogResponse,
  PaginationParams,
  FilterParams,
  OdooTemplate,
  OdooDeployment,
  OdooDeploymentCreate
} from '@/types/api';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://odoo-bangladesh.com';

// Create axios instance
const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 30000,
});

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear auth token and redirect to login
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    
    const errorMessage = error.response?.data?.error || error.message || 'An error occurred';
    console.error('API Error:', error);
    
    // Show toast for non-auth errors
    if (error.response?.status !== 401) {
      toast.error(errorMessage);
    }
    
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  login: (credentials: LoginRequest): Promise<AxiosResponse<TokenResponse>> =>
    api.post('/auth/login', new URLSearchParams({
      username: credentials.username,
      password: credentials.password
    }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    }),

  getProfile: (): Promise<AxiosResponse<AdminProfile>> =>
    api.get('/auth/me'),
};

// VPS Management API
export const vpsApi = {
  list: (activeOnly = false): Promise<AxiosResponse<VPSHost[]>> =>
    api.get('/vps', { params: { active_only: activeOnly } }),

  get: (id: string): Promise<AxiosResponse<any>> =>
    api.get(`/vps/${id}`),

  onboard: (data: VPSOnboardRequest): Promise<AxiosResponse<ApiResponse>> =>
    api.post('/vps/onboard', data),

  bootstrap: (id: string): Promise<AxiosResponse<ApiResponse>> =>
    api.post(`/vps/${id}/bootstrap`),

  checkHealth: (id: string): Promise<AxiosResponse<VPSHealthResponse>> =>
    api.post(`/vps/${id}/health`),

  delete: (id: string): Promise<AxiosResponse<ApiResponse>> =>
    api.delete(`/vps/${id}`),
};

// Nginx Configuration API
export const nginxApi = {
  listConfigs: (vpsId: string): Promise<AxiosResponse<NginxConfig[]>> =>
    api.get(`/vps/${vpsId}/nginx/configs`),

  getConfig: (vpsId: string, version: number, maskSensitive = true): Promise<AxiosResponse<any>> =>
    api.get(`/vps/${vpsId}/nginx/configs/${version}`, { 
      params: { mask_sensitive: maskSensitive }
    }),

  previewConfig: (vpsId: string, data: NginxConfigPreviewRequest): Promise<AxiosResponse<ValidationResponse>> =>
    api.post(`/vps/${vpsId}/nginx/preview`, data),

  createConfig: (vpsId: string, data: NginxConfigCreateRequest): Promise<AxiosResponse<ApiResponse>> =>
    api.post(`/vps/${vpsId}/nginx/configs`, data),

  applyConfig: (vpsId: string, data: NginxConfigApplyRequest): Promise<AxiosResponse<ApiResponse>> =>
    api.post(`/vps/${vpsId}/nginx/apply`, data),

  revertConfig: (vpsId: string, data: NginxConfigRevertRequest): Promise<AxiosResponse<ApiResponse>> =>
    api.post(`/vps/${vpsId}/nginx/revert`, data),

  getStatus: (vpsId: string): Promise<AxiosResponse<any>> =>
    api.get(`/vps/${vpsId}/nginx/status`),

  getTemplates: (): Promise<AxiosResponse<{ templates: NginxTemplate[] }>> =>
    api.get('/nginx/templates'),
};

// Monitoring API
export const monitoringApi = {
  getMetrics: (): Promise<AxiosResponse<string>> =>
    api.get('/monitoring/metrics'),

  getSystemMetrics: (): Promise<AxiosResponse<SystemMetrics>> =>
    api.get('/monitoring/system-metrics'),

  sendAlert: (data: AlertRequest): Promise<AxiosResponse<ApiResponse>> =>
    api.post('/monitoring/alerts/send', data),

  testAlerts: (): Promise<AxiosResponse<ApiResponse>> =>
    api.get('/monitoring/alerts/test'),

  getHealth: (): Promise<AxiosResponse<any>> =>
    api.get('/monitoring/health'),

  getRecentAuditLogs: (params: PaginationParams & FilterParams = {}): Promise<AxiosResponse<AuditLogResponse>> =>
    api.get('/monitoring/audit/recent', { params }),
};

// Odoo API
export const odooApi = {
  getTemplates: (params: { is_public?: boolean; industry?: string; version?: string; category?: string; complexity_level?: string } = {}): Promise<AxiosResponse<{ templates: OdooTemplate[]; total: number; page: number; per_page: number }>> =>
    api.get('/odoo/templates', { params }),
    getVpsHosts: () => vpsApi.list(),
  createTemplate: (data: FormData): Promise<AxiosResponse<OdooTemplate>> =>
    api.post('/odoo/templates', data, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    }),

  deleteTemplate: (templateId: string): Promise<AxiosResponse<ApiResponse>> =>
    api.delete(`/odoo/templates/${templateId}`),

  getDeployments: (): Promise<AxiosResponse<{ deployments: OdooDeployment[] }>> =>
    api.get('/odoo/deployments'),

  deployOdoo: (data: OdooDeploymentCreate): Promise<AxiosResponse<OdooDeployment>> =>
    api.post('/odoo/deployments', data),
};

// Generic API wrapper
export const apiClient = {
  get: <T = any>(url: string, params?: any): Promise<AxiosResponse<T>> =>
    api.get(url, { params }),

  post: <T = any>(url: string, data?: any): Promise<AxiosResponse<T>> =>
    api.post(url, data),

  put: <T = any>(url: string, data?: any): Promise<AxiosResponse<T>> =>
    api.put(url, data),

  delete: <T = any>(url: string): Promise<AxiosResponse<T>> =>
    api.delete(url),
};

export default api;