import api from './api';

export const getNotifications = (page = 1) => api.get('/notifications/', { params: { page } }).then(response => response.data);
export const getUnreadNotificationCount = () => api.get('/notifications/unread-count/').then(response => response.data.count);
export const markNotificationRead = id => api.post(`/notifications/${id}/read/`).then(response => response.data);
export const markAllNotificationsRead = () => api.post('/notifications/mark-all-read/').then(response => response.data);
