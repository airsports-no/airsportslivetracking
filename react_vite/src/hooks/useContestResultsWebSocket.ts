import { useEffect, useRef, useCallback } from 'react';
import { useContestResultsStore } from '../store/contestResultsStore';
import { useFrontendContext } from './useFrontendContext';

export const useContestResultsWebSocket = (contestId: number | null) => {
  const { context, loading: contextLoading, error: contextError } = useFrontendContext();
  const { setResults, setError } = useContestResultsStore();
  const ws = useRef<WebSocket | null>(null);

  const connectWebSocket = useCallback(() => {
    if (!contestId || !context || contextLoading || contextError) {
      return;
    }

    // Ensure previous connection is closed if exists
    if (ws.current) {
      ws.current.close();
    }

    // Construct WebSocket URL using the frontend context
    // Assuming 'contestResultsWebSocketUrl' is a new URL in django_js_reverse that returns the full ws:// or wss:// URL
    // For now, we'll construct it manually based on what we know from display/routing.py
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const websocketUrl = `${protocol}//${host}/ws/contestresults/${contestId}/`;

    ws.current = new WebSocket(websocketUrl);

    ws.current.onopen = () => {
      console.log('WebSocket connected for contest:', contestId);
      // Optionally send a ping or initial message
      ws.current?.send(JSON.stringify({ type: 'ping' }));
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'pong') {
        // Handle pong
      } else if (data.type === 'contestresults') { // Assuming the backend sends data with type 'contestresults'
        setResults(data.content); // Update Zustand store with real-time data
      }
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setError('WebSocket connection error.');
    };

    ws.current.onclose = (event) => {
      console.log('WebSocket disconnected:', event.code, event.reason);
      // Attempt to reconnect after a delay if it's an unexpected closure
      if (!event.wasClean && event.code !== 1000) { // 1000 is normal closure
        setTimeout(connectWebSocket, 3000); // Reconnect after 3 seconds
      }
    };

    return () => {
      if (ws.current) {
        ws.current.close(1000, 'Component unmounted'); // Clean closure
      }
    };
  }, [contestId, context, contextLoading, contextError, setResults, setError]);

  useEffect(() => {
    connectWebSocket();
  }, [connectWebSocket]); // Reconnect when connectWebSocket changes (e.g. context changes)

  return ws.current;
};
