import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import {
  AuthUser,
  loginWithEmail,
  registerWithEmail,
  requestPasswordReset,
  resetPassword,
  verifyEmailCode,
} from "@/services/auth";

interface AuthStore {
  currentUser: AuthUser | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (email: string, displayName: string, password: string) => Promise<{ dev_code?: string }>;
  verifyEmail: (email: string, code: string) => Promise<void>;
  requestPasswordReset: (email: string) => Promise<{ dev_code?: string; message: string }>;
  resetPassword: (email: string, code: string, newPassword: string) => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthStore>()(
  devtools(
    persist(
      (set) => ({
        currentUser: null,
        isAuthenticated: false,
        loading: false,
        error: null,

        login: async (email, password) => {
          set({ loading: true, error: null });
          try {
            const result = await loginWithEmail({ email, password });
            if (!result.ok || !result.user) {
              throw new Error("Invalid login response");
            }
            set({
              currentUser: result.user,
              isAuthenticated: true,
              loading: false,
              error: null,
            });
          } catch (error) {
            set({
              loading: false,
              error: error instanceof Error ? error.message : "Login failed",
            });
            throw error;
          }
        },

        logout: () =>
          set({
            currentUser: null,
            isAuthenticated: false,
            loading: false,
            error: null,
          }),

        register: async (email, displayName, password) => {
          set({ loading: true, error: null });
          try {
            const result = await registerWithEmail({
              email,
              display_name: displayName,
              password,
            });
            set({ loading: false, error: null });
            return { dev_code: result.dev_code };
          } catch (error) {
            set({
              loading: false,
              error: error instanceof Error ? error.message : "Register failed",
            });
            throw error;
          }
        },

        verifyEmail: async (email, code) => {
          set({ loading: true, error: null });
          try {
            await verifyEmailCode({ email, code });
            set({ loading: false, error: null });
          } catch (error) {
            set({
              loading: false,
              error: error instanceof Error ? error.message : "Email verification failed",
            });
            throw error;
          }
        },

        requestPasswordReset: async (email) => {
          set({ loading: true, error: null });
          try {
            const result = await requestPasswordReset({ email });
            set({ loading: false, error: null });
            return { dev_code: result.dev_code, message: result.message };
          } catch (error) {
            set({
              loading: false,
              error: error instanceof Error ? error.message : "Password reset request failed",
            });
            throw error;
          }
        },

        resetPassword: async (email, code, newPassword) => {
          set({ loading: true, error: null });
          try {
            await resetPassword({
              email,
              code,
              new_password: newPassword,
            });
            set({ loading: false, error: null });
          } catch (error) {
            set({
              loading: false,
              error: error instanceof Error ? error.message : "Password reset failed",
            });
            throw error;
          }
        },

        clearError: () => set({ error: null }),
      }),
      {
        name: "authStore",
        partialize: (state) => ({
          currentUser: state.currentUser,
          isAuthenticated: state.isAuthenticated,
        }),
      }
    ),
    { name: "AuthStore" }
  )
);

export function getCurrentUserId() {
  const state = useAuthStore.getState();
  return state.currentUser?.id || process.env.NEXT_PUBLIC_USER_ID || "frontend";
}
