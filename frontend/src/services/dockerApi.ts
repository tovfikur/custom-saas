import { apiClient } from '@/services/api';

export interface DockerStatus {
  success: boolean;
  status: string;
  version: string;
  containers_running: number;
  containers_total: number;
  images_count: number;
  system_info: Record<string, any>;
}

export interface ContainerInfo {
  id: string;
  name: string;
  image: string;
  status: string;
  created: string;
  ports: string[];
  labels: Record<string, string>;
}

export interface ContainersResponse {
  success: boolean;
  containers: ContainerInfo[];
}

export interface ImageInfo {
  id: string;
  repository: string;
  tag: string;
  created: string;
  size: string;
}

export interface ImagesResponse {
  success: boolean;
  images: ImageInfo[];
}

export const dockerApi = {
  // Get Docker status
  getStatus: (vpsId: string) =>
    apiClient.get<DockerStatus>(`/vps/${vpsId}/docker/status`),

  // Get containers
  getContainers: (vpsId: string, allContainers = false) =>
    apiClient.get<ContainersResponse>(`/vps/${vpsId}/docker/containers`, { all_containers: allContainers }),

  // Container actions
  containerAction: (vpsId: string, containerId: string, action: string) =>
    apiClient.post(`/vps/${vpsId}/docker/container/action`, {
      container_id: containerId,
      action: action
    }),

  // Get images
  getImages: (vpsId: string) =>
    apiClient.get<ImagesResponse>(`/vps/${vpsId}/docker/images`),
};

export const dockerScheduleApi = {
  // Get schedules for a VPS
  getSchedules: (vpsId: string, page = 1, perPage = 50, activeOnly = true) =>
    apiClient.get(`/vps/${vpsId}/schedules`, { page, per_page: perPage, active_only: activeOnly }),

  // Create a new schedule
  create: (vpsId: string, scheduleData: any) =>
    apiClient.post(`/vps/${vpsId}/schedules`, scheduleData),

  // Update a schedule
  update: (scheduleId: string, scheduleData: any) =>
    apiClient.put(`/schedules/${scheduleId}`, scheduleData),

  // Delete a schedule
  delete: (scheduleId: string) =>
    apiClient.delete(`/schedules/${scheduleId}`),

  // Execute schedule now
  executeNow: (scheduleId: string) =>
    apiClient.post(`/schedules/${scheduleId}/execute`),

  // Toggle schedule active/inactive
  toggle: (scheduleId: string) =>
    apiClient.post(`/schedules/${scheduleId}/toggle`),

  // Get schedule executions
  getExecutions: (scheduleId: string, limit = 50) =>
    apiClient.get(`/schedules/${scheduleId}/executions`, { limit }),
};