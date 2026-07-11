import { useEffect, useRef, useCallback } from 'react';
import { useContestResultsStore } from '../store/contestResultsStore';

export const useContestResultsWebSocket = (contestId: number | null) => {
  const { applyRealtimeMessage, setError } = useContestResultsStore();
  const ws = useRef<WebSocket | null>(null);

  const connectWebSocket = useCallback(() => {
    if (!contestId) {
      return;
    }

    if (ws.current) {
      ws.current.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const websocketUrl = `${protocol}//${host}/ws/contestresults/${contestId}/`;

    ws.current = new WebSocket(websocketUrl);

    ws.current.onopen = () => {
      console.log('WebSocket connected for contest:', contestId);
      ws.current?.send(JSON.stringify({ type: 'ping' }));
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'pong') {
        return;
      }
      applyRealtimeMessage(data);
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setError('WebSocket connection error.');
    };

    ws.current.onclose = (event) => {
      console.log('WebSocket disconnected:', event.code, event.reason);
      if (!event.wasClean && event.code !== 1000) {
        setTimeout(connectWebSocket, 3000);
      }
    };

    return () => {
      if (ws.current) {
        ws.current.close(1000, 'Component unmounted');
      }
    };
  }, [contestId, applyRealtimeMessage, setError]);

  useEffect(() => {
    connectWebSocket();
  }, [connectWebSocket]);

  return ws.current;
};
