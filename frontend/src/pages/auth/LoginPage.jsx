import { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import Button from '../../components/Button';
import Input from '../../components/Input';
import AuthBrandPanel from '../../components/AuthBrandPanel';
import { Link, useNavigate } from 'react-router-dom';

const LoginPage = () => {
  const { login, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [credentials, setCredentials] = useState({
    username: '',
    password: '',
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setCredentials(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const user = await login(credentials);
      const destination = {
        donor: '/donor/dashboard',
        recipient: '/recipient/dashboard',
        volunteer: '/volunteer/pickups',
        admin: '/admin/dashboard',
      }[user.role] || '/';
      navigate(destination, { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="container auth-layout">
        <AuthBrandPanel />
        <div className="auth-card">
          <p className="auth-card-eyebrow">WELCOME BACK</p>
          <h2>Login to ShareHarvest</h2>
          <form onSubmit={handleSubmit} noValidate>
            <div className="form-group">
              <Input
                label="Username"
                type="text"
                name="username"
                value={credentials.username}
                onChange={handleChange}
                required
                autoFocus
                error={error?.email ? 'Invalid email' : undefined}
              />
            </div>
            <div className="form-group">
              <Input
                label="Password"
                type="password"
                name="password"
                value={credentials.password}
                onChange={handleChange}
                required
                error={error?.password ? 'Invalid password' : undefined}
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
              Login
            </Button>
          </form>
          <div className="auth-footer">
            <p>
              Don't have an account?{' '}
              <Link to="/register" className="link">
                Register
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
