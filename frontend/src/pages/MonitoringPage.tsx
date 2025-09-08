import { useQuery } from '@tanstack/react-query';
import { monitoringApi } from '@/services/api';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import { 
  ChartBarIcon, 
  ServerIcon, 
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon
} from '@heroicons/react/24/outline';

export default function MonitoringPage() {
  const { data: systemMetrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['system-metrics'],
    queryFn: () => monitoringApi.getSystemMetrics(),
    refetchInterval: 30000,
  });

  const { data: recentLogs } = useQuery({
    queryKey: ['recent-audit-logs'],
    queryFn: () => monitoringApi.getRecentAuditLogs({ limit: 20 }),
    refetchInterval: 60000,
  });

  const { data: healthCheck } = useQuery({
    queryKey: ['monitoring-health'],
    queryFn: () => monitoringApi.getHealth(),
    refetchInterval: 30000,
  });

  if (metricsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  const metrics = systemMetrics?.data;
  const logs = recentLogs?.data?.logs || [];
  const health = healthCheck?.data;

  return (
    <div className="px-4 sm:px-6 lg:px-8">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">Monitoring</h1>
          <p className="mt-2 text-sm text-gray-700">
            System metrics, health status, and activity logs
          </p>
        </div>
      </div>

      {/* System Health Status */}
      <div className="mt-8">
        <h2 className="text-lg font-medium text-gray-900 mb-4">System Health</h2>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <div className="card">
            <div className="card-body">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <ServerIcon className="h-8 w-8 text-primary-600" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      Active VPS Hosts
                    </dt>
                    <dd className="text-lg font-medium text-gray-900">
                      {metrics?.active_vps_hosts || 0}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-body">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <ChartBarIcon className="h-8 w-8 text-success-600" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      Odoo Instances
                    </dt>
                    <dd className="text-lg font-medium text-gray-900">
                      {metrics?.active_odoo_instances || 0}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-body">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <CheckCircleIcon className="h-8 w-8 text-primary-600" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      Nginx Operations (24h)
                    </dt>
                    <dd className="text-lg font-medium text-gray-900">
                      {metrics?.total_nginx_operations || 0}
                      {metrics?.failed_nginx_operations && metrics.failed_nginx_operations > 0 && (
                        <span className="ml-2 text-sm text-danger-600">
                          ({metrics.failed_nginx_operations} failed)
                        </span>
                      )}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-body">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <ExclamationTriangleIcon className="h-8 w-8 text-warning-600" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      Recent Alerts
                    </dt>
                    <dd className="text-lg font-medium text-gray-900">
                      {metrics?.recent_alerts || 0}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Service Status */}
      {health && (
        <div className="mt-8">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Service Status</h2>
          <div className="card">
            <div className="card-body">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-900">Prometheus Metrics</p>
                    <p className="text-xs text-gray-500">Data collection service</p>
                  </div>
                  <span className={`status-indicator ${health.prometheus_metrics ? 'success' : 'danger'}`}>
                    {health.prometheus_metrics ? 'Healthy' : 'Down'}
                  </span>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-900">Alerting Service</p>
                    <p className="text-xs text-gray-500">Notification system</p>
                  </div>
                  <span className={`status-indicator ${health.alerting_service ? 'success' : 'danger'}`}>
                    {health.alerting_service ? 'Healthy' : 'Down'}
                  </span>
                </div>

                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-900">Overall Status</p>
                    <p className="text-xs text-gray-500">System health</p>
                  </div>
                  <span className={`status-indicator ${health.status === 'healthy' ? 'success' : 'danger'}`}>
                    {health.status}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Recent Activity */}
      <div className="mt-8">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h2>
        <div className="card">
          <div className="card-body">
            {logs.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No recent activity</p>
            ) : (
              <div className="flow-root">
                <ul role="list" className="-mb-8">
                  {logs.map((log, logIdx) => (
                    <li key={log.id}>
                      <div className="relative pb-8">
                        {logIdx !== logs.length - 1 ? (
                          <span
                            className="absolute left-4 top-4 -ml-px h-full w-0.5 bg-gray-200"
                            aria-hidden="true"
                          />
                        ) : null}
                        <div className="relative flex space-x-3">
                          <div>
                            <span
                              className={`
                                h-8 w-8 rounded-full flex items-center justify-center ring-8 ring-white
                                ${log.status === 'success' 
                                  ? 'bg-success-500' 
                                  : log.status === 'failed' 
                                  ? 'bg-danger-500' 
                                  : 'bg-gray-400'
                                }
                              `}
                            >
                              <ClockIcon className="h-5 w-5 text-white" aria-hidden="true" />
                            </span>
                          </div>
                          <div className="flex min-w-0 flex-1 justify-between space-x-4 pt-1.5">
                            <div>
                              <p className="text-sm text-gray-900 font-medium">
                                {log.action.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                              </p>
                              <p className="text-sm text-gray-500 mt-1">
                                {log.description}
                              </p>
                              {log.error_message && (
                                <p className="text-sm text-danger-600 mt-1">
                                  Error: {log.error_message}
                                </p>
                              )}
                              <div className="flex items-center space-x-4 mt-2 text-xs text-gray-400">
                                <span>Task ID: {log.task_id}</span>
                                {log.duration_seconds && (
                                  <span>Duration: {log.duration_seconds}s</span>
                                )}
                                <span className={`px-2 py-1 rounded-full ${
                                  log.status === 'success' ? 'bg-success-50 text-success-600' :
                                  log.status === 'failed' ? 'bg-danger-50 text-danger-600' :
                                  'bg-gray-50 text-gray-600'
                                }`}>
                                  {log.status}
                                </span>
                              </div>
                            </div>
                            <div className="whitespace-nowrap text-right text-sm text-gray-500">
                              <time dateTime={log.started_at}>
                                {new Date(log.started_at).toLocaleString()}
                              </time>
                            </div>
                          </div>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* External Monitoring Links */}
      <div className="mt-8">
        <h2 className="text-lg font-medium text-gray-900 mb-4">External Monitoring</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="card">
            <div className="card-body">
              <div className="flex items-center space-x-3">
                <ChartBarIcon className="h-8 w-8 text-primary-600" />
                <div>
                  <h3 className="text-sm font-medium text-gray-900">Prometheus</h3>
                  <p className="text-sm text-gray-500">Raw metrics and queries</p>
                </div>
              </div>
              <div className="mt-4">
                <a
                  href="http://localhost:9090"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary w-full text-center"
                >
                  Open Prometheus
                </a>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-body">
              <div className="flex items-center space-x-3">
                <ChartBarIcon className="h-8 w-8 text-primary-600" />
                <div>
                  <h3 className="text-sm font-medium text-gray-900">Grafana</h3>
                  <p className="text-sm text-gray-500">Detailed dashboards and alerts</p>
                </div>
              </div>
              <div className="mt-4">
                <a
                  href="http://localhost:3001"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary w-full text-center"
                >
                  Open Grafana
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}