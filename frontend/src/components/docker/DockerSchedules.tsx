import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dockerScheduleApi } from '@/services/dockerApi';
import { 
  ClockIcon, 
  PlayIcon, 
  PauseIcon, 
  PlusIcon,
  PencilIcon,
  TrashIcon,
  CalendarIcon,
  BoltIcon,
  StopIcon
} from '@heroicons/react/24/outline';
import { CheckCircleIcon, XCircleIcon, ExclamationTriangleIcon } from '@heroicons/react/24/solid';
import CreateScheduleModal from './CreateScheduleModal';
import EditScheduleModal from './EditScheduleModal';

interface DockerSchedulesProps {
  vpsId: string;
}

interface DockerSchedule {
  id: string;
  name: string;
  description?: string;
  container_id: string;
  container_name: string;
  action: 'start' | 'stop' | 'restart';
  schedule_type: 'cron' | 'interval' | 'once';
  cron_expression?: string;
  interval_seconds?: number;
  scheduled_at?: string;
  is_active: boolean;
  is_running: boolean;
  last_run?: string;
  next_run?: string;
  run_count: number;
  success_count: number;
  failure_count: number;
  created_at: string;
}

export default function DockerSchedules({ vpsId }: DockerSchedulesProps) {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<DockerSchedule | null>(null);
  const queryClient = useQueryClient();

  const { data: schedulesData, isLoading } = useQuery({
    queryKey: ['docker-schedules', vpsId],
    queryFn: () => dockerScheduleApi.getSchedules(vpsId),
  });

  const executeScheduleMutation = useMutation({
    mutationFn: (scheduleId: string) => dockerScheduleApi.executeNow(scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['docker-schedules', vpsId] });
    },
  });

  const toggleScheduleMutation = useMutation({
    mutationFn: (scheduleId: string) => dockerScheduleApi.toggle(scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['docker-schedules', vpsId] });
    },
  });

  const deleteScheduleMutation = useMutation({
    mutationFn: (scheduleId: string) => dockerScheduleApi.delete(scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['docker-schedules', vpsId] });
    },
  });

  const handleExecuteNow = (scheduleId: string) => {
    if (confirm('Execute this schedule now?')) {
      executeScheduleMutation.mutate(scheduleId);
    }
  };

  const handleToggleActive = (scheduleId: string) => {
    toggleScheduleMutation.mutate(scheduleId);
  };

  const handleDelete = (schedule: DockerSchedule) => {
    if (confirm(`Delete schedule "${schedule.name}"? This action cannot be undone.`)) {
      deleteScheduleMutation.mutate(schedule.id);
    }
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'start': return <PlayIcon className="h-4 w-4 text-green-500" />;
      case 'stop': return <StopIcon className="h-4 w-4 text-red-500" />;
      case 'restart': return <BoltIcon className="h-4 w-4 text-blue-500" />;
      default: return <PlayIcon className="h-4 w-4" />;
    }
  };

  const getScheduleTypeDisplay = (schedule: DockerSchedule) => {
    switch (schedule.schedule_type) {
      case 'cron':
        return `Cron: ${schedule.cron_expression}`;
      case 'interval':
        return `Every ${Math.floor(schedule.interval_seconds! / 60)} minutes`;
      case 'once':
        return `Once: ${new Date(schedule.scheduled_at!).toLocaleString()}`;
      default:
        return schedule.schedule_type;
    }
  };

  const getStatusBadge = (schedule: DockerSchedule) => {
    if (schedule.is_running) {
      return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
        <ExclamationTriangleIcon className="h-3 w-3 mr-1" />
        Running
      </span>;
    }
    
    if (!schedule.is_active) {
      return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
        <PauseIcon className="h-3 w-3 mr-1" />
        Inactive
      </span>;
    }

    const successRate = schedule.run_count > 0 ? (schedule.success_count / schedule.run_count) * 100 : 0;
    if (successRate >= 80) {
      return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
        <CheckCircleIcon className="h-3 w-3 mr-1" />
        Healthy
      </span>;
    } else if (successRate >= 50) {
      return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
        <ExclamationTriangleIcon className="h-3 w-3 mr-1" />
        Warning
      </span>;
    } else {
      return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
        <XCircleIcon className="h-3 w-3 mr-1" />
        Error
      </span>;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  const schedules = schedulesData?.data?.schedules || [];

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-medium text-gray-900">Docker Schedules</h2>
          <p className="text-sm text-gray-500">
            Automated start, stop, and restart schedules for containers
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          <PlusIcon className="h-4 w-4 mr-2" />
          New Schedule
        </button>
      </div>

      {schedules.length === 0 ? (
        <div className="text-center py-12">
          <ClockIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No schedules</h3>
          <p className="mt-1 text-sm text-gray-500">
            Get started by creating your first container schedule.
          </p>
          <div className="mt-6">
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
            >
              <PlusIcon className="h-4 w-4 mr-2" />
              New Schedule
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul className="divide-y divide-gray-200">
            {schedules.map((schedule: DockerSchedule) => (
              <li key={schedule.id}>
                <div className="px-4 py-4 sm:px-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      {getActionIcon(schedule.action)}
                      <div className="ml-3">
                        <h3 className="text-sm font-medium text-gray-900">
                          {schedule.name}
                        </h3>
                        <p className="text-sm text-gray-500">
                          {schedule.container_name} • {schedule.action}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {getStatusBadge(schedule)}
                      <div className="flex space-x-1">
                        <button
                          onClick={() => handleExecuteNow(schedule.id)}
                          className="p-1 rounded text-gray-400 hover:text-blue-600"
                          title="Execute now"
                        >
                          <PlayIcon className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => setEditingSchedule(schedule)}
                          className="p-1 rounded text-gray-400 hover:text-green-600"
                          title="Edit"
                        >
                          <PencilIcon className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleToggleActive(schedule.id)}
                          className="p-1 rounded text-gray-400 hover:text-yellow-600"
                          title={schedule.is_active ? "Deactivate" : "Activate"}
                        >
                          {schedule.is_active ? (
                            <PauseIcon className="h-4 w-4" />
                          ) : (
                            <PlayIcon className="h-4 w-4" />
                          )}
                        </button>
                        <button
                          onClick={() => handleDelete(schedule)}
                          className="p-1 rounded text-gray-400 hover:text-red-600"
                          title="Delete"
                        >
                          <TrashIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                  
                  <div className="mt-3 text-sm text-gray-600">
                    <div className="flex items-center space-x-4">
                      <span className="flex items-center">
                        <CalendarIcon className="h-4 w-4 mr-1" />
                        {getScheduleTypeDisplay(schedule)}
                      </span>
                      {schedule.next_run && (
                        <span className="text-gray-500">
                          Next: {new Date(schedule.next_run).toLocaleString()}
                        </span>
                      )}
                    </div>
                    {schedule.description && (
                      <p className="mt-1 text-gray-500">{schedule.description}</p>
                    )}
                  </div>

                  <div className="mt-3 flex items-center space-x-6 text-xs text-gray-500">
                    <span>Executions: {schedule.run_count}</span>
                    <span className="text-green-600">Success: {schedule.success_count}</span>
                    <span className="text-red-600">Failed: {schedule.failure_count}</span>
                    {schedule.last_run && (
                      <span>Last run: {new Date(schedule.last_run).toLocaleString()}</span>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {showCreateModal && (
        <CreateScheduleModal
          vpsId={vpsId}
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            queryClient.invalidateQueries({ queryKey: ['docker-schedules', vpsId] });
          }}
        />
      )}

      {editingSchedule && (
        <EditScheduleModal
          schedule={editingSchedule}
          onClose={() => setEditingSchedule(null)}
          onSuccess={() => {
            setEditingSchedule(null);
            queryClient.invalidateQueries({ queryKey: ['docker-schedules', vpsId] });
          }}
        />
      )}
    </div>
  );
}