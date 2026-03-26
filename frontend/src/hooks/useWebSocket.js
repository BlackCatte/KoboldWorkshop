import { useEffect, useRef, useState, useCallback } from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// Properly construct WebSocket URL
const getWebSocketURL = () => {
  // If BACKEND_URL starts with https, use wss, otherwise ws
  if (BACKEND_URL.startsWith('https://')) {
    return BACKEND_URL.replace('https://', 'wss://') + '/ws';
  } else if (BACKEND_URL.startsWith('http://')) {
    return BACKEND_URL.replace('http://', 'ws://') + '/ws';
  } else {
    // Fallback for relative URLs
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws`;
  }
};

const WS_URL = getWebSocketURL();

export const useWebSocket = (onMessage) => {
  const ws = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const reconnectTimeout = useRef(null);

  const connect = useCallback(() => {
    try {
      console.log('Connecting to WebSocket:', WS_URL);
      ws.current = new WebSocket(WS_URL);

      ws.current.onopen = () => {
        console.log('✅ WebSocket connected');
        setIsConnected(true);
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
          if (onMessage) {
            onMessage(data);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.current.onclose = () => {
        console.log('❌ WebSocket disconnected');
        setIsConnected(false);
        
        // Attempt to reconnect after 3 seconds
        reconnectTimeout.current = setTimeout(() => {
          console.log('🔄 Attempting to reconnect...');
          connect();
        }, 3000);
      };
    } catch (error) {
      console.error('Error creating WebSocket:', error);
    }
  }, [onMessage]);

  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
    }
    if (ws.current) {
      ws.current.close();
    }
  }, []);

  const sendMessage = useCallback((message) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { isConnected, lastMessage, sendMessage };
};

export default useWebSocket;
