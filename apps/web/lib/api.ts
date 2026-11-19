/**
 * API client for StockLens backend
 * All calls go through backend — no AI keys in frontend
 */
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function errorMessage(value: unknown): string | undefined {
  if (typeof value === "string") return value || undefined;
  if (Array.isArray(value)) return value.map(errorMessage).filter(Boolean).join("; ") || undefined;
  if (value && typeof value === "object") {
    const error = value as Record<string, unknown>;
    return errorMessage(error.message) || errorMessage(error.detail) ||
      errorMessage(error.msg) || errorMessage(error.reason) || errorMessage(error.error);
  }
}

export async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const headers = new Headers(options?.headers);
  if (!isFormData && options?.body != null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      msg = errorMessage(err) || msg;
    } catch {}
    throw new ApiError(res.status, msg);
  }

  if (res.status === 204 || res.status === 205) return undefined as T;
  return res.json();
}

// ── Market Data ──────────────────────────────────────────────
export const marketApi = {
  getStatus: () => fetchApi("/api/v1/market/status"),
  getQuote: (symbol: string) => fetchApi(`/api/v1/market/quote/${encodeURIComponent(symbol)}`),
  getCandles: (symbol: string, interval = "1D", limit = 200) =>
    fetchApi(`/api/v1/market/candles/${encodeURIComponent(symbol)}?interval=${encodeURIComponent(interval)}&limit=${limit}`),
  getIndices: () => fetchApi("/api/v1/market/indices"),
};

// ── Stocks ───────────────────────────────────────────────────
export const stocksApi = {
  list: (params?: Record<string, string | number>) => {
    const qs = params ? "?" + new URLSearchParams(params as any).toString() : "";
    return fetchApi(`/api/v1/stocks${qs}`);
  },
  getDetail: (symbol: string) => fetchApi(`/api/v1/stocks/${encodeURIComponent(symbol)}`),
  getFinancials: (symbol: string) => fetchApi(`/api/v1/stocks/${encodeURIComponent(symbol)}/financials`),
  getRatios: (symbol: string) => fetchApi(`/api/v1/stocks/${encodeURIComponent(symbol)}/ratios`),
  getValuation: (symbol: string) => fetchApi(`/api/v1/stocks/${encodeURIComponent(symbol)}/valuation`),
  getReverseDcf: (symbol: string) => fetchApi(`/api/v1/stocks/${encodeURIComponent(symbol)}/reverse-dcf`),
  getPeers: (symbol: string) => fetchApi(`/api/v1/stocks/${encodeURIComponent(symbol)}/peers`),
  getShareholding: (symbol: string) => fetchApi(`/api/v1/stocks/${encodeURIComponent(symbol)}/shareholding`),
  getSignal: (symbol: string) => fetchApi(`/api/v1/stocks/${encodeURIComponent(symbol)}/signals`),
  getRiskFlags: (symbol: string) => fetchApi(`/api/v1/stocks/${encodeURIComponent(symbol)}/risk-flags`),
};

// ── ML ───────────────────────────────────────────────────────
export const mlApi = {
  getClusters: () => fetchApi("/api/v1/ml/clusters"),
  getCluster: (label: string) => fetchApi(`/api/v1/ml/clusters/${encodeURIComponent(label)}`),
  getScores: (symbol: string) => fetchApi(`/api/v1/ml/scores/${encodeURIComponent(symbol)}`),
  runInference: () => fetchApi("/api/v1/ml/run-inference", { method: "POST" }),
};

// ── AI ───────────────────────────────────────────────────────
export const aiApi = {
  getSummary: (symbol: string) => fetchApi(`/api/v1/ai/summary/${encodeURIComponent(symbol)}`),
  generateSummary: (symbol: string) =>
    fetchApi(`/api/v1/ai/generate/${encodeURIComponent(symbol)}`, { method: "POST" }),
  getSectorSummary: (sector: string) => fetchApi(`/api/v1/ai/sector-summary/${encodeURIComponent(sector)}`),
  explainDcf: (symbol: string) =>
    fetchApi(`/api/v1/ai/dcf-explain/${encodeURIComponent(symbol)}`, { method: "POST" }),
};

