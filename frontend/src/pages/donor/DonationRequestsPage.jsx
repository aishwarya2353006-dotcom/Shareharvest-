import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Loading from '../../components/Loading';
import FactList from '../../components/FactList';
import PageIntro from '../../components/PageIntro';
import StatusBadge from '../../components/StatusBadge';
import { approveDonationRequest, getApiErrorMessage, getDonorDonations, getDonorOrganizations, getRequestsForDonations, getUnit, quantityInBase, fromBaseQuantity, rejectDonationRequest } from '../../services/donorApi';

const donationAvailableInUnit = (donation, requests, targetUnit) => {
  const donationUnit = getUnit(donation.unit);
  const target = getUnit(targetUnit);
  if (!donationUnit || !target || donationUnit.dimension !== target.dimension) return null;
  const totalBase = quantityInBase(donation.quantity, donation.unit);
  const allocatedBase = requests
    .filter(request => request.donation === donation.id)
    .flatMap(request => request.allocations || [])
    .reduce((sum, allocation) => {
      const unit = getUnit(allocation.approved_unit);
      return unit?.dimension === donationUnit.dimension
        ? sum + quantityInBase(allocation.approved_quantity, allocation.approved_unit)
        : sum;
    }, 0);
  return Math.max(0, fromBaseQuantity(totalBase - allocatedBase, targetUnit));
};

const getIdempotencyKey = () => globalThis.crypto?.randomUUID?.()
  || `${Date.now()}-${Math.random().toString(36).slice(2)}`;

const RequestCard = ({ request, donation, organizations, requests, onApprove, onReject, busy }) => {
  const [quantity, setQuantity] = useState(String(request.remaining_quantity ?? request.requested_quantity));
  const [error, setError] = useState('');
  const idempotencyKey = useRef('');
  const canReview = ['pending', 'partially_approved'].includes(request.status);
  const canReject = request.status === 'pending';
  const donationIsAllocatable = donation?.status === 'published'
    && new Date(donation.available_from).getTime() <= Date.now()
    && new Date(donation.available_until).getTime() > Date.now();
  const availableForRequest = donation && canReview && donationIsAllocatable
    ? donationAvailableInUnit(donation, requests, request.requested_unit)
    : 0;
  const requestRemaining = Number(request.remaining_quantity ?? request.requested_quantity);
  const maximum = availableForRequest === null ? 0 : Math.min(requestRemaining, availableForRequest);

  const approve = async event => {
    event.preventDefault();
    setError('');
    const amount = Number(quantity);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError('Enter a quantity greater than zero.');
      return;
    }
    if (amount > maximum) {
      setError(`The maximum safe allocation is ${maximum.toFixed(2)} ${request.requested_unit}.`);
      return;
    }
    try {
      if (!idempotencyKey.current) idempotencyKey.current = getIdempotencyKey();
      const result = await onApprove(request, { approved_quantity: amount.toFixed(2), approved_unit: request.requested_unit }, idempotencyKey.current);
      idempotencyKey.current = '';
      setQuantity(String(result.data.remaining_quantity));
    } catch (actionError) {
      setError(getApiErrorMessage(actionError));
    }
  };

  const reject = async () => {
    setError('');
    try { await onReject(request); }
    catch (actionError) { setError(getApiErrorMessage(actionError)); }
  };

  return (
    <article className="donor-request-card">
      <div className="donor-request-heading"><div><span className="donor-category-label">{donation?.food_category || 'Donation'}</span><h3>{donation?.title || 'Donation listing'}</h3></div><StatusBadge status={request.status} /></div>
      <FactList className="cols-3" items={[
        ['Recipient organization', organizations.find(org => org.id === request.organization)?.name || 'Not provided'],
        ['Requested', `${request.requested_quantity} ${request.requested_unit}`],
        ['Approved', `${request.approved_quantity} ${request.requested_unit}`],
        ['Still requested', `${request.remaining_quantity} ${request.requested_unit}`],
        ['Submitted', new Date(request.created_at).toLocaleString()],
      ]} />
      {request.notes && <p className="donor-request-notes">“{request.notes}”</p>}
      {request.allocations?.length > 0 && <div className="donor-allocation-list"><strong>Allocations</strong>{request.allocations.map(allocation => <span key={allocation.id}>{allocation.approved_quantity} {allocation.approved_unit} · {new Date(allocation.created_at).toLocaleString()}</span>)}</div>}
      {canReview && <form className="donor-review-controls" onSubmit={approve}>
        <label><span>Approve quantity <small>(max {maximum.toFixed(2)} {request.requested_unit})</small></span><input type="number" min="0.01" step="0.01" max={maximum} value={quantity} onChange={event => { setQuantity(event.target.value); idempotencyKey.current = ''; }} required disabled={busy || maximum <= 0} /></label>
        <span className="donor-review-unit">{request.requested_unit}</span>
        <button className="donor-button" type="submit" disabled={busy || maximum <= 0}>{busy ? 'Saving…' : 'Approve allocation'}</button>
        {canReject && <button className="donor-button donor-button-danger" type="button" onClick={reject} disabled={busy}>Reject</button>}
      </form>}
      {canReview && maximum <= 0 && <p className="donor-action-note">{!donationIsAllocatable ? 'Approvals require a published donation inside its availability window.' : 'No safely allocatable quantity is available in compatible units.'}</p>}
      {error && <div className="donor-form-error" role="alert">{error}</div>}
    </article>
  );
};

