import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { vpsApi } from '@/services/api';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import VPSOnboardingModal from '@/components/modals/VPSOnboardingModal';
import { PlusIcon, ServerIcon, Cog6ToothIcon, TrashIcon } from '@heroicons/react/24/outline';

export default function VPSManagement() {
  const queryClient = useQueryClient();
  const [showOnboardingModal, setShowOnboardingModal] = useState(false);

  const { data: vpsHosts, isLoading } = useQuery({
    queryKey: ['vps-hosts'],
    queryFn: () => vpsApi.list(),
  });

  const healthCheckMutation = useMutation({
    mutationFn: vpsApi.checkHealth,
    onSuccess: () => {
      toast.success('Health check completed');
      queryClient.invalidateQueries({ queryKey: ['vps-hosts'] });
    },
    onError: () => {
      toast.error('Health check failed');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: vpsApi.delete,
    onSuccess: () => {
      toast.success('VPS deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['vps-hosts'] });
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to delete VPS';
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

  const hosts = vpsHosts?.data || [];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'status-indicator success';
      case 'pending': return 'status-indicator info';
      case 'error': return 'status-indicator danger';
      case 'inactive': return 'status-indicator warning';
      default: return 'status-indicator';
    }
  };

  return (
    <div className="px-4 sm:px-6 lg:px-8">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">VPS Management</h1>
          <p className="mt-2 text-sm text-gray-700">
            Manage your VPS hosts and their configurations
          </p>
        </div>
        <div className="mt-4 sm:ml-16 sm:mt-0 sm:flex-none">
          <button
            type="button"
            className="btn-primary"
            onClick={() => setShowOnboardingModal(true)}
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            Add VPS
          </button>
        </div>
      </div>

      <div className="mt-8 flow-root">
        <div className="-mx-4 -my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
          <div className="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8">
            <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
              <table className="min-w-full divide-y divide-gray-300">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      VPS Host
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Status
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Services
                    </th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Last Check
                    </th>
                    <th scope="col" className="relative px-6 py-3">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {hosts.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-12 text-center text-sm text-gray-500">
                        No VPS hosts configured yet.{' '}
                        <button 
                          className="text-primary-600 hover:text-primary-500"
                          onClick={() => setShowOnboardingModal(true)}
                        >
                          Add your first VPS
                        </button>
                      </td>
                    </tr>
                  ) : (
                    hosts.map((host) => (
                      <tr key={host.id}>
                        <td className="whitespace-nowrap px-6 py-4">
                          <div className="flex items-center">
                            <ServerIcon className="h-10 w-10 text-gray-400" />
                            <div className="ml-4">
                              <div className="text-sm font-medium text-gray-900">
                                {host.name}
                              </div>
                              <div className="text-sm text-gray-500">
                                {host.ip_address}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="whitespace-nowrap px-6 py-4">
                          <span className={getStatusColor(host.status)}>
                            {host.status}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                          <div>
                            {host.docker_version && (
                              <div>Docker: {host.docker_version}</div>
                            )}
                            {host.nginx_version && (
                              <div>Nginx: {host.nginx_version}</div>
                            )}
                          </div>
                        </td>
                        <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                          {host.last_successful_connection ? (
                            <time dateTime={host.last_successful_connection}>
                              {new Date(host.last_successful_connection).toLocaleString()}
                            </time>
                          ) : (
                            'Never'
                          )}
                        </td>
                        <td className="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                          <div className="flex justify-end items-center space-x-3">
                            <button
                              onClick={() => healthCheckMutation.mutate(host.id)}
                              disabled={healthCheckMutation.isPending}
                              className="text-primary-600 hover:text-primary-900"
                            >
                              {healthCheckMutation.isPending && healthCheckMutation.variables === host.id ? (
                                <LoadingSpinner size="sm" />
                              ) : (
                                'Check Health'
                              )}
                            </button>
                            <Link
                              to={`/vps/${host.id}`}
                              className="bg-primary-600 hover:bg-primary-700 text-white px-3 py-1.5 rounded-md inline-flex items-center text-sm font-medium transition-colors"
                              title="Access VPS Dashboard (Terminal, Docker, Containers)"
                            >
                              <ServerIcon className="h-4 w-4 mr-1" />
                              Manage
                            </Link>
                            <Link
                              to={`/vps/${host.id}/nginx`}
                              className="text-primary-600 hover:text-primary-900 inline-flex items-center"
                            >
                              <Cog6ToothIcon className="h-4 w-4 mr-1" />
                              Nginx Config
                            </Link>
                            <button
                              onClick={() => {
                                if (confirm(`Are you sure you want to delete ${host.name}? This action cannot be undone.`)) {
                                  deleteMutation.mutate(host.id);
                                }
                              }}
                              disabled={deleteMutation.isPending}
                              className="text-red-600 hover:text-red-900 inline-flex items-center"
                            >
                              {deleteMutation.isPending && deleteMutation.variables === host.id ? (
                                <LoadingSpinner size="sm" />
                              ) : (
                                <TrashIcon className="h-4 w-4" />
                              )}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
      
      {/* VPS Onboarding Modal */}
      <VPSOnboardingModal 
        isOpen={showOnboardingModal} 
        onClose={() => setShowOnboardingModal(false)} 
      />
    </div>
  );
}