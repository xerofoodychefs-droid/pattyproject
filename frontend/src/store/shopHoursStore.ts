import { create } from 'zustand';
import { api } from '../api/client';

export interface ShopStatus {
  is_open: boolean;
  opening_time: string;
  closing_time: string;
  reason: string;
  timezone?: string;
  current_uk_time?: string;
}

interface ShopHoursState {
  isOpen: boolean;
  openingTime: string;
  closingTime: string;
  reason: string;
  isLoading: boolean;
  lastUpdated: number | null;
  fetchShopStatus: () => Promise<void>;
  setShopStatus: (status: Partial<ShopStatus>) => void;
}

export const useShopHoursStore = create<ShopHoursState>((set) => ({
  isOpen: true,
  openingTime: '11:00',
  closingTime: '23:00',
  reason: 'OPEN',
  isLoading: true,
  lastUpdated: null,

  fetchShopStatus: async () => {
    try {
      const data = await api.get<ShopStatus>(`/shop/status?_t=${Date.now()}`);
      if (data && typeof data.is_open === 'boolean') {
        set({
          isOpen: data.is_open,
          openingTime: data.opening_time || '11:00',
          closingTime: data.closing_time || '23:00',
          reason: data.reason || (data.is_open ? 'OPEN' : 'OUTSIDE_HOURS'),
          isLoading: false,
          lastUpdated: Date.now(),
        });
      }
    } catch (err) {
      console.warn('[ShopHoursStore] Failed to fetch shop status:', err);
      set({ isLoading: false });
    }
  },

  setShopStatus: (status) => {
    set((state) => ({
      isOpen: typeof status.is_open === 'boolean' ? status.is_open : state.isOpen,
      openingTime: status.opening_time || state.openingTime,
      closingTime: status.closing_time || state.closingTime,
      reason: status.reason || (status.is_open ? 'OPEN' : 'OUTSIDE_HOURS'),
      isLoading: false,
      lastUpdated: Date.now(),
    }));
  },
}));

export function formatTime12h(time24: string): string {
  if (!time24 || !time24.includes(':')) return time24 || '';
  const [hStr, mStr] = time24.split(':');
  const h = parseInt(hStr, 10);
  const m = parseInt(mStr, 10);
  if (isNaN(h) || isNaN(m)) return time24;
  const period = h >= 12 ? 'PM' : 'AM';
  const displayH = h % 12 === 0 ? 12 : h % 12;
  const displayM = m < 10 ? `0${m}` : `${m}`;
  return `${displayH}:${displayM} ${period}`;
}
