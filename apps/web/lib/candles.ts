export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export type CandleInterval = "1D" | "1W" | "1M";

/** Aggregate daily bars using UTC calendar boundaries, independent of browser timezone. */
export function aggregateCandles(candles: Candle[], interval: CandleInterval): Candle[] {
  const sorted = [...candles].sort((a, b) => a.time - b.time);
  if (interval === "1D") return sorted;

  const groups = new Map<string, Candle>();
  for (const candle of sorted) {
    const date = new Date(candle.time * 1_000);
    if (interval === "1W") {
      // Trading weeks start on Monday.
      date.setUTCDate(date.getUTCDate() - (date.getUTCDay() + 6) % 7);
    }
    const key = date.toISOString().slice(0, interval === "1M" ? 7 : 10);
    const group = groups.get(key);
    if (!group) {
      groups.set(key, { ...candle, volume: candle.volume ?? 0 });
    } else {
      group.high = Math.max(group.high, candle.high);
      group.low = Math.min(group.low, candle.low);
      group.close = candle.close;
      group.volume = (group.volume ?? 0) + (candle.volume ?? 0);
    }
  }
  return [...groups.values()];
}
