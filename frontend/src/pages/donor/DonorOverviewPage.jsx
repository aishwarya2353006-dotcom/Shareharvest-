import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Loading from '../../components/Loading';
import StatusBadge from '../../components/StatusBadge';
import PageIntro from '../../components/PageIntro';
import { getDonorDonations, getRequestsForDonations, getApiErrorMessage } from '../../services/donorApi';
import { getPickups } from '../../services/pickupApi';

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

const DonorOverviewPage = () => {
  const [donations, setDonations] = useState([]);
  const [requests, setRequests] = useState([]);
  const [pickups, setPickups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [requestError, setRequestError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    setRequestError('');
    try {
      const ownedDonations = await getDonorDonations();
      setDonations(ownedDonations);
      const [requestResult, pickupResult] = await Promise.allSettled([
        ownedDonations.length ? getRequestsForDonations(ownedDonations) : Promise.resolve([]),
        getPickups(),
      ]);
      if (requestResult.status === 'fulfilled') setRequests(requestResult.value);
      else { setRequests([]); setRequestError(getApiErrorMessage(requestResult.reason)); }
      if (pickupResult.status === 'fulfilled') setPickups(pickupResult.value);
      else setPickups([]);
    } catch (donationLoadError) {
      setDonations([]);
      setRequests([]);
      setPickups([]);
      setError(getApiErrorMessage(donationLoadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="donor-dashboard-loading" aria-label="Loading donor overview"><Loading message="Loading your donations…" /></div>;
  if (error) return <section className="donor-state-panel" role="alert"><h2>We couldn’t load your overview</h2><p>{error}</p><button type="button" className="donor-button donor-button-secondary" onClick={load}>Try again</button></section>;

  const availableCount = donations.filter(isCurrentlyAvailable).length;
  const openRequests = requests.filter(request => ['pending', 'partially_approved'].includes(request.status)).length;
  const upcomingPickups = pickups.filter(pickup => ['scheduled', 'in_progress'].includes(pickup.status)).length;

  return (
    <div className="donor-overview-page">
      <PageIntro
        eyebrow="DONOR WORKSPACE"
        title="Donor overview"
        description="Track your active donations, open requests, and upcoming pickups at a glance."
        action={<Link className="donor-text-link" to="/donor/donations">Manage donations <span aria-hidden="true">→</span></Link>}
      />
      <section className="donor-metrics-grid" aria-label="Donation overview">
        <MetricCard label="Total donations" value={donations.length} hint="Across all statuses" to="/donor/donations" />
        <MetricCard label="Available now" value={availableCount} hint="Published and within availability window" to="/donor/donations" />
        {requestError
          ? <MetricCard label="Pending requests" hint="Request data could not be loaded" unavailable />
          : <MetricCard label="Pending requests" value={openRequests} hint="Pending or partially approved" to="/donor/requests" />}
        <MetricCard label="Upcoming pickups" value={upcomingPickups} hint="Scheduled or in progress" to="/donor/pickups" />
      </section>
      {donations.length === 0 && (
        <section className="donor-welcome-card">
          <div><p className="donor-eyebrow">YOUR FOOD SHARING ACTIVITY</p><h2>Your first donation starts here</h2><p>List surplus food so verified recipient organizations can find and request it.</p></div>
          <Link className="donor-button" to="/donor/donations">Create a donation</Link>
        </section>
      )}
      {requestError && <div className="donor-inline-error" role="alert"><span>Request summary unavailable: {requestError}</span><button type="button" onClick={load}>Retry</button></div>}
      <section className="donor-overview-lower">
        <div className="donor-panel">
          <div className="donor-panel-heading"><div><p className="donor-eyebrow">RECENT ACTIVITY</p><h2>My donations</h2></div><Link to="/donor/donations">View all</Link></div>
          {donations.length === 0 ? <p className="donor-empty-copy">There are no donations to show yet.</p> : (
            <div className="donor-recent-list">
              {donations.slice(0, 4).map(donation => <div className="donor-recent-row" key={donation.id}>
                <span className="donor-food-mark" aria-hidden="true">{donation.food_category?.slice(0, 1).toUpperCase() || 'F'}</span>
                <span className="donor-recent-copy"><strong>{donation.title}</strong><small>{donation.quantity} {donation.unit} · {donation.food_category}</small></span>
                <StatusBadge status={donation.status} />
              </div>)}
            </div>
          )}
        </div>
        <aside className="donor-panel donor-next-step"><p className="donor-eyebrow">NEXT STEP</p><h2>Keep good food moving</h2><p>Create a listing with a clear pickup window and location for recipient organizations.</p><Link to="/donor/donations">Manage donations <span aria-hidden="true">→</span></Link></aside>
      </section>
    </div>
  );
};

export default DonorOverviewPage;
