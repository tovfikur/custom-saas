import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dockerApi } from '@/services/dockerApi';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import toast from 'react-hot-toast';
import {
  PlayIcon,
  StopIcon,
  ArrowPathIcon,
  TrashIcon,
  CommandLineIcon,
  PauseIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon
} from '@heroicons/react/24/outline';

interface ContainerListProps {
  vpsId: string;
  onOpenTerminal: (containerId: string, containerName: string) => void;
}

export default function ContainerList({ vpsId, onOpenTerminal }: ContainerListProps) {
  const [showAllContainers, setShowAllContainers] = useState(false);
  const queryClient = useQueryClient();

  const { data: containersData, isLoading, error, refetch } = useQuery({
    queryKey: ['docker-containers', vpsId, showAllContainers],
    queryFn: () => dockerApi.getContainers(vpsId, showAllContainers),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const containerActionMutation = useMutation({
    mutationFn: ({ containerId, action }: { containerId: string; action: string }) =>
      dockerApi.containerAction(vpsId, containerId, action),
    onSuccess: (_, variables) => {
      toast.success(`Container ${variables.action} successful`);
      queryClient.invalidateQueries({ queryKey: ['docker-containers', vpsId] });
      queryClient.invalidateQueries({ queryKey: ['docker-status', vpsId] });
    },
    onError: (error: any, variables) => {
      const message = error.response?.data?.message || `Failed to ${variables.action} container`;
      toast.error(message);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error || !containersData?.data) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <div className="flex">
          <ExclamationCircleIcon className="h-5 w-5 text-red-400" />
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">
              Failed to load containers
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

  const containers = containersData.data.containers || [];

  const getStatusIcon = (status: string) => {
    const statusLower = status.toLowerCase();
    if (statusLower.includes('up') || statusLower.includes('running')) {
      return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
    } else if (statusLower.includes('paused')) {
      return <PauseIcon className="h-5 w-5 text-yellow-500" />;
    } else if (statusLower.includes('exited') || statusLower.includes('stopped')) {
      return <StopIcon className="h-5 w-5 text-red-500" />;
    } else {
      return <ClockIcon className="h-5 w-5 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    const statusLower = status.toLowerCase();
    if (statusLower.includes('up') || statusLower.includes('running')) {
      return 'bg-green-100 text-green-800';
    } else if (statusLower.includes('paused')) {
      return 'bg-yellow-100 text-yellow-800';
    } else if (statusLower.includes('exited') || statusLower.includes('stopped')) {
      return 'bg-red-100 text-red-800';
    } else {
      return 'bg-gray-100 text-gray-800';
    }
  };

  const isContainerRunning = (status: string) => {
    return status.toLowerCase().includes('up') || status.toLowerCase().includes('running');
  };

  const handleContainerAction = (containerId: string, action: string, containerName: string) => {
    const confirmActions = ['remove'];
    if (confirmActions.includes(action)) {
      if (!confirm(`Are you sure you want to ${action} container "${containerName}"? This action cannot be undone.`)) {
        return;
      }
    }
    
    containerActionMutation.mutate({ containerId, action });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-gray-900">Docker Containers</h3>
          <p className="text-sm text-gray-500">
            {containers.length} container{containers.length !== 1 ? 's' : ''} found
          </p>
        </div>
        
        <div className="flex items-center space-x-3">
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={showAllContainers}
              onChange={(e) => setShowAllContainers(e.target.checked)}
              className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            <span className="ml-2 text-sm text-gray-700">Show all containers</span>
          </label>
          
          <button
            onClick={() => refetch()}
            className="btn-secondary"
            disabled={isLoading}
          >
            <ArrowPathIcon className="h-4 w-4 mr-2" />
            Refresh
          </button>
        </div>
      </div>

      {/* Containers List */}
      {containers.length === 0 ? (
        <div className="text-center py-12">
          <div className="mx-auto h-12 w-12 text-gray-400">
            <svg fill="none" stroke="currentColor" viewBox="0 0 48 48">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16l2.879-2.879a3 3 0 014.242 0L18 16l7-7 7 7-7 7-7-7zM8 16v16h32V16" />
            </svg>
          </div>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No containers found</h3>
          <p className="mt-1 text-sm text-gray-500">
            {showAllContainers ? 'No containers exist on this VPS.' : 'No running containers found. Try showing all containers.'}
          </p>
        </div>
      ) : (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul className="divide-y divide-gray-200">
            {containers.map((container) => (
              <li key={container.id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4 flex-1 min-w-0">
                    {getStatusIcon(container.status)}
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {container.name || 'Unnamed'}
                        </p>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(container.status)}`}>
                          {container.status}
                        </span>
                      </div>
                      
                      <div className="mt-1 flex items-center text-sm text-gray-500 space-x-4">
                        <span>
                          <span className="font-medium">Image:</span> {container.image}
                        </span>
                        <span>
                          <span className="font-medium">ID:</span> {container.id}
                        </span>
                        {container.created && (
                          <span>
                            <span className="font-medium">Created:</span> {container.created}
                          </span>
                        )}
                      </div>
                      
                      {container.ports && container.ports.length > 0 && (
                        <div className="mt-1 text-sm text-gray-500">
                          <span className="font-medium">Ports:</span> {container.ports.join(', ')}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center space-x-2">
                    {/* Terminal Button */}
                    {isContainerRunning(container.status) && (
                      <button
                        onClick={() => onOpenTerminal(container.id, container.name)}
                        className="p-2 text-gray-400 hover:text-gray-600 rounded-md hover:bg-gray-100"
                        title="Open Terminal"
                      >
                        <CommandLineIcon className="h-5 w-5" />
                      </button>
                    )}

                    {/* Start Button */}
                    {!isContainerRunning(container.status) && (
                      <button
                        onClick={() => handleContainerAction(container.id, 'start', container.name)}
                        disabled={containerActionMutation.isPending}
                        className="p-2 text-green-600 hover:text-green-800 rounded-md hover:bg-green-50"
                        title="Start Container"
                      >
                        {containerActionMutation.isPending ? (
                          <LoadingSpinner size="sm" />
                        ) : (
                          <PlayIcon className="h-5 w-5" />
                        )}
                      </button>
                    )}

                    {/* Stop Button */}
                    {isContainerRunning(container.status) && (
                      <button
                        onClick={() => handleContainerAction(container.id, 'stop', container.name)}
                        disabled={containerActionMutation.isPending}
                        className="p-2 text-red-600 hover:text-red-800 rounded-md hover:bg-red-50"
                        title="Stop Container"
                      >
                        {containerActionMutation.isPending ? (
                          <LoadingSpinner size="sm" />
                        ) : (
                          <StopIcon className="h-5 w-5" />
                        )}
                      </button>
                    )}

                    {/* Restart Button */}
                    <button
                      onClick={() => handleContainerAction(container.id, 'restart', container.name)}
                      disabled={containerActionMutation.isPending}
                      className="p-2 text-blue-600 hover:text-blue-800 rounded-md hover:bg-blue-50"
                      title="Restart Container"
                    >
                      {containerActionMutation.isPending ? (
                        <LoadingSpinner size="sm" />
                      ) : (
                        <ArrowPathIcon className="h-5 w-5" />
                      )}
                    </button>

                    {/* Remove Button */}
                    <button
                      onClick={() => handleContainerAction(container.id, 'remove', container.name)}
                      disabled={containerActionMutation.isPending}
                      className="p-2 text-red-600 hover:text-red-800 rounded-md hover:bg-red-50"
                      title="Remove Container"
                    >
                      {containerActionMutation.isPending ? (
                        <LoadingSpinner size="sm" />
                      ) : (
                        <TrashIcon className="h-5 w-5" />
                      )}
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}