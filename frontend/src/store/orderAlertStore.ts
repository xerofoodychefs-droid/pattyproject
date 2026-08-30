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
  syncAlerts: (orders: Array<Partial<Order> & { id: string; status: string; payment_status?: string }>) => void;
  clearAll: () => void;
  toggleMute: () => void;
  enableAudioPermission: () => Promise<boolean>;
  setWsConnected: (connected: boolean) => void;
}

const CHANNEL_NAME = 'patty_admin_alerts';
const RECENT_ACCEPTED_WINDOW_MS = 60000; // 60s memory of accepted orders to prevent late resurrected alerts
const WS_ARRIVAL_GRACE_WINDOW_MS = 15000; // 15s grace window to protect fresh WS events against stale REST syncs

// In-memory bounded caches per tab
const recentlyAcceptedMap = new Map<string, number>();
const recentWsArrivalsMap = new Map<string, number>();

const pruneCaches = (now: number) => {
  for (const [id, time] of recentlyAcceptedMap.entries()) {
    if (now - time > RECENT_ACCEPTED_WINDOW_MS) {
      recentlyAcceptedMap.delete(id);
    }
  }
  for (const [id, time] of recentWsArrivalsMap.entries()) {
    if (now - time > WS_ARRIVAL_GRACE_WINDOW_MS) {
      recentWsArrivalsMap.delete(id);
    }
  }
};

export const useOrderAlertStore = create<OrderAlertState>((set, get) => {
  let broadcastChannel: BroadcastChannel | null = null;

  if (typeof window !== 'undefined') {
    // 1. Subscribe to audioAlert manager changes
    audioAlert.subscribe((newAudioState) => {
      set({ audioState: newAudioState });
    });

    // 2. Cross-tab synchronization via BroadcastChannel
    if ('BroadcastChannel' in window) {
      try {
        broadcastChannel = new BroadcastChannel(CHANNEL_NAME);
        broadcastChannel.onmessage = (event: MessageEvent) => {
          const data = event.data;
          if (!data || typeof data !== 'object') return;

          const now = Date.now();
          pruneCaches(now);

          if (data.type === 'ALERT_ADDED' && data.orderId) {
            const acceptedAt = recentlyAcceptedMap.get(data.orderId);
            if (acceptedAt && now - acceptedAt < RECENT_ACCEPTED_WINDOW_MS) {
              return; // Ignore resurrection of already accepted order
            }

            recentWsArrivalsMap.set(data.orderId, now);
            const current = get().alertingOrderIds;
            if (!current.includes(data.orderId)) {
              const next = [...current, data.orderId];
              set({
                alertingOrderIds: next,
                lastAnnouncement: data.orderNumber
                  ? `New incoming order ${data.orderNumber}${data.amount ? ` for £${data.amount.toFixed(2)}` : ''}`
                  : 'New order received',
              });
              audioAlert.startAlertLoop();
            }
          } else if (data.type === 'ALERT_REMOVED' && data.orderId) {
            recentlyAcceptedMap.set(data.orderId, now);
            recentWsArrivalsMap.delete(data.orderId);

            const current = get().alertingOrderIds;
            if (current.includes(data.orderId)) {
              const next = current.filter((id) => id !== data.orderId);
              set({ alertingOrderIds: next });
              if (next.length === 0) {
                audioAlert.stopAlertLoop();
              }
            }
          }
        };
      } catch (e) {
        console.warn('[OrderAlertStore] BroadcastChannel setup skipped:', e);
      }
    }
  }

  const broadcastEvent = (payload: any) => {
    try {
      if (broadcastChannel) {
        broadcastChannel.postMessage(payload);
      }
    } catch {}
  };

  return {
    alertingOrderIds: [],
    audioState: audioAlert.getState(),
    wsConnected: false,
    lastAnnouncement: null,

    addAlert: (orderId: string, orderNumber?: string, amount?: number) => {
      const now = Date.now();
      pruneCaches(now);

      const acceptedAt = recentlyAcceptedMap.get(orderId);
      if (acceptedAt && now - acceptedAt < RECENT_ACCEPTED_WINDOW_MS) {
        return; // Guard: do not re-add an order that was already acknowledged
      }

      recentWsArrivalsMap.set(orderId, now);
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
        broadcastEvent({
          type: 'ALERT_ADDED',
          orderId,
          orderNumber,
          amount,
        });
      }
    },

    removeAlert: (orderId: string) => {
      const now = Date.now();
      pruneCaches(now);

      recentlyAcceptedMap.set(orderId, now);
      recentWsArrivalsMap.delete(orderId);

      const current = get().alertingOrderIds;
      if (current.includes(orderId)) {
        const next = current.filter((id) => id !== orderId);
        set({ alertingOrderIds: next });
        if (next.length === 0) {
          audioAlert.stopAlertLoop();
        }
        broadcastEvent({
          type: 'ALERT_REMOVED',
          orderId,
        });
      }
    },

    syncAlerts: (orders) => {
      const now = Date.now();
      pruneCaches(now);

      // Find orders that are currently unaccepted incoming orders with verified payment
      const incomingIds = orders
        .filter(
          (o) =>
            o.id &&
            (o.status === 'INCOMING' || o.status === 'PENDING_PAYMENT') &&
            (o.payment_status === 'PAID' || !o.payment_status)
        )
        .map((o) => o.id)
        .filter((id) => {
          const acceptedAt = recentlyAcceptedMap.get(id);
          return !(acceptedAt && now - acceptedAt < RECENT_ACCEPTED_WINDOW_MS);
        });

      // Merge any freshly arrived WS events within the grace window
      for (const [freshId, freshTime] of recentWsArrivalsMap.entries()) {
        if (now - freshTime < WS_ARRIVAL_GRACE_WINDOW_MS && !incomingIds.includes(freshId)) {
          const wasAccepted = recentlyAcceptedMap.get(freshId);
          if (!(wasAccepted && now - wasAccepted < RECENT_ACCEPTED_WINDOW_MS)) {
            incomingIds.push(freshId);
          }
        }
      }

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
      recentlyAcceptedMap.clear();
      recentWsArrivalsMap.clear();
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
