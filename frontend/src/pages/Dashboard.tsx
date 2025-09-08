import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { 
  ServerIcon, 
  Cog6ToothIcon, 
  ChartBarIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline';
import { vpsApi, monitoringApi } from '@/services/api';
import LoadingSpinner from '@/components/ui/LoadingSpinner';

export default function Dashboard() {
  const { data: vpsHosts, isLoading: vpsLoading } = useQuery({
    queryKey: ['vps-hosts'],
    queryFn: () => vpsApi.list(),
  });

  const { data: systemMetrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['system-metrics'],
    queryFn: () => monitoringApi.getSystemMetrics(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const { data: recentLogs } = useQuery({
    queryKey: ['recent-audit-logs'],
    queryFn: () => monitoringApi.getRecentAuditLogs({ limit: 10 }),
    refetchInterval: 60000, // Refresh every minute
  });

  if (vpsLoading || metricsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  const hosts = vpsHosts?.data || [];
  const metrics = systemMetrics?.data;
  const logs = recentLogs?.data?.logs || [];

  const activeHosts = hosts.filter(h => h.status === 'active').length;
  const healthyHosts = hosts.filter(h => h.is_healthy).length;

  const stats = [
    {
      name: 'Active VPS Hosts',
      value: activeHosts,
      total: hosts.length,
      icon: ServerIcon,
      color: 'text-primary-600',
      bgColor: 'bg-primary-100',
    },
    {
      name: 'Healthy Hosts',
      value: healthyHosts,
      total: activeHosts,
      icon: CheckCircleIcon,
      color: 'text-success-600',
      bgColor: 'bg-success-100',
    },
    {
      name: 'Nginx Operations (24h)',
      value: metrics?.total_nginx_operations || 0,
      failed: metrics?.failed_nginx_operations || 0,
      icon: Cog6ToothIcon,
      color: 'text-primary-600',
      bgColor: 'bg-primary-100',
    },
    {
      name: 'Recent Alerts',
      value: metrics?.recent_alerts || 0,
      icon: ExclamationTriangleIcon,
      color: 'text-warning-600',
      bgColor: 'bg-warning-100',
    },
  ];

  return (
    <div className="px-4 sm:px-6 lg:px-8">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
          <p className="mt-2 text-sm text-gray-700">
            Overview of your SaaS orchestration platform
          </p>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat, index) => (
          <div key={index} className="card">
            <div className="card-body">
              <div className="flex items-center">
                <div className={`flex-shrink-0 rounded-md p-3 ${stat.bgColor}`}>
                  <stat.icon className={`h-6 w-6 ${stat.color}`} />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      {stat.name}
                    </dt>
                    <dd className="text-lg font-medium text-gray-900">
                      {stat.value}
                      {stat.total !== undefined && (
                        <span className="text-sm text-gray-500">
                          {' '}/ {stat.total}
                        </span>
                      )}
                      {stat.failed !== undefined && stat.failed > 0 && (
                        <span className="ml-2 text-sm text-danger-600">
                          ({stat.failed} failed)
                        </span>
                      )}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="mt-8">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Link
            to="/vps"
            className="group relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm hover:shadow-md transition-shadow"
          >
            <div className="flex items-center space-x-3">
              <ServerIcon className="h-8 w-8 text-primary-600" />
              <div>
                <h3 className="text-sm font-medium text-gray-900 group-hover:text-primary-600">
                  Manage VPS Hosts
                </h3>
                <p className="text-sm text-gray-500">
                  Add, configure, and monitor VPS instances
                </p>
              </div>
            </div>
          </Link>

          <Link
            to="/monitoring"
            className="group relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm hover:shadow-md transition-shadow"
          >
            <div className="flex items-center space-x-3">
              <ChartBarIcon className="h-8 w-8 text-primary-600" />
              <div>
                <h3 className="text-sm font-medium text-gray-900 group-hover:text-primary-600">
                  View Monitoring
                </h3>
                <p className="text-sm text-gray-500">
                  Check metrics, alerts, and system health
                </p>
              </div>
            </div>
          </Link>
        </div>
      </div>

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
                  {logs.slice(0, 5).map((log, logIdx) => (
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
                              <CheckCircleIcon className="h-5 w-5 text-white" aria-hidden="true" />
                            </span>
                          </div>
                          <div className="flex min-w-0 flex-1 justify-between space-x-4 pt-1.5">
                            <div>
                              <p className="text-sm text-gray-500">
                                {log.description}
                                {log.error_message && (
                                  <span className="ml-2 text-danger-600">
                                    - {log.error_message}
                                  </span>
                                )}
                              </p>
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
    </div>
  );
}