import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getMyDonationRequests, getRecipientOrganizations } from '../../services/recipientApi';
import { getApiErrorMessage } from '../../services/donorApi';
import FactList from '../../components/FactList';
import Loading from '../../components/Loading';
import PageIntro from '../../components/PageIntro';
import StatusBadge from '../../components/StatusBadge';

const dateTime = value => value ? new Date(value).toLocaleString() : '—';

function RequestCard({ request, organizations }) {
  const organization = organizations.find(org => org.id === request.organization);
  return (
    <article className="recipient-request-card">
      <div className="donor-request-heading"><div><span className="donor-category-label">Request #{request.id}</span><h2>{request.donation_title || `Donation #${request.donation}`}</h2></div><StatusBadge status={request.status} /></div>
      <FactList items={[
        ['Recipient organization', organization?.name || 'Not provided'],
        ['Requested', `${request.requested_quantity} ${request.requested_unit}`],
        ['Allocated', `${request.approved_quantity ?? '0'} ${request.requested_unit}`],
        ['Still requested', `${request.remaining_quantity ?? request.requested_quantity} ${request.requested_unit}`],
        ['Submitted', dateTime(request.created_at)],
        ...(request.reviewed_at ? [['Last reviewed', dateTime(request.reviewed_at)]] : []),
      ]} />
      {request.notes && <p className="recipient-request-notes">{request.notes}</p>}
      {request.allocations?.length > 0 && <div className="recipient-allocation-list"><strong>Allocation details</strong>{request.allocations.map(allocation => <span key={allocation.id}>{allocation.approved_quantity} {allocation.approved_unit} allocated · {dateTime(allocation.created_at)}{allocation.notes ? ` · ${allocation.notes}` : ''}</span>)}</div>}
    </article>
  );
}

export default function MyRequestsPage() {
  const [requests, setRequests] = useState([]);
  const [organizations, setOrganizations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [myRequests, memberships] = await Promise.all([getMyDonationRequests(), getRecipientOrganizations()]);
      setRequests(myRequests);
      setOrganizations(memberships);
    } catch (loadError) { setError(getApiErrorMessage(loadError)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="recipient-page">
      <PageIntro
        eyebrow="RECIPIENT WORKSPACE"
        title="My requests"
        description="Review request status and any quantities allocated by the donor."
        action={<button className="donor-button donor-button-secondary" type="button" onClick={load} disabled={loading}>Refresh</button>}
      />
      {loading ? <div className="donor-panel"><Loading message="Loading your requests…" /></div> : error ? <section className="donor-state-panel" role="alert"><h2>We couldn’t load your requests</h2><p>{error}</p><button className="donor-button donor-button-secondary" type="button" onClick={load}>Try again</button></section> : requests.length === 0 ? <section className="donor-empty-panel donor-panel"><div className="donor-empty-icon" aria-hidden="true">✓</div><h2>No requests yet</h2><p>When you request food from a listing, its status and allocations will appear here.</p></section> : <div className="recipient-request-list">{requests.map(request => <RequestCard key={request.id} request={request} organizations={organizations} />)}</div>}
      <p className="recipient-pickup-note">Coordinate approved allocations on the <Link to="/recipient/pickups">Pickups page</Link>.</p>
    </div>
  );
}
