import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import {
  changePassword,
  getApiErrorMessage,
  getMyProfile,
  updateMyProfile,
} from '../../services/accountApi';
import Loading from '../../components/Loading';

const SettingsSection = ({ title, description, children, interactive = false }) => (
  <section className={`settings-section${interactive ? ' is-interactive' : ''}`} aria-labelledby={`settings-${title.toLowerCase()}-heading`}>
    <div className="settings-section-copy">
      <h3 id={`settings-${title.toLowerCase()}-heading`}>{title}</h3>
      <p>{description}</p>
    </div>
    {children}
  </section>
);

const EDITABLE_FIELDS = [
  ['first_name', 'First name'],
  ['last_name', 'Last name'],
  ['email', 'Email'],
  ['phone', 'Phone'],
];

// Protected fields are shown read-only; the backend serializer rejects them anyway.
const READ_ONLY_FIELDS = [
  ['username', 'Username'],
  ['role', 'Role'],
  ['is_verified', 'Verified'],
];

function ProfileSection() {
  const { checkSession } = useAuth();
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [formError, setFormError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [success, setSuccess] = useState('');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setLoadError('');
      try {
        const data = await getMyProfile();
        if (!active) return;
        setProfile(data);
        setForm({
          first_name: data.first_name || '',
          last_name: data.last_name || '',
          email: data.email || '',
          phone: data.phone || '',
        });
      } catch (loadError) {
        if (active) setLoadError(getApiErrorMessage(loadError));
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => { active = false; };
  }, []);

  const updateField = event => {
    setForm(previous => ({ ...previous, [event.target.name]: event.target.value }));
    setFieldErrors(previous => {
      if (!previous[event.target.name]) return previous;
      const next = { ...previous };
      delete next[event.target.name];
      return next;
    });
  };

  const submit = async event => {
    event.preventDefault();
    setFormError('');
    setSuccess('');
    setFieldErrors({});
    if (!form.email.trim()) {
      setFieldErrors({ email: 'Email is required.' });
      return;
    }
    setSaving(true);
    try {
      const updated = await updateMyProfile({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
      });
      setProfile(updated);
      setForm({
        first_name: updated.first_name || '',
        last_name: updated.last_name || '',
        email: updated.email || '',
        phone: updated.phone || '',
      });
      setSuccess('Profile updated.');
      // Keep the topbar/sidebar identity in sync with the saved profile.
      await checkSession();
    } catch (saveError) {
      if (saveError.response?.status === 401 || saveError.response?.status === 403) {
        setFormError('Your session has expired. Please sign in again.');
      } else {
        const data = saveError.response?.data;
        if (data && typeof data === 'object' && !data.detail) {
          setFieldErrors(Object.fromEntries(
            Object.entries(data).map(([field, messages]) => [
              field,
              Array.isArray(messages) ? messages.join(' ') : String(messages),
            ])
          ));
        } else {
          setFormError(getApiErrorMessage(saveError));
        }
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="settings-loading" role="status"><Loading message="Loading your profile…" /></div>;
  }
  if (loadError) {
    return <div className="settings-note settings-note-error" role="alert">We couldn’t load your profile. {loadError}</div>;
  }

  return (
    <form className="settings-form" onSubmit={submit} noValidate>
      <div className="settings-facts">
        {READ_ONLY_FIELDS.map(([field, label]) => (
          <span key={field}><b>{label}</b>{field === 'is_verified'
            ? (profile.is_verified ? 'Yes' : 'No')
            : (profile[field] || '—')}</span>
        ))}
      </div>
      <div className="settings-fields">
        {EDITABLE_FIELDS.map(([field, label]) => (
          <label className="donor-field" key={field}>
            {label}
            <input
              name={field}
              type={field === 'email' ? 'email' : 'text'}
              value={form[field]}
              onChange={updateField}
              maxLength="254"
              autoComplete={field === 'email' ? 'email' : 'off'}
              aria-invalid={fieldErrors[field] ? 'true' : undefined}
              aria-describedby={fieldErrors[field] ? `settings-${field}-error` : undefined}
            />
            {fieldErrors[field] && <small id={`settings-${field}-error`} role="alert">{fieldErrors[field]}</small>}
          </label>
        ))}
      </div>
      {success && <p className="settings-note settings-note-success" role="status">{success}</p>}
      {formError && <p className="settings-note settings-note-error" role="alert">{formError}</p>}
      <div className="settings-form-actions">
        <button className="donor-button" type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </form>
  );
}

function SecuritySection() {
  const [form, setForm] = useState({ current_password: '', new_password: '', new_password_confirm: '' });
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [success, setSuccess] = useState('');
  const [saving, setSaving] = useState(false);

  const updateField = event => {
    setForm(previous => ({ ...previous, [event.target.name]: event.target.value }));
    setFieldErrors(previous => {
      if (!previous[event.target.name]) return previous;
      const next = { ...previous };
      delete next[event.target.name];
      return next;
    });
  };

  const submit = async event => {
    event.preventDefault();
    setFormError('');
    setSuccess('');
    const errors = {};
    if (!form.current_password) errors.current_password = 'Current password is required.';
    if (form.new_password.length < 8) errors.new_password = 'New password must be at least 8 characters.';
    if (form.new_password !== form.new_password_confirm) {
      errors.new_password_confirm = 'Passwords do not match.';
    } else if (form.new_password && form.new_password === form.current_password) {
      errors.new_password = 'New password must differ from the current password.';
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;

    setSaving(true);
    try {
      await changePassword({
        current_password: form.current_password,
        new_password: form.new_password,
        new_password_confirm: form.new_password_confirm,
      });
      // Never retain password values in state after submission.
      setForm({ current_password: '', new_password: '', new_password_confirm: '' });
      setSuccess('Password changed successfully.');
    } catch (saveError) {
      if (saveError.response?.status === 401 || saveError.response?.status === 403) {
        setFormError('Your session has expired. Please sign in again.');
      } else {
        const data = saveError.response?.data;
        if (data && typeof data === 'object' && !data.detail) {
          setFieldErrors(Object.fromEntries(
            Object.entries(data).map(([field, messages]) => [
              field,
              Array.isArray(messages) ? messages.join(' ') : String(messages),
            ])
          ));
        } else {
          setFormError(getApiErrorMessage(saveError));
        }
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="settings-form" onSubmit={submit} noValidate>
      <div className="settings-fields">
        {[
          ['current_password', 'Current password', 'current-password'],
          ['new_password', 'New password', 'new-password'],
          ['new_password_confirm', 'Confirm new password', 'new-password'],
        ].map(([field, label, autoComplete]) => (
          <label className="donor-field" key={field}>
            {label}
            <input
              name={field}
              type="password"
              value={form[field]}
              onChange={updateField}
              autoComplete={autoComplete}
              aria-invalid={fieldErrors[field] ? 'true' : undefined}
              aria-describedby={fieldErrors[field] ? `settings-${field}-error` : undefined}
            />
            {fieldErrors[field] && <small id={`settings-${field}-error`} role="alert">{fieldErrors[field]}</small>}
          </label>
        ))}
      </div>
      {success && <p className="settings-note settings-note-success" role="status">{success}</p>}
      {formError && <p className="settings-note settings-note-error" role="alert">{formError}</p>}
      <div className="settings-form-actions">
        <button className="donor-button" type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Change password'}
        </button>
      </div>
    </form>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const organizationsPath = {
    donor: '/donor/organizations',
    recipient: '/recipient/organizations',
    admin: '/admin/organizations',
  }[user?.role];

  return (
    <div className="settings-page">
      <header className="settings-intro">
        <p className="donor-eyebrow">YOUR ACCOUNT</p>
        <h2>Settings</h2>
        <p>Manage your account and workspace preferences.</p>
      </header>

      <div className="settings-sections">
        <SettingsSection
          title="Profile"
          description="Update your contact details. Username, role, and verification are managed by ShareHarvest."
          interactive
        >
          <ProfileSection />
        </SettingsSection>

        <SettingsSection
          title="Security"
          description="Change your password. You will stay signed in on this device."
          interactive
        >
          <SecuritySection />
        </SettingsSection>

        <SettingsSection
          title="Notifications"
          description="Review and manage notifications for requests and pickups."
        >
          <Link className="settings-link" to="/notifications">Open notifications</Link>
        </SettingsSection>

        <SettingsSection
          title="Organization"
          description="View your organization memberships and available management actions."
        >
          {organizationsPath
            ? <Link className="settings-link" to={organizationsPath}>Open organizations</Link>
            : <span className="settings-status">No organization page is available for this role.</span>}
        </SettingsSection>
      </div>
    </div>
  );
}
