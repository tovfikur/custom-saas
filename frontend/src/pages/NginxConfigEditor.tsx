import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { nginxApi } from '@/services/api';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import { 
  DocumentTextIcon, 
  PlayIcon, 
  EyeIcon,
  ArrowUturnLeftIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline';

export default function NginxConfigEditor() {
  const { vpsId } = useParams<{ vpsId: string }>();
  const queryClient = useQueryClient();
  
  const [activeTab, setActiveTab] = useState<'raw' | 'template'>('raw');
  const [configContent, setConfigContent] = useState('');
  const [configName, setConfigName] = useState('default');
  const [summary, setSummary] = useState('');
  const [validationResult, setValidationResult] = useState<any>(null);
  const [, setSelectedVersion] = useState<number | null>(null);

  const { data: configs, isLoading: configsLoading } = useQuery({
    queryKey: ['nginx-configs', vpsId],
    queryFn: () => nginxApi.listConfigs(vpsId!),
    enabled: !!vpsId,
  });

  const { data: templates } = useQuery({
    queryKey: ['nginx-templates'],
    queryFn: () => nginxApi.getTemplates(),
  });

  const previewMutation = useMutation({
    mutationFn: (data: any) => nginxApi.previewConfig(vpsId!, data),
    onSuccess: (response) => {
      setValidationResult(response.data);
    },
  });

  const applyMutation = useMutation({
    mutationFn: (data: any) => nginxApi.applyConfig(vpsId!, data),
    onSuccess: () => {
      toast.success('Configuration applied successfully');
      queryClient.invalidateQueries({ queryKey: ['nginx-configs', vpsId] });
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => nginxApi.createConfig(vpsId!, data),
    onSuccess: () => {
      toast.success('Configuration version created');
      queryClient.invalidateQueries({ queryKey: ['nginx-configs', vpsId] });
    },
  });

  useEffect(() => {
    if (!configContent && templates?.data?.templates && templates.data.templates.length > 0) {
      // Set default template content
      const basicTemplate = templates.data.templates.find(t => t.name === 'basic_server_block');
      if (basicTemplate) {
        setConfigContent(basicTemplate.template);
      }
    }
  }, [templates, configContent]);

  if (!vpsId) {
    return <div>VPS ID not found</div>;
  }

  if (configsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  const configList = configs?.data || [];
  const templateList = templates?.data?.templates || [];

  const handlePreview = () => {
    if (!configContent.trim()) {
      toast.error('Please enter configuration content');
      return;
    }

    previewMutation.mutate({
      content: configContent,
      vps_id: vpsId,
      config_name: configName,
      config_type: 'server_block'
    });
  };

  const handleSaveVersion = () => {
    if (!configContent.trim()) {
      toast.error('Please enter configuration content');
      return;
    }

    createMutation.mutate({
      content: configContent,
      vps_id: vpsId,
      config_name: configName,
      config_type: 'server_block',
      summary: summary || 'Manual configuration'
    });
  };

  const handleApply = (configId: string, dryRun = false) => {
    applyMutation.mutate({
      config_id: configId,
      dry_run: dryRun,
      watch_window_seconds: 120
    });
  };

  const insertTemplate = (template: any) => {
    setConfigContent(template.template);
    setConfigName(template.name);
    toast.success(`${template.display_name} template inserted`);
  };

  return (
    <div className="px-4 sm:px-6 lg:px-8">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">
            Nginx Configuration Editor
          </h1>
          <p className="mt-2 text-sm text-gray-700">
            VPS ID: {vpsId} - Edit and manage nginx configurations safely
          </p>
        </div>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Main Editor */}
        <div className="lg:col-span-2">
          <div className="card">
            <div className="card-header">
              <div className="flex items-center justify-between">
                <div className="flex space-x-4">
                  <button
                    onClick={() => setActiveTab('raw')}
                    className={`px-3 py-2 text-sm font-medium rounded-md ${
                      activeTab === 'raw'
                        ? 'bg-primary-100 text-primary-700'
                        : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    Raw Editor
                  </button>
                  <button
                    onClick={() => setActiveTab('template')}
                    className={`px-3 py-2 text-sm font-medium rounded-md ${
                      activeTab === 'template'
                        ? 'bg-primary-100 text-primary-700'
                        : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    Templates
                  </button>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={handlePreview}
                    disabled={previewMutation.isPending}
                    className="btn-secondary"
                  >
                    <EyeIcon className="h-4 w-4 mr-2" />
                    {previewMutation.isPending ? 'Validating...' : 'Preview & Validate'}
                  </button>
                  <button
                    onClick={handleSaveVersion}
                    disabled={createMutation.isPending}
                    className="btn-primary"
                  >
                    <DocumentTextIcon className="h-4 w-4 mr-2" />
                    Save Version
                  </button>
                </div>
              </div>
            </div>

            <div className="card-body">
              {activeTab === 'raw' ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div>
                      <label htmlFor="configName" className="block text-sm font-medium text-gray-700">
                        Configuration Name
                      </label>
                      <input
                        type="text"
                        id="configName"
                        value={configName}
                        onChange={(e) => setConfigName(e.target.value)}
                        className="form-input"
                        placeholder="e.g., main-site"
                      />
                    </div>
                    <div>
                      <label htmlFor="summary" className="block text-sm font-medium text-gray-700">
                        Summary
                      </label>
                      <input
                        type="text"
                        id="summary"
                        value={summary}
                        onChange={(e) => setSummary(e.target.value)}
                        className="form-input"
                        placeholder="Brief description of changes"
                      />
                    </div>
                  </div>

                  <div>
                    <label htmlFor="configContent" className="block text-sm font-medium text-gray-700">
                      Nginx Configuration
                    </label>
                    <textarea
                      id="configContent"
                      rows={20}
                      value={configContent}
                      onChange={(e) => setConfigContent(e.target.value)}
                      className="form-textarea font-mono text-sm custom-scrollbar"
                      placeholder="Enter your nginx configuration here..."
                    />
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <h3 className="text-lg font-medium text-gray-900">Available Templates</h3>
                  <div className="grid gap-4">
                    {templateList.map((template) => (
                      <div key={template.name} className="border rounded-lg p-4 hover:bg-gray-50">
                        <div className="flex justify-between items-start">
                          <div>
                            <h4 className="font-medium text-gray-900">{template.display_name}</h4>
                            <p className="text-sm text-gray-500 mt-1">{template.description}</p>
                            <span className="inline-block mt-2 px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded">
                              {template.category}
                            </span>
                          </div>
                          <button
                            onClick={() => insertTemplate(template)}
                            className="btn-secondary"
                          >
                            Use Template
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Validation Results */}
          {validationResult && (
            <div className="mt-6 card">
              <div className="card-header">
                <h3 className="text-lg font-medium text-gray-900 flex items-center">
                  {validationResult.is_valid ? (
                    <CheckCircleIcon className="h-5 w-5 text-success-600 mr-2" />
                  ) : (
                    <ExclamationTriangleIcon className="h-5 w-5 text-danger-600 mr-2" />
                  )}
                  Validation Results
                </h3>
              </div>
              <div className="card-body">
                <div className={`p-4 rounded-md ${
                  validationResult.is_valid ? 'bg-success-50' : 'bg-danger-50'
                }`}>
                  <p className={`text-sm font-medium ${
                    validationResult.is_valid ? 'text-success-800' : 'text-danger-800'
                  }`}>
                    {validationResult.is_valid ? 'Configuration is valid' : 'Configuration has errors'}
                  </p>
                  
                  {validationResult.errors?.length > 0 && (
                    <ul className="mt-2 text-sm text-danger-700 list-disc list-inside">
                      {validationResult.errors.map((error: string, index: number) => (
                        <li key={index}>{error}</li>
                      ))}
                    </ul>
                  )}
                  
                  {validationResult.warnings?.length > 0 && (
                    <ul className="mt-2 text-sm text-warning-700 list-disc list-inside">
                      {validationResult.warnings.map((warning: string, index: number) => (
                        <li key={index}>{warning}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Version History Sidebar */}
        <div className="lg:col-span-1">
          <div className="card">
            <div className="card-header">
              <h3 className="text-lg font-medium text-gray-900">Configuration Versions</h3>
            </div>
            <div className="card-body">
              {configList.length === 0 ? (
                <p className="text-gray-500 text-center py-4">
                  No configurations yet
                </p>
              ) : (
                <div className="space-y-3">
                  {configList.slice(0, 10).map((config) => (
                    <div
                      key={config.id}
                      className={`border rounded-lg p-3 cursor-pointer hover:bg-gray-50 ${
                        config.is_active ? 'bg-primary-50 border-primary-200' : ''
                      }`}
                      onClick={() => setSelectedVersion(config.version)}
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            v{config.version}
                            {config.is_active && (
                              <span className="ml-2 text-xs bg-primary-100 text-primary-800 px-2 py-1 rounded">
                                Active
                              </span>
                            )}
                          </p>
                          <p className="text-xs text-gray-500 mt-1">
                            {config.summary || 'No summary'}
                          </p>
                          <p className="text-xs text-gray-400 mt-1">
                            {new Date(config.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <span className={`status-indicator ${
                          config.status === 'applied' ? 'success' :
                          config.status === 'failed' ? 'danger' :
                          'info'
                        }`}>
                          {config.status}
                        </span>
                      </div>
                      
                      {config.status === 'draft' && (
                        <div className="mt-2 flex space-x-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleApply(config.id, true);
                            }}
                            className="text-xs btn-secondary py-1 px-2"
                            disabled={applyMutation.isPending}
                          >
                            Dry Run
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleApply(config.id, false);
                            }}
                            className="text-xs btn-primary py-1 px-2"
                            disabled={applyMutation.isPending}
                          >
                            <PlayIcon className="h-3 w-3 mr-1" />
                            Apply
                          </button>
                        </div>
                      )}
                      
                      {config.rollback_triggered && (
                        <div className="mt-2">
                          <span className="text-xs text-warning-600 flex items-center">
                            <ArrowUturnLeftIcon className="h-3 w-3 mr-1" />
                            Auto-rollback triggered
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}