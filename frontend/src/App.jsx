import { Route, Routes } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/auth/LoginPage';
import RegisterPage from './pages/auth/RegisterPage';
import MainLayout from './layouts/MainLayout';
import ProtectedRoute from './components/ProtectedRoute';
import DonorOverviewPage from './pages/donor/DonorOverviewPage';
import MyDonationsPage from './pages/donor/MyDonationsPage';
import DonationRequestsPage from './pages/donor/DonationRequestsPage';
import RecipientOverviewPage from './pages/recipient/RecipientOverviewPage';
import BrowseFoodPage from './pages/recipient/BrowseFoodPage';
import MyRequestsPage from './pages/recipient/MyRequestsPage';
import OrganizationsPage from './pages/organizations/OrganizationsPage';
import PickupsPage from './pages/pickups/PickupsPage';
import NotificationsPage from './pages/notifications/NotificationsPage';
import SettingsPage from './pages/settings/SettingsPage';
import CompliancePage from './pages/compliance/CompliancePage';
import ImpactDashboardPage from './pages/impact/ImpactDashboardPage';
import AdminDashboardPage from './pages/admin/AdminDashboardPage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute allowedRoles={['donor']} />}>
        <Route element={<MainLayout />}>
          <Route path="/donor/dashboard" element={<DonorOverviewPage />} />
          <Route path="/donor/donations" element={<MyDonationsPage />} />
          <Route path="/donor/requests" element={<DonationRequestsPage />} />
          <Route path="/donor/pickups" element={<PickupsPage />} />
          <Route path="/donor/organizations" element={<OrganizationsPage />} />
        </Route>
      </Route>
      <Route element={<ProtectedRoute allowedRoles={['recipient']} />}>
        <Route element={<MainLayout />}>
          <Route path="/recipient/dashboard" element={<RecipientOverviewPage />} />
          <Route path="/recipient/browse" element={<BrowseFoodPage />} />
          <Route path="/recipient/requests" element={<MyRequestsPage />} />
          <Route path="/recipient/pickups" element={<PickupsPage />} />
          <Route path="/recipient/organizations" element={<OrganizationsPage />} />
        </Route>
      </Route>
      <Route element={<ProtectedRoute allowedRoles={['volunteer']} />}>
        <Route element={<MainLayout />}>
          <Route path="/volunteer/pickups" element={<PickupsPage />} />
        </Route>
      </Route>
      <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
        <Route element={<MainLayout />}>
          <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
          <Route path="/admin/organizations" element={<OrganizationsPage />} />
        </Route>
      </Route>
      <Route element={<ProtectedRoute allowedRoles={['donor', 'recipient', 'volunteer', 'admin']} />}>
        <Route element={<MainLayout />}>
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/compliance" element={<CompliancePage />} />
          <Route path="/impact" element={<ImpactDashboardPage />} />
        </Route>
      </Route>
      <Route path="*" element={<main className="access-denied"><h1>Page not found</h1><p>The page you requested does not exist.</p></main>} />
    </Routes>
  );
}

export default App;
