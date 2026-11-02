import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getAvailableDonations, getMyDonationRequests } from '../../services/recipientApi';
import { getApiErrorMessage } from '../../services/donorApi';
import Loading from '../../components/Loading';
import { getPickups } from '../../services/pickupApi';
import StatusBadge from '../../components/StatusBadge';
import PageIntro from '../../components/PageIntro';

const isCurrentlyAvailable = donation => {
  const now = Date.now();
  return donation.status === 'published'
    && new Date(donation.available_from).getTime() <= now
    && new Date(donation.available_until).getTime() > now;
};

const MetricCard = ({ label, value, hint, to, unavailable = false }) => {
  const content = <>
    <span className="donor-metric-label">{label}</span>
    <strong className={unavailable ? 'is-unavailable' : ''}>{unavailable ? 'Unavailable' : value}</strong>
    <span className="donor-metric-hint">{hint}</span>
  </>;
  return to ? <Link className="donor-metric-card" to={to}>{content}</Link> : <div className="donor-metric-card">{content}</div>;
};

export default function RecipientOverviewPage() {
  const [donations, setDonations] = useState([]);
  const [requests, setRequests] = useState([]);
  const [pickups, setPickups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [available, myRequests, myPickups] = await Promise.all([
        getAvailableDonations(),
        getMyDonationRequests(),
        getPickups(),
      ]);
      setDonations(available);
      setRequests(myRequests);
      setPickups(myPickups);
    } catch (loadError) {
      setError(getApiErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="donor-dashboard-loading" aria-label="Loading recipient overview"><Loading message="Loading your overview…" /></div>;
  if (error) return <section className="donor-state-panel" role="alert"><h2>We couldn’t load your overview</h2><p>{error}</p><button type="button" className="donor-button donor-button-secondary" onClick={load}>Try again</button></section>;

  const availableCount = donations.filter(isCurrentlyAvailable).length;
  const openRequests = requests.filter(request => ['pending', 'partially_approved'].includes(request.status)).length;
  const approvedRequests = requests.filter(request => ['approved', 'partially_approved'].includes(request.status)).length;
  const upcomingPickups = pickups.filter(pickup => ['scheduled', 'in_progress'].includes(pickup.status)).length;

  return (
    <div className="recipient-overview">
      <PageIntro
        eyebrow="RECIPIENT WORKSPACE"
        title="Recipient overview"
        description="Track your open requests, allocated donations, and upcoming pickups in one place."
        action={<Link className="donor-text-link" to="/recipient/browse">Browse available food <span aria-hidden="true">→</span></Link>}
      />
      <section className="donor-metrics-grid" aria-label="Recipient overview">
        <MetricCard label="Available now" value={availableCount} hint="Published donations in their window" to="/recipient/browse" />
        <MetricCard label="Open requests" value={openRequests} hint="Pending or partially approved" to="/recipient/requests" />
        <MetricCard label="Allocated to you" value={approvedRequests} hint="Approved or partially approved" to="/recipient/requests" />
        <MetricCard label="Upcoming pickups" value={upcomingPickups} hint="Scheduled or in progress" to="/recipient/pickups" />
      </section>
      <section className="donor-overview-lower">
        <div className="donor-panel">
          <div className="donor-panel-heading"><div><p className="donor-eyebrow">RECENT ACTIVITY</p><h2>My requests</h2></div><Link to="/recipient/requests">View all</Link></div>
          {requests.length === 0 ? <p className="donor-empty-copy">No requests yet. Browse available food to submit one.</p> : (
            <div className="donor-recent-list">
              {requests.slice(0, 4).map(request => <div className="donor-recent-row" key={request.id}>
                <span className="donor-food-mark" aria-hidden="true">↗</span>
                <span className="donor-recent-copy"><strong>{`Request #${request.id}`}</strong><small>{request.requested_quantity} {request.requested_unit}</small></span>
                <StatusBadge status={request.status} />
              </div>)}
            </div>
          )}
        </div>
        <aside className="donor-panel donor-next-step">
          <p className="donor-eyebrow">NEXT STEP</p>
          <h2>Find good food for your community</h2>
          <p>Browse available donations from local donors and request what your organization needs.</p>
          <Link to="/recipient/browse">Browse available food <span aria-hidden="true">→</span></Link>
        </aside>
      </section>
    </div>
  );
}
