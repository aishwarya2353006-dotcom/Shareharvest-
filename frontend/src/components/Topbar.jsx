import { forwardRef, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useNotifications } from '../context/NotificationsContext';
import { getNotifications, markNotificationRead } from '../services/notificationApi';

const displayName = user => [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'Account';
const initials = user => displayName(user).split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
const relatedPath = (notification, role) => {
  if (notification.related_object_type === 'donationrequest') return role === 'donor' ? '/donor/requests' : role === 'recipient' ? '/recipient/requests' : null;
  if (notification.related_object_type === 'pickup') return role === 'donor' ? '/donor/pickups' : role === 'recipient' ? '/recipient/pickups' : role === 'volunteer' ? '/volunteer/pickups' : null;
  return null;
};

const Topbar = forwardRef(({ user, title, mobileNavOpen, onMenuClick, onLogout }, menuTriggerRef) => {
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [recent, setRecent] = useState([]);
  const [noticeLoading, setNoticeLoading] = useState(false);
  const [noticeError, setNoticeError] = useState('');
  const { unreadCount, refreshUnreadCount } = useNotifications();
  const topbarActionsRef = useRef(null);

  const loadRecent = async () => {
    setNoticeLoading(true);
    setNoticeError('');
    try {
      const response = await getNotifications(1);
      setRecent(response.results.slice(0, 5));
    } catch {
      setNoticeError('Notifications could not be loaded.');
    } finally {
      setNoticeLoading(false);
    }
  };

  useEffect(() => { if (noticeOpen) loadRecent(); }, [noticeOpen]);

  // Close either popover on Escape or an outside click, returning focus to
  // its trigger so keyboard users don't get stranded.
  useEffect(() => {
    if (!noticeOpen && !profileOpen) return undefined;
    const closeAll = () => { setNoticeOpen(false); setProfileOpen(false); };
    const handleKey = event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeAll();
        topbarActionsRef.current?.querySelector('button')?.focus();
      }
    };
    const handleClick = event => {
      if (!topbarActionsRef.current?.contains(event.target)) closeAll();
    };
    document.addEventListener('keydown', handleKey);
    document.addEventListener('mousedown', handleClick);
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.removeEventListener('mousedown', handleClick);
    };
  }, [noticeOpen, profileOpen]);

  const openNotice = () => { setNoticeOpen(open => !open); setProfileOpen(false); };
  const handleRead = async id => {
    try { await markNotificationRead(id); await Promise.all([loadRecent(), refreshUnreadCount()]); }
    catch { setNoticeError('This notification could not be updated. Try again.'); }
  };

  return (
    <header className="app-topbar">
      <button ref={menuTriggerRef} className="mobile-menu-toggle" type="button" onClick={onMenuClick} aria-label="Toggle application navigation" aria-controls="application-sidebar" aria-expanded={mobileNavOpen}><span /><span /><span /></button>
      <div className="topbar-title-area"><span className="topbar-context">ShareHarvest workspace</span><span className="topbar-current-title">{title}</span></div>
      <div className="topbar-actions" ref={topbarActionsRef}>
        <div className="topbar-popover-wrap">
          <button className={`topbar-icon-button${noticeOpen ? ' is-selected' : ''}`} type="button" aria-haspopup="dialog" aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ''}`} aria-expanded={noticeOpen} aria-controls="topbar-notifications" onClick={openNotice}>
            <svg viewBox="0 0 24 24" aria-hidden="true" fill="none"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>
            {unreadCount > 0 && <span className="notification-count" aria-hidden="true">{unreadCount > 99 ? '99+' : unreadCount}</span>}
          </button>
          <span className="sr-only" aria-live="polite">{unreadCount > 0 ? `${unreadCount} unread notifications` : 'No unread notifications'}</span>
          {noticeOpen && <div id="topbar-notifications" className="topbar-popover notification-popover" aria-label="Recent notifications">
            <div className="notification-popover-heading"><strong>Notifications</strong><Link to="/notifications" onClick={() => setNoticeOpen(false)}>View all</Link></div>
            {noticeLoading ? <p role="status">Loading notifications…</p> : noticeError ? <div className="notification-popover-error" role="alert"><p>{noticeError}</p><button type="button" onClick={loadRecent}>Retry</button></div> : recent.length ? <ul className="notification-popover-list">{recent.map(item => {
              const href = relatedPath(item, user?.role);
              return <li key={item.id} className={item.is_read ? 'is-read' : 'is-unread'}>{href ? <Link to={href} onClick={() => { if (!item.is_read) handleRead(item.id); setNoticeOpen(false); }}><strong>{item.title}</strong><span>{item.message}</span></Link> : <div><strong>{item.title}</strong><span>{item.message}</span></div>}{!item.is_read && <button type="button" aria-label={`Mark ${item.title} as read`} onClick={() => handleRead(item.id)}>Mark read</button>}</li>;
            })}</ul> : <p>You’re all caught up.</p>}
          </div>}
        </div>
        <div className="topbar-popover-wrap">
          <button className={`profile-trigger${profileOpen ? ' is-selected' : ''}`} type="button" aria-haspopup="dialog" aria-expanded={profileOpen} onClick={() => { setProfileOpen(open => !open); setNoticeOpen(false); }}>
            <span className="profile-avatar" aria-hidden="true">{initials(user)}</span><span className="profile-copy"><strong>{displayName(user)}</strong><small>{user?.role || 'Member'}</small></span>
            <svg className="profile-chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </button>
          {profileOpen && <div className="topbar-popover profile-popover"><div className="profile-popover-heading"><strong>{displayName(user)}</strong><span>{user?.email}</span></div><button type="button" className="profile-logout" onClick={onLogout}><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M8 3H4.5A1.5 1.5 0 0 0 3 4.5v11A1.5 1.5 0 0 0 4.5 17H8m4-3 4-4-4-4m4 4H7" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>Log out</button></div>}
        </div>
      </div>
    </header>
  );
});

Topbar.displayName = 'Topbar';
export default Topbar;
