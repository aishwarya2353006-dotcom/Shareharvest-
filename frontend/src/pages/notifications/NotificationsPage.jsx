import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useNotifications } from '../../context/NotificationsContext';
import { getNotifications, markAllNotificationsRead, markNotificationRead } from '../../services/notificationApi';
import PageIntro from '../../components/PageIntro';

function relatedPath(notification, role) {
  if (notification.related_object_type === 'donationrequest') {
    return role === 'donor' ? '/donor/requests' : role === 'recipient' ? '/recipient/requests' : null;
  }
  if (notification.related_object_type === 'pickup') {
    return role === 'donor' ? '/donor/pickups' : role === 'recipient' ? '/recipient/pickups' : role === 'volunteer' ? '/volunteer/pickups' : null;
  }
  return null;
}

const NotificationsPage = () => {
  const { user } = useAuth();
  const { unreadCount, refreshUnreadCount } = useNotifications();
  const [pageData, setPageData] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (pageNumber = 1) => {
    setLoading(true);
    setError('');
    try {
      setPageData(await getNotifications(pageNumber));
      setPage(pageNumber);
    } catch {
      setError('Notifications could not be loaded. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(1); }, [load]);

  const markRead = async id => {
    setBusy(true);
    try {
      await markNotificationRead(id);
      await Promise.all([load(page), refreshUnreadCount()]);
    } catch {
      setError('This notification could not be marked as read. Please retry.');
    } finally {
      setBusy(false);
    }
  };

  const markAllRead = async () => {
    setBusy(true);
    try {
      await markAllNotificationsRead();
      await Promise.all([load(page), refreshUnreadCount()]);
    } catch {
      setError('Notifications could not be marked as read. Please retry.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="notification-page" aria-labelledby="notification-heading">
      <PageIntro
        eyebrow="NOTIFICATIONS"
        title="Notification history"
        description="Updates about requests and pickups that involve your account."
        action={
          unreadCount > 0 && (
            <button type="button" className="donor-button donor-button-secondary" onClick={markAllRead} disabled={busy || unreadCount === 0}>
              Mark all as read
            </button>
          )
        }
      />
      {error && <div className="notification-error" role="alert"><span>{error}</span><button type="button" className="donor-text-link" onClick={() => load(page)} disabled={loading}>Retry</button></div>}
      {loading ? <div className="notification-state" role="status">Loading notifications…</div> : !pageData?.results?.length ? (
        <div className="notification-empty"><span aria-hidden="true">✓</span><h3>You’re all caught up</h3><p>New request and pickup updates will appear here.</p></div>
      ) : (
        <>
          <div className="notification-list" aria-live="polite">
            {pageData.results.map(notification => {
              const href = relatedPath(notification, user?.role);
              return <article className={`notification-card${notification.is_read ? ' is-read' : ' is-unread'}`} key={notification.id}>
                <span className="notification-dot" aria-hidden="true" />
                <div className="notification-card-copy"><div className="notification-card-title"><h3>{notification.title}</h3><time dateTime={notification.created_at}>{new Date(notification.created_at).toLocaleString()}</time></div><p>{notification.message}</p><div className="notification-card-actions">{href && <Link className="donor-text-link" to={href}>View related {notification.related_object_type === 'pickup' ? 'pickup' : 'request'}</Link>}{!notification.is_read && <button type="button" className="donor-text-link" onClick={() => markRead(notification.id)} disabled={busy}>Mark as read</button>}{notification.is_read && <span className="notification-read-label">Read</span>}</div></div>
              </article>;
            })}
          </div>
          <div className="notification-pagination"><span>Page {page} of {Math.max(1, Math.ceil(pageData.count / 20))}</span><div><button type="button" className="donor-button donor-button-secondary" onClick={() => load(page - 1)} disabled={!pageData.previous || loading}>Previous</button><button type="button" className="donor-button donor-button-secondary" onClick={() => load(page + 1)} disabled={!pageData.next || loading}>Next</button></div></div>
        </>
      )}
    </section>
  );
};

export default NotificationsPage;
