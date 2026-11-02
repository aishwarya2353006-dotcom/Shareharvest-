import { useCallback, useEffect, useMemo, useState } from 'react';
import Loading from '../../components/Loading';
import { useAuth } from '../../hooks/useAuth';
import {
  getApiErrorMessage,
} from '../../services/donorApi';
import FactList from '../../components/FactList';
import PageIntro from '../../components/PageIntro';
import StatusBadge from '../../components/StatusBadge';
import {
  assignPickupVolunteer,
  cancelPickup,
  completePickup,
  createPickup,
  failPickup,
  getAvailableVolunteers,
  getEligibleAllocations,
  getPickups,
  markPickupNoShow,
  startPickup,
  updatePickup,
} from '../../services/pickupApi';

const localDateTime = value => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
};

const defaultSchedule = () => {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(10, 0, 0, 0);
  return localDateTime(date);
};

function ScheduleForm({ allocations, onRefresh }) {
  const [allocationId, setAllocationId] = useState('');
  const [form, setForm] = useState({
    scheduled_at: defaultSchedule(),
    pickup_type: 'self',
    pickup_address: '',
    contact_person: '',
    contact_phone: '',
    notes: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const selected = allocations.find(item => String(item.id) === allocationId);

  useEffect(() => {
    if (allocations.length && !allocations.some(item => String(item.id) === allocationId)) {
      setAllocationId(String(allocations[0].id));
    }
  }, [allocationId, allocations]);

  useEffect(() => {
    if (!selected) return;
    setForm(previous => ({
      ...previous,
      pickup_address: selected.pickup_address || '',
      contact_person: selected.contact_person || '',
      contact_phone: selected.contact_phone || '',
    }));
  }, [selected]);

  const updateField = event => {
    setForm(previous => ({ ...previous, [event.target.name]: event.target.value }));
  };

  const submit = async event => {
    event.preventDefault();
    setError('');
    if (!selected) {
      setError('Choose an approved allocation before scheduling a pickup.');
      return;
    }
    setSaving(true);
    try {
      await createPickup({
        allocation: selected.id,
        pickup_type: form.pickup_type,
        scheduled_at: new Date(form.scheduled_at).toISOString(),
        pickup_address: form.pickup_address.trim(),
        contact_person: form.contact_person.trim(),
        contact_phone: form.contact_phone.trim(),
        notes: form.notes.trim(),
      });
      setForm(previous => ({ ...previous, notes: '', scheduled_at: defaultSchedule() }));
      await onRefresh();
    } catch (saveError) {
      setError(getApiErrorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="pickup-panel">
      <div className="donor-panel-heading">
        <div>
          <p className="donor-eyebrow">APPROVED ALLOCATIONS</p>
          <h2>Schedule a pickup</h2>
        </div>
      </div>
      {!allocations.length ? (
        <p className="pickup-muted">Approved allocations that do not yet have a pickup will appear here.</p>
      ) : (
        <form className="pickup-form" onSubmit={submit}>
          <label className="donor-field pickup-field-full">
            Approved allocation
            <select value={allocationId} onChange={event => setAllocationId(event.target.value)} required>
              {allocations.map(item => (
                <option key={item.id} value={item.id}>
                  {item.donation_title} · {item.approved_quantity} {item.approved_unit}
                  {' · '}{item.recipient_organization_name}
                </option>
              ))}
            </select>
          </label>
          <label className="donor-field">
            Pickup date and time
            <input
              type="datetime-local"
              name="scheduled_at"
              value={form.scheduled_at}
              onChange={updateField}
              required
            />
          </label>
          <label className="donor-field">
            Pickup type
            <select name="pickup_type" value={form.pickup_type} onChange={updateField} required>
              <option value="self">Self pickup</option>
              <option value="volunteer">Volunteer pickup</option>
              <option value="delivery_partner">Delivery partner</option>
            </select>
          </label>
          <label className="donor-field pickup-field-full">
            Pickup location
            <textarea name="pickup_address" value={form.pickup_address} onChange={updateField} rows="2" required />
          </label>
          <label className="donor-field">
            Contact person
            <input name="contact_person" value={form.contact_person} onChange={updateField} maxLength="255" required />
          </label>
          <label className="donor-field">
            Contact phone
            <input name="contact_phone" type="tel" value={form.contact_phone} onChange={updateField} maxLength="20" required />
          </label>
          <label className="donor-field pickup-field-full">
            Pickup instructions
            <textarea name="notes" value={form.notes} onChange={updateField} rows="2" />
          </label>
          {error && <div className="donor-form-error pickup-field-full" role="alert">{error}</div>}
          <div className="pickup-form-actions pickup-field-full">
            <button className="donor-button" type="submit" disabled={saving || !selected}>
              {saving ? 'Scheduling…' : 'Schedule pickup'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function PickupCard({ pickup, role, onRefresh }) {
  const [volunteers, setVolunteers] = useState([]);
  const [volunteer, setVolunteer] = useState(pickup.volunteer ? String(pickup.volunteer) : '');
  const [schedule, setSchedule] = useState({
    scheduled_at: localDateTime(pickup.scheduled_at),
    pickup_type: pickup.pickup_type,
    pickup_address: pickup.pickup_address,
    contact_person: pickup.contact_person,
    contact_phone: pickup.contact_phone,
    notes: pickup.notes || '',
  });
  const [quantity, setQuantity] = useState(String(pickup.allocation_quantity));
  const [failureReason, setFailureReason] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const isOrganizationUser = role === 'donor' || role === 'recipient';
  const isScheduled = pickup.status === 'scheduled';
  const scheduledTimeHasPassed = new Date(pickup.scheduled_at).getTime() <= Date.now();
  const isFinished = ['completed', 'cancelled', 'no_show', 'failed'].includes(pickup.status);

  useEffect(() => {
    setVolunteer(pickup.volunteer ? String(pickup.volunteer) : '');
    setSchedule({
      scheduled_at: localDateTime(pickup.scheduled_at),
      pickup_type: pickup.pickup_type,
      pickup_address: pickup.pickup_address,
      contact_person: pickup.contact_person,
      contact_phone: pickup.contact_phone,
      notes: pickup.notes || '',
    });
    if (pickup.actual_quantity != null) setQuantity(String(pickup.actual_quantity));
  }, [pickup]);

  useEffect(() => {
    if (!isOrganizationUser || !isScheduled) {
      setVolunteers([]);
      return;
    }
    let active = true;
    getAvailableVolunteers(pickup.allocation).then(items => {
      if (active) setVolunteers(items);
    }).catch(loadError => {
      if (active) setError(getApiErrorMessage(loadError));
    });
    return () => { active = false; };
  }, [isOrganizationUser, isScheduled, pickup.allocation]);

  const run = async operation => {
    setError('');
    setNotice('');
    setBusy(true);
    try {
      await operation();
      setNotice('Pickup updated.');
      await onRefresh();
    } catch (actionError) {
      setError(getApiErrorMessage(actionError));
    } finally {
      setBusy(false);
    }
  };

  const saveSchedule = event => {
    event.preventDefault();
    run(() => updatePickup(pickup.id, {
      ...schedule,
      scheduled_at: new Date(schedule.scheduled_at).toISOString(),
    }));
  };

  return (
    <article className="donor-request-card pickup-card">
      <div className="donor-request-heading">
        <div>
          <span className="donor-category-label">Pickup #{pickup.id} · {pickup.pickup_type.replaceAll('_', ' ')}</span>
          <h3>{pickup.donation_title}</h3>
        </div>
        <StatusBadge status={pickup.status} />
      </div>
      <FactList className="cols-3" items={[
        ['Approved quantity', `${pickup.allocation_quantity} ${pickup.allocation_unit}`],
        ['Scheduled for', new Date(pickup.scheduled_at).toLocaleString()],
        ['Donor organization', pickup.donor_organization_name],
        ['Recipient organization', pickup.recipient_organization_name],
        ['Pickup contact', `${pickup.contact_person} · ${pickup.contact_phone}`],
        ['Volunteer', pickup.volunteer_username || 'Not assigned'],
        ...(pickup.actual_quantity != null ? [['Collected', `${pickup.actual_quantity} ${pickup.actual_unit}`]] : []),
        ...(pickup.failure_reason ? [['Failure reason', pickup.failure_reason]] : []),
        ...(pickup.started_at ? [['Started', new Date(pickup.started_at).toLocaleString()]] : []),
        ...(pickup.completed_at ? [['Completed', new Date(pickup.completed_at).toLocaleString()]] : []),
      ]} />
      <p className="pickup-location"><b>Location</b>{pickup.pickup_address}</p>
      {pickup.notes && <p className="recipient-request-notes"><b>Instructions:</b> {pickup.notes}</p>}

      {isOrganizationUser && isScheduled && (
        <div className="pickup-card-tools">
          <details>
            <summary>Reschedule or edit pickup details</summary>
            <form className="pickup-form pickup-edit-form" onSubmit={saveSchedule}>
              <label className="donor-field">Date and time<input type="datetime-local" value={schedule.scheduled_at} onChange={event => setSchedule(previous => ({ ...previous, scheduled_at: event.target.value }))} required /></label>
              <label className="donor-field">Pickup type<select value={schedule.pickup_type} onChange={event => setSchedule(previous => ({ ...previous, pickup_type: event.target.value }))}><option value="self">Self pickup</option><option value="volunteer">Volunteer pickup</option><option value="delivery_partner">Delivery partner</option></select></label>
              <label className="donor-field pickup-field-full">Location<textarea value={schedule.pickup_address} onChange={event => setSchedule(previous => ({ ...previous, pickup_address: event.target.value }))} rows="2" required /></label>
              <label className="donor-field">Contact person<input value={schedule.contact_person} onChange={event => setSchedule(previous => ({ ...previous, contact_person: event.target.value }))} maxLength="255" required /></label>
              <label className="donor-field">Contact phone<input type="tel" value={schedule.contact_phone} onChange={event => setSchedule(previous => ({ ...previous, contact_phone: event.target.value }))} maxLength="20" required /></label>
              <label className="donor-field pickup-field-full">Instructions<textarea value={schedule.notes} onChange={event => setSchedule(previous => ({ ...previous, notes: event.target.value }))} rows="2" /></label>
              <button className="donor-button pickup-field-full" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save pickup details'}</button>
            </form>
          </details>
          <label className="pickup-assign">
            Assign a volunteer
            <span className="pickup-assign-controls">
              <select value={volunteer} onChange={event => setVolunteer(event.target.value)} disabled={busy}>
                <option value="">No volunteer assigned</option>
                {volunteers.map(item => <option key={item.id} value={item.id}>{item.username}</option>)}
              </select>
              <button className="donor-button donor-button-secondary" type="button" disabled={busy} onClick={() => run(() => assignPickupVolunteer(pickup.id, volunteer ? Number(volunteer) : null))}>
                Save
              </button>
            </span>
          </label>
          <button className="donor-button donor-button-danger" type="button" disabled={busy} onClick={() => run(() => cancelPickup(pickup.id))}>Cancel pickup</button>
        </div>
      )}

      {!isFinished && (
        <div className="pickup-progress-tools">
          {pickup.status === 'scheduled' && (
            <button className="donor-button" type="button" disabled={busy || !scheduledTimeHasPassed} onClick={() => run(() => startPickup(pickup.id))}>
              Start pickup
            </button>
          )}
          {pickup.status === 'in_progress' && (
            <>
              <form className="pickup-complete-form" onSubmit={event => {
                event.preventDefault();
                run(() => completePickup(pickup.id, {
                  actual_quantity: Number(quantity).toFixed(3),
                  actual_unit: pickup.allocation_unit,
                }));
              }}>
                <label className="donor-field">
                  Collected quantity ({pickup.allocation_unit})
                  <input type="number" min="0.001" step="0.001" max={pickup.allocation_quantity} value={quantity} onChange={event => setQuantity(event.target.value)} required />
                </label>
                <button className="donor-button" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Complete pickup'}</button>
              </form>
              <form className="pickup-failure-form" onSubmit={event => {
                event.preventDefault();
                run(() => failPickup(pickup.id, failureReason.trim()));
              }}>
                <label className="donor-field">
                  Unable to complete? Provide a reason
                  <input value={failureReason} onChange={event => setFailureReason(event.target.value)} minLength="5" maxLength="2000" required />
                </label>
                <button className="donor-button donor-button-danger" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Mark pickup failed'}</button>
              </form>
            </>
          )}
          {pickup.status === 'scheduled' && scheduledTimeHasPassed && (
            <button className="donor-button donor-button-secondary" type="button" disabled={busy} onClick={() => run(() => markPickupNoShow(pickup.id))}>Mark no-show</button>
          )}
        </div>
      )}
      {pickup.status === 'scheduled' && !scheduledTimeHasPassed && (
        <p className="pickup-muted">Progress actions become available at the scheduled time.</p>
      )}
      {notice && <p className="donor-success" role="status">{notice}</p>}
      {error && <div className="donor-form-error" role="alert">{error}</div>}
    </article>
  );
}

export default function PickupsPage() {
  const { user } = useAuth();
  const role = user?.role;
  const [pickups, setPickups] = useState([]);
  const [allocations, setAllocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const canSchedule = role === 'donor' || role === 'recipient';
  const showScheduleForm = useMemo(() => canSchedule && allocations.length > 0, [allocations.length, canSchedule]);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const [pickupItems, allocationItems] = await Promise.all([
        getPickups(),
        canSchedule ? getEligibleAllocations() : Promise.resolve([]),
      ]);
      setPickups(pickupItems);
      setAllocations(allocationItems);
    } catch (loadError) {
      setError(getApiErrorMessage(loadError));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [canSchedule]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="donor-panel"><Loading message="Loading pickups…" /></div>;

  return (
    <div className="donor-data-page pickup-page">
      <PageIntro
        eyebrow={role === 'volunteer' ? 'VOLUNTEER WORKSPACE' : `${role?.toUpperCase()} WORKSPACE`}
        title="Pickups"
        description="Schedule one pickup per approved allocation and track progress without changing donation stock."
        action={<button className="donor-button donor-button-secondary" type="button" onClick={() => load(true)} disabled={refreshing}>{refreshing ? 'Refreshing…' : 'Refresh'}</button>}
      />
      {error && <section className="donor-state-panel" role="alert"><h2>Pickups could not be loaded</h2><p>{error}</p><button className="donor-button donor-button-secondary" type="button" onClick={() => load(true)}>Try again</button></section>}
      {showScheduleForm && <ScheduleForm allocations={allocations} onRefresh={() => load(true)} />}
      {canSchedule && !allocations.length && (
        <section className="donor-panel pickup-empty-allocations">
          <h2>No unscheduled approved allocations</h2>
          <p>Once an allocation is approved, it can be scheduled here. Each allocation can have one pickup.</p>
        </section>
      )}
      {!pickups.length ? (
        <section className="donor-panel donor-empty-panel">
          <div className="donor-empty-icon" aria-hidden="true">↗</div>
          <h2>No pickups yet</h2>
          <p>Pickup schedules and updates for your authorized organizations will appear here.</p>
        </section>
      ) : (
        <div className="donor-request-list pickup-list">
          {pickups.map(pickup => (
            <PickupCard key={pickup.id} pickup={pickup} role={role} onRefresh={() => load(true)} />
          ))}
        </div>
      )}
    </div>
  );
}
