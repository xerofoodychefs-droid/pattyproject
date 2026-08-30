import { useEffect, useRef, useCallback } from 'react';
import { getProductWebSocketUrl } from '../api/client';

interface UseProductRealtimeOptions {
  onProductAvailabilityChange?: (productId: string, isOutOfStock: boolean) => void;
  onReconnect?: () => void;
  enabled?: boolean;
}

export const useProductRealtime = ({
  onProductAvailabilityChange,
  onReconnect,
  enabled = true,
}: UseProductRealtimeOptions = {}) => {
  const onProductAvailabilityChangeRef = useRef(onProductAvailabilityChange);
  const onReconnectRef = useRef(onReconnect);

  useEffect(() => {
    onProductAvailabilityChangeRef.current = onProductAvailabilityChange;
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
    if (!enabled) return;

    clearTimers();

    try {
      const wsUrl = getProductWebSocketUrl();
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        const wasReconnecting = wasConnectedRef.current;
        wasConnectedRef.current = true;
        reconnectAttemptsRef.current = 0;

        // Periodic 20s heartbeat keepalive
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

          if (type === 'product_availability_changed') {
            const productId = data.product_id;
            const isOutOfStock = Boolean(data.is_out_of_stock);
            if (productId && onProductAvailabilityChangeRef.current) {
              onProductAvailabilityChangeRef.current(productId, isOutOfStock);
            }
            return;
          }
        } catch {
          // Ignore parse errors on malformed messages
        }
      };

      ws.onclose = () => {
        if (!isMountedRef.current) return;
        clearTimers();

        // Exponential backoff reconnect: 1s, 2s, 4s, 8s, up to 15s max
        const attempts = reconnectAttemptsRef.current;
        const delay = Math.min(1000 * Math.pow(2, attempts), 15000);
        reconnectAttemptsRef.current += 1;

        reconnectTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current && enabled) {
            connect();
          }
        }, delay);
      };

      ws.onerror = () => {
        try {
          ws.close();
        } catch {}
      };
    } catch {
      // Reconnect if instantiation fails
      const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 15000);
      reconnectAttemptsRef.current += 1;
      reconnectTimeoutRef.current = setTimeout(() => {
        if (isMountedRef.current && enabled) {
          connect();
        }
      }, delay);
    }
  }, [enabled, clearTimers]);

  useEffect(() => {
    isMountedRef.current = true;
    if (enabled) {
      connect();
    }

    return () => {
      isMountedRef.current = false;
      clearTimers();
      if (wsRef.current) {
        try {
          wsRef.current.onclose = null;
          wsRef.current.onerror = null;
          wsRef.current.close();
        } catch {}
        wsRef.current = null;
      }
    };
  }, [enabled, connect, clearTimers]);
};
