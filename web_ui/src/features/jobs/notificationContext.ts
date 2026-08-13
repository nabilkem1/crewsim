import { createContext } from 'react';

/**
 * The context object and its types only -- no component, no hook.
 *
 * Split out of NotificationContext.tsx/useNotification.ts: a file that
 * exports a component alongside a non-component value (a hook, a context
 * object) cannot be a React Fast Refresh boundary, so Vite falls back to
 * invalidating and remounting everything that imports it -- and this
 * context is imported by `App.tsx` at the root of the whole tree via
 * `NotificationProvider`. In a dev environment with several people editing
 * web_ui/src concurrently, every one of their saves was forcing a full
 * remount of the entire app for anyone else with it open: the "flickering"
 * this file exists to fix.
 */

export interface Notification {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
}

export interface NotificationContextType {
  notifications: Notification[];
  addNotification: (message: string, type?: Notification['type']) => void;
  removeNotification: (id: string) => void;
}

export const NotificationContext = createContext<NotificationContextType | undefined>(undefined);
