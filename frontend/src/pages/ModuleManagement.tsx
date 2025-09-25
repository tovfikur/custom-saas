import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  PlusIcon,
  FolderIcon,
  TrashIcon,
  ArrowDownTrayIcon,
  InformationCircleIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';
import type { Module } from '@/types/api';

export default function ModuleManagement() {
  const [showUploadAddon, setShowUploadAddon] = useState(false);
  const [selectedModule, setSelectedModule] = useState<Module | null>(null);
  const [showModuleDetails, setShowModuleDetails] = useState(false);
  const queryClient = useQueryClient();

  const { data: modules, isLoading } = useQuery({
    queryKey: ['custom-addons'],
    queryFn: () => {
      // Mock data for now - this will be replaced with actual addon API
      return Promise.resolve({
        modules: [
          // Example addon structure - empty for now
        ],
        total: 0
      });
    },
    retry: false,
  });

  const uploadAddonMutation = useMutation({
    mutationFn: (data: FormData) => {
      // This will be replaced with actual addon upload API
      console.log('Uploading addon:', Object.fromEntries(data));
      return Promise.reject(new Error('Addon upload API not implemented yet'));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-addons'] });
      setShowUploadAddon(false);
    },
    onError: () => {
      alert('Addon upload functionality will be implemented to store custom addons for deployment to VPS servers.');
    }
  });

  const deleteAddonMutation = useMutation({
    mutationFn: (moduleId: string) => {
      console.log('Deleting addon:', moduleId);
      return Promise.reject(new Error('Addon delete API not implemented yet'));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-addons'] });
    },
    onError: () => {
      alert('Addon delete functionality will be implemented.');
    }
  });

  const handleUploadAddon = (formData: FormData) => {
    uploadAddonMutation.mutate(formData);
  };

  const handleDeleteAddon = (moduleId: string, moduleName: string) => {
    if (window.confirm(`Are you sure you want to delete the addon "${moduleName}"? This action cannot be undone.`)) {
      deleteAddonMutation.mutate(moduleId);
    }
  };

  const handleModuleClick = (module: Module) => {
    setSelectedModule(module);
    setShowModuleDetails(true);
  };

  return (
    <div className="px-4 sm:px-6 lg:px-8">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">Module Management</h1>
          <p className="mt-2 text-sm text-gray-700">
            Upload and manage custom Odoo addons for your deployments.
          </p>
        </div>
      </div>

      <div className="mt-8">
        <div className="sm:flex sm:items-center mb-6">
          <div className="sm:flex-auto">
            <h2 className="text-lg font-medium text-gray-900">Custom Odoo Addons</h2>
            <p className="mt-1 text-sm text-gray-700">
              Upload custom addons to use in your Odoo deployments
            </p>
          </div>
          <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
            <button
              type="button"
              onClick={() => setShowUploadAddon(true)}
              className="inline-flex items-center justify-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 sm:w-auto"
            >
              <PlusIcon className="h-4 w-4 mr-2" />
              Upload Addon
            </button>
          </div>
        </div>

        {/* Addons Grid */}
        {isLoading ? (
          <div className="text-center py-12">
            <p className="text-gray-500">Loading addons...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {modules?.modules && modules.modules.length > 0 ? (
              modules.modules.map((module: Module) => (
                <div key={module.id} className="bg-white overflow-hidden shadow rounded-lg hover:shadow-lg transition-shadow duration-200 cursor-pointer">
                  <div className="p-6" onClick={() => handleModuleClick(module)}>
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-medium text-gray-900 flex items-center">
                        {module.name}
                        <InformationCircleIcon className="h-4 w-4 ml-2 text-gray-400" />
                      </h3>
                      {module.file_type && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          {module.file_type}
                        </span>
                      )}
                    </div>
                    <p className="mt-2 text-sm text-gray-600">{module.description || 'Custom Odoo addon'}</p>
                    <div className="mt-2 text-xs text-gray-500">
                      Size: {module.file_size_mb} MB • Click for details
                    </div>
                  </div>
                  <div className="px-6 py-3 bg-gray-50 flex justify-between">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteAddon(module.id, module.name);
                      }}
                      disabled={deleteAddonMutation.isPending}
                      className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-red-700 bg-red-100 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
                    >
                      <TrashIcon className="h-4 w-4 mr-1" />
                      {deleteAddonMutation.isPending ? 'Deleting...' : 'Delete'}
                    </button>
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        alert('Download functionality will be implemented for custom addons.');
                      }}
                      className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-blue-700 bg-blue-100 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                    >
                      <ArrowDownTrayIcon className="h-4 w-4 mr-1" />
                      Download
                    </button>
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        alert('Deploy to VPS functionality will be implemented. This will deploy the addon to a selected VPS server.');
                      }}
                      className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-green-700 bg-green-100 hover:bg-green-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                    >
                      <svg className="h-4 w-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 12h14M12 5l7 7-7 7"/>
                      </svg>
                      Deploy to VPS
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-3 text-center py-12">
                <FolderIcon className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-2 text-sm font-medium text-gray-900">No addons uploaded</h3>
                <p className="mt-1 text-gray-500">Upload your first custom Odoo addon to get started.</p>
                <div className="mt-6">
                  <button
                    type="button"
                    onClick={() => setShowUploadAddon(true)}
                    className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <PlusIcon className="h-4 w-4 mr-2" />
                    Upload Addon
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Upload Addon Modal */}
      {showUploadAddon && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-[500px] max-w-lg shadow-lg rounded-md bg-white">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Upload Custom Addon</h3>
            <form onSubmit={(e) => {
              e.preventDefault();
              handleUploadAddon(new FormData(e.target as HTMLFormElement));
            }} encType="multipart/form-data">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Addon Name</label>
                  <input
                    type="text"
                    name="name"
                    required
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    placeholder="my_custom_addon"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Description (optional)</label>
                  <textarea
                    name="description"
                    rows={2}
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    placeholder="Brief description of your custom addon"
                  />
                </div>

                {/* Addon Files */}
                <div>
                  <label className="block text-sm font-medium text-gray-700">Addon Files</label>
                  <input
                    type="file"
                    name="addon_files"
                    multiple
                    required
                    accept=".zip,.tar.gz,.py,.xml,.js,.css,.scss,.png,.jpg,.svg,.csv"
                    className="mt-1 block w-full text-sm text-gray-500
                      file:mr-4 file:py-2 file:px-4
                      file:rounded-full file:border-0
                      file:text-sm file:font-semibold
                      file:bg-blue-50 file:text-blue-700
                      hover:file:bg-blue-100"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Upload custom addon files for Odoo. Supports: Python files, XML views, JS/CSS assets, images, compressed folders
                  </p>
                  <div className="mt-2 text-xs text-gray-400">
                    <strong>File Manager Preview:</strong> These files will be stored and can be deployed to VPS servers using Docker volumes (e.g., -v ~/custom-addons:/mnt/extra-addons)
                  </div>
                </div>
              </div>
              <div className="mt-6 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowUploadAddon(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploadAddonMutation.isPending}
                  className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                >
                  {uploadAddonMutation.isPending ? 'Uploading...' : 'Upload Addon'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Addon Details Modal */}
      {showModuleDetails && selectedModule && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-[600px] max-w-2xl shadow-lg rounded-md bg-white">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-semibold text-gray-900">Addon Details</h3>
              <button
                onClick={() => setShowModuleDetails(false)}
                className="text-gray-400 hover:text-gray-600 focus:outline-none"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <h4 className="text-lg font-medium text-gray-900 mb-3">Basic Information</h4>
                <div className="bg-gray-50 p-4 rounded-md space-y-2">
                  <div>
                    <span className="text-sm font-medium text-gray-500">Name:</span>
                    <p className="text-sm text-gray-900">{selectedModule.name}</p>
                  </div>
                  {selectedModule.file_type && (
                    <div>
                      <span className="text-sm font-medium text-gray-500">File Type:</span>
                      <p className="text-sm text-gray-900">{selectedModule.file_type}</p>
                    </div>
                  )}
                  <div>
                    <span className="text-sm font-medium text-gray-500">File Size:</span>
                    <p className="text-sm text-gray-900">{selectedModule.file_size_mb} MB</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-gray-500">Uploaded:</span>
                    <p className="text-sm text-gray-900">
                      {new Date(selectedModule.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>

              {/* Description */}
              {selectedModule.description && (
                <div>
                  <h4 className="text-lg font-medium text-gray-900 mb-3">Description</h4>
                  <p className="text-sm text-gray-700 bg-gray-50 p-4 rounded-md">{selectedModule.description}</p>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="mt-6 flex justify-between">
              <button
                onClick={() => handleDeleteAddon(selectedModule.id, selectedModule.name)}
                disabled={deleteAddonMutation.isPending}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-red-700 bg-red-100 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
              >
                <TrashIcon className="h-4 w-4 mr-2" />
                {deleteAddonMutation.isPending ? 'Deleting...' : 'Delete Addon'}
              </button>
              <div className="flex space-x-3">
                <button
                  onClick={() => setShowModuleDetails(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Close
                </button>
                <button
                  onClick={() => {
                    alert('Download functionality will be implemented for custom addons.');
                  }}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
                  Download Addon
                </button>
                <button
                  onClick={() => {
                    alert('Deploy to VPS functionality will be implemented. This will create a custom-addons folder on the selected VPS and deploy the addon.');
                  }}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                >
                  <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                  Deploy to VPS
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}