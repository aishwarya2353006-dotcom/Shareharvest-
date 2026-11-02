import { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import Button from '../../components/Button';
import Input from '../../components/Input';
import AuthBrandPanel from '../../components/AuthBrandPanel';
import { Link, useNavigate } from 'react-router-dom';

const RegisterPage = () => {
  const { register, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [formData, setFormData] = useState({
    role: '',
    username: '',
    email: '',
    password: '',
    password_confirm: '',
    first_name: '',
    last_name: '',
    phone: '',
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.role) {
      setError('Select Food Donor or Recipient Organization to continue.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const user = await register(formData);
      navigate(user.role === 'recipient' ? '/recipient/dashboard' : '/donor/dashboard', { replace: true });
    } catch (err) {
      const data = err.response?.data;
      const message = data?.detail || (data && Object.entries(data).map(([field, messages]) => `${field.replaceAll('_', ' ')}: ${Array.isArray(messages) ? messages.join(' ') : messages}`).join(' ')) || err.message || 'Registration failed';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page register-page">
      <div className="container auth-layout">
        <AuthBrandPanel />
        <div className="auth-card register-card">
          <p className="auth-card-eyebrow">JOIN SHAREHARVEST</p>
          <h2>Register for ShareHarvest</h2>
          <form className="register-form" onSubmit={handleSubmit} noValidate>
            <fieldset className="register-role-fieldset" aria-describedby="register-role-hint">
              <legend>Choose your account type</legend>
              <p id="register-role-hint" className="register-role-hint">
                Select the option that describes how your organization will use ShareHarvest.
              </p>
              <div className="register-role-options">
                <label className={`register-role-card ${formData.role === 'donor' ? 'is-selected' : ''}`}>
                  <input
                    type="radio"
                    name="role"
                    value="donor"
                    checked={formData.role === 'donor'}
                    onChange={handleChange}
                    required
                  />
                  <span className="register-role-copy">
                    <strong>Food Donor</strong>
                    <small>For restaurants, supermarkets, hotels, caterers, and other food donors.</small>
                  </span>
                </label>
                <label className={`register-role-card ${formData.role === 'recipient' ? 'is-selected' : ''}`}>
                  <input
                    type="radio"
                    name="role"
                    value="recipient"
                    checked={formData.role === 'recipient'}
                    onChange={handleChange}
                    required
                  />
                  <span className="register-role-copy">
                    <strong>Recipient Organization</strong>
                    <small>For NGOs, charitable trusts, and community organizations requesting food.</small>
                  </span>
                </label>
              </div>
              <p className="register-onboarding-note">
                Organization setup happens after registration. New organizations stay pending until a platform administrator verifies them.
              </p>
            </fieldset>
            <div className="form-group">
              <Input
                label="Username"
                type="text"
                name="username"
                value={formData.username}
                onChange={handleChange}
                required
                autoFocus
                error={error?.username ? 'Username is required' : undefined}
              />
            </div>
            <div className="form-group">
              <Input
                label="Email"
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                required
                error={error?.email ? 'Invalid email' : undefined}
              />
            </div>
            <div className="form-group">
              <Input
                label="First Name"
                type="text"
                name="first_name"
                value={formData.first_name}
                onChange={handleChange}
                required
              />
            </div>
            <div className="form-group">
              <Input
                label="Last Name"
                type="text"
                name="last_name"
                value={formData.last_name}
                onChange={handleChange}
                required
              />
            </div>
            <div className="form-group register-field-phone">
              <Input
                label="Phone Number"
                type="tel"
                name="phone"
                value={formData.phone}
                onChange={handleChange}
                placeholder="e.g., +1234567890"
                error={error?.phone ? 'Phone number is required' : undefined}
              />
            </div>
            <div className="form-group">
              <Input
                label="Password"
                type="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                required
                minLength={8}
                error={error?.password ? 'Password must be at least 8 characters' : undefined}
              />
            </div>
            <div className="form-group">
              <Input
                label="Confirm Password"
                type="password"
                name="password_confirm"
                value={formData.password_confirm}
                onChange={handleChange}
                required
                error={
                  formData.password !== formData.password_confirm
                    ? 'Passwords do not match'
                    : undefined
                }
              />
            </div>
            {error && (
              <div className="form-error">
                <p>{error}</p>
              </div>
            )}
            <Button 
              type="submit" 
              loading={loading || authLoading} 
              variant="primary" 
              block
            >
              Register
            </Button>
          </form>
          <div className="auth-footer">
            <p>
              Already have an account?{' '}
              <Link to="/login" className="link">
                Login
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
