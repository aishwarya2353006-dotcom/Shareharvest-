import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import Loading from '../../components/Loading';
import PageIntro from '../../components/PageIntro';
import StatusBadge from '../../components/StatusBadge';
import {
  getMyCompliance, submitCompliance, verifyCompliance, rejectCompliance,
  getMyAllergenDeclarations, submitAllergenDeclaration, reviewAllergenDeclaration,
  getAllergenDeclarations, getOrganizationCompliance,
  ALLERGEN_CHOICES, getAllergenLabel,
} from '../../services/complianceApi';

const initialComplianceForm = {
  fssai_license_number: '',
  fssai_license_expiry: '',
  notes: '',
};

const initialAllergenForm = {
  allergens_present: [],
  cross_contamination_risk: false,
  cross_contamination_details: '',
};

function ComplianceRecordCard({ record, isAdmin, onAction, busyId, rejectionReason, setRejectionReason, rejectingId, setRejectingId }) {
  const isExpired = record.license_expired;

  return (
    <article className="compliance-card">
      <div className="compliance-card-header">
        <div>
          <span className="compliance-org">{record.organization_name}</span>
          <StatusBadge status={record.compliance_status} className="compliance-status-badge" />
          {isExpired && <span className="compliance-expired-tag">License expired</span>}
        </div>
        {record.fssai_license_number && <span className="compliance-license">FSSAI: {record.fssai_license_number}</span>}
      </div>
      {record.fssai_license_expiry && <p className="compliance-expiry">License expires: {record.fssai_license_expiry}</p>}
      {record.notes && <p className="compliance-notes">{record.notes}</p>}
      {isAdmin && record.compliance_status === 'submitted' && (
        <div className="compliance-actions">
          <button type="button" className="donor-button" disabled={busyId === record.id} onClick={() => onAction(record.id, 'verify', {})}>
            {busyId === record.id ? 'Verifying…' : 'Verify'}
          </button>
          <button type="button" className="donor-button donor-button-danger" disabled={busyId === record.id} onClick={() => {
            setRejectionReason('');
            setRejectingId(record.id);
          }}>
            {busyId === record.id ? 'Rejecting…' : 'Reject'}
          </button>
          {rejectingId === record.id && (
            <div className="compliance-reject-form">
              <label className="donor-field">Rejection reason <b>*</b>
                <textarea rows="2" required value={rejectionReason} onChange={event => setRejectionReason(event.target.value)} />
              </label>
              <div className="donor-form-actions">
                <button type="button" className="donor-button donor-button-secondary" onClick={() => setRejectingId(null)}>Cancel</button>
                <button type="button" className="donor-button donor-button-danger" onClick={() => onAction(record.id, 'reject', { rejection_reason: rejectionReason })} disabled={!rejectionReason.trim() || busyId === record.id}>
                  Confirm reject
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {record.compliance_status === 'rejected' && record.rejection_reason && (
        <p className="compliance-rejection">Reason: {record.rejection_reason}</p>
      )}
    </article>
  );
}

function AllergenDeclarationCard({ declaration, isAdmin, onAction, busyId, rejectionNotes, setRejectionNotes, rejectingId, setRejectingId }) {
  const allergens = declaration.allergen_list || [];

  return (
    <article className="allergen-card">
      <div className="allergen-card-header">
        <div>
          <span className="allergen-donation">{declaration.donation_title}</span>
          <StatusBadge status={declaration.declaration_status} className="allergen-status-badge" />
        </div>
        {allergens.length > 0 && <span className="allergen-tags">{allergens.map(a => getAllergenLabel(a)).join(', ')}</span>}
      </div>
      {declaration.cross_contamination_risk && <p className="allergen-cc">Cross-contamination risk: Yes</p>}
      {declaration.cross_contamination_details && <p className="allergen-cc-details">{declaration.cross_contamination_details}</p>}
      {isAdmin && declaration.declaration_status === 'pending' && (
        <div className="allergen-actions">
          <button type="button" className="donor-button" disabled={busyId === declaration.id} onClick={() => onAction(declaration.id, 'verify', { review_notes: '' })}>
            {busyId === declaration.id ? 'Verifying…' : 'Verify'}
          </button>
          <button type="button" className="donor-button donor-button-danger" disabled={busyId === declaration.id} onClick={() => {
            setRejectionNotes('');
            setRejectingId(declaration.id);
          }}>
            {busyId === declaration.id ? 'Rejecting…' : 'Reject'}
          </button>
          {rejectingId === declaration.id && (
            <div className="allergen-reject-form">
              <label className="donor-field">Review notes <b>*</b>
                <textarea rows="2" required value={rejectionNotes} onChange={event => setRejectionNotes(event.target.value)} />
              </label>
              <div className="donor-form-actions">
                <button type="button" className="donor-button donor-button-secondary" onClick={() => setRejectingId(null)}>Cancel</button>
                <button type="button" className="donor-button donor-button-danger" onClick={() => onAction(declaration.id, 'reject', { review_notes: rejectionNotes })} disabled={!rejectionNotes.trim() || busyId === declaration.id}>
                  Confirm reject
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {declaration.declaration_status === 'rejected' && declaration.review_notes && (
        <p className="allergen-rejection">Notes: {declaration.review_notes}</p>
      )}
    </article>
  );
}

function ComplianceSubmissionForm({ onSubmit, busy }) {
  const [form, setForm] = useState(initialComplianceForm);
  const [fieldErrors, setFieldErrors] = useState({});

  const updateField = (name, value) => {
    setForm(prev => ({ ...prev, [name]: value }));
    setFieldErrors(prev => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  const handleSubmit = async event => {
    event.preventDefault();
    setFieldErrors({});
    const errors = {};
    if (!form.fssai_license_number.trim()) errors.fssai_license_number = 'FSSAI license number is required.';
    else if (!/^\d{14}$/.test(form.fssai_license_number)) errors.fssai_license_number = 'FSSAI license number must be 14 digits.';
    if (!form.fssai_license_expiry) errors.fssai_license_expiry = 'License expiry date is required.';
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;

    try {
      await onSubmit({
        fssai_license_number: form.fssai_license_number.trim(),
        fssai_license_expiry: form.fssai_license_expiry,
        notes: form.notes.trim(),
      });
      setForm(initialComplianceForm);
    } catch (submitError) {
      const data = submitError.response?.data;
      if (data && typeof data === 'object') {
        if (data.detail) setFieldErrors({ __form__: data.detail });
        else {
          Object.entries(data).forEach(([field, messages]) => {
            setFieldErrors(prev => ({ ...prev, [field]: Array.isArray(messages) ? messages.join(' ') : String(messages) }));
          });
        }
      }
    }
  };

  return (
    <form className="donor-form compliance-form" onSubmit={handleSubmit} noValidate>
      <h3>Submit FSSAI compliance for your organization</h3>
      <p className="compliance-form-copy">Provide your organization's FSSAI license details. A platform administrator will review and verify the submission. ShareHarvest does not automatically verify FSSAI licenses.</p>
      {fieldErrors.__form__ && <div className="donor-form-error" role="alert">{fieldErrors.__form__}</div>}
      <label className="donor-field">FSSAI license number <b>*</b>
        <input type="text" maxLength="14" value={form.fssai_license_number} onChange={e => updateField('fssai_license_number', e.target.value)} aria-invalid={fieldErrors.fssai_license_number ? 'true' : undefined} />
        {fieldErrors.fssai_license_number && <small className="field-error" role="alert">{fieldErrors.fssai_license_number}</small>}
      </label>
      <label className="donor-field">License expiry date <b>*</b>
        <input type="date" value={form.fssai_license_expiry} onChange={e => updateField('fssai_license_expiry', e.target.value)} aria-invalid={fieldErrors.fssai_license_expiry ? 'true' : undefined} />
        {fieldErrors.fssai_license_expiry && <small className="field-error" role="alert">{fieldErrors.fssai_license_expiry}</small>}
      </label>
      <label className="donor-field donor-field-full">Additional notes
        <textarea rows="2" value={form.notes} onChange={e => updateField('notes', e.target.value)} />
      </label>
      <div className="donor-form-actions">
        <button type="submit" className="donor-button" disabled={busy}>{busy ? 'Submitting…' : 'Submit for review'}</button>
      </div>
    </form>
  );
}

function AllergenDeclarationForm({ donationId, onSubmit, busy }) {
  const [form, setForm] = useState({ ...initialAllergenForm });
  const [fieldErrors, setFieldErrors] = useState({});

  const toggleAllergen = allergen => {
    setForm(prev => {
      const next = { ...prev, allergens_present: [...prev.allergens_present] };
      const index = next.allergens_present.indexOf(allergen);
      if (index >= 0) next.allergens_present.splice(index, 1);
      else next.allergens_present.push(allergen);
      return next;
    });
  };

  const updateField = (name, value) => setForm(prev => ({ ...prev, [name]: value }));

  const handleSubmit = async event => {
    event.preventDefault();
    setFieldErrors({});
    try {
      await onSubmit({
        donation: donationId,
        allergens_present: form.allergens_present,
        cross_contamination_risk: form.cross_contamination_risk,
        cross_contamination_details: form.cross_contamination_details.trim(),
      });
      setForm({ ...initialAllergenForm });
    } catch (submitError) {
      const data = submitError.response?.data;
      if (data && typeof data === 'object') {
        if (data.detail) setFieldErrors({ __form__: data.detail });
        else {
          Object.entries(data).forEach(([field, messages]) => {
            setFieldErrors(prev => ({ ...prev, [field]: Array.isArray(messages) ? messages.join(' ') : String(messages) }));
          });
        }
      }
    }
  };

  return (
    <form className="donor-form allergen-form" onSubmit={handleSubmit} noValidate>
      <h3>Declare allergens for this donation</h3>
      <p className="allergen-form-copy">List allergens present in the donated food. Never mark food as "allergen-free" based on missing information. Declare only what you know is present.</p>
      {fieldErrors.__form__ && <div className="donor-form-error" role="alert">{fieldErrors.__form__}</div>}
      <fieldset className="allergen-checkbox-group">
        <legend>Allergens present</legend>
        {ALLERGEN_CHOICES.map(choice => (
          <label key={choice.value} className="allergen-checkbox">
            <input type="checkbox" value={choice.value} checked={form.allergens_present.includes(choice.value)} onChange={() => toggleAllergen(choice.value)} />
            {choice.label}
          </label>
        ))}
      </fieldset>
      <label className="donor-field">Cross-contamination risk
        <input type="checkbox" checked={form.cross_contamination_risk} onChange={e => updateField('cross_contamination_risk', e.target.checked)} />
      </label>
      {form.cross_contamination_risk && (
        <label className="donor-field donor-field-full">Cross-contamination details
          <textarea rows="2" value={form.cross_contamination_details} onChange={e => updateField('cross_contamination_details', e.target.value)} />
        </label>
      )}
      <div className="donor-form-actions">
        <button type="submit" className="donor-button" disabled={busy}>{busy ? 'Submitting…' : 'Declare allergens'}</button>
      </div>
    </form>
  );
}

export default function CompliancePage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [complianceRecords, setComplianceRecords] = useState([]);
  const [allergenDeclarations, setAllergenDeclarations] = useState([]);
  const [donations, setDonations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [complianceFormOpen, setComplianceFormOpen] = useState(false);
  const [complianceBusy, setComplianceBusy] = useState(false);
  const [allergenBusy, setAllergenBusy] = useState(false);
  const [selectedDonation, setSelectedDonation] = useState(null);
  const [allergenFormOpen, setAllergenFormOpen] = useState(false);
  const [complianceRejectionReason, setComplianceRejectionReason] = useState('');
  const [allergenRejectionNotes, setAllergenRejectionNotes] = useState('');
  const [rejectingComplianceId, setRejectingComplianceId] = useState(null);
  const [rejectingAllergenId, setRejectingAllergenId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      let records, declarations;
      if (isAdmin) {
        [records, declarations] = await Promise.all([
          getOrganizationCompliance(),
          getAllergenDeclarations(),
        ]);
      } else {
        records = await getMyCompliance();
        declarations = await getMyAllergenDeclarations();
      }
      const recordsData = Array.isArray(records) ? records : (records.results || []);
      setComplianceRecords(recordsData);
      setAllergenDeclarations(declarations);
      if (!isAdmin) {
        const allDonations = await fetch('/api/donations/donations/?mine=true').then(r => r.json());
        const donationList = Array.isArray(allDonations) ? allDonations : (allDonations.results || []);
        setDonations(donationList.filter(d => d.status === 'published'));
      }
    } catch (loadError) {
      setError('We couldn’t load compliance records.');
    } finally { setLoading(false); }
  }, [isAdmin]);

  useEffect(() => { load(); }, [load]);

  const submitComplianceAction = async payload => {
    setComplianceBusy(true);
    setError('');
    try {
      await submitCompliance(payload);
      setNotice('Compliance submission sent for review.');
      setComplianceFormOpen(false);
      await load();
    } catch (submitError) {
      setError('Failed to submit compliance record.');
    } finally { setComplianceBusy(false); }
  };

  const handleComplianceAction = async (id, action, payload) => {
    setBusyId(id);
    setError('');
    try {
      if (action === 'verify') await verifyCompliance(id, payload);
      else await rejectCompliance(id, payload);
      setNotice(`Compliance record ${action === 'verify' ? 'verified' : 'rejected'}.`);
      setRejectingComplianceId(null);
      setComplianceRejectionReason('');
      await load();
    } catch (actionError) {
      setError(`Failed to ${action} compliance record.`);
    } finally { setBusyId(null); }
  };

  const submitAllergenAction = async payload => {
    setAllergenBusy(true);
    setError('');
    try {
      await submitAllergenDeclaration(payload);
      setNotice('Allergen declaration submitted.');
      setAllergenFormOpen(false);
      setSelectedDonation(null);
      await load();
    } catch (submitError) {
      setError('Failed to submit allergen declaration.');
    } finally { setAllergenBusy(false); }
  };

  const handleAllergenAction = async (id, action, payload) => {
    setBusyId(id);
    setError('');
    try {
      await reviewAllergenDeclaration(id, { action, ...payload });
      setNotice(`Allergen declaration ${action === 'verify' ? 'verified' : 'rejected'}.`);
      setRejectingAllergenId(null);
      setAllergenRejectionNotes('');
      await load();
    } catch (actionError) {
      setError(`Failed to ${action} allergen declaration.`);
    } finally { setBusyId(null); }
  };

  const myOrg = useMemo(() => {
    if (!complianceRecords.length) return null;
    return complianceRecords[0];
  }, [complianceRecords]);

  const existingDeclaration = useMemo(() => {
    if (!selectedDonation) return null;
    return allergenDeclarations.find(d => d.donation === selectedDonation.id);
  }, [selectedDonation, allergenDeclarations]);

  return (
    <div className="compliance-page">
      <PageIntro
        eyebrow={isAdmin ? 'PLATFORM ADMINISTRATION' : 'FOOD SAFETY & COMPLIANCE'}
        title={isAdmin ? 'Compliance review' : 'Organization compliance and allergen declarations'}
        description={isAdmin
          ? 'Review and verify FSSAI compliance submissions and allergen declarations across organizations.'
          : 'Submit your organization’s FSSAI compliance details and declare allergens for your donated food.'}
        action={
          !isAdmin && !myOrg && (
            <button type="button" className="donor-button" onClick={() => { setComplianceFormOpen(true); setError(''); }}>
              {complianceFormOpen ? 'Close form' : 'Submit compliance'}
            </button>
          )
        }
      />
      {notice && <p className="compliance-notice" role="status">{notice}</p>}
      {error && <div className="donor-inline-error" role="alert"><span>{error}</span><button type="button" onClick={load}>Try again</button></div>}

      {!isAdmin && (
        <section className="compliance-section">
          <h2>Your organization’s FSSAI compliance</h2>
          {loading ? <div className="donor-panel"><Loading message="Loading compliance record…" /></div> : (
            myOrg ? (
              <ComplianceRecordCard record={myOrg} isAdmin={false} onAction={handleComplianceAction} busyId={busyId} />
            ) : (
              <section className="donor-empty-panel donor-panel">
                <h2>No compliance record yet</h2>
                <p>Your organization has not submitted FSSAI compliance details. Submit your license information for review.</p>
              </section>
            )
          )}
          {!myOrg && complianceFormOpen && (
            <ComplianceSubmissionForm
              onSubmit={submitComplianceAction}
              busy={complianceBusy}
            />
          )}
        </section>
      )}

      {isAdmin && (
        <section className="compliance-section">
          <h2>All organization compliance records</h2>
          {loading ? <div className="donor-panel"><Loading message="Loading compliance records…" /></div> : (
            complianceRecords.length === 0 ? (
              <section className="donor-empty-panel donor-panel"><h2>No compliance records</h2><p>No organizations have submitted compliance details yet.</p></section>
            ) : (
              <div className="compliance-list">
                {complianceRecords.map(record => (
                  <ComplianceRecordCard
                    key={record.id}
                    record={record}
                    isAdmin={true}
                    onAction={handleComplianceAction}
                    busyId={busyId}
                    rejectionReason={complianceRejectionReason}
                    setRejectionReason={setComplianceRejectionReason}
                    rejectingId={rejectingComplianceId}
                    setRejectingId={setRejectingComplianceId}
                  />
                ))}
              </div>
            )
          )}
        </section>
      )}

      <section className="compliance-section allergen-section">
        <h2>Allergen declarations</h2>
        {!isAdmin ? (
          <div>
            {loading ? <div className="donor-panel"><Loading message="Loading declarations…" /></div> : (
              donations.length === 0 ? (
                <section className="donor-empty-panel donor-panel">
                  <h2>No published donations</h2>
                  <p>Publish a donation first to declare allergens for it.</p>
                </section>
              ) : (
                <div>
                  {donations.map(donation => {
                    const existing = allergenDeclarations.find(d => d.donation === donation.id);
                    return (
                      <div key={donation.id} className="donation-allergen-row">
                        <span>{donation.title}</span>
                        {existing ? (
                          <span className="allergen-existing">Declared: {existing.allergen_list?.length > 0 ? existing.allergen_list.join(', ') : 'No allergens declared'} <StatusBadge status={existing.declaration_status} /></span>
                        ) : (
                          allergenFormOpen && selectedDonation?.id === donation.id ? (
                            <AllergenDeclarationForm donationId={donation.id} onSubmit={submitAllergenAction} busy={allergenBusy} />
                          ) : (
                            <button type="button" className="donor-button donor-button-secondary" onClick={() => { setSelectedDonation(donation); setAllergenFormOpen(true); setError(''); }}>
                              Declare allergens
                            </button>
                          )
                        )}
                      </div>
                    );
                  })}
                </div>
              )
            )}
            {allergenFormOpen && selectedDonation && !existingDeclaration && (
              <AllergenDeclarationForm donationId={selectedDonation.id} onSubmit={submitAllergenAction} busy={allergenBusy} />
            )}
          </div>
        ) : (
          <div>
            {loading ? <div className="donor-panel"><Loading message="Loading allergen declarations…" /></div> : (
              allergenDeclarations.length === 0 ? (
                <section className="donor-empty-panel donor-panel"><h2>No allergen declarations</h2><p>No allergen declarations have been submitted yet.</p></section>
              ) : (
                <div className="compliance-list">
                  {allergenDeclarations.map(declaration => (
                    <AllergenDeclarationCard
                      key={declaration.id}
                      declaration={declaration}
                      isAdmin={true}
                      onAction={handleAllergenAction}
                      busyId={busyId}
                      rejectionNotes={allergenRejectionNotes}
                      setRejectionNotes={setAllergenRejectionNotes}
                      rejectingId={rejectingAllergenId}
                      setRejectingId={setRejectingAllergenId}
                    />
                  ))}
                </div>
              )
            )}
          </div>
        )}
      </section>
    </div>
  );
}
