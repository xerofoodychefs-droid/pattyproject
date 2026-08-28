import { useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '../store/authStore';
import { useOrderAlertStore } from '../store/orderAlertStore';
import { getAdminWebSocketUrl } from '../api/client';
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
  const { token, user } = useAuthStore();
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

  const connect = useCallback(() => {
    if (!token || !user) return;
    if (user.role !== 'SUPER_ADMIN' && user.role !== 'BRANCH_ADMIN') return;

    clearTimers();

    try {
      const wsUrl = getAdminWebSocketUrl(token);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        setWsConnected(true);
        const wasReconnecting = wasConnectedRef.current;
        wasConnectedRef.current = true;
        reconnectAttemptsRef.current = 0;

        // Periodic 20s heartbeat ping to keep connection healthy
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

          if (type === 'ORDER_INCOMING') {
            const orderData = data.order;
            if (orderData && orderData.id) {
              // Strictly enforce branch isolation on frontend
              if (
                user.role === 'BRANCH_ADMIN' &&
                user.branch_ids &&
                user.branch_ids.length > 0 &&
                !user.branch_ids.includes(orderData.branch_id)
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
              if (
                orderData.status === 'ACCEPTED' ||
                ['CANCELLED', 'REJECTED', 'DELIVERED', 'COLLECTED'].includes(orderData.status)
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

      ws.onclose = (event) => {
        if (!isMountedRef.current) return;
        setWsConnected(false);
        clearTimers();

        // 1008 = Policy violation / unauthorized
        if (event.code === 1008) {
          console.warn('[AdminWS] Unauthorized admin role or invalid session.');
          return;
        }

        // Exponential backoff reconnect
        if (token && isMountedRef.current) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 15000);
          reconnectAttemptsRef.current += 1;
          reconnectTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current && token) {
              connect();
            }
          }, delay);
        }
      };
    } catch (err) {
      console.warn('[AdminWS] Socket instantiation failed:', err);
    }
  }, [token, user, addAlert, removeAlert, setWsConnected, clearTimers]);

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
      setWsConnected(false);
    };
  }, [connect, clearTimers, setWsConnected]);

  return {
    wsRef,
  };
};
