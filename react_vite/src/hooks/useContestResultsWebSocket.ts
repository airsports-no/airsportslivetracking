import { useEffect, useRef, useCallback } from 'react';
import { useContestResultsStore } from '../store/contestResultsStore';

export const useContestResultsWebSocket = (contestId: number | null) => {
  const { applyRealtimeMessage, setError } = useContestResultsStore();
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Always holds the latest connectWebSocket. The reconnect timeout below can fire up to 3s
  // after the connection that scheduled it dropped - if contestId changes in that window,
  // calling connectWebSocket directly (closing over the value from when this specific
  // closure was created) would reconnect using the stale contestId instead of the current one.
  const connectWebSocketRef = useRef<() => void>(() => {});

  const connectWebSocket = useCallback(() => {
    if (!contestId) {
      return;
    }

    // Clear ws.current before closing the previous socket (rather than close-then-clear), so
    // that socket's onclose handler below - which can still fire, possibly reporting an
    // unclean close, even for a deliberate close() - sees `ws.current !== socket` and skips
    // scheduling a reconnect for a connection nothing points to any more.
    const previousSocket = ws.current;
    ws.current = null;
    previousSocket?.close();

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const websocketUrl = `${protocol}//${host}/ws/contestresults/${contestId}/`;

    const socket = new WebSocket(websocketUrl);
    ws.current = socket;

    socket.onopen = () => {
      console.log('WebSocket connected for contest:', contestId);
      socket.send(JSON.stringify({ type: 'ping' }));
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'pong') {
        return;
      }
      applyRealtimeMessage(data);
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
      setError('WebSocket connection error.');
    };

    socket.onclose = (event) => {
      // This handler is bound to `socket`, not "whichever socket is current" - if ws.current
      // has already moved on (a newer connectWebSocket call, or unmount/cleanup below), this
      // is a stale/late event for a socket nothing references any more, so it must not
      // schedule a reconnect (GH review on #762: WebSocket.close() requesting code 1000 does
      // not guarantee the resulting close event reports wasClean/1000, so this stale event
      // could otherwise look exactly like an unexpected disconnect worth reconnecting from).
      if (ws.current !== socket) {
        return;
      }
      console.log('WebSocket disconnected:', event.code, event.reason);
      if (!event.wasClean && event.code !== 1000) {
        reconnectTimeoutRef.current = setTimeout(() => connectWebSocketRef.current(), 3000);
      }
    };
  }, [contestId, applyRealtimeMessage, setError]);

  useEffect(() => {
    // Refs must not be written during render (react-hooks/refs) - keep this updated from an
    // effect instead, which still runs (synchronously, on commit) well before any
    // setTimeout-scheduled reconnect could fire.
    connectWebSocketRef.current = connectWebSocket;
  }, [connectWebSocket]);

  useEffect(() => {
    connectWebSocket();

    // connectWebSocket used to return this same cleanup, but useEffect only uses the return
    // value of *this* callback, not of a function it merely calls - so that cleanup was
    // never actually wired up, and the socket was never explicitly closed on unmount or
    // before the next reconnect. Also clears any pending reconnect timeout, so a stale
    // reconnect can't fire (and open an unreferenced, never-closed socket) after unmount.
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      // Clear ws.current before closing, for the same reason as connectWebSocket's own
      // preemptive close above: this socket's onclose can still fire after this point, and
      // must see `ws.current !== socket` rather than schedule a reconnect for a component
      // that has already unmounted.
      const socket = ws.current;
      ws.current = null;
      socket?.close(1000, 'Component unmounted');
    };
  }, [connectWebSocket]);

  // No caller uses the previous `return ws.current` value (react_vite/src/features/
  // contest-results/ContestResultsTable.tsx calls this hook for its side effects only), and
  // reading a ref's .current during render is itself a react-hooks/refs violation - so this
  // hook returns nothing rather than reintroduce that render-time ref read.
};
