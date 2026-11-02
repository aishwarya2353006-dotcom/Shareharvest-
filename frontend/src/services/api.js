import axios from 'axios';
import { getCookie } from '../utils/cookies';

// Create an axios instance
const api = axios.create({
  baseURL: '/api',
  withCredentials: true, // Important for sending cookies (sessionid, csrftoken)
});

// Request interceptor to add CSRF token to unsafe requests
api.interceptors.request.use(
  async (config) => {
    const unsafeMethods = ['post', 'put', 'patch', 'delete'];
    if (unsafeMethods.includes(config.method?.toLowerCase()) && !config.url?.includes('/accounts/csrf_token/')) {
      let csrftoken = getCookie('csrftoken');
      if (!csrftoken) {
        await api.get('/accounts/csrf_token/');
        csrftoken = getCookie('csrftoken');
      }
      if (csrftoken) config.headers['X-CSRFToken'] = csrftoken;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle common errors
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // On an expired session, send the user back to the login page once so
    // every page does not render its own generic "couldn't load" panel.
    // The CSRF bootstrap, login and session-check endpoints are excluded so
    // the login flow itself and ProtectedRoute's own session check are not
    // double-triggered by this redirect.
    const status = error?.response?.status;
    const requestUrl = error?.config?.url || '';
    const isAuthFlow = requestUrl.includes('/accounts/csrf_token/')
      || requestUrl.includes('/accounts/login/')
      || requestUrl.includes('/accounts/session/');
    if (status === 401 && !isAuthFlow && globalThis.location?.pathname !== '/login') {
      globalThis.location.assign('/login');
    }
    return Promise.reject(error);
  }
);

export default api;
