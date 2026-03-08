// frontend/src/hooks/useAlertSocket.ts
import { useState, useEffect, useRef, useCallback } from "react";
import type { TradeAlert } from "../types";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8005";
const MAX_ALERTS = 50;

export function useAlertSocket(countries: string[] = []) {
  const [alerts, setAlerts] = useState<TradeAlert[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    const query = countries.length ? `?countries=${countries.join(",")}` : "";
    const ws = new WebSocket(`${WS_URL}/ws/alerts${query}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log("[GeoTrade] Alert WebSocket connected");
    };

    ws.onmessage = (event) => {
      try {
        const alert: TradeAlert = JSON.parse(event.data);
        setAlerts(prev => [alert, ...prev].slice(0, MAX_ALERTS));
      } catch (e) {
        console.warn("Failed to parse alert:", e);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      // Reconnect after 3s
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [countries.join(",")]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const dismissAlert = useCallback((alertId: string) => {
    setAlerts(prev => prev.filter(a => a.alert_id !== alertId));
  }, []);

  return { alerts, connected, dismissAlert };
}
