import { create } from 'zustand';
import { User } from '../types';
import { API_BASE } from '../api/client';

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  setAuth: (token: string, user: User, refreshToken?: string | null) => void;
  setToken: (token: string, refreshToken?: string | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => {
  // Synchronize state when session expires in API client
  if (typeof window !== 'undefined') {
    window.addEventListener('patty:auth_session_expired', () => {
      set({ token: null, refreshToken: null, user: null });
    });
  }

  return {
    token: localStorage.getItem('patty_token'),
    refreshToken: localStorage.getItem('patty_refresh_token'),
    user: localStorage.getItem('patty_user') ? JSON.parse(localStorage.getItem('patty_user')!) : null,
    setAuth: (token, user, refreshToken) => {
      localStorage.setItem('patty_token', token);
      localStorage.setItem('patty_user', JSON.stringify(user));
      if (refreshToken) {
        localStorage.setItem('patty_refresh_token', refreshToken);
      }
      set({ token, user, refreshToken: refreshToken || localStorage.getItem('patty_refresh_token') });
    },
    setToken: (token, refreshToken) => {
      localStorage.setItem('patty_token', token);
      if (refreshToken) {
        localStorage.setItem('patty_refresh_token', refreshToken);
      }
      set({ token, refreshToken: refreshToken || localStorage.getItem('patty_refresh_token') });
    },
    logout: () => {
      const activeRefreshToken = localStorage.getItem('patty_refresh_token');
      if (activeRefreshToken) {
        try {
          fetch(`${API_BASE}/auth/logout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: activeRefreshToken }),
          }).catch(() => {});
        } catch {}
      }
      localStorage.removeItem('patty_token');
      localStorage.removeItem('patty_refresh_token');
      localStorage.removeItem('patty_user');
      set({ token: null, refreshToken: null, user: null });
    },
  };
});
