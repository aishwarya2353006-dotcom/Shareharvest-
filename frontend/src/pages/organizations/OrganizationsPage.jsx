import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import Loading from '../../components/Loading';
import PageIntro from '../../components/PageIntro';
import StatusBadge from '../../components/StatusBadge';
import { getApiErrorMessage } from '../../services/donorApi';
import { createMembership, createOrganization, getMyMemberships, getOrganizationMemberships, getOrganizations, searchOrganizationUsers, setOrganizationVerification, updateMembership } from '../../services/organizationApi';

const types = [
  ['restaurant', 'Restaurant'], ['hotel', 'Hotel'], ['supermarket', 'Supermarket'],
  ['mall', 'Shopping mall'], ['catering', 'Catering company'], ['event', 'Event organizer'],
  ['ngo', 'NGO / Charity'], ['trust', 'Trust'], ['community', 'Community organization'], ['other', 'Other'],
];
const typeName = value => types.find(([key]) => key === value)?.[1] || value;
const membershipRoles = [['owner', 'Owner', 4], ['admin', 'Admin', 3], ['member', 'Member', 2], ['volunteer', 'Volunteer', 1]];
const initialForm = { name: '', org_type: 'restaurant', description: '', address: '', city: '', state: '', postal_code: '', country: 'India', phone: '', email: '', website: '' };

