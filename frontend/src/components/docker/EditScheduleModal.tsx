import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { dockerApi, dockerScheduleApi } from '@/services/dockerApi';
import { XMarkIcon } from '@heroicons/react/24/outline';

interface EditScheduleModalProps {
  schedule: any;
  onClose: () => void;
  onSuccess: () => void;
}

interface ScheduleFormData {
  name: string;
  description: string;
  container_id: string;
  container_name: string;
  action: 'start' | 'stop' | 'restart';
  schedule_type: 'cron' | 'interval' | 'once';
  cron_expression: string;
  interval_seconds: number;
  scheduled_at: string;
  timeout_seconds: number;
  retry_count: number;
  retry_delay_seconds: number;
}

export default function EditScheduleModal({ schedule, onClose, onSuccess }: EditScheduleModalProps) {
  const [formData, setFormData] = useState<ScheduleFormData>({
    name: '',
    description: '',
    container_id: '',
    container_name: '',
    action: 'restart',
    schedule_type: 'cron',
    cron_expression: '0 2 * * *',
    interval_seconds: 3600,
    scheduled_at: '',
    timeout_seconds: 300,
    retry_count: 3,
    retry_delay_seconds: 60,
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  // Get containers for this VPS
  const { data: containersData } = useQuery({
    queryKey: ['docker-containers', schedule.vps_id],
    queryFn: () => dockerApi.getContainers(schedule.vps_id, true),
  });

  // Initialize form with schedule data
  useEffect(() => {
    if (schedule) {
      setFormData({
        name: schedule.name || '',
        description: schedule.description || '',
        container_id: schedule.container_id || '',
        container_name: schedule.container_name || '',
        action: schedule.action || 'restart',
        schedule_type: schedule.schedule_type || 'cron',
        cron_expression: schedule.cron_expression || '0 2 * * *',
        interval_seconds: schedule.interval_seconds || 3600,
        scheduled_at: schedule.scheduled_at ? new Date(schedule.scheduled_at).toISOString().slice(0, 16) : '',
        timeout_seconds: schedule.timeout_seconds || 300,
        retry_count: schedule.retry_count || 3,
        retry_delay_seconds: schedule.retry_delay_seconds || 60,
      });
    }
  }, [schedule]);

  const updateMutation = useMutation({
    mutationFn: (data: any) => dockerScheduleApi.update(schedule.id, data),
    onSuccess: () => {
      onSuccess();
    },
    onError: (error: any) => {
      console.error('Failed to update schedule:', error);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    const newErrors: Record<string, string> = {};
    
    // Validation
    if (!formData.name.trim()) newErrors.name = 'Name is required';
    if (!formData.container_id) newErrors.container_id = 'Container is required';
    
    if (formData.schedule_type === 'cron' && !formData.cron_expression.trim()) {
      newErrors.cron_expression = 'Cron expression is required';
    }
    
    if (formData.schedule_type === 'interval' && formData.interval_seconds < 60) {
      newErrors.interval_seconds = 'Interval must be at least 60 seconds';
    }
    
    if (formData.schedule_type === 'once' && !formData.scheduled_at) {
      newErrors.scheduled_at = 'Scheduled date/time is required';
    }

    setErrors(newErrors);
    
    if (Object.keys(newErrors).length === 0) {
      const payload: any = {
        name: formData.name,
        description: formData.description || undefined,
        action: formData.action,
        schedule_type: formData.schedule_type,
        timeout_seconds: formData.timeout_seconds,
        retry_count: formData.retry_count,
        retry_delay_seconds: formData.retry_delay_seconds,
      };

      // Add schedule-specific fields
      if (formData.schedule_type === 'cron') {
        payload.cron_expression = formData.cron_expression;
      } else if (formData.schedule_type === 'interval') {
        payload.interval_seconds = formData.interval_seconds;
      } else if (formData.schedule_type === 'once') {
        payload.scheduled_at = formData.scheduled_at ? new Date(formData.scheduled_at).toISOString() : null;
      }

      updateMutation.mutate(payload);
    }
  };

  const handleContainerChange = (containerId: string) => {
    const container = containersData?.data?.containers?.find((c: any) => c.id === containerId);
    setFormData(prev => ({
      ...prev,
      container_id: containerId,
      container_name: container?.name || '',
    }));
  };

  const getNextScheduleTime = () => {
    if (formData.schedule_type === 'cron') {
      return `Next run will be calculated based on: ${formData.cron_expression}`;
    } else if (formData.schedule_type === 'interval') {
      const minutes = Math.floor(formData.interval_seconds / 60);
      const hours = Math.floor(minutes / 60);
      if (hours > 0) {
        return `Will run every ${hours} hour${hours > 1 ? 's' : ''}`;
      }
      return `Will run every ${minutes} minute${minutes > 1 ? 's' : ''}`;
    } else if (formData.schedule_type === 'once') {
      return formData.scheduled_at ? `Will run once at: ${new Date(formData.scheduled_at).toLocaleString()}` : '';
    }
    return '';
  };

  const containers = containersData?.data?.containers || [];

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-full max-w-2xl shadow-lg rounded-md bg-white">
        <div className="flex items-center justify-between pb-3">
          <h3 className="text-lg font-medium text-gray-900">Edit Docker Schedule</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Basic Info */}
          <div className="grid grid-cols-1 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700">Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g., Daily Backup Restart"
              />
              {errors.name && <p className="mt-1 text-sm text-red-600">{errors.name}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Description (Optional)</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                rows={2}
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="What does this schedule do?"
              />
            </div>
          </div>

          {/* Container Selection */}
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700">Container</label>
              <select
                value={formData.container_id}
                onChange={(e) => handleContainerChange(e.target.value)}
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Select a container</option>
                {containers.map((container: any) => (
                  <option key={container.id} value={container.id}>
                    {container.name} ({container.id.substring(0, 12)})
                  </option>
                ))}
              </select>
              {errors.container_id && <p className="mt-1 text-sm text-red-600">{errors.container_id}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Action</label>
              <select
                value={formData.action}
                onChange={(e) => setFormData(prev => ({ ...prev, action: e.target.value as any }))}
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="start">Start Container</option>
                <option value="stop">Stop Container</option>
                <option value="restart">Restart Container</option>
              </select>
            </div>
          </div>

          {/* Schedule Configuration */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">Schedule Type</label>
            <div className="space-y-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  value="cron"
                  checked={formData.schedule_type === 'cron'}
                  onChange={(e) => setFormData(prev => ({ ...prev, schedule_type: e.target.value as any }))}
                  className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300"
                />
                <span className="ml-3 text-sm text-gray-700">Cron Expression (Advanced)</span>
              </label>

              {formData.schedule_type === 'cron' && (
                <div className="ml-7">
                  <input
                    type="text"
                    value={formData.cron_expression}
                    onChange={(e) => setFormData(prev => ({ ...prev, cron_expression: e.target.value }))}
                    className="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    placeholder="0 2 * * * (2 AM daily)"
                  />
                  {errors.cron_expression && <p className="mt-1 text-sm text-red-600">{errors.cron_expression}</p>}
                  <p className="mt-1 text-xs text-gray-500">
                    Examples: "0 2 * * *" (2 AM daily), "0 */6 * * *" (every 6 hours), "0 9 * * 1-5" (9 AM weekdays)
                  </p>
                </div>
              )}

              <label className="flex items-center">
                <input
                  type="radio"
                  value="interval"
                  checked={formData.schedule_type === 'interval'}
                  onChange={(e) => setFormData(prev => ({ ...prev, schedule_type: e.target.value as any }))}
                  className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300"
                />
                <span className="ml-3 text-sm text-gray-700">Repeat Every</span>
              </label>

              {formData.schedule_type === 'interval' && (
                <div className="ml-7 flex items-center space-x-2">
                  <input
                    type="number"
                    value={Math.floor(formData.interval_seconds / 60)}
                    onChange={(e) => setFormData(prev => ({ ...prev, interval_seconds: parseInt(e.target.value) * 60 }))}
                    min="1"
                    className="block w-24 border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                  <span className="text-sm text-gray-700">minutes</span>
                  {errors.interval_seconds && <p className="ml-2 text-sm text-red-600">{errors.interval_seconds}</p>}
                </div>
              )}

              <label className="flex items-center">
                <input
                  type="radio"
                  value="once"
                  checked={formData.schedule_type === 'once'}
                  onChange={(e) => setFormData(prev => ({ ...prev, schedule_type: e.target.value as any }))}
                  className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300"
                />
                <span className="ml-3 text-sm text-gray-700">Run Once</span>
              </label>

              {formData.schedule_type === 'once' && (
                <div className="ml-7">
                  <input
                    type="datetime-local"
                    value={formData.scheduled_at}
                    onChange={(e) => setFormData(prev => ({ ...prev, scheduled_at: e.target.value }))}
                    className="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                  {errors.scheduled_at && <p className="mt-1 text-sm text-red-600">{errors.scheduled_at}</p>}
                </div>
              )}
            </div>

            {getNextScheduleTime() && (
              <p className="mt-2 text-sm text-blue-600">{getNextScheduleTime()}</p>
            )}
          </div>

          {/* Advanced Options */}
          <details className="group">
            <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-gray-900">
              Advanced Options
            </summary>
            <div className="mt-4 grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Timeout (seconds)</label>
                <input
                  type="number"
                  value={formData.timeout_seconds}
                  onChange={(e) => setFormData(prev => ({ ...prev, timeout_seconds: parseInt(e.target.value) }))}
                  min="30"
                  max="3600"
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Retry Count</label>
                <input
                  type="number"
                  value={formData.retry_count}
                  onChange={(e) => setFormData(prev => ({ ...prev, retry_count: parseInt(e.target.value) }))}
                  min="0"
                  max="10"
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Retry Delay (seconds)</label>
                <input
                  type="number"
                  value={formData.retry_delay_seconds}
                  onChange={(e) => setFormData(prev => ({ ...prev, retry_delay_seconds: parseInt(e.target.value) }))}
                  min="10"
                  max="300"
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>
          </details>

          {/* Actions */}
          <div className="flex items-center justify-end space-x-3 pt-6 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={updateMutation.isPending}
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              {updateMutation.isPending ? 'Updating...' : 'Update Schedule'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}