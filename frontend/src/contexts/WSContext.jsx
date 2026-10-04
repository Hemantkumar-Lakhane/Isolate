// frontend/src/contexts/WSContext.jsx
import {
  createContext, useContext, useEffect, useRef,
  useState, useCallback
} from 'react';
import { useAuth } from './AuthContext';
import { WS_BASE } from '../api/client';

const WSContext = createContext(null);

export function WSProvider({ children }) {
  const { token } = useAuth();
  const [status, setStatus] = useState('disconnected'); // connected | disconnected | error
  const [events, setEvents]   = useState([]);           // rolling buffer of last 500 events
  const wsRef        = useRef(null);
  const listenersRef = useRef(new Map());               // eventType → Set<handler>
  const reconnTimer  = useRef(null);
  const pingTimer    = useRef(null);

  const addEvent = useCallback((event) => {
    setEvents(prev => {
      const next = [...prev, event];
      return next.length > 500 ? next.slice(-500) : next;
    });
  }, []);

  const dispatch = useCallback((event) => {
    // Notify subscribers for this specific event type
    listenersRef.current.get(event.type)?.forEach(fn => { try { fn(event); } catch (_) {} });
    // Notify wildcard '*' subscribers
    listenersRef.current.get('*')?.forEach(fn => { try { fn(event); } catch (_) {} });
  }, []);

  const connect = useCallback(() => {
    if (!token) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    clearTimeout(reconnTimer.current);
    clearInterval(pingTimer.current);

    const sid = Math.random().toString(36).slice(2, 10);
    const ws  = new WebSocket(`${WS_BASE}/${sid}?token=${encodeURIComponent(token)}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      // Heartbeat every 25 s to keep proxy connections alive
      pingTimer.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, 25_000);
    };

    ws.onclose = () => {
      setStatus('disconnected');
      clearInterval(pingTimer.current);
      // Auto-reconnect with back-off
      reconnTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      setStatus('error');
    };

    ws.onmessage = (e) => {
      if (e.data === 'pong') return;
      try {
        const raw = JSON.parse(e.data);
        const event = { ...raw, _receivedAt: new Date().toISOString() };
        addEvent(event);
        dispatch(event);
      } catch (_) { /* ignore malformed frames */ }
    };
  }, [token, addEvent, dispatch]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnTimer.current);
      clearInterval(pingTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  /**
   * Subscribe to WebSocket events.
   * @param {string} eventType - specific event type OR '*' for all
   * @param {function} handler - called with the event object
   * @returns {function} unsubscribe function
   */
  const subscribe = useCallback((eventType, handler) => {
    if (!listenersRef.current.has(eventType)) {
      listenersRef.current.set(eventType, new Set());
    }
    listenersRef.current.get(eventType).add(handler);
    return () => listenersRef.current.get(eventType)?.delete(handler);
  }, []);

  /**
   * Send a raw message to the WebSocket server.
   */
  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }, []);

  return (
    <WSContext.Provider value={{ status, events, subscribe, send }}>
      {children}
    </WSContext.Provider>
  );
}

export function useWebSocket() {
  const ctx = useContext(WSContext);
  if (!ctx) throw new Error('useWebSocket must be used inside <WSProvider>');
  return ctx;
}

/**
 * Hook: subscribe to specific workflow events by run_id.
 * Returns an array of events for that run, newest last.
 */
export function useWorkflowEvents(runId) {
  const { subscribe, events } = useWebSocket();
  const [runEvents, setRunEvents] = useState([]);

  useEffect(() => {
    if (!runId) return;
    setRunEvents(events.filter(e => e.data?.run_id === runId));

    const unsub = subscribe('*', (event) => {
      if (event.data?.run_id === runId) {
        setRunEvents(prev => [...prev, event]);
      }
    });
    // Always return the unsubscribe to prevent memory leaks on rapid navigation
    return () => { if (typeof unsub === 'function') unsub(); };
  }, [runId, subscribe]); // eslint-disable-line react-hooks/exhaustive-deps

  return runEvents;
}