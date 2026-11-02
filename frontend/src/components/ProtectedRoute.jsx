import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import Loading from './Loading';

const ProtectedRoute = ({ allowedRoles }) => {
  const { user, loading, error, checkSession } = useAuth();

  if (loading) {
    return <Loading />;
  }

  if (!user && error) {
    return <main className="access-denied" role="alert"><h1>We couldn’t load your session</h1><p>Check your connection and try again.</p><button className="access-retry" type="button" onClick={checkSession}>Try again</button></main>;
  }
  if (!user) return <Navigate to="/login" replace />;
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <main className="access-denied" role="alert"><h1>Access unavailable</h1><p>This page is not available for your account.</p></main>;
  }
  return <Outlet />;
};

export default ProtectedRoute;
