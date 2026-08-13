import { useState } from 'react';
import type { ReactNode } from 'react';
import './Jobs.css';
import { NotificationContext, type Notification } from './notificationContext';

/** The provider component only -- see notificationContext.ts for why this
 *  is split from the context object and the useNotification hook. */
export const NotificationProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const addNotification = (message: string, type: Notification['type'] = 'info') => {
    const id = Math.random().toString(36).substr(2, 9);
    setNotifications(prev => [...prev, { id, message, type }]);

    // Auto remove after 5 seconds
    setTimeout(() => {
      removeNotification(id);
    }, 5000);
  };

  const removeNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  return (
    <NotificationContext.Provider value={{ notifications, addNotification, removeNotification }}>
      {children}
      <div className="notification-container">
        {notifications.map(note => (
          <div key={note.id} className={`notification-toast toast-${note.type}`}>
            <span>{note.message}</span>
            <button onClick={() => removeNotification(note.id)} className="toast-close">&times;</button>
          </div>
        ))}
      </div>
    </NotificationContext.Provider>
  );
};
