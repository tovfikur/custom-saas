import { Routes, Route, Navigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { authApi } from '@/services/api';
import LoginPage from '@/pages/LoginPage';
import DashboardLayout from '@/components/layout/DashboardLayout';
import Dashboard from '@/pages/Dashboard';
import VPSManagement from '@/pages/VPSManagement';
import VPSDashboard from '@/pages/VPSDashboard';
import NginxConfigEditor from '@/pages/NginxConfigEditor';
import MonitoringPage from '@/pages/MonitoringPage';
import OdooManagement from '@/pages/OdooManagement';
import ModuleManagement from '@/pages/ModuleManagement';
import LoadingSpinner from '@/components/ui/LoadingSpinner';

function App() {
  const token = localStorage.getItem('auth_token');
  
  const { data: profile, isLoading, error } = useQuery({
    queryKey: ['profile'],
    queryFn: () => authApi.getProfile(),
    enabled: !!token,
    retry: false,
  });

  // Show loading spinner while checking authentication
  if (token && isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  // If no token or profile fetch failed, show login
  if (!token || error) {
    return <LoginPage />;
  }

  // Authenticated routes
  return (
    <DashboardLayout user={profile?.data}>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/vps" element={<VPSManagement />} />
        <Route path="/vps/:vpsId" element={<VPSDashboard />} />
        <Route path="/vps/:vpsId/nginx" element={<NginxConfigEditor />} />
        <Route path="/odoo" element={<OdooManagement />} />
        <Route path="/modules" element={<ModuleManagement />} />
        <Route path="/monitoring" element={<MonitoringPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </DashboardLayout>
  );
}

export default App;