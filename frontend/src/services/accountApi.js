import api from './api';
import { getApiErrorMessage } from './donorApi';

export const getMyProfile = () => api.get('/accounts/me/').then(response => response.data);

export const updateMyProfile = payload => api
  .patch('/accounts/me/', payload)
  .then(response => response.data);

export const changePassword = payload => api
  .post('/accounts/change-password/', payload)
  .then(response => response.data);

export { getApiErrorMessage };
