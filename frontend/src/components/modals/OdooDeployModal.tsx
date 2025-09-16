import { Dialog } from '@headlessui/react';
import { XMarkIcon } from '@heroicons/react/24/outline';

interface OdooDeployModalProps {
    isOpen: boolean;
    onClose: () => void;
    template: any; // you can type as OdooTemplate
    vpsHosts: any[];
    onSubmit: (formData: FormData) => void;
}

export default function OdooDeployModal({ isOpen, onClose, template, vpsHosts, onSubmit }: OdooDeployModalProps) {
    if (!isOpen || !template) return null;

    return (
        <Dialog open={isOpen} onClose={onClose} as="div" className="fixed inset-0 z-50 overflow-y-auto">
            <div className="flex items-center justify-center min-h-screen px-4">
                <Dialog.Overlay className="fixed inset-0 bg-black bg-opacity-30" />

                <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
                    <div className="flex justify-between items-center mb-4">
                        <Dialog.Title className="text-lg font-medium text-gray-900">
                            Deploy Template: {template.name}
                        </Dialog.Title>
                        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
                            <XMarkIcon className="h-6 w-6" />
                        </button>
                    </div>

                    <form
                        onSubmit={(e) => {
                            e.preventDefault();
                            const formData = new FormData(e.target as HTMLFormElement);
                            onSubmit(formData);
                        }}
                        className="space-y-4"
                    >
                        {/* VPS Dropdown */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700">Select VPS</label>
                            <select name="vps_id" required className="form-select mt-1 w-full">
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
                            <input type="text" name="domain" required className="form-input mt-1 w-full" placeholder="example.com" />
                        </div>

                        {/* DB Credentials */}
                        <div className="grid grid-cols-2 gap-4">
                            <input type="text" name="db_name" required placeholder="DB Name" className="form-input mt-1 w-full" />
                            <input type="text" name="db_user" required placeholder="DB User" className="form-input mt-1 w-full" />
                            <input type="password" name="db_password" required placeholder="DB Password" className="form-input mt-1 w-full" />
                            <input type="text" name="db_host" defaultValue="192.168.50.2" className="form-input mt-1 w-full" />
                            <input type="number" name="db_port" defaultValue="5432" className="form-input mt-1 w-full" />
                            <input type="text" name="deployment_name" placeholder="Deployment Name (optional)" className="form-input mt-1 w-full" />
                        </div>

                        {/* Actions */}
                        <div className="mt-6 flex justify-end space-x-3">
                            <button type="button" onClick={onClose} className="btn-secondary">
                                Cancel
                            </button>
                            <button type="submit" className="btn-primary">
                                Deploy
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </Dialog>
    );
}