const DonationRequestsPage = () => {
  const [donations, setDonations] = useState([]);
  const [organizations, setOrganizations] = useState([]);
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);
  const donationById = useMemo(() => new Map(donations.map(donation => [donation.id, donation])), [donations]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const ownedDonations = await getDonorDonations();
      const ownedRequests = await getRequestsForDonations(ownedDonations);
      const [donationResult, orgResult] = await Promise.allSettled([
        Promise.resolve(ownedDonations),
        getDonorOrganizations(),
      ]);
      setDonations(donationResult.status === 'fulfilled' ? donationResult.value : []);
      setOrganizations(orgResult.status === 'fulfilled' ? orgResult.value : []);
      setRequests(ownedRequests);
    } catch (loadError) {
      setError(getApiErrorMessage(loadError));
      setDonations([]);
      setRequests([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const runAction = async (request, action) => {
    setBusyId(request.id);
    try {
      const result = await action();
      await load();
      return result;
    } finally {
      setBusyId(null);
    }
  };

  const approve = (request, payload, idempotencyKey) => runAction(
    request, () => approveDonationRequest(request.id, payload, idempotencyKey)
  );
  const reject = request => runAction(request, () => rejectDonationRequest(request.id));

  if (loading) return <div className="donor-panel"><Loading message="Loading donation requests…" /></div>;
  if (error) return <section className="donor-state-panel" role="alert"><h2>We couldn’t load donation requests</h2><p>{error}</p><button className="donor-button donor-button-secondary" type="button" onClick={load}>Try again</button></section>;

  return (
    <div className="donor-data-page">
      <PageIntro
        eyebrow="DONOR WORKSPACE"
        title="Donation Requests"
        description="Review requests for donations you created. Allocation limits are checked against both the request and remaining donation stock."
        action={<button className="donor-button donor-button-secondary" type="button" onClick={load}>Refresh</button>}
      />
      {requests.length === 0 ? <section className="donor-panel donor-empty-panel"><div className="donor-empty-icon" aria-hidden="true">✓</div><h2>No requests yet</h2><p>Requests submitted for your donations will appear here.</p></section> : <div className="donor-request-list">{requests.map(request => <RequestCard key={request.id} request={request} donation={donationById.get(request.donation)} organizations={organizations} requests={requests} onApprove={approve} onReject={reject} busy={busyId === request.id} />)}</div>}
    </div>
  );
};

export default DonationRequestsPage;
