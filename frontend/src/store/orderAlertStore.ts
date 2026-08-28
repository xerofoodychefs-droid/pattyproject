import { create } from 'zustand';
import { audioAlert, AudioAlertState } from '../utils/audioAlert';
import { Order } from '../types';

interface OrderAlertState {
  alertingOrderIds: string[];
  audioState: AudioAlertState;
  wsConnected: boolean;
  lastAnnouncement: string | null;

  // Actions
  addAlert: (orderId: string, orderNumber?: string, amount?: number) => void;
  removeAlert: (orderId: string) => void;
  syncAlerts: (orders: Order[]) => void;
  clearAll: () => void;
  toggleMute: () => void;
  enableAudioPermission: () => Promise<boolean>;
  setWsConnected: (connected: boolean) => void;
}

export const useOrderAlertStore = create<OrderAlertState>((set, get) => {
  // Subscribe to audioAlert manager changes
  if (typeof window !== 'undefined') {
    audioAlert.subscribe((newAudioState) => {
      set({ audioState: newAudioState });
    });
  }

  return {
    alertingOrderIds: [],
    audioState: audioAlert.getState(),
    wsConnected: false,
    lastAnnouncement: null,

    addAlert: (orderId: string, orderNumber?: string, amount?: number) => {
      const current = get().alertingOrderIds;
      if (!current.includes(orderId)) {
        const next = [...current, orderId];
        set({
          alertingOrderIds: next,
          lastAnnouncement: orderNumber
            ? `New incoming order ${orderNumber}${amount ? ` for £${amount.toFixed(2)}` : ''}`
            : 'New order received',
        });
        audioAlert.startAlertLoop();
      }
    },

    removeAlert: (orderId: string) => {
      const current = get().alertingOrderIds;
      if (current.includes(orderId)) {
        const next = current.filter((id) => id !== orderId);
        set({ alertingOrderIds: next });
        if (next.length === 0) {
          audioAlert.stopAlertLoop();
        }
      }
    },

    syncAlerts: (orders: Order[]) => {
      // Find orders that are currently unaccepted incoming orders
      const incomingIds = orders
        .filter((o) => (o.status === 'INCOMING' || o.status === 'PENDING_PAYMENT') && (o.payment_status === 'PAID' || !o.payment_status))
        .map((o) => o.id);

      const current = get().alertingOrderIds;
      // If set of IDs is identical, avoid unnecessary state churn & re-renders
      if (
        current.length === incomingIds.length &&
        current.every((id) => incomingIds.includes(id))
      ) {
        return;
      }

      set({ alertingOrderIds: incomingIds });
      if (incomingIds.length > 0) {
        audioAlert.startAlertLoop();
      } else {
        audioAlert.stopAlertLoop();
      }
    },

    clearAll: () => {
      set({ alertingOrderIds: [] });
      audioAlert.stopAlertLoop();
    },

    toggleMute: () => {
      audioAlert.toggleMute();
    },

    enableAudioPermission: async () => {
      const granted = await audioAlert.initAudio();
      if (granted && get().alertingOrderIds.length > 0) {
        audioAlert.startAlertLoop();
      }
      return granted;
    },

    setWsConnected: (connected: boolean) => {
      set({ wsConnected: connected });
    },
  };
});
