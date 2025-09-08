import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { vpsApi } from '@/services/api';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import VPSTerminal from '@/components/terminals/VPSTerminal';
import DockerStatus from '@/components/docker/DockerStatus';
import ContainerList from '@/components/docker/ContainerList';
import ContainerTerminal from '@/components/terminals/ContainerTerminal';
import DockerSchedules from '@/components/docker/DockerSchedules';
import { 
  Bars3Icon, 
  XMarkIcon,
  ServerIcon,
  CommandLineIcon,
  CubeIcon,
  Square3Stack3DIcon,
  ClockIcon
} from '@heroicons/react/24/outline';

type TabType = 'terminal' | 'docker' | 'containers' | 'schedules';

interface ActiveTerminal {
  type: 'vps' | 'container';
  id: string;
  name: string;
}

export default function VPSDashboard() {
  const { vpsId } = useParams<{ vpsId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabType>('terminal');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTerminals, setActiveTerminals] = useState<ActiveTerminal[]>([]);
  const [selectedTerminal, setSelectedTerminal] = useState<ActiveTerminal | null>(null);

  // Get VPS details
  const { data: vpsDetails, isLoading: vpsLoading } = useQuery({
    queryKey: ['vps-details', vpsId],
    queryFn: () => vpsApi.get(vpsId!),
    enabled: !!vpsId,
  });

  useEffect(() => {
    if (vpsId && !activeTerminals.find(t => t.type === 'vps')) {
      const vpsTerminal: ActiveTerminal = {
        type: 'vps',
        id: vpsId,
        name: vpsDetails?.data?.name || 'VPS Terminal'
      };
      setActiveTerminals([vpsTerminal]);
      setSelectedTerminal(vpsTerminal);
    }
  }, [vpsId, vpsDetails, activeTerminals]);

  const openContainerTerminal = (containerId: string, containerName: string) => {
    const terminalId = `${containerId}`;
    const existingTerminal = activeTerminals.find(
      t => t.type === 'container' && t.id === terminalId
    );

    if (!existingTerminal) {
      const containerTerminal: ActiveTerminal = {
        type: 'container',
        id: terminalId,
        name: `${containerName} Terminal`
      };
      setActiveTerminals(prev => [...prev, containerTerminal]);
      setSelectedTerminal(containerTerminal);
    } else {
      setSelectedTerminal(existingTerminal);
    }
    setActiveTab('terminal');
  };

  const closeTerminal = (terminal: ActiveTerminal) => {
    setActiveTerminals(prev => prev.filter(t => 
      !(t.type === terminal.type && t.id === terminal.id)
    ));
    
    if (selectedTerminal?.type === terminal.type && selectedTerminal?.id === terminal.id) {
      const remaining = activeTerminals.filter(t => 
        !(t.type === terminal.type && t.id === terminal.id)
      );
      setSelectedTerminal(remaining[0] || null);
    }
  };

  if (vpsLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!vpsDetails?.data) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <ServerIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">VPS not found</h3>
          <p className="mt-1 text-sm text-gray-500">
            The VPS you're looking for doesn't exist or has been removed.
          </p>
          <div className="mt-6">
            <button
              onClick={() => navigate('/vps')}
              className="btn-primary"
            >
              Back to VPS List
            </button>
          </div>
        </div>
      </div>
    );
  }

  const vps = vpsDetails.data;

  const tabs = [
    { id: 'terminal', name: 'Terminal', icon: CommandLineIcon },
    { id: 'docker', name: 'Docker Status', icon: CubeIcon },
    { id: 'containers', name: 'Containers', icon: Square3Stack3DIcon },
    { id: 'schedules', name: 'Schedules', icon: ClockIcon },
  ];

  return (
    <div className="h-screen flex bg-gray-50">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-16'} bg-white shadow-sm transition-all duration-300 border-r border-gray-200`}>
        <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
          {sidebarOpen && (
            <div>
              <h1 className="text-lg font-semibold text-gray-900 truncate">{vps.name}</h1>
              <p className="text-sm text-gray-500">{vps.ip_address}</p>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1 rounded-md text-gray-400 hover:text-gray-600"
          >
            {sidebarOpen ? (
              <XMarkIcon className="h-6 w-6" />
            ) : (
              <Bars3Icon className="h-6 w-6" />
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="mt-8">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as TabType)}
                className={`${
                  activeTab === tab.id
                    ? 'bg-primary-50 border-primary-500 text-primary-700'
                    : 'border-transparent text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                } group flex items-center px-3 py-2 text-sm font-medium border-l-4 w-full`}
              >
                <Icon className={`${
                  activeTab === tab.id ? 'text-primary-500' : 'text-gray-400 group-hover:text-gray-500'
                } flex-shrink-0 h-6 w-6 ${sidebarOpen ? 'mr-3' : ''}`} />
                {sidebarOpen && tab.name}
              </button>
            );
          })}
        </nav>

        {/* Active Terminals */}
        {sidebarOpen && activeTerminals.length > 0 && (
          <div className="mt-8">
            <h3 className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Active Terminals
            </h3>
            <div className="mt-2 space-y-1">
              {activeTerminals.map((terminal) => (
                <div
                  key={`${terminal.type}-${terminal.id}`}
                  className={`${
                    selectedTerminal?.type === terminal.type && selectedTerminal?.id === terminal.id
                      ? 'bg-gray-100 text-gray-900'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  } group flex items-center justify-between px-3 py-2 text-sm font-medium rounded-md mx-2`}
                >
                  <button
                    onClick={() => {
                      setSelectedTerminal(terminal);
                      setActiveTab('terminal');
                    }}
                    className="flex items-center flex-1 text-left truncate"
                  >
                    <CommandLineIcon className="flex-shrink-0 h-4 w-4 mr-2" />
                    <span className="truncate">{terminal.name}</span>
                  </button>
                  <button
                    onClick={() => closeTerminal(terminal)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-gray-600"
                  >
                    <XMarkIcon className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white shadow-sm border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                {tabs.find(t => t.id === activeTab)?.name}
              </h2>
              <p className="text-sm text-gray-500">
                {activeTab === 'terminal' && selectedTerminal 
                  ? `Active: ${selectedTerminal.name}`
                  : `Managing ${vps.name} (${vps.ip_address})`
                }
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                vps.status === 'active' 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-gray-100 text-gray-800'
              }`}>
                {vps.status}
              </span>
              <button
                onClick={() => navigate('/vps')}
                className="btn-secondary"
              >
                Back to VPS List
              </button>
            </div>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'terminal' && selectedTerminal && (
            <div className="h-full">
              {selectedTerminal.type === 'vps' ? (
                <VPSTerminal vpsId={vpsId!} />
              ) : (
                <ContainerTerminal 
                  vpsId={vpsId!} 
                  containerId={selectedTerminal.id}
                />
              )}
            </div>
          )}

          {activeTab === 'docker' && (
            <div className="h-full p-6 overflow-y-auto">
              <DockerStatus vpsId={vpsId!} />
            </div>
          )}

          {activeTab === 'containers' && (
            <div className="h-full p-6 overflow-y-auto">
              <ContainerList 
                vpsId={vpsId!} 
                onOpenTerminal={openContainerTerminal}
              />
            </div>
          )}

          {activeTab === 'schedules' && (
            <div className="h-full overflow-y-auto">
              <DockerSchedules vpsId={vpsId!} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}