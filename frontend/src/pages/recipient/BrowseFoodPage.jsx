import { useCallback, useEffect, useMemo, useState } from 'react';
import { createDonationRequest, getAvailableDonations, getRecipientOrganizations } from '../../services/recipientApi';
import { getApiErrorMessage, getUnit, QUANTITY_UNITS } from '../../services/donorApi';
import FactList from '../../components/FactList';
import Loading from '../../components/Loading';
import PageIntro from '../../components/PageIntro';
import StatusBadge from '../../components/StatusBadge';

const recipientOrganization = org => org.status === 'verified' && ['ngo', 'trust', 'community'].includes(org.org_type);
const isCurrentlyAvailable = donation => {
  const now = Date.now();
  return donation.status === 'published'
    && new Date(donation.available_from).getTime() <= now
    && new Date(donation.available_until).getTime() > now;
};
const availableUnits = donation => {
  const source = getUnit(donation.unit);
  return source ? QUANTITY_UNITS.filter(unit => unit.dimension === source.dimension) : [];
};
const dateTime = value => value ? new Date(value).toLocaleString() : 'Not provided';

function DonationCard({ donation, organizations }) {
  const [formOpen, setFormOpen] = useState(false);
  const [quantity, setQuantity] = useState('');
  const [unit, setUnit] = useState(donation.unit);
  const [organization, setOrganization] = useState(organizations[0]?.id || '');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const units = availableUnits(donation);

  const submit = async event => {
    event.preventDefault();
    setError('');
    setSuccess('');
    if (!organization) return setError('Choose a verified recipient organization to submit a request.');
    if (!Number.isFinite(Number(quantity)) || Number(quantity) <= 0) return setError('Enter a quantity greater than zero.');
    setBusy(true);
    try {
      const response = await createDonationRequest({
        donation: donation.id,
        organization: Number(organization),
        requested_quantity: quantity,
        requested_unit: unit,
        notes,
      });
      setSuccess(`Request #${response.data.id} submitted. Current status: ${response.data.status}.`);
      setQuantity('');
      setNotes('');
      setFormOpen(false);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="recipient-food-card">
      <div className="recipient-food-head">
        <div><span className="donor-category-label">{donation.food_category || 'Food'}</span><h2>{donation.title}</h2></div>
        <StatusBadge status={donation.status} />
      </div>
      {donation.description && <p className="recipient-food-description">{donation.description}</p>}
      <FactList items={[
        ['Listed quantity', `${donation.quantity} ${donation.unit}`],
        ['Donor organization', donation.organization_name || 'Not provided'],
        ['Pickup location', donation.pickup_address || 'Not provided'],
        ['Available from', dateTime(donation.available_from)],
        ['Available until', dateTime(donation.available_until)],
      ]} />
      {donation.allergen_declaration && (
        <div className="recipient-allergen-info">
          <strong>Allergen information</strong>
          {donation.allergen_declaration.allergens_present?.length > 0 && (
            <span className="allergen-tags">{donation.allergen_declaration.allergens_present.map(a => {
              const labels = {
                cereals_containing_gluten: 'Cereals containing gluten',
                crustaceans: 'Crustaceans',
                eggs: 'Eggs',
                fish: 'Fish',
                peanuts: 'Peanuts',
                soybeans: 'Soybeans',
                milk: 'Milk',
                tree_nuts: 'Tree nuts',
                sulphites: 'Sulphites',
                lupin: 'Lupin',
                molluscs: 'Molluscs',
                sesame_seeds: 'Sesame seeds',
              };
              return labels[a] || a;
            }).join(', ')}</span>
          )}
          {donation.allergen_declaration.cross_contamination_risk && (
            <span className="allergen-cc-warning">Cross-contamination risk: Yes</span>
          )}
          <StatusBadge status={donation.allergen_declaration.status} className="allergen-status-badge" />
          {donation.allergen_declaration.allergens_present?.length === 0 && !donation.allergen_declaration.cross_contamination_risk && (
            <span className="allergen-none">No allergens declared</span>
          )}
        </div>
      )}
      {!donation.allergen_declaration && (
        <div className="recipient-allergen-info recipient-allergen-missing">
          <strong>Allergen information</strong>
          <span className="allergen-missing">Not available — allergen declaration has not been submitted for this donation.</span>
        </div>
      )}
      <p className="recipient-stock-note">Final availability is confirmed by ShareHarvest when you submit your request.</p>
      {success && <p className="recipient-success" role="status">{success}</p>}
      {error && <p className="donor-form-error" role="alert">{error}</p>}
      {organizations.length === 0 ? <p className='donor-inline-note'>Requesting requires an active membership in a verified NGO, trust, or community organization.</p> : !isCurrentlyAvailable(donation) ? <p className='donor-inline-note'>This listing is not currently available for requests.</p> : (
        <>
          {!formOpen ? <button type="button" className="donor-button" onClick={() => { setError(''); setFormOpen(true); }}>Request food</button> : (
            <form className="recipient-request-form" onSubmit={submit}>
              <label className="donor-field">Recipient organization
                <select required value={organization} onChange={event => setOrganization(event.target.value)}>
                  {organizations.map(org => <option key={org.id} value={org.id}>{org.name}</option>)}
                </select>
              </label>
              <label className="donor-field">Quantity
                <input required type="number" min="0.01" step="0.01" value={quantity} onChange={event => setQuantity(event.target.value)} />
              </label>
              <label className="donor-field">Unit
                <select value={unit} onChange={event => setUnit(event.target.value)}>
                  {units.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              <label className="donor-field">Notes (optional)
                <textarea rows="2" value={notes} onChange={event => setNotes(event.target.value)} />
              </label>
              <div className="recipient-form-actions"><button className="donor-button" type="submit" disabled={busy}>{busy ? 'Submitting…' : 'Submit request'}</button><button className="donor-button donor-button-secondary" type="button" disabled={busy} onClick={() => setFormOpen(false)}>Cancel</button></div>
            </form>
          )}
        </>
      )}
    </article>
  );
}

const categoryLabels = {
  prepared: 'Prepared meals', produce: 'Fresh produce', dairy: 'Dairy & eggs',
  bakery: 'Bakery items', packaged: 'Packaged foods', beverages: 'Beverages', other: 'Other',
};
const categoryLabel = value => categoryLabels[value] || value;

export default function BrowseFoodPage() {
  const [donations, setDonations] = useState([]);
  const [organizations, setOrganizations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [available, memberships] = await Promise.all([getAvailableDonations(), getRecipientOrganizations()]);
      setDonations(available);
      setOrganizations(memberships.filter(recipientOrganization));
    } catch (loadError) {
      setError(getApiErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const categories = useMemo(() => [...new Set(donations.map(item => item.food_category).filter(Boolean))], [donations]);
  const filtersActive = search.trim() !== '' || category !== 'all';
  const filtered = useMemo(() => donations.filter(item => {
    const terms = `${item.title || ''} ${item.description || ''} ${item.food_category || ''} ${item.pickup_address || ''}`.toLowerCase();
    return terms.includes(search.trim().toLowerCase()) && (category === 'all' || item.food_category === category);
  }), [donations, search, category]);

  return (
    <div className="recipient-page">
      <PageIntro
        eyebrow="RECIPIENT WORKSPACE"
        title="Browse available food"
        description="Find published donations currently within their availability window. Submit a request for your verified recipient organization."
        action={<button className="donor-button donor-button-secondary" type="button" onClick={load} disabled={loading}>Refresh listings</button>}
      />
      <div className="recipient-filters">
        <label className="donor-field">Search listings<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Food, category, or location" /></label>
        <label className="donor-field">Category<select value={category} onChange={event => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map(value => <option key={value} value={value}>{categoryLabel(value)}</option>)}</select></label>
        {filtersActive && <button className="donor-button donor-button-secondary" type="button" onClick={() => { setSearch(''); setCategory('all'); }}>Reset filters</button>}
      </div>
      {loading ? <div className="donor-panel"><Loading message="Loading available donations…" /></div> : error ? <section className="donor-state-panel" role="alert"><h2>We couldn’t load available food</h2><p>{error}</p><button className="donor-button donor-button-secondary" onClick={load} type="button">Try again</button></section> : donations.length === 0 ? <section className="donor-empty-panel donor-panel"><div className="donor-empty-icon" aria-hidden="true">↗</div><h2>No food listings right now</h2><p>Published donations currently available for pickup will appear here.</p></section> : filtered.length === 0 ? <section className="donor-empty-panel donor-panel"><h2>No matching listings</h2><p>Try a different search or category.</p></section> : <div className="recipient-food-list">{filtered.map(donation => <DonationCard key={donation.id} donation={donation} organizations={organizations} />)}</div>}
    </div>
  );
}
