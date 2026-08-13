import { useContext } from 'react';
import { NotificationContext } from './notificationContext';

/** The hook only -- see notificationContext.ts for why this is its own file. */
export const useNotification = () => {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error('useNotification must be used within a NotificationProvider');
  }
  return context;
};
