import { useState, Fragment } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Dialog, Transition } from '@headlessui/react';
import { XMarkIcon, EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import { vpsApi } from '@/services/api';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import type { VPSOnboardRequest } from '@/types/api';

interface VPSOnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function VPSOnboardingModal({ isOpen, onClose }: VPSOnboardingModalProps) {
  const queryClient = useQueryClient();
  const [showPassword, setShowPassword] = useState(false);
  const [showPrivateKey, setShowPrivateKey] = useState(false);
  const [authMethod, setAuthMethod] = useState<'password' | 'key'>('password');

  const [formData, setFormData] = useState<VPSOnboardRequest>({
    name: '',
    hostname: '',
    ip_address: '',
    username: 'root',
    port: 22,
    password: '',
    private_key: '',
    bootstrap: true
  });

  const onboardMutation = useMutation({
    mutationFn: vpsApi.onboard,
    onSuccess: () => {
      toast.success('VPS onboarded successfully!');
      queryClient.invalidateQueries({ queryKey: ['vps-hosts'] });
      onClose();
      resetForm();
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to onboard VPS';
      toast.error(message);
    },
  });

  const resetForm = () => {
    setFormData({
      name: '',
      hostname: '',
      ip_address: '',
      username: 'root',
      port: 22,
      password: '',
      private_key: '',
      bootstrap: true
    });
    setAuthMethod('password');
    setShowPassword(false);
    setShowPrivateKey(false);
  };

  const handleClose = () => {
    if (!onboardMutation.isPending) {
      onClose();
      resetForm();
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validation
    if (!formData.name.trim()) {
      toast.error('Please enter a VPS name');
      return;
    }
    
    // Allow either hostname or IP address
    const hasHostname = !!formData.hostname?.trim();
    const hasIp = !!formData.ip_address?.trim();
    if (!hasHostname && !hasIp) {
      toast.error('Please provide either a hostname or an IP address');
      return;
    }
    
    if (!formData.username.trim()) {
      toast.error('Please enter a username');
      return;
    }

    // Check authentication method
    if (authMethod === 'password' && !formData.password?.trim()) {
      toast.error('Please enter a password');
      return;
    }

    if (authMethod === 'key' && !formData.private_key?.trim()) {
      toast.error('Please enter a private key');
      return;
    }

    // Submit form
    // Normalize: if only one of hostname/IP provided, use it for both fields
    const normalizedHostname = hasHostname ? (formData.hostname || '').trim() : (formData.ip_address || '').trim();
    const normalizedIp = hasIp ? (formData.ip_address || '').trim() : (formData.hostname || '').trim();
    const submitData = {
      ...formData,
      hostname: normalizedHostname,
      ip_address: normalizedIp,
      password: authMethod === 'password' ? formData.password : undefined,
      private_key: authMethod === 'key' ? formData.private_key : undefined
    };

    onboardMutation.mutate(submitData);
  };

  const handleInputChange = (field: keyof VPSOnboardRequest, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  return (
    <Transition show={isOpen} as={Fragment}>
      <Dialog onClose={handleClose} className="relative z-50">
        <Transition.Child
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 z-10 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <Transition.Child
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-2xl sm:p-6">
                
                {/* Header */}
                <div className="absolute right-0 top-0 hidden pr-4 pt-4 sm:block">
                  <button
                    type="button"
                    className="rounded-md bg-white text-gray-400 hover:text-gray-500"
                    onClick={handleClose}
                    disabled={onboardMutation.isPending}
                  >
                    <XMarkIcon className="h-6 w-6" />
                  </button>
                </div>

                <div className="sm:flex sm:items-start">
                  <div className="w-full">
                    <Dialog.Title as="h3" className="text-base font-semibold leading-6 text-gray-900">
                      Add New VPS
                    </Dialog.Title>
                
                <div className="mt-2">
                  <p className="text-sm text-gray-500">
                    Onboard a new VPS server to manage Nginx configurations and deployments.
                  </p>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="mt-6 space-y-6">
                  <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                    
                    {/* Basic Information */}
                    <div className="sm:col-span-2">
                      <h4 className="text-sm font-medium text-gray-900 mb-4">Basic Information</h4>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        VPS Name *
                      </label>
                      <input
                        type="text"
                        value={formData.name}
                        onChange={(e) => handleInputChange('name', e.target.value)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                        placeholder="e.g., Production Server 1"
                        required
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        Hostname
                      </label>
                      <input
                        type="text"
                        value={formData.hostname}
                        onChange={(e) => handleInputChange('hostname', e.target.value)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                        placeholder="e.g., server1.example.com"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        IP Address
                      </label>
                      <input
                        type="text"
                        value={formData.ip_address}
                        onChange={(e) => handleInputChange('ip_address', e.target.value)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                        placeholder="e.g., 192.168.1.100"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        SSH Port
                      </label>
                      <input
                        type="number"
                        value={formData.port}
                        onChange={(e) => handleInputChange('port', parseInt(e.target.value) || 22)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                        min="1"
                        max="65535"
                      />
                    </div>

                    {/* SSH Authentication */}
                    <div className="sm:col-span-2">
                      <h4 className="text-sm font-medium text-gray-900 mb-4">SSH Authentication</h4>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        Username *
                      </label>
                      <input
                        type="text"
                        value={formData.username}
                        onChange={(e) => handleInputChange('username', e.target.value)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                        required
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Authentication Method
                      </label>
                      <div className="flex space-x-4">
                        <label className="flex items-center">
                          <input
                            type="radio"
                            name="authMethod"
                            value="password"
                            checked={authMethod === 'password'}
                            onChange={() => setAuthMethod('password')}
                            className="focus:ring-primary-500 h-4 w-4 text-primary-600 border-gray-300"
                          />
                          <span className="ml-2 text-sm text-gray-700">Password</span>
                        </label>
                        <label className="flex items-center">
                          <input
                            type="radio"
                            name="authMethod"
                            value="key"
                            checked={authMethod === 'key'}
                            onChange={() => setAuthMethod('key')}
                            className="focus:ring-primary-500 h-4 w-4 text-primary-600 border-gray-300"
                          />
                          <span className="ml-2 text-sm text-gray-700">Private Key</span>
                        </label>
                      </div>
                    </div>

                    {/* Password field */}
                    {authMethod === 'password' && (
                      <div className="sm:col-span-2">
                        <label className="block text-sm font-medium text-gray-700">
                          Password *
                        </label>
                        <div className="mt-1 relative">
                          <input
                            type={showPassword ? 'text' : 'password'}
                            value={formData.password}
                            onChange={(e) => handleInputChange('password', e.target.value)}
                            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 pr-10"
                            required
                          />
                          <button
                            type="button"
                            className="absolute inset-y-0 right-0 flex items-center pr-3"
                            onClick={() => setShowPassword(!showPassword)}
                          >
                            {showPassword ? (
                              <EyeSlashIcon className="h-5 w-5 text-gray-400" />
                            ) : (
                              <EyeIcon className="h-5 w-5 text-gray-400" />
                            )}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Private key field */}
                    {authMethod === 'key' && (
                      <div className="sm:col-span-2">
                        <label className="block text-sm font-medium text-gray-700">
                          Private Key *
                        </label>
                        <div className="mt-1 relative">
                          <textarea
                            value={formData.private_key}
                            onChange={(e) => handleInputChange('private_key', e.target.value)}
                            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
                            rows={showPrivateKey ? 10 : 3}
                            placeholder="-----BEGIN PRIVATE KEY-----&#10;...&#10;-----END PRIVATE KEY-----"
                            required
                          />
                          <button
                            type="button"
                            className="absolute top-2 right-2 text-sm text-gray-500 hover:text-gray-700"
                            onClick={() => setShowPrivateKey(!showPrivateKey)}
                          >
                            {showPrivateKey ? 'Collapse' : 'Expand'}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Bootstrap option */}
                    <div className="sm:col-span-2">
                      <div className="flex items-center">
                        <input
                          type="checkbox"
                          checked={formData.bootstrap}
                          onChange={(e) => handleInputChange('bootstrap', e.target.checked)}
                          className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                        />
                        <label className="ml-2 block text-sm text-gray-700">
                          Bootstrap VPS (Install Docker and Nginx)
                        </label>
                      </div>
                      <div className="mt-2 p-3 bg-blue-50 rounded-md">
                        <p className="text-xs text-blue-800 font-medium mb-1">Bootstrap Requirements:</p>
                        <ul className="text-xs text-blue-700 space-y-1">
                          <li>• User must have sudo privileges</li>
                          <li>• Internet access for package installation</li>
                          <li>• Ubuntu/Debian or CentOS/RHEL system</li>
                        </ul>
                        <p className="text-xs text-blue-600 mt-2">
                          If bootstrap fails, the VPS will still be added but you'll need to manually install Docker and Nginx.
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Buttons */}
                  <div className="mt-6 flex justify-end space-x-3">
                    <button
                      type="button"
                      onClick={handleClose}
                      disabled={onboardMutation.isPending}
                      className="inline-flex justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={onboardMutation.isPending}
                      className="inline-flex justify-center rounded-md bg-primary-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600 disabled:opacity-50"
                    >
                      {onboardMutation.isPending ? (
                        <>
                          <LoadingSpinner size="sm" className="mr-2" />
                          Onboarding...
                        </>
                      ) : (
                        'Add VPS'
                      )}
                    </button>
                  </div>
                </form>
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
