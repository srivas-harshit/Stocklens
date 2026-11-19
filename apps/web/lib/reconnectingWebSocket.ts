interface WebSocketCallbacks {
  onMessage: (event: MessageEvent) => void;
  onConnectionChange: (connected: boolean) => void;
}

/** Each effect owns its socket and retry timer, including during route changes. */
export function createReconnectingWebSocket(url: string, callbacks: WebSocketCallbacks): () => void {
  let socket: WebSocket | null = null;
  let stopped = false;
  let reconnectDelay = 1_000;
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

  const retry = () => {
    if (stopped || reconnectTimer !== undefined) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = undefined;
      reconnectDelay = Math.min(reconnectDelay * 2, 30_000);
      connect();
    }, reconnectDelay);
  };

  const connect = () => {
    if (stopped) return;
    try {
      const ws = new WebSocket(url);
      socket = ws;
      const isCurrent = () => !stopped && socket === ws;

      ws.onopen = () => {
        if (!isCurrent()) return;
        reconnectDelay = 1_000;
        callbacks.onConnectionChange(true);
      };
      ws.onmessage = (event) => {
        if (isCurrent()) callbacks.onMessage(event);
      };
      ws.onclose = () => {
        if (!isCurrent()) return;
        socket = null;
        callbacks.onConnectionChange(false);
        retry();
      };
      ws.onerror = () => {
        if (isCurrent()) ws.close();
      };
    } catch {
      callbacks.onConnectionChange(false);
      retry();
    }
  };

  connect();
  return () => {
    stopped = true;
    clearTimeout(reconnectTimer);
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      socket.onerror = null;
      socket.close();
      socket = null;
    }
    callbacks.onConnectionChange(false);
  };
}
