import { Dialog } from '@headlessui/react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { useEffect, useRef, useState } from 'react';
import LoadingSpinner from '@/components/ui/LoadingSpinner';

interface OdooDeployModalProps {
  isOpen: boolean;
  onClose: () => void;
  template: any; // you can type as OdooTemplate
  vpsHosts: any[];
  onSubmit: (formData: FormData) => Promise<any> | any;
}

export default function OdooDeployModal({ isOpen, onClose, template, vpsHosts, onSubmit }: OdooDeployModalProps) {
  const [isDeploying, setIsDeploying] = useState(false);
  const [progress, setProgress] = useState(0);
  const timerRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
  }, []);

  const startProgress = () => {
    setProgress(5);
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = window.setInterval(() => {
      setProgress((p) => {
        // Ease towards 90% while deploying
        if (p < 90) return Math.min(90, p + Math.max(2, Math.round((100 - p) * 0.05)));
        return p;
      });
    }, 800);
  };

  const stopProgress = (to = 100) => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setProgress(to);
  };

  if (!isOpen || !template) return null;

    return (
        <Dialog open={isOpen} onClose={onClose} as="div" className="fixed inset-0 z-50 overflow-y-auto">
            <div className="flex items-center justify-center min-h-screen px-4">
                <Dialog.Overlay className="fixed inset-0 bg-black bg-opacity-30" />

                <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
                    {/* Progress bar */}
                    {isDeploying && (
                      <div className="absolute left-0 right-0 top-0 h-1 bg-gray-200 overflow-hidden rounded-t-lg">
                        <div
                          className="h-full bg-blue-600 transition-all"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                    )}
                    <div className="flex justify-between items-center mb-4">
                        <Dialog.Title className="text-lg font-medium text-gray-900">
                            Deploy Template: {template.name}
                        </Dialog.Title>
                        <button onClick={onClose} className="text-gray-400 hover:text-gray-600" disabled={isDeploying}>
                            <XMarkIcon className="h-6 w-6" />
                        </button>
                    </div>

                    <form
                        onSubmit={async (e) => {
                          e.preventDefault();
                          const formData = new FormData(e.target as HTMLFormElement);
                          try {
                            setIsDeploying(true);
                            startProgress();
                            await onSubmit(formData);
                            if (!mountedRef.current) return;
                            stopProgress(100);
                          } catch (err) {
                            if (!mountedRef.current) return;
                            // Let parent handle toast; just stop progress
                            stopProgress(0);
                            setIsDeploying(false);
                          }
                        }}
                        className="space-y-4"
                    >
                        {isDeploying && (
                          <div className="rounded-md bg-blue-50 p-3 text-sm text-blue-700">
                            <div className="flex items-center">
                              <LoadingSpinner size="sm" className="mr-2" />
                              Deploying... This can take a few minutes. Please keep this tab open.
                            </div>
                          </div>
                        )}
                        {/* VPS Dropdown */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700">Select VPS</label>
                            <select name="vps_id" required className="form-select mt-1 w-full" disabled={isDeploying}>
                                {vpsHosts.map((host) => (
                                    <option key={host.id} value={host.id}>
                                        {host.name} ({host.ip_address})
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Domain */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700">Domain</label>
                            <input type="text" name="domain" required className="form-input mt-1 w-full" placeholder="example.com" disabled={isDeploying} />
                        </div>

                        {/* DB Credentials */}
                        <div className="grid grid-cols-2 gap-4">
                            <input type="text" name="db_name" required placeholder="DB Name" className="form-input mt-1 w-full" disabled={isDeploying} />
                            <input type="text" name="db_user" required placeholder="DB User" className="form-input mt-1 w-full" disabled={isDeploying} />
                            <input type="password" name="db_password" required placeholder="DB Password" className="form-input mt-1 w-full" disabled={isDeploying} />
                            <input type="text" name="db_host" defaultValue="192.168.50.2" className="form-input mt-1 w-full" disabled={isDeploying} />
                            <input type="number" name="db_port" defaultValue="5432" className="form-input mt-1 w-full" disabled={isDeploying} />
                            <input type="text" name="deployment_name" placeholder="Deployment Name (optional)" className="form-input mt-1 w-full" disabled={isDeploying} />
                        </div>

                        {/* Actions */}
                        <div className="mt-6 flex justify-end space-x-3">
                            <button type="button" onClick={onClose} className="btn-secondary" disabled={isDeploying}>
                                Cancel
                            </button>
                            <button type="submit" className="btn-primary" disabled={isDeploying}>
                              {isDeploying ? (
                                <>
                                  <LoadingSpinner size="sm" className="mr-2" />
                                  Deploying...
                                </>
                              ) : (
                                'Deploy'
                              )}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </Dialog>
    );
}
