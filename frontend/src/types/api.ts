// API Types for SaaS Orchestrator

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  task_id?: string;
}

// Authentication
export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface AdminProfile {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  last_login: string;
}

// VPS Management
export interface VPSHost {
  id: string;
  name: string;
  hostname: string;
  ip_address: string;
  status: 'pending' | 'active' | 'inactive' | 'error' | 'requires_manual_intervention';
  last_ping: string | null;
  last_successful_connection: string | null;
  docker_version: string | null;
  nginx_version: string | null;
  max_odoo_instances: number;
  created_at: string;
  is_healthy: boolean;
}

export interface VPSOnboardRequest {
  name: string;
  hostname: string;
  ip_address: string;
  username: string;
  port?: number;
  password?: string;
  private_key?: string;
  bootstrap?: boolean;
}

export interface VPSHealthResponse {
  success: boolean;
  task_id: string;
  status: string;
  services: {
    nginx?: {
      active: boolean;
      status: string;
    };
    docker?: {
      active: boolean;
      status: string;
    };
  };
}

// Nginx Configuration
export interface NginxConfig {
  id: string;
  version: number;
  author_id: string;
  summary: string | null;
  status: 'draft' | 'applied' | 'rolled_back' | 'failed';
  config_name: string;
  config_type: string;
  applied_at: string | null;
  created_at: string;
  is_active: boolean;
  rollback_triggered: boolean;
}

export interface NginxConfigCreateRequest {
  content: string;
  vps_id: string;
  config_name: string;
  config_type?: string;
  summary?: string;
  template_used?: string;
}

export interface NginxConfigPreviewRequest {
  content: string;
  vps_id: string;
  config_name: string;
  config_type?: string;
}

export interface ValidationResponse {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  task_id: string;
  nginx_test_output?: string;
}

export interface NginxConfigApplyRequest {
  config_id: string;
  dry_run?: boolean;
  scheduled_at?: string;
  watch_window_seconds?: number;
}

export interface NginxConfigRevertRequest {
  vps_id: string;
  target_version?: number;
}

export interface NginxTemplate {
  name: string;
  display_name: string;
  description: string;
  category: string;
  template: string;
}

// Odoo Templates and Deployments
export interface OdooTemplateCreate {
  name: string;
  industry: string;
  version: string;
  description?: string;
  
  // Database backup credentials
  backup_db_name?: string;
  backup_db_user?: string;
  backup_db_password?: string;
  backup_db_host?: string;
  backup_db_port?: number;
  
  // Template configuration
  docker_image?: string;
  default_modules?: string[];
  config_template?: Record<string, any>;
  env_vars_template?: Record<string, any>;
  is_public?: boolean;
  tags?: string[];
  category?: string;
  complexity_level?: 'beginner' | 'intermediate' | 'advanced';
  setup_instructions?: string;
  post_install_script?: string;
  required_addons?: string[];
  screenshots?: string[];
  demo_url?: string;
  documentation_url?: string;
}

export interface OdooTemplate {
  id: string;
  name: string;
  industry: string;
  version: string;
  description?: string;
  is_active: boolean;
  is_public: boolean;
  deployment_count: number;
  download_count: number;
  backup_file_size_mb: number;
  category?: string;
  complexity_level: string;
  tags?: string[];
  created_at: string;
  updated_at: string;
  
  // Database backup info (not exposed for security)
  backup_db_name?: string;
  backup_db_user?: string;
  backup_db_host?: string;
  backup_db_port?: number;
}

export interface OdooDeploymentCreate {
  template_id: string;
  vps_id: string;
  deployment_name: string;
  domain: string;
  selected_version?: string;
  selected_modules?: string[];
  custom_config?: Record<string, any>;
  custom_env_vars?: Record<string, any>;
  admin_password?: string;
}

export interface OdooDeployment {
  id: string;
  template_id: string;
  instance_id?: string;
  vps_id: string;
  deployment_name: string;
  name: string; // Alias for deployment_name for backward compatibility
  domain: string;
  selected_version: string;
  status: string;
  progress: number;
  port: number;
  db_name: string;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds: number;
  deployed_by: string;
  created_at: string;
  
  // Additional fields for UI compatibility
  template_name?: string;
  vps_name?: string;
}

// Monitoring
export interface SystemMetrics {
  active_vps_hosts: number;
  active_odoo_instances: number;
  total_nginx_operations: number;
  failed_nginx_operations: number;
  recent_alerts: number;
}

export interface AlertRequest {
  alert_type: string;
  severity: 'info' | 'warning' | 'critical';
  title: string;
  message: string;
  recipients?: string[];
}

// Audit Logs
export interface AuditLog {
  id: string;
  task_id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  actor_id: string | null;
  actor_ip: string | null;
  description: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
  details: Record<string, any> | null;
  is_sensitive: boolean;
}

export interface AuditLogResponse {
  logs: AuditLog[];
  total_count: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

// Common interfaces
export interface PaginationParams {
  limit?: number;
  offset?: number;
}

export interface FilterParams {
  search?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
}