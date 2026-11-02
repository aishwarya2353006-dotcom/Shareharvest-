import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { getUnreadNotificationCount } from '../services/notificationApi';

const NotificationsContext = createContext(null);

export const NotificationsProvider = ({ children }) => {
  const [unreadCount, setUnreadCount] = useState(0);
  const [countError, setCountError] = useState(false);
  const refreshUnreadCount = useCallback(async () => {
    try {
      setUnreadCount(await getUnreadNotificationCount());
      setCountError(false);
    } catch {
      setCountError(true);
    }
  }, []);

  useEffect(() => { refreshUnreadCount(); }, [refreshUnreadCount]);

  return (
    <NotificationsContext.Provider value={{ unreadCount, countError, refreshUnreadCount }}>
      {children}
    </NotificationsContext.Provider>
  );
};

export const useNotifications = () => {
  const context = useContext(NotificationsContext);
  if (!context) throw new Error('useNotifications must be used within NotificationsProvider');
  return context;
};
