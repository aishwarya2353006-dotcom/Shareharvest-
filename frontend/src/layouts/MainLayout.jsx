import { useEffect, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import { NotificationsProvider } from '../context/NotificationsContext';

const MainLayout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [logoutError, setLogoutError] = useState('');
  const mobileMenuTriggerRef = useRef(null);
  const sidebarRef = useRef(null);
  const isRecipient = user?.role === 'recipient';
  const pageTitles = {
    '/donor/dashboard': 'Donor overview',
    '/donor/donations': 'My donations',
    '/donor/requests': 'Donation requests',
    '/donor/pickups': 'Pickups',
    '/recipient/dashboard': 'Recipient overview',
    '/recipient/browse': 'Browse food',
    '/recipient/requests': 'My requests',
    '/recipient/pickups': 'Pickups',
    '/volunteer/pickups': 'My pickups',
    '/donor/organizations': 'Organizations',
    '/recipient/organizations': 'Organizations',
    '/admin/dashboard': 'Admin Dashboard',
    '/admin/organizations': 'Organization verification',
    '/impact': 'Impact dashboard',
    '/notifications': 'Notifications',
    '/settings': 'Settings',
  };
  const pageTitle = pageTitles[location.pathname] || (isRecipient ? 'Recipient overview' : user?.role === 'admin' ? 'Platform workspace' : 'Donor overview');

  useEffect(() => {
    if (!mobileNavOpen) return undefined;

    const sidebar = sidebarRef.current;
    const menuTrigger = mobileMenuTriggerRef.current;
    const getFocusableItems = () => sidebar?.querySelectorAll(
      'a[href]:not([aria-disabled="true"]), button:not(:disabled), [tabindex]:not([tabindex="-1"])'
    ) || [];
    const focusTimer = window.setTimeout(() => getFocusableItems()[0]?.focus(), 50);

    const handleDrawerKeyDown = event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setMobileNavOpen(false);
        menuTrigger?.focus();
        return;
      }

      if (event.key === 'Tab') {
        const items = getFocusableItems();
        if (!items.length) {
          event.preventDefault();
          return;
        }
        const first = items[0];
        const last = items[items.length - 1];
        if (event.shiftKey && (document.activeElement === first || !sidebar.contains(document.activeElement))) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || !sidebar.contains(document.activeElement))) {
          event.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener('keydown', handleDrawerKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', handleDrawerKeyDown);
      menuTrigger?.focus();
    };
  }, [mobileNavOpen]);

  const handleLogout = async () => {
    setLogoutError('');
    try {
      await logout();
      navigate('/login', { replace: true, state: { from: location } });
    } catch {
      setLogoutError('We could not end your session. Please try again.');
    }
  };

  return (
    <NotificationsProvider><div className="app-shell">
      {mobileNavOpen && <button className="sidebar-scrim" type="button" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}
      <Sidebar ref={sidebarRef} role={user?.role} open={mobileNavOpen} onNavigate={() => setMobileNavOpen(false)} />
      <div className="app-main-column">
        <Topbar ref={mobileMenuTriggerRef} user={user} title={pageTitle} mobileNavOpen={mobileNavOpen} onMenuClick={() => setMobileNavOpen(open => !open)} onLogout={handleLogout} />
        <main className="app-content" id="main-content">
          {logoutError && <div className="app-alert" role="alert">{logoutError}</div>}
          <div className="app-page-heading">
            <div>
              <p className="app-eyebrow">SHAREHARVEST</p>
              <h1>{pageTitle}</h1>
              <p className="app-page-subtitle">Good food, shared with purpose.</p>
            </div>
          </div>
          <div key={location.pathname} className="app-page-transition">
            <Outlet />
          </div>
        </main>
        <footer className="app-footer">ShareHarvest <span>·</span> Good Food. Shared with Purpose.</footer>
      </div>
    </div></NotificationsProvider>
  );
};

export default MainLayout;
