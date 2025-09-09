import { useQuery } from '@tanstack/react-query';
import { dockerApi } from '@/services/dockerApi';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import {
  CubeIcon,
  PlayIcon,
  PhotoIcon,
  CheckCircleIcon,
  XCircleIcon
} from '@heroicons/react/24/outline';

interface DockerStatusProps {
  vpsId: string;
}

export default function DockerStatus({ vpsId }: DockerStatusProps) {
  const { data: dockerStatus, isLoading, error, refetch } = useQuery({
    queryKey: ['docker-status', vpsId],
    queryFn: () => dockerApi.getStatus(vpsId),
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error || !dockerStatus?.data) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <div className="flex">
          <XCircleIcon className="h-5 w-5 text-red-400" />
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">
              Failed to load Docker status
            </h3>
            <div className="mt-2">
              <button
                onClick={() => refetch()}
                className="text-sm bg-red-100 text-red-700 px-3 py-1 rounded hover:bg-red-200"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const status = dockerStatus.data;
  const statusKey = status.status as string;

  const stateMap: Record<string, {
    label: string;
    badgeClass: string;
    headerBgClass: string;
    iconClass: string;
    isRunning: boolean;
  }> = {
    running: {
      label: 'Running',
      badgeClass: 'bg-green-100 text-green-800',
      headerBgClass: 'bg-green-100',
      iconClass: 'text-green-600',
      isRunning: true,
    },
    stopped: {
      label: 'Stopped',
      badgeClass: 'bg-red-100 text-red-800',
      headerBgClass: 'bg-red-100',
      iconClass: 'text-red-600',
      isRunning: false,
    },
    not_present: {
      label: 'Docker Unavailable',
      badgeClass: 'bg-gray-100 text-gray-800',
      headerBgClass: 'bg-gray-100',
      iconClass: 'text-gray-600',
      isRunning: false,
    },
    error: {
      label: 'Error',
      badgeClass: 'bg-red-100 text-red-800',
      headerBgClass: 'bg-red-100',
      iconClass: 'text-red-600',
      isRunning: false,
    },
  };

  const mapped = stateMap[statusKey] ?? stateMap.error;

  const stats = [
    {
      name: 'Running Containers',
      value: status.containers_running,
      icon: PlayIcon,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
    {
      name: 'Total Containers',
      value: status.containers_total,
      icon: CubeIcon,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    {
      name: 'Images',
      value: status.images_count,
      icon: PhotoIcon,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
    },
  ];

  const formatBytes = (bytes: number | string): string => {
    if (typeof bytes === 'string') return bytes;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 Bytes';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="space-y-6">
      {/* Docker Status Header */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <div className={`p-2 rounded-md ${mapped.headerBgClass}`}>
              {mapped.isRunning ? (
                <CheckCircleIcon className={`h-6 w-6 ${mapped.iconClass}`} />
              ) : (
                <XCircleIcon className={`h-6 w-6 ${mapped.iconClass}`} />
              )}
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-medium text-gray-900">Docker Status</h3>
              <p className="text-sm text-gray-500">
                {status.version || 'Version information not available'}
              </p>
            </div>
          </div>
          <div className="flex items-center">
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${mapped.badgeClass}`}>
              {mapped.label}
            </span>
          </div>
        </div>
      </div>

      {/* Statistics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.name} className="bg-white shadow rounded-lg p-6">
              <div className="flex items-center">
                <div className={`p-2 rounded-md ${stat.bgColor}`}>
                  <Icon className={`h-6 w-6 ${stat.color}`} />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">{stat.name}</p>
                  <p className="text-2xl font-semibold text-gray-900">{stat.value}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* System Information */}
      {status.system_info && Object.keys(status.system_info).length > 0 && (
        <div className="bg-white shadow rounded-lg p-6">
          <h4 className="text-lg font-medium text-gray-900 mb-4">System Information</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {status.system_info.ServerVersion && (
              <div className="flex justify-between py-2">
                <span className="text-sm font-medium text-gray-500">Server Version:</span>
                <span className="text-sm text-gray-900">{status.system_info.ServerVersion}</span>
              </div>
            )}
            {status.system_info.Architecture && (
              <div className="flex justify-between py-2">
                <span className="text-sm font-medium text-gray-500">Architecture:</span>
                <span className="text-sm text-gray-900">{status.system_info.Architecture}</span>
              </div>
            )}
            {status.system_info.OSType && (
              <div className="flex justify-between py-2">
                <span className="text-sm font-medium text-gray-500">OS Type:</span>
                <span className="text-sm text-gray-900">{status.system_info.OSType}</span>
              </div>
            )}
            {status.system_info.KernelVersion && (
              <div className="flex justify-between py-2">
                <span className="text-sm font-medium text-gray-500">Kernel Version:</span>
                <span className="text-sm text-gray-900">{status.system_info.KernelVersion}</span>
              </div>
            )}
            {status.system_info.MemTotal && (
              <div className="flex justify-between py-2">
                <span className="text-sm font-medium text-gray-500">Total Memory:</span>
                <span className="text-sm text-gray-900">{formatBytes(status.system_info.MemTotal)}</span>
              </div>
            )}
            {status.system_info.NCPU && (
              <div className="flex justify-between py-2">
                <span className="text-sm font-medium text-gray-500">CPUs:</span>
                <span className="text-sm text-gray-900">{status.system_info.NCPU}</span>
              </div>
            )}
            {status.system_info.Driver && (
              <div className="flex justify-between py-2">
                <span className="text-sm font-medium text-gray-500">Storage Driver:</span>
                <span className="text-sm text-gray-900">{status.system_info.Driver}</span>
              </div>
            )}
            {status.system_info.DockerRootDir && (
              <div className="flex justify-between py-2">
                <span className="text-sm font-medium text-gray-500">Docker Root Dir:</span>
                <span className="text-sm text-gray-900 truncate">{status.system_info.DockerRootDir}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error Information */}
      {status.system_info?.error && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
          <div className="flex">
            <XCircleIcon className="h-5 w-5 text-yellow-400" />
            <div className="ml-3">
              <h3 className="text-sm font-medium text-yellow-800">
                System Information Warning
              </h3>
              <p className="text-sm text-yellow-700 mt-1">
                {status.system_info.error}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
