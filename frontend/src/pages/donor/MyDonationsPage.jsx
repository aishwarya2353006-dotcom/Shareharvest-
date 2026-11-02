import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Loading from '../../components/Loading';
import { createDonation, getDonorDonations, getDonorOrganizations, getApiErrorMessage, updateDonation, QUANTITY_UNITS } from '../../services/donorApi';
import FactList from '../../components/FactList';
import PageIntro from '../../components/PageIntro';
import StatusBadge from '../../components/StatusBadge';

const categories = [
  ['prepared', 'Prepared meals'], ['produce', 'Fresh produce'], ['dairy', 'Dairy & eggs'],
  ['bakery', 'Bakery items'], ['packaged', 'Packaged foods'], ['beverages', 'Beverages'], ['other', 'Other'],
];

const emptyForm = () => ({ organization: '', title: '', description: '', food_category: 'produce', quantity: '', unit: 'kg', available_from: '', available_until: '', pickup_address: '', pickup_instructions: '' });
const localDateTime = value => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const offsetDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return offsetDate.toISOString().slice(0, 16);
};
const displayDate = value => value ? new Date(value).toLocaleString() : '—';

const DonationForm = ({ organizations, editing, onSubmit, onCancel, submitting, error }) => {
  const [form, setForm] = useState(emptyForm);
  const [formError, setFormError] = useState('');
  const editingOrg = organizations.find(org => org.id === editing?.organization);
  const selectedOrg = organizations.find(org => String(org.id) === String(form.organization));

  useEffect(() => {
    if (!editing) {
      setForm(emptyForm());
      setFormError('');
      return;
    }
    setForm({
      organization: String(editing.organization), title: editing.title || '', description: editing.description || '',
      food_category: editing.food_category || 'other', quantity: String(editing.quantity ?? ''), unit: editing.unit || 'kg',
      available_from: localDateTime(editing.available_from), available_until: localDateTime(editing.available_until),
      pickup_address: editing.pickup_address || '', pickup_instructions: editing.pickup_instructions || '',
    });
    setFormError('');
  }, [editing]);

  const updateField = event => setForm(previous => ({ ...previous, [event.target.name]: event.target.value }));
  const submit = async event => {
    event.preventDefault();
    setFormError('');
    if (!event.currentTarget.reportValidity()) return;
    if (!editing && !selectedOrg) {
      setFormError('Choose an organization where you have an active membership.');
      return;
    }
    if (!Number.isFinite(Number(form.quantity)) || Number(form.quantity) <= 0) {
      setFormError('Quantity must be a number greater than zero.');
      return;
    }
    const from = new Date(form.available_from);
    const until = new Date(form.available_until);
    if (from >= until) {
      setFormError('The availability end must be after the start.');
      return;
    }
    const payload = {
      title: form.title.trim(), description: form.description.trim(), food_category: form.food_category,
      quantity: Number(form.quantity).toFixed(2), unit: form.unit,
      available_from: from.toISOString(), available_until: until.toISOString(),
      pickup_address: form.pickup_address.trim(), pickup_instructions: form.pickup_instructions.trim(),
      ...(!editing && { organization: Number(form.organization) }),
    };
    try {
      await onSubmit(payload);
      if (!editing) setForm(emptyForm());
    } catch (submitError) {
      setFormError(getApiErrorMessage(submitError));
    }
  };

  return (
    <section className="donor-panel donor-form-panel">
      <div className="donor-panel-heading"><div><p className="donor-eyebrow">{editing ? 'UPDATE LISTING' : 'NEW LISTING'}</p><h2>{editing ? 'Edit donation' : 'Create a donation'}</h2></div></div>
      {error && <div className="donor-inline-error" role="alert">{error}</div>}
      <form className="donor-form" onSubmit={submit}>
        {!editing && <label className="donor-field donor-field-full"><span>Donating organization <b aria-hidden="true">*</b></span><select name="organization" value={form.organization} onChange={updateField} required disabled={!organizations.length}><option value="">Select an organization</option>{organizations.map(org => <option key={org.id} value={org.id}>{org.name} · {org.status}</option>)}</select>{selectedOrg && selectedOrg.status !== 'verified' && <small>This organization is not verified. New donations remain drafts and cannot be published.</small>}</label>}
        {editing && <div className="donor-selected-org">Organization: <strong>{editingOrg?.name || `#${editing.organization}`}</strong>{editingOrg && <span className={`donor-org-status donor-org-${editingOrg.status}`}>{editingOrg.status}</span>}</div>}
        <label className="donor-field"><span>Food name <b aria-hidden="true">*</b></span><input name="title" value={form.title} onChange={updateField} maxLength="255" required /></label>
        <label className="donor-field"><span>Food category <b aria-hidden="true">*</b></span><select name="food_category" value={form.food_category} onChange={updateField} required>{categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="donor-field donor-field-full"><span>Description <b aria-hidden="true">*</b></span><textarea name="description" value={form.description} onChange={updateField} rows="3" required /></label>
        <div className="donor-field donor-quantity-field"><label htmlFor="donation-quantity">Quantity <b aria-hidden="true">*</b></label><input id="donation-quantity" name="quantity" type="number" min="0.01" step="0.01" value={form.quantity} onChange={updateField} required /></div>
        <label className="donor-field"><span>Unit <b aria-hidden="true">*</b></span><select name="unit" value={form.unit} onChange={updateField} required>{QUANTITY_UNITS.map(unit => <option key={unit.value} value={unit.value}>{unit.label}</option>)}</select></label>
        <label className="donor-field"><span>Available from <b aria-hidden="true">*</b></span><input name="available_from" type="datetime-local" value={form.available_from} onChange={updateField} required /></label>
        <label className="donor-field"><span>Available until / expiry <b aria-hidden="true">*</b></span><input name="available_until" type="datetime-local" value={form.available_until} onChange={updateField} required /></label>
        <label className="donor-field donor-field-full"><span>Pickup location <b aria-hidden="true">*</b></span><textarea name="pickup_address" value={form.pickup_address} onChange={updateField} rows="2" required /></label>
        <label className="donor-field donor-field-full"><span>Pickup instructions</span><textarea name="pickup_instructions" value={form.pickup_instructions} onChange={updateField} rows="2" /></label>
        {formError && <div className="donor-form-error donor-field-full" role="alert">{formError}</div>}
        <div className="donor-form-actions donor-field-full"><button className="donor-button" type="submit" disabled={submitting || (!editing && !organizations.length)}>{submitting ? 'Saving…' : editing ? 'Save changes' : 'Create draft donation'}</button>{editing && <button className="donor-button donor-button-secondary" type="button" onClick={onCancel} disabled={submitting}>Cancel</button>}</div>
      </form>
    </section>
  );
};

const DonationRow = ({ donation, organization, onEdit, onPublish, actioning }) => (
  <article className="donor-donation-card">
    <div className="donor-donation-card-main">
      <div className="donor-donation-title-row"><div><span className="donor-category-label">{donation.food_category}</span><h3>{donation.title}</h3></div><StatusBadge status={donation.status} /></div>
      <p className="donor-donation-description">{donation.description}</p>
      <FactList items={[
        ['Quantity', `${donation.quantity} ${donation.unit}`],
        ['Organization', organization?.name || 'Not provided'],
        ['Available', `${displayDate(donation.available_from)} – ${displayDate(donation.available_until)}`],
        ['Pickup', donation.pickup_address],
      ]} />
      {donation.pickup_instructions && <p className="donor-pickup-instructions"><b>Pickup instructions:</b> {donation.pickup_instructions}</p>}
    </div>
    <div className="donor-donation-actions"><button type="button" className="donor-button donor-button-secondary" onClick={() => onEdit(donation)}>Edit</button>{donation.status === 'draft' && organization?.status === 'verified' && <button type="button" className="donor-button" onClick={() => onPublish(donation)} disabled={actioning}>{actioning ? 'Publishing…' : 'Publish'}</button>}{donation.status === 'draft' && organization && organization.status !== 'verified' && <span className="donor-action-note">Publishing requires a verified organization.</span>}</div>
  </article>
);

const MyDonationsPage = () => {
  const [donations, setDonations] = useState([]);
  const [organizations, setOrganizations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [donationError, setDonationError] = useState('');
  const [organizationError, setOrganizationError] = useState('');
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [actioningId, setActioningId] = useState(null);
  const [pageError, setPageError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setDonationError('');
    setOrganizationError('');
    const [donationResult, organizationResult] = await Promise.allSettled([getDonorDonations(), getDonorOrganizations()]);
    if (donationResult.status === 'fulfilled') setDonations(donationResult.value);
    else { setDonations([]); setDonationError(getApiErrorMessage(donationResult.reason)); }
    if (organizationResult.status === 'fulfilled') setOrganizations(organizationResult.value);
    else { setOrganizations([]); setOrganizationError(getApiErrorMessage(organizationResult.reason)); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const saveDonation = async payload => {
    setSubmitting(true);
    try {
      if (editing) await updateDonation(editing.id, payload);
      else await createDonation(payload);
      setEditing(null);
      await load();
    } finally {
      setSubmitting(false);
    }
  };

  const publishDonation = async donation => {
    setActioningId(donation.id);
    setPageError('');
    try {
      await updateDonation(donation.id, { status: 'published' });
      await load();
    } catch (error) {
      setPageError(getApiErrorMessage(error));
    } finally {
      setActioningId(null);
    }
  };

  return (
    <div className="donor-data-page">
      <PageIntro
        eyebrow="DONOR WORKSPACE"
        title="My Donations"
        description="Manage your listings and pickup details."
        action={<Link className="donor-text-link" to="/donor/requests">Review requests <span aria-hidden="true">→</span></Link>}
      />
      {loading ? <div className="donor-panel"><Loading message="Loading your donations…" /></div> : donationError ? <section className="donor-state-panel" role="alert"><h2>We couldn’t load your donations</h2><p>{donationError}</p><button className="donor-button donor-button-secondary" type="button" onClick={load}>Try again</button></section> : (
        <>
          {pageError && <div className="donor-inline-error" role="alert">{pageError}</div>}
          {organizationError && <div className="donor-inline-error" role="alert"><span>Organization list unavailable: {organizationError}. You can still review existing listings.</span><button type="button" onClick={load}>Retry</button></div>}
          {organizations.length === 0 && !organizationError && <div className="donor-inline-note">No active organization membership is available for creating a donation. An active membership is required by the API.</div>}
          {donations.length === 0 ? <section className="donor-panel donor-empty-panel"><div className="donor-empty-icon" aria-hidden="true">+</div><h2>No donations yet</h2><p>Start with a draft. You can publish it once its organization is verified.</p></section> : <div className="donor-donation-list">{donations.map(donation => <DonationRow key={donation.id} donation={donation} organization={organizations.find(org => org.id === donation.organization)} onEdit={setEditing} onPublish={publishDonation} actioning={actioningId === donation.id} />)}</div>}
          {!organizationError && organizations.length > 0 && <DonationForm key={editing?.id || 'new'} organizations={organizations} editing={editing} onSubmit={saveDonation} onCancel={() => setEditing(null)} submitting={submitting} />}
        </>
      )}
    </div>
  );
};

export default MyDonationsPage;
