/**
 * Notifications state store.
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { AppNotification } from "@/types/models";

interface NotificationStore {
  notifications: AppNotification[];
  history: AppNotification[];

  addNotification: (
    notification: Omit<AppNotification, "id" | "createdAt" | "dismissed">
  ) => string;
  upsertNotification: (notification: AppNotification) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
  markAsRead: (id: string) => void;
  markAllRead: () => void;
  dismiss: (id: string) => void;
  getUnreadCount: () => number;
  getRecentNotifications: (limit?: number) => AppNotification[];
  reset: () => void;
}

export const useNotificationStore = create<NotificationStore>()(
  devtools(
    (set, get) => ({
      notifications: [],
      history: [],

      addNotification: (notification) => {
        const id = `notif-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        const newNotif: AppNotification = {
          ...notification,
          id,
          dismissed: false,
          createdAt: Date.now(),
        };

        set((state) => ({
          notifications: [...state.notifications, newNotif],
          history: [...state.history, newNotif].slice(-1000),
        }));

        return id;
      },

      upsertNotification: (notification) =>
        set((state) => {
          const existingIdx = state.notifications.findIndex(
            (n) => n.id === notification.id
          );
          const existingHistoryIdx = state.history.findIndex(
            (n) => n.id === notification.id
          );

          const nextNotifications = [...state.notifications];
          if (existingIdx >= 0) {
            nextNotifications[existingIdx] = {
              ...nextNotifications[existingIdx],
              ...notification,
            };
          } else {
            nextNotifications.push(notification);
          }

          const nextHistory = [...state.history];
          if (existingHistoryIdx >= 0) {
            nextHistory[existingHistoryIdx] = {
              ...nextHistory[existingHistoryIdx],
              ...notification,
            };
          } else {
            nextHistory.push(notification);
          }

          return {
            notifications: nextNotifications,
            history: nextHistory.slice(-1000),
          };
        }),

      removeNotification: (id) =>
        set((state) => ({
          notifications: state.notifications.filter((n) => n.id !== id),
        })),

      clearNotifications: () => set({ notifications: [] }),

      markAsRead: (id) =>
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
          history: state.history.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
        })),

      markAllRead: () =>
        set((state) => ({
          notifications: state.notifications.map((n) => ({ ...n, read: true })),
          history: state.history.map((n) => ({ ...n, read: true })),
        })),

      dismiss: (id) =>
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, dismissed: true } : n
          ),
        })),

      getUnreadCount: () => {
        const state = get();
        return state.notifications.filter((n) => !n.read && !n.dismissed)
          .length;
      },

      getRecentNotifications: (limit = 20) => {
        const state = get();
        return [...state.history].reverse().slice(0, limit);
      },

      reset: () => set({ notifications: [], history: [] }),
    }),
    { name: "NotificationStore" }
  )
);
