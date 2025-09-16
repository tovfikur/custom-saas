import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import OdooDeployModal from '@/components/modals/OdooDeployModal';
import { odooApi, vpsApi } from '@/services/api';
import {
  PlusIcon,
  ServerIcon,
  PlayIcon,
  StopIcon,
  TrashIcon,
  BuildingOfficeIcon,
  InformationCircleIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';
import type {OdooTemplate, OdooDeployment, VPSHost} from '@/types/api';

export default function OdooManagement() {
  const [activeTab, setActiveTab] = useState<'templates' | 'deployments'>('templates');
  const [showCreateTemplate, setShowCreateTemplate] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<OdooTemplate | null>(null);
  const [showTemplateDetails, setShowTemplateDetails] = useState(false);
  const queryClient = useQueryClient();
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [selectedTemplateForDeploy, setSelectedTemplateForDeploy] = useState<OdooTemplate | null>(null);

    const { data: vpsHosts = [] } = useQuery<VPSHost[]>({
        queryKey: ['vps-hosts'],
        queryFn: () => vpsApi.list(true).then(r => r.data), // r.data is VPSHost[]
    });


  const { data: templates } = useQuery({
    queryKey: ['odoo-templates'],
    queryFn: () => odooApi.getTemplates({ is_public: false }).then(res => res.data)
  });

  const { data: deployments } = useQuery({
    queryKey: ['odoo-deployments'],
    queryFn: () => odooApi.getDeployments().then(res => res.data)
  });

  const createTemplateMutation = useMutation({
    mutationFn: (data: FormData) => odooApi.createTemplate(data).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['odoo-templates'] });
      setShowCreateTemplate(false);
    }
  });

  const deleteTemplateMutation = useMutation({
    mutationFn: (templateId: string) => odooApi.deleteTemplate(templateId).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['odoo-templates'] });
    }
  });

  const handleCreateTemplate = (formData: FormData) => {
    // FormData already contains all the form fields including file uploads
    createTemplateMutation.mutate(formData);
  };

  const handleDeleteTemplate = (templateId: string, templateName: string) => {
    if (window.confirm(`Are you sure you want to delete the template "${templateName}"? This action cannot be undone.`)) {
      deleteTemplateMutation.mutate(templateId);
    }
  };

  const handleTemplateClick = (template: OdooTemplate) => {
    setSelectedTemplate(template);
    setShowTemplateDetails(true);
  };

  const industries = [
    'Restaurant', 'Retail', 'Manufacturing', 'Healthcare', 
    'Education', 'Real Estate', 'Construction', 'Other'
  ];

  const odooVersions = ['17', '16', '15', '14'];

  return (
    <div className="px-4 sm:px-6 lg:px-8">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">Odoo Management</h1>
          <p className="mt-2 text-sm text-gray-700">
            Create industry-specific Odoo templates and deploy them to your VPS servers.
          </p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="mt-8">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('templates')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'templates'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <BuildingOfficeIcon className="w-5 h-5 inline mr-2" />
              Templates
            </button>
            <button
              onClick={() => setActiveTab('deployments')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'deployments'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <ServerIcon className="w-5 h-5 inline mr-2" />
              Deployments
            </button>
          </nav>
        </div>
      </div>

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div className="mt-8">
          <div className="sm:flex sm:items-center mb-6">
            <div className="sm:flex-auto">
              <h2 className="text-lg font-medium text-gray-900">Odoo Templates</h2>
              <p className="mt-1 text-sm text-gray-700">
                Industry-specific Odoo configurations with backup databases
              </p>
            </div>
            <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
              <button
                type="button"
                onClick={() => setShowCreateTemplate(true)}
                className="inline-flex items-center justify-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 sm:w-auto"
              >
                <PlusIcon className="h-4 w-4 mr-2" />
                Create Template
              </button>
            </div>
          </div>

          {/* Templates List */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {templates?.templates && templates.templates.length > 0 ? (
              templates.templates.map((template: OdooTemplate) => (
                <div key={template.id} className="bg-white overflow-hidden shadow rounded-lg hover:shadow-lg transition-shadow duration-200 cursor-pointer">
                  <div className="p-6" onClick={() => handleTemplateClick(template)}>
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-medium text-gray-900 flex items-center">
                        {template.name}
                        <InformationCircleIcon className="h-4 w-4 ml-2 text-gray-400" />
                      </h3>
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        v{template.version}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-gray-600">{template.description || 'No description available'}</p>
                    <div className="mt-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                        {template.industry}
                      </span>
                    </div>
                    <div className="mt-2 text-xs text-gray-500">
                      Click to view details
                    </div>
                  </div>
                  <div className="px-6 py-3 bg-gray-50 flex justify-between">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteTemplate(template.id, template.name);
                      }}
                      disabled={deleteTemplateMutation.isPending}
                      className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-red-700 bg-red-100 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
                    >
                      <TrashIcon className="h-4 w-4 mr-1" />
                      {deleteTemplateMutation.isPending ? 'Deleting...' : 'Delete'}
                    </button>
                    <button
                        onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setSelectedTemplateForDeploy(template);
                            setShowDeployModal(true);
                        }}

                        className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-blue-700 bg-blue-100 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                    >
                      <PlayIcon className="h-4 w-4 mr-1" />
                      Deploy
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-3 text-center py-12">
                <BuildingOfficeIcon className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-2 text-sm font-medium text-gray-900">No templates</h3>
                <p className="mt-1 text-sm text-gray-500">Get started by creating your first Odoo template.</p>
                <div className="mt-6">
                  <button
                    type="button"
                    onClick={() => setShowCreateTemplate(true)}
                    className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <PlusIcon className="h-4 w-4 mr-2" />
                    Create Template
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Deployments Tab */}
      {activeTab === 'deployments' && (
        <div className="mt-8">
          <div className="sm:flex sm:items-center mb-6">
            <div className="sm:flex-auto">
              <h2 className="text-lg font-medium text-gray-900">Active Deployments</h2>
              <p className="mt-1 text-sm text-gray-700">
                Running Odoo instances across your VPS servers
              </p>
            </div>
          </div>

          {/* Deployments Table */}
          <div className="mt-8 flex flex-col">
            <div className="-my-2 -mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
              <div className="inline-block min-w-full py-2 align-middle md:px-6 lg:px-8">
                <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
                  <table className="min-w-full divide-y divide-gray-300">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                          Name
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                          Template
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                          VPS
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                          Status
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                          Domain
                        </th>
                        <th className="relative px-6 py-3">
                          <span className="sr-only">Actions</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {deployments?.deployments && deployments.deployments.length > 0 ? (
                        deployments.deployments.map((deployment: OdooDeployment) => (
                          <tr key={deployment.id}>
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                              {deployment.name}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {deployment.template_name}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {deployment.vps_name}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                                deployment.status === 'running' ? 'bg-green-100 text-green-800' :
                                deployment.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                                deployment.status === 'stopped' ? 'bg-gray-100 text-gray-800' :
                                'bg-red-100 text-red-800'
                              }`}>
                                {deployment.status}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              <a href={`http://${deployment.domain}`} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-900">
                                {deployment.domain}
                              </a>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                              <div className="flex space-x-2">
                                <button className="text-blue-600 hover:text-blue-900">
                                  <PlayIcon className="h-4 w-4" />
                                </button>
                                <button className="text-gray-600 hover:text-gray-900">
                                  <StopIcon className="h-4 w-4" />
                                </button>
                                <button className="text-red-600 hover:text-red-900">
                                  <TrashIcon className="h-4 w-4" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} className="px-6 py-12 text-center text-sm text-gray-500">
                            <ServerIcon className="mx-auto h-12 w-12 text-gray-400" />
                            <h3 className="mt-2 text-sm font-medium text-gray-900">No deployments</h3>
                            <p className="mt-1 text-sm text-gray-500">Deploy your first Odoo template to see it here.</p>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Template Modal */}
      {showCreateTemplate && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-[600px] max-w-2xl shadow-lg rounded-md bg-white">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Create Odoo Template</h3>
            <form onSubmit={(e) => {
              e.preventDefault();
              handleCreateTemplate(new FormData(e.target as HTMLFormElement));
            }} encType="multipart/form-data">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Name</label>
                  <input
                    type="text"
                    name="name"
                    required
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    placeholder="Restaurant Management System"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Industry</label>
                  <select
                    name="industry"
                    required
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  >
                    <option value="">Select Industry</option>
                    {industries.map(industry => (
                      <option key={industry} value={industry}>{industry}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Odoo Version</label>
                  <select
                    name="version"
                    required
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  >
                    <option value="">Select Version</option>
                    {odooVersions.map(version => (
                      <option key={version} value={version}>{version}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Description</label>
                  <textarea
                    name="description"
                    rows={3}
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    placeholder="Complete restaurant management with POS, inventory, and accounting"
                  />
                </div>

                {/* Database Backup File */}
                <div>
                  <label className="block text-sm font-medium text-gray-700">Database Backup File</label>
                  <input
                    type="file"
                    name="backup_file"
                    accept=".zip,.sql,.gz"
                    className="mt-1 block w-full text-sm text-gray-500
                      file:mr-4 file:py-2 file:px-4
                      file:rounded-full file:border-0
                      file:text-sm file:font-semibold
                      file:bg-blue-50 file:text-blue-700
                      hover:file:bg-blue-100"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Upload a database backup file (.zip, .sql, or .gz). This will be used as the base database for new deployments.
                  </p>
                </div>
              </div>
              <div className="mt-6 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowCreateTemplate(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createTemplateMutation.isPending}
                  className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                >
                  {createTemplateMutation.isPending ? 'Creating...' : 'Create Template'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Template Details Modal */}
      {showTemplateDetails && selectedTemplate && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-[700px] max-w-4xl shadow-lg rounded-md bg-white">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-semibold text-gray-900">Template Details</h3>
              <button
                onClick={() => setShowTemplateDetails(false)}
                className="text-gray-400 hover:text-gray-600 focus:outline-none"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>
            
            <div className="space-y-6">
              {/* Basic Information */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-lg font-medium text-gray-900 mb-3">Basic Information</h4>
                  <div className="space-y-2">
                    <div>
                      <span className="text-sm font-medium text-gray-500">Name:</span>
                      <p className="text-sm text-gray-900">{selectedTemplate.name}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-gray-500">Industry:</span>
                      <p className="text-sm text-gray-900">{selectedTemplate.industry}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-gray-500">Odoo Version:</span>
                      <p className="text-sm text-gray-900">v{selectedTemplate.version}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-gray-500">Category:</span>
                      <p className="text-sm text-gray-900">{selectedTemplate.category || 'Not specified'}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-gray-500">Complexity:</span>
                      <p className="text-sm text-gray-900 capitalize">{selectedTemplate.complexity_level || 'Not specified'}</p>
                    </div>
                  </div>
                </div>
                
                <div>
                  <h4 className="text-lg font-medium text-gray-900 mb-3">Usage Statistics</h4>
                  <div className="space-y-2">
                    <div>
                      <span className="text-sm font-medium text-gray-500">Deployments:</span>
                      <p className="text-sm text-gray-900">{selectedTemplate.deployment_count}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-gray-500">Downloads:</span>
                      <p className="text-sm text-gray-900">{selectedTemplate.download_count}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-gray-500">Backup Size:</span>
                      <p className="text-sm text-gray-900">{selectedTemplate.backup_file_size_mb} MB</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-gray-500">Status:</span>
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        selectedTemplate.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                      }`}>
                        {selectedTemplate.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-gray-500">Visibility:</span>
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        selectedTemplate.is_public ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
                      }`}>
                        {selectedTemplate.is_public ? 'Public' : 'Private'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Description */}
              {selectedTemplate.description && (
                <div>
                  <h4 className="text-lg font-medium text-gray-900 mb-3">Description</h4>
                  <p className="text-sm text-gray-700 bg-gray-50 p-4 rounded-md">{selectedTemplate.description}</p>
                </div>
              )}


              {/* Tags */}
              {selectedTemplate.tags && selectedTemplate.tags.length > 0 && (
                <div>
                  <h4 className="text-lg font-medium text-gray-900 mb-3">Tags</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedTemplate.tags.map((tag, index) => (
                      <span
                        key={index}
                        className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Dates */}
              <div>
                <h4 className="text-lg font-medium text-gray-900 mb-3">Timeline</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <span className="text-sm font-medium text-gray-500">Created:</span>
                    <p className="text-sm text-gray-900">
                      {new Date(selectedTemplate.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-gray-500">Updated:</span>
                    <p className="text-sm text-gray-900">
                      {new Date(selectedTemplate.updated_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="mt-8 flex justify-between">
              <button
                onClick={() => handleDeleteTemplate(selectedTemplate.id, selectedTemplate.name)}
                disabled={deleteTemplateMutation.isPending}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-red-700 bg-red-100 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
              >
                <TrashIcon className="h-4 w-4 mr-2" />
                {deleteTemplateMutation.isPending ? 'Deleting...' : 'Delete Template'}
              </button>
              <div className="flex space-x-3">
                <button
                  onClick={() => setShowTemplateDetails(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Close
                </button>
                <button
                  onClick={() => {
                    setShowTemplateDetails(false);
                    console.log('Deploy template:', selectedTemplate.id);
                  }}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <PlayIcon className="h-4 w-4 mr-2" />
                  Deploy Template
                </button>
                  <button
                      onClick={() => {
                          setShowTemplateDetails(false);
                          setSelectedTemplateForDeploy(selectedTemplate);
                          setShowDeployModal(true);
                      }}
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                      <PlayIcon className="h-4 w-4 mr-2" />
                      Deploy Template
                  </button>
              </div>
            </div>
          </div>
        </div>
      )}
        {showDeployModal && selectedTemplateForDeploy && (
            <OdooDeployModal
                isOpen={showDeployModal}
                onClose={() => setShowDeployModal(false)}
                template={selectedTemplateForDeploy}
                vpsHosts={vpsHosts}
                onSubmit={async (formData) => {
                    const data = Object.fromEntries(formData as any) as any;
                    const token = localStorage.getItem('auth_token') ?? '';
                    console.log('Token found:', token ? 'Yes' : 'No', token?.substring(0, 20) + '...');
                    const payload = {
                        template_id: selectedTemplateForDeploy.id,
                        vps_id: data.vps_id,
                        deployment_name:
                            (data.deployment_name as string) ??
                            selectedTemplateForDeploy.name.replace(/\s+/g, '-').toLowerCase(),
                        domain: data.domain,
                        // optional:
                        selected_version: selectedTemplateForDeploy.version,
                        selected_modules: [],
                        custom_config: {},
                        custom_env_vars: {},
                        // database configuration:
                        db_name: data.db_name,
                        db_user: data.db_user,
                        db_password: data.db_password,
                        db_host: data.db_host || 'localhost',
                        db_port: data.db_port ? parseInt(data.db_port) : 5432,
                    };

                    try {
                        const res = await odooApi.deployOdoo(payload);
                        console.log('Deployment successful:', res.data);
                        // Refresh deployments list
                        queryClient.invalidateQueries({ queryKey: ['odoo-deployments'] });
                        setShowDeployModal(false);
                    } catch (error: any) {
                        console.error('Deploy failed:', error.response?.data || error.message);
                        // show your toast/alert here
                        return;
                    }
                }}
            />
        )}
    </div>
  );
}