// ── Screener ─────────────────────────────────────────────────
export const screenerApi = {
  getPrebuilt: () => fetchApi("/api/v1/screener/prebuilt"),
  runPrebuilt: (id: string) => fetchApi(`/api/v1/screener/prebuilt/${encodeURIComponent(id)}`),
  runCustom: (conditions: object) =>
    fetchApi("/api/v1/screener/custom", {
      method: "POST",
      body: JSON.stringify(conditions),
    }),
};

// ── Watchlist ────────────────────────────────────────────────
export const watchlistApi = {
  get: () => fetchApi("/api/v1/watchlist"),
  add: (symbol: string, notes?: string) =>
    fetchApi("/api/v1/watchlist/items", {
      method: "POST",
      body: JSON.stringify({ nse_symbol: symbol, notes }),
    }),
  remove: (id: string) =>
    fetchApi(`/api/v1/watchlist/items/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

// ── Portfolio ────────────────────────────────────────────────
export const portfolioApi = {
  get: () => fetchApi("/api/v1/portfolio"),
  addHolding: (holding: object) =>
    fetchApi("/api/v1/portfolio/holdings", {
      method: "POST",
      body: JSON.stringify(holding),
    }),
  updateHolding: (id: string, data: object) =>
    fetchApi(`/api/v1/portfolio/holdings/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteHolding: (id: string) =>
    fetchApi(`/api/v1/portfolio/holdings/${encodeURIComponent(id)}`, { method: "DELETE" }),
  getAnalytics: () => fetchApi("/api/v1/portfolio/analytics"),
};

// ── Sectors ──────────────────────────────────────────────────
export const sectorsApi = {
  list: () => fetchApi("/api/v1/sectors"),
  getDetail: (id: string) => fetchApi(`/api/v1/sectors/${encodeURIComponent(id)}`),
  getStocks: (id: string) => fetchApi(`/api/v1/sectors/${encodeURIComponent(id)}/stocks`),
};

export const foApi = {
  getEligible: () => fetchApi("/api/v1/fo/eligible"),
  getOi: (symbol: string) => fetchApi(`/api/v1/fo/oi/${encodeURIComponent(symbol)}`),
  getPcr: (symbol: string) => fetchApi(`/api/v1/fo/pcr/${encodeURIComponent(symbol)}`),
  getChain: (symbol: string) => fetchApi(`/api/v1/fo/chain/${encodeURIComponent(symbol)}`),
};

export const alertsApi = {
  get: () => fetchApi("/api/v1/alerts"),
  create: (alert: object) => fetchApi("/api/v1/alerts", {
    method: "POST",
    body: JSON.stringify(alert),
  }),
  remove: (id: string) => fetchApi(`/api/v1/alerts/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

// ── Backtest ────────────────────────────────────────────────
export const backtestApi = {
  getStrategies: () => fetchApi("/api/v1/backtest/strategies"),
  getHistory: () => fetchApi("/api/v1/backtest/history"),
  run: (payload: object) => fetchApi("/api/v1/backtest/run", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  getResults: (id: string) => fetchApi(`/api/v1/backtest/${encodeURIComponent(id)}/results`),
};

// ── Admin ────────────────────────────────────────────────────
export const adminApi = {
  getJobs: () => fetchApi("/api/v1/admin/jobs"),
  triggerJob: (job: string) =>
    fetchApi(`/api/v1/admin/jobs/trigger/${encodeURIComponent(job)}`, { method: "POST" }),
  getAuditLogs: () => fetchApi("/api/v1/admin/audit-logs"),
  // BUG20 FIX: FormData body — fetchApi auto-detects and skips Content-Type header
  importStocks: (formData: FormData) =>
    fetchApi("/api/v1/admin/stocks/import", {
      method: "POST",
      body: formData,
    }),
  uploadFinancials: (formData: FormData) =>
    fetchApi("/api/v1/admin/financials/upload", {
      method: "POST",
      body: formData,
    }),
};

export { ApiError };