function OrganizationCard({ organization, role, members, admin, onVerifyAction, onRoleChange, onAddMember, busy, membershipBusyId }) {
  const [addOpen, setAddOpen] = useState(false);
  const [userSearch, setUserSearch] = useState('');
  const [userResults, setUserResults] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [newRole, setNewRole] = useState('volunteer');
  const [addBusy, setAddBusy] = useState(false);
  const [addError, setAddError] = useState('');
  const [addNotice, setAddNotice] = useState('');
  const status = organization.status || 'unknown';
  const roleLevel = membershipRoles.find(([value]) => value === role)?.[2] || 0;
  const assignableRoles = membershipRoles.filter(([, , level]) => level <= roleLevel);
  const existingMembership = members?.find(member => Number(member.user) === selectedUser?.id);

  useEffect(() => {
    const term = userSearch.trim();
    if (!addOpen || term.length < 2) {
      setUserResults([]);
      setSearchBusy(false);
      setSearchError('');
      return undefined;
    }

    let current = true;
    setSearchBusy(true);
    setSearchError('');
    const timer = setTimeout(async () => {
      try {
        const results = await searchOrganizationUsers(organization.id, term);
        if (current) setUserResults(results);
      } catch (error) {
        if (current) {
          setUserResults([]);
          setSearchError(getApiErrorMessage(error));
        }
      } finally {
        if (current) setSearchBusy(false);
      }
    }, 250);

    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [addOpen, organization.id, userSearch]);

  const submitAddMember = async event => {
    event.preventDefault();
    setAddError('');
    setAddNotice('');
    if (!selectedUser) {
      setAddError('Search for and select an existing account.');
      return;
    }
    if (existingMembership?.is_active) {
      setAddError('This user is already an active member of this organization.');
      return;
    }
    setAddBusy(true);
    try {
      await onAddMember(organization.id, selectedUser.id, newRole, existingMembership);
      setAddNotice(existingMembership ? 'Existing membership reactivated.' : 'Member added successfully.');
      setUserSearch('');
      setSelectedUser(null);
      setUserResults([]);
      setAddOpen(false);
    } catch (error) {
      setAddError(getApiErrorMessage(error));
    } finally {
      setAddBusy(false);
    }
  };

  return (
    <article className="org-card">
      <div className="org-card-heading">
        <div className="org-card-title">
          <span className="donor-category-label">{typeName(organization.org_type)}</span>
          <h2>{organization.name}</h2>
        </div>
        <StatusBadge status={status} />
      </div>
      {organization.description && <p className="org-description">{organization.description}</p>}
      <div className="org-information-grid">
        <section className="org-info-group" aria-label="Organization location">
          <h3>Location</h3>
          {organization.address && <p>{organization.address}</p>}
          <p>{[organization.city, organization.state, organization.country].filter(Boolean).join(', ') || 'Not provided'}</p>
        </section>
        <section className="org-info-group" aria-label="Organization contact">
          <h3>Contact</h3>
          {organization.phone && <a href={`tel:${organization.phone}`}>{organization.phone}</a>}
          {organization.email && <a href={`mailto:${organization.email}`}>{organization.email}</a>}
          {organization.website && <span>{organization.website}</span>}
          {!organization.phone && !organization.email && !organization.website && <p>Not provided</p>}
        </section>
      </div>
      {role && <div className="org-membership-summary">
        <span>Your membership</span>
        <strong>{role}</strong>
      </div>}
      {admin && <div className="org-actions">
        {status !== 'verified' && <button type="button" className="donor-button" disabled={busy} onClick={() => onVerifyAction(organization, 'verify')}>{busy ? 'Saving…' : 'Verify'}</button>}
        {status !== 'rejected' && <button type="button" className="donor-button donor-button-danger" disabled={busy} onClick={() => onVerifyAction(organization, 'reject')}>{busy ? 'Saving…' : 'Reject'}</button>}
        {status !== 'pending' && <button type="button" className="donor-button donor-button-secondary" disabled={busy} onClick={() => onVerifyAction(organization, 'pending')}>{busy ? 'Saving…' : 'Set pending'}</button>}
      </div>}
      {!admin && ['owner', 'admin'].includes(role) && members && <section className="org-members">
        <div className="org-members-heading"><h3>Memberships</h3><button type="button" className="donor-button donor-button-secondary" onClick={() => { setAddOpen(open => !open); setAddError(''); setAddNotice(''); }}>{addOpen ? 'Close' : 'Add member'}</button></div>
        {addNotice && <p className="org-notice" role="status">{addNotice}</p>}
        {addOpen && <form className="org-add-member-form" onSubmit={submitAddMember}>
          {addError && <div className="donor-form-error" role="alert">{addError}</div>}
          <label className="donor-field">Search username or email <b>*</b><input type="search" value={userSearch} onChange={event => { setUserSearch(event.target.value); setSelectedUser(null); setAddError(''); }} placeholder="Enter at least 2 characters" autoComplete="off" aria-describedby={`org-member-help-${organization.id}`} aria-controls={`org-user-results-${organization.id}`} /></label>
          <small id={`org-member-help-${organization.id}`} className="org-members-note">Search is limited to active accounts that are not already active members of this organization.</small>
          {searchBusy && <p className="org-add-member-match" role="status">Searching accounts…</p>}
          {searchError && <div className="donor-form-error" role="alert">Couldn’t search accounts: {searchError}</div>}
          {!searchBusy && !searchError && userSearch.trim().length >= 2 && userResults.length === 0 && !selectedUser && <p className="org-add-member-match" role="status">No matching accounts found.</p>}
          {userResults.length > 0 && <div id={`org-user-results-${organization.id}`} className="org-user-search-results" role="group" aria-label="Matching user accounts">{userResults.map(account => <button key={account.id} type="button" className="org-user-result" onClick={() => { setSelectedUser(account); setUserResults([]); setAddError(''); }}><strong>{account.username}</strong><span>{account.email || 'No email provided'}</span></button>)}</div>}
          {selectedUser && <div className="org-selected-user" role="status"><span>Selected account</span><strong>{selectedUser.username}</strong><small>{selectedUser.email || 'No email provided'}</small><button type="button" onClick={() => { setSelectedUser(null); setUserResults([]); }}>Change selection</button></div>}
          {existingMembership && <p className="org-add-member-match" role="status">{existingMembership.is_active ? 'That user is already an active member.' : 'An inactive membership exists and will be reactivated.'}</p>}
          <label className="donor-field">Membership role <b>*</b><select required value={newRole} onChange={event => setNewRole(event.target.value)}>{assignableRoles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <button type="submit" className="donor-button" disabled={addBusy || searchBusy || !selectedUser || Boolean(existingMembership?.is_active)}>{addBusy ? 'Saving…' : existingMembership ? 'Reactivate membership' : 'Add member'}</button>
        </form>}
        {members.length === 0 ? <p>No memberships found.</p> : members.map(member => (
          <div className="org-member-row" key={member.id}>
            <span className="org-member-name">
              {member.user_details ? `${member.user_details.first_name || ''} ${member.user_details.last_name || ''}`.trim() || member.user_details.username : `User #${member.user}`}
              {!member.is_active && <span className="org-member-inactive">Inactive</span>}
            </span>
            <span className="org-member-role">{member.role}</span>
            {member.is_active && <label className="org-role-control"><span className="sr-only">Change role for user #{member.user}</span><select value={member.role} disabled={membershipBusyId === member.id} onChange={event => onRoleChange(organization.id, member, event.target.value)}>{assignableRoles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
          </div>
        ))}<p className="org-members-note">Role changes follow the backend hierarchy; you cannot assign a role higher than your own.</p></section>}
    </article>
  );
}

export default function OrganizationsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [organizations, setOrganizations] = useState([]);
  const [memberships, setMemberships] = useState([]);
  const [managedMemberships, setManagedMemberships] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [formOpen, setFormOpen] = useState(false);
  const [formBusy, setFormBusy] = useState(false);
  const [formError, setFormError] = useState('');
  const [notice, setNotice] = useState('');
  const membershipByOrg = useMemo(() => new Map(memberships.filter(item => item.is_active).map(item => [item.organization, item.role])), [memberships]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [orgs, ownMemberships] = await Promise.all([
        getOrganizations(),
        isAdmin ? Promise.resolve([]) : getMyMemberships(),
      ]);
      const ownRoles = new Map(ownMemberships.filter(item => item.is_active).map(item => [item.organization, item.role]));
      const managerOrganizations = isAdmin ? [] : orgs.filter(org => ['owner', 'admin'].includes(ownRoles.get(org.id)));
      const managerLists = await Promise.all(managerOrganizations.map(org => getOrganizationMemberships(org.id)));
      setManagedMemberships(Object.fromEntries(managerOrganizations.map((org, index) => [org.id, managerLists[index]])));
      setOrganizations(orgs);
      setMemberships(ownMemberships);
    } catch (loadError) {
      setError(getApiErrorMessage(loadError));
    } finally { setLoading(false); }
  }, [isAdmin]);
  useEffect(() => { load(); }, [load]);

  const submit = async event => {
    event.preventDefault();
    setFormError('');
    setNotice('');
    setFormBusy(true);
    try {
      const response = await createOrganization(form);
      setNotice(`${response.data.name} was created and is pending verification.`);
      setForm(initialForm);
      setFormOpen(false);
      await load();
    } catch (submitError) { setFormError(getApiErrorMessage(submitError)); }
    finally { setFormBusy(false); }
  };

  const verifyAction = async (organization, action) => {
    setBusyId(organization.id);
    setActionError('');
    setNotice('');
    try {
      await setOrganizationVerification(organization.id, action);
      setNotice(`${organization.name} status updated.`);
      await load();
    } catch (actionFailure) { setActionError(getApiErrorMessage(actionFailure)); }
    finally { setBusyId(null); }
  };

  const changeMembershipRole = async (organizationId, membership, role) => {
    setBusyId(membership.id);
    setActionError('');
    setNotice('');
    try {
      await updateMembership(membership.id, organizationId, { role });
      setNotice(`Membership for user #${membership.user} updated.`);
      await load();
    } catch (actionFailure) { setActionError(getApiErrorMessage(actionFailure)); }
    finally { setBusyId(null); }
  };

  const addMember = async (organizationId, userId, role, existingMembership) => {
    setActionError('');
    setNotice('');
    if (existingMembership) {
      await updateMembership(existingMembership.id, organizationId, { role, is_active: true });
    } else {
      await createMembership({ user: userId, organization: organizationId, role });
    }
    setNotice(existingMembership ? 'Membership reactivated.' : 'Member added.');
    await load();
  };

  return (
    <div className="org-page">
      <PageIntro
        eyebrow={isAdmin ? 'PLATFORM ADMINISTRATION' : 'YOUR ORGANIZATIONS'}
        title={isAdmin ? 'Organization review' : 'Organizations and memberships'}
        description={isAdmin ? 'Review organization verification status using platform-admin actions.' : 'Manage organizations you belong to, review your membership, or add an organization.'}
        action={!isAdmin && <button type="button" className="donor-button" onClick={() => { setFormOpen(open => !open); setFormError(''); }}>{formOpen ? 'Close form' : 'Add organization'}</button>}
      />
      {notice && <p className="org-notice" role="status">{notice}</p>}
      {actionError && <div className="donor-inline-error" role="alert"><span>{actionError}</span><button type="button" onClick={() => setActionError('')}>Dismiss</button></div>}
      {formOpen && !isAdmin && <section className="donor-panel org-form-panel"><h2>Create an organization</h2><p className="org-form-copy">New organizations start pending verification. Creating one adds you as its owner.</p>{formError && <div className="donor-form-error" role="alert">{formError}</div>}<form className="donor-form org-form" onSubmit={submit}>
        <label className="donor-field">Organization name <b>*</b><input required maxLength="255" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label>
        <label className="donor-field">Organization type <b>*</b><select required value={form.org_type} onChange={e => setForm({ ...form, org_type: e.target.value })}>{types.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="donor-field donor-field-full">Description<textarea rows="2" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></label>
        <label className="donor-field donor-field-full">Street address <b>*</b><textarea required value={form.address} onChange={e => setForm({ ...form, address: e.target.value })} /></label>
        <label className="donor-field">City <b>*</b><input required value={form.city} onChange={e => setForm({ ...form, city: e.target.value })} /></label>
        <label className="donor-field">State / province <b>*</b><input required value={form.state} onChange={e => setForm({ ...form, state: e.target.value })} /></label>
        <label className="donor-field">Postal code <b>*</b><input required value={form.postal_code} onChange={e => setForm({ ...form, postal_code: e.target.value })} /></label>
        <label className="donor-field">Country <b>*</b><input required value={form.country} onChange={e => setForm({ ...form, country: e.target.value })} /></label>
        <label className="donor-field">Phone <b>*</b><input required type="tel" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} /></label>
        <label className="donor-field">Email <b>*</b><input required type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></label>
        <label className="donor-field donor-field-full">Website<input type="url" value={form.website} onChange={e => setForm({ ...form, website: e.target.value })} /></label>
        <div className="donor-form-actions"><button type="submit" className="donor-button" disabled={formBusy}>{formBusy ? 'Creating…' : 'Create organization'}</button></div>
      </form></section>}
      {loading ? <div className="donor-panel"><Loading message="Loading organizations…" /></div> : error ? <section className="donor-state-panel" role="alert"><h2>We couldn’t load organizations</h2><p>{error}</p><button className="donor-button donor-button-secondary" type="button" onClick={load}>Try again</button></section> : organizations.length === 0 ? <section className="donor-empty-panel donor-panel"><h2>{isAdmin ? 'No organizations found' : 'No organization memberships yet'}</h2><p>{isAdmin ? 'Organizations will appear here for verification.' : 'Create an organization to become its owner, or ask an existing organization admin to add your membership.'}</p></section> : <div className="org-list">{organizations.map(org => <OrganizationCard key={org.id} organization={org} role={membershipByOrg.get(org.id)} members={managedMemberships[org.id]} admin={isAdmin} busy={busyId === org.id} membershipBusyId={busyId} onVerifyAction={verifyAction} onRoleChange={changeMembershipRole} onAddMember={addMember} />)}</div>}
    </div>
  );
}
