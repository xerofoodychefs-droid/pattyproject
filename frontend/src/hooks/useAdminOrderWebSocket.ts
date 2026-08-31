import { useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '../store/authStore';
import { useOrderAlertStore } from '../store/orderAlertStore';
import { useShopHoursStore } from '../store/shopHoursStore';
import { getAdminWebSocketUrl, getValidAccessToken } from '../api/client';
import { Order } from '../types';

interface UseAdminOrderWebSocketOptions {
  onIncomingOrder?: (order: Partial<Order> & { id: string; branch_id: string; status: string }) => void;
  onOrderStatusChanged?: (order: Partial<Order> & { id: string; branch_id: string; status: string }) => void;
  onReconnect?: () => void;
}

export const useAdminOrderWebSocket = ({
  onIncomingOrder,
  onOrderStatusChanged,
  onReconnect,
}: UseAdminOrderWebSocketOptions = {}) => {
  const { user } = useAuthStore();
  const { addAlert, removeAlert, setWsConnected } = useOrderAlertStore();

  const onIncomingOrderRef = useRef(onIncomingOrder);
  const onOrderStatusChangedRef = useRef(onOrderStatusChanged);
  const onReconnectRef = useRef(onReconnect);

  useEffect(() => {
    onIncomingOrderRef.current = onIncomingOrder;
    onOrderStatusChangedRef.current = onOrderStatusChanged;
    onReconnectRef.current = onReconnect;
  });

  const wsRef = useRef<WebSocket | null>(null);
  const isConnectingRef = useRef<boolean>(false);
  const reconnectAttemptsRef = useRef<number>(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef<boolean>(true);
  const wasConnectedRef = useRef<boolean>(false);

  const clearTimers = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);

  const connect = useCallback(async () => {
    const currentUser = useAuthStore.getState().user;
    if (!currentUser) return;
    if (currentUser.role !== 'SUPER_ADMIN' && currentUser.role !== 'BRANCH_ADMIN') return;

    if (isConnectingRef.current) return;
    isConnectingRef.current = true;

    clearTimers();

    try {
      const validToken = await getValidAccessToken();
      if (!validToken || !isMountedRef.current) {
        setWsConnected(false);
        return;
      }

      // Close existing socket before opening a replacement
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
        wsRef.current = null;
      }

      const wsUrl = getAdminWebSocketUrl(validToken);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        setWsConnected(true);
        const wasReconnecting = wasConnectedRef.current;
        wasConnectedRef.current = true;
        reconnectAttemptsRef.current = 0;

        // 20-second heartbeat keepalive
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'PING' }));
          }
        }, 20000);

        if (wasReconnecting && onReconnectRef.current) {
          onReconnectRef.current();
        }
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const data = JSON.parse(event.data);
          const type = data.type;

          if (type === 'PING') {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'PONG' }));
            }
            return;
          }

          if (type === 'CONNECTED') {
            setWsConnected(true);
            return;
          }

          if (type === 'shop_status_changed') {
            useShopHoursStore.getState().setShopStatus({
              is_open: typeof data.is_open === 'boolean' ? data.is_open : undefined,
              opening_time: data.opening_time,
              closing_time: data.closing_time,
              reason: data.reason,
            });
            return;
          }

          if (type === 'ORDER_INCOMING') {
            const orderData = data.order;
            if (orderData && orderData.id) {
              // SuperAdmin processes all branches; BranchAdmin checks branch isolation
              if (
                currentUser.role === 'BRANCH_ADMIN' &&
                currentUser.branch_ids &&
                currentUser.branch_ids.length > 0 &&
                !currentUser.branch_ids.includes(orderData.branch_id)
              ) {
                return;
              }

              addAlert(orderData.id, orderData.order_number, orderData.total_amount);
              if (onIncomingOrderRef.current) {
                onIncomingOrderRef.current(orderData);
              }
            }
            return;
          }

          if (type === 'ORDER_STATUS_CHANGED') {
            const orderData = data.order;
            if (orderData && orderData.id) {
              // When order is accepted or reached terminal state, remove active alert
              if (
                orderData.status === 'ACCEPTED' ||
                ['CANCELLED', 'REJECTED', 'DELIVERED', 'COLLECTED', 'READY', 'PREPARING'].includes(
                  orderData.status
                )
              ) {
                removeAlert(orderData.id);
              }
              if (onOrderStatusChangedRef.current) {
                onOrderStatusChangedRef.current(orderData);
              }
            }
            return;
          }
        } catch (e) {
          console.warn('[AdminWS] Failed to parse message:', e);
        }
      };

      ws.onerror = () => {
        // Handled in onclose
      };

      ws.onclose = async (event) => {
        if (!isMountedRef.current) return;
        setWsConnected(false);
        clearTimers();

        // 1008 = Policy violation / unauthorized
        if (event.code === 1008) {
          console.warn('[AdminWS] Unauthorized admin role or invalid session.');
          return;
        }

        // Verify token before scheduling reconnect; if refresh fails, stop reconnecting
        const nextToken = await getValidAccessToken();
        if (!nextToken || !isMountedRef.current) {
          console.warn('[AdminWS] Session expired or invalid. Halting WebSocket reconnection.');
          return;
        }

        // Exponential backoff reconnect with randomized jitter: 1s, 2s, 4s up to 10s max
        const attempts = reconnectAttemptsRef.current;
        const delay = Math.min(1000 * Math.pow(2, attempts), 10000) + Math.random() * 500;
        reconnectAttemptsRef.current += 1;

        reconnectTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current) {
            connect();
          }
        }, delay);
      };
    } catch (e) {
      console.warn('[AdminWS] Connection initialization error:', e);
    } finally {
      isConnectingRef.current = false;
    }
  }, [addAlert, removeAlert, setWsConnected, clearTimers]);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      clearTimers();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, clearTimers]);
};
