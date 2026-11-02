import { forwardRef } from 'react';
import { NavLink } from 'react-router-dom';

const navigationByRole = {
  donor: [
    { label: 'Overview', path: '/donor/dashboard', icon: '⌂' },
    { label: 'My Donations', path: '/donor/donations', icon: '▤' },
    { label: 'Donation Requests', path: '/donor/requests', icon: '↗' },
    { label: 'Organizations', path: '/donor/organizations', icon: '⌂' },
    { label: 'Food Safety & Compliance', path: '/compliance', icon: '📋' },
    { label: 'Impact', path: '/impact', icon: '📊' },
    { label: 'Pickups', path: '/donor/pickups', icon: '▣' },
    { label: 'Notifications', path: '/notifications', icon: '◉' },
    { label: 'Settings', path: '/settings', icon: '⚙' },
  ],
  recipient: [
    { label: 'Overview', path: '/recipient/dashboard', icon: '⌂' },
    { label: 'Browse Food', path: '/recipient/browse', icon: '⌕' },
    { label: 'My Requests', path: '/recipient/requests', icon: '▤' },
    { label: 'Organizations', path: '/recipient/organizations', icon: '⌂' },
    { label: 'Pickups', path: '/recipient/pickups', icon: '▣' },
    { label: 'Impact', path: '/impact', icon: '📊' },
    { label: 'Notifications', path: '/notifications', icon: '◉' },
    { label: 'Settings', path: '/settings', icon: '⚙' },
  ],
  admin: [
    { label: 'Admin Dashboard', path: '/admin/dashboard', icon: '▦' },
    { label: 'Impact', path: '/impact', icon: '📊' },
    { label: 'Organization review', path: '/admin/organizations', icon: '⌂' },
    { label: 'Food Safety & Compliance', path: '/compliance', icon: '📋' },
    { label: 'Notifications', path: '/notifications', icon: '◉' },
    { label: 'Settings', path: '/settings', icon: '⚙' },
  ],
  volunteer: [
    { label: 'My pickups', path: '/volunteer/pickups', icon: '▣' },
    { label: 'Impact', path: '/impact', icon: '📊' },
    { label: 'Notifications', path: '/notifications', icon: '◉' },
    { label: 'Settings', path: '/settings', icon: '⚙' },
  ],
};

const Sidebar = forwardRef(({ role, open, onNavigate }, sidebarRef) => {
  const roleLinks = navigationByRole[role] || [];
  const roleName = role === 'recipient' ? 'Recipient workspace'
    : role === 'admin' ? 'Platform workspace'
      : role === 'volunteer' ? 'Volunteer workspace' : 'Donor workspace';

  return (
    <aside ref={sidebarRef} id="application-sidebar" className={`app-sidebar${open ? ' is-open' : ''}`} aria-label="Application navigation" role={open ? 'dialog' : undefined} aria-modal={open ? 'true' : undefined}>
      <NavLink className="app-brand" to="/" onClick={onNavigate}>
        <span className="app-brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><path d="M26.5 5.5C15.2 5.8 7.1 9.4 7.1 18.2c0 4.3 3.1 7.2 7.1 7.2 8.9 0 12.5-8.2 12.3-19.9Z" fill="currentColor"/><path d="M5.5 27c4.3-6.8 8.8-10.5 15.2-14.3" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg></span>
        <span className="app-brand-word">share<span>harvest</span></span>
      </NavLink>
      <div className="sidebar-workspace-label">WORKSPACE</div>
      <p className="sidebar-role-label">{roleName}</p>
      <nav className="sidebar-nav" aria-label={`${roleName} navigation`}>
        {roleLinks.map(item => item.path ? (
          <NavLink key={item.label} to={item.path} end className={({ isActive }) => `sidebar-nav-item${isActive ? ' is-active' : ''}`} onClick={onNavigate}>
            <span className="sidebar-nav-icon" aria-hidden="true">{item.icon}</span><span>{item.label}</span>
          </NavLink>
        ) : <div key={item.label} className="sidebar-nav-item is-unavailable" aria-disabled="true" title="This area is not available yet"><span className="sidebar-nav-icon" aria-hidden="true">{item.icon}</span><span>{item.label}</span><span className="sidebar-coming-soon">Soon</span></div>)}
      </nav>
      <div className="sidebar-bottom-note"><span className="sidebar-note-mark" aria-hidden="true">✳</span><p>Good food finds a good home.</p></div>
    </aside>
  );
});

Sidebar.displayName = 'Sidebar';
export default Sidebar;
