"use client";
import { useEffect } from "react";
import { useMarketStore } from "@/store/market";
import { createReconnectingWebSocket } from "@/lib/reconnectingWebSocket";

const WS_BASE = (
  process.env.NEXT_PUBLIC_WS_URL || process.env.NEXT_PUBLIC_API_URL || "ws://localhost:8000"
).replace(/^http/, "ws").replace(/\/+$/, "");

export function useDashboardWebSocket() {
  const updateQuotes = useMarketStore((state) => state.updateQuotes);
  const setWsConnected = useMarketStore((state) => state.setWsConnected);

  useEffect(() => createReconnectingWebSocket(WS_BASE + "/api/v1/ws/dashboard", {
    onConnectionChange: setWsConnected,
    onMessage: (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "batch" && Array.isArray(msg.updates)) updateQuotes(msg.updates);
      } catch {
        // Ignore malformed or non-JSON messages.
      }
    },
  }), [updateQuotes, setWsConnected]);
}

export function useSymbolWebSocket(symbol: string) {
  const updateQuote = useMarketStore((state) => state.updateQuote);
  const setWsConnected = useMarketStore((state) => state.setWsConnected);

  useEffect(() => {
    const normalizedSymbol = symbol.trim().toUpperCase();
    if (!normalizedSymbol) return;

    return createReconnectingWebSocket(
      WS_BASE + "/api/v1/ws/ticks/" + encodeURIComponent(normalizedSymbol),
      {
        onConnectionChange: setWsConnected,
        onMessage: (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.data && msg.symbol === normalizedSymbol) {
              updateQuote({ ...msg.data, nse_symbol: normalizedSymbol });
            }
          } catch {
            // Ignore malformed or non-JSON messages.
          }
        },
      },
    );
  }, [symbol, updateQuote, setWsConnected]);
}
