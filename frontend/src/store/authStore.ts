import { create } from 'zustand';
import { User } from '../types';
import { API_BASE, getSafeStorage, setSafeStorage, removeSafeStorage } from '../api/client';
import { useCartStore } from './cartStore';

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  setAuth: (token: string, user: User, refreshToken?: string | null) => void;
  setToken: (token: string, refreshToken?: string | null) => void;
  logout: () => void;
}

const getInitialUser = (): User | null => {
  const raw = getSafeStorage('patty_user');
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const useAuthStore = create<AuthState>((set) => {
  // Synchronize state when session expires or token is refreshed in API client
  if (typeof window !== 'undefined') {
    window.addEventListener('patty:auth_session_expired', () => {
      useCartStore.getState().resetCartOnLogout();
      set({ token: null, refreshToken: null, user: null });
    });

    window.addEventListener('patty:auth_token_refreshed', ((e: CustomEvent) => {
      if (e.detail?.token) {
        set((state) => ({
          token: e.detail.token,
          refreshToken: e.detail.refreshToken || state.refreshToken || getSafeStorage('patty_refresh_token'),
        }));
      }
    }) as EventListener);
  }

  return {
    token: getSafeStorage('patty_token'),
    refreshToken: getSafeStorage('patty_refresh_token'),
    user: getInitialUser(),
    setAuth: (token, user, refreshToken) => {
      setSafeStorage('patty_token', token);
      setSafeStorage('patty_user', JSON.stringify(user));
      if (refreshToken) {
        setSafeStorage('patty_refresh_token', refreshToken);
      }
      set({ token, user, refreshToken: refreshToken || getSafeStorage('patty_refresh_token') });
      // Trigger cart migration / hydration
      useCartStore.getState().onAuthChange(user);
    },
    setToken: (token, refreshToken) => {
      setSafeStorage('patty_token', token);
      if (refreshToken) {
        setSafeStorage('patty_refresh_token', refreshToken);
      }
      set({ token, refreshToken: refreshToken || getSafeStorage('patty_refresh_token') });
    },
    logout: () => {
      const activeRefreshToken = getSafeStorage('patty_refresh_token');
      if (activeRefreshToken) {
        try {
          fetch(`${API_BASE}/auth/logout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: activeRefreshToken }),
          }).catch(() => {});
        } catch {}
      }
      removeSafeStorage('patty_token');
      removeSafeStorage('patty_refresh_token');
      removeSafeStorage('patty_user');
      useCartStore.getState().resetCartOnLogout();
      set({ token: null, refreshToken: null, user: null });
    },
  };
});
