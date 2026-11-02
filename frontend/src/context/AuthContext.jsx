import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import api from '../services/api';

export const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Django's /me/ endpoint returns the serialized user directly (not { data: user }).
  const checkSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/accounts/me/');
      setUser(response.data);
      return response.data;
    } catch (err) {
      setUser(null);
      // A missing/expired session is the normal signed-out state.
      if (err.response?.status !== 401 && err.response?.status !== 403) setError(err);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (credentials) => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.post('/accounts/login/', {
        username: credentials.username.trim(),
        password: credentials.password,
      });
      // Login returns the serialized user and establishes the session cookie.
      setUser(response.data);
      return response.data;
    } catch (err) {
      setUser(null);
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const register = useCallback(async (userData) => {
    setLoading(true);
    setError(null);
    try {
      const registration = await api.post('/accounts/register/', {
        username: userData.username,
        email: userData.email,
        role: userData.role,
        password: userData.password,
        password_confirm: userData.password_confirm,
        first_name: userData.first_name,
        last_name: userData.last_name,
        phone: userData.phone,
      });
      // Registration does not create a session. Sign in using the username the API accepts.
      await login({ username: userData.username, password: userData.password });
      return registration.data;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [login]);

  const logout = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await api.post('/accounts/logout/');
      setUser(null);
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { checkSession(); }, [checkSession]);

  const value = useMemo(() => ({ user, loading, error, login, register, logout, checkSession }), [user, loading, error, login, register, logout, checkSession]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuthContext = () => useContext(AuthContext);
