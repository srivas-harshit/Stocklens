"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft, Zap, Play, Info, TrendingUp, TrendingDown,
  ShieldAlert, Award, Activity, RefreshCw, CheckCircle2
} from "lucide-react";
import { backtestApi } from "@/lib/api";

const PRESET_STRATEGIES = [
  {
    id: "graham_net_net",
    name: "Graham Net-Net Screen",
    description: "Stocks trading with positive margin of safety and strong valuation upside",
    conditions: { min_upside: 20, min_mos: 0.1 },
  },
  {
    id: "quality_growth",
    name: "Quality Growth Compounders",
    description: "High fundamental score (>60), low debt/equity (<0.8), solid growth",
    conditions: { min_fundamental_score: 60, max_debt_equity: 0.8 },
  },
  {
    id: "dividend_compounders",
    name: "Dividend Compounders",
    description: "Yield > 2%, low risk score (<50), positive earnings consistency",
    conditions: { min_div_yield: 0.02, max_risk_score: 50 },
  },
  {
    id: "green_signal",
    name: "Green Signals Only",
    description: "Stocks categorized as 'Potentially Undervalued' by StockLens gating engine",
    conditions: { signal_color: "GREEN" },
  },
];

export default function BacktestPage() {
  const router = useRouter();
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [results, setResults] = useState<any>(null);

  const handleRun = async (strategy: any) => {
    setActivePreset(strategy.id);
    setRunning(true);
    setErrorMsg(null);

    try {
      const data = await backtestApi.run({
        strategy: strategy.id,
        name: strategy.name,
        parameters: strategy.conditions,
      }) as any;
      setResults(data);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to execute backtest. Please retry.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      {/* Topbar */}
      <div className="topbar">
        <button className="btn btn-ghost" onClick={() => router.push("/")}>
          <ArrowLeft className="w-4 h-4" /> Dashboard
        </button>
        <span style={{ color: "var(--text-muted)" }}>›</span>
        <Zap className="w-5 h-5 text-yellow-400" />
        <span className="font-bold" style={{ color: "var(--text-primary)" }}>Strategy Backtest</span>
      </div>

      <div className="main-content max-w-5xl mx-auto py-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
              Strategy Backtesting & Historical Analysis
            </h1>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Simulate investment strategies against historical database data with realistic execution assumptions.
            </p>
          </div>
        </div>

        {/* Requirements notice */}
        <div className="card p-4 mb-6 flex items-start gap-3" style={{ borderColor: "rgba(33,136,255,0.3)" }}>
          <Info className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
          <div className="text-xs" style={{ color: "var(--text-secondary)" }}>
            <strong style={{ color: "var(--text-primary)" }}>Simulation Methodology:</strong>{" "}
            Evaluates strategy selection criteria, executes simulated positions across historical daily candles,
            and benchmarks total performance against NIFTY50. Past performance is an analytical indicator and does not guarantee future results.
          </div>
        </div>

        {/* Preset strategies grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {PRESET_STRATEGIES.map((s) => (
            <div
              key={s.id}
              className={`card p-5 flex flex-col justify-between transition-all ${
                activePreset === s.id ? "border-blue-500 shadow-md" : ""
              }`}
            >
              <div>
                <div className="font-semibold text-sm mb-1.5" style={{ color: "var(--text-primary)" }}>
                  {s.name}
                </div>
                <div className="text-xs mb-4 line-clamp-2" style={{ color: "var(--text-muted)" }}>
                  {s.description}
                </div>
              </div>
              <button
                className="btn btn-primary w-full text-xs flex items-center justify-center gap-1.5"
                onClick={() => handleRun(s)}
                disabled={running}
              >
                {running && activePreset === s.id ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Running Simulation...
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5" /> Run Strategy
                  </>
                )}
              </button>
            </div>
          ))}
        </div>

        {/* Error message */}
        {errorMsg && (
          <div className="card p-4 mb-6 border-red-500 text-red-400 text-sm">
            {errorMsg}
          </div>
        )}

        {/* Results Section */}
        {results && (
          <div className="space-y-6 animate-slide-up">
            {/* Header summary */}
            <div className="card p-6">
              <div className="flex flex-wrap items-center justify-between gap-4 mb-4 pb-4 border-b border-gray-800">
                <div>
                  <div className="text-xs uppercase tracking-wider font-semibold text-blue-400">
                    Backtest Completed
                  </div>
                  <h2 className="text-lg font-bold mt-0.5" style={{ color: "var(--text-primary)" }}>
                    {results.name}
                  </h2>
                  <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                    Period: {results.from_date} to {results.to_date} · Benchmark: {results.benchmark}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="badge px-3 py-1 bg-green-500/10 text-green-400 text-xs font-semibold rounded-full border border-green-500/20">
                    Verified Execution
                  </span>
                </div>
              </div>

              {/* Key Metrics Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="metric-card bg-gray-900/50 p-4 rounded-lg border border-gray-800">
                  <div className="metric-label text-xs" style={{ color: "var(--text-muted)" }}>Total Strategy Return</div>
                  <div
                    className={`text-xl font-bold font-mono mt-1 ${
                      results.summary.total_return_pct >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {results.summary.total_return_pct >= 0 ? "+" : ""}
                    {results.summary.total_return_pct}%
                  </div>
                  <div className="text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
                    Benchmark: {results.summary.benchmark_return_pct}%
                  </div>
                </div>

                <div className="metric-card bg-gray-900/50 p-4 rounded-lg border border-gray-800">
                  <div className="metric-label text-xs" style={{ color: "var(--text-muted)" }}>Annualized (CAGR)</div>
                  <div className="text-xl font-bold font-mono text-blue-400 mt-1">
                    {results.summary.cagr_pct}%
                  </div>
                  <div className="text-[11px] mt-1 text-green-400">
                    Alpha: {results.summary.alpha_pct > 0 ? "+" : ""}{results.summary.alpha_pct}%
                  </div>
                </div>

                <div className="metric-card bg-gray-900/50 p-4 rounded-lg border border-gray-800">
                  <div className="metric-label text-xs" style={{ color: "var(--text-muted)" }}>Win Rate / Trades</div>
                  <div className="text-xl font-bold font-mono text-yellow-400 mt-1">
                    {results.summary.win_rate_pct}%
                  </div>
                  <div className="text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
                    {results.summary.profitable_trades} of {results.summary.total_trades} profitable
                  </div>
                </div>

                <div className="metric-card bg-gray-900/50 p-4 rounded-lg border border-gray-800">
                  <div className="metric-label text-xs" style={{ color: "var(--text-muted)" }}>Sharpe / Max DD</div>
                  <div className="text-xl font-bold font-mono text-purple-400 mt-1">
                    {results.summary.sharpe_ratio}
                  </div>
                  <div className="text-[11px] mt-1 text-red-400">
                    Max Drawdown: -{results.summary.max_drawdown_pct}%
                  </div>
                </div>
              </div>

              {/* Equity Curve Visualizer */}
              {results.equity_curve && results.equity_curve.length > 0 && (
                <div className="mt-6 pt-4 border-t border-gray-800">
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                      Equity Curve Progression (Base ₹100,000)
                    </span>
                    <div className="flex gap-4 text-xs">
                      <span className="flex items-center gap-1.5 text-blue-400">
                        <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block" /> Strategy
                      </span>
                      <span className="flex items-center gap-1.5 text-gray-400">
                        <span className="w-2.5 h-2.5 rounded-full bg-gray-600 inline-block" /> Benchmark ({results.benchmark})
                      </span>
                    </div>
                  </div>

                  <div className="h-44 w-full flex items-end gap-1.5 pt-4 pb-2 px-2 bg-gray-950/60 rounded border border-gray-800/80">
                    {results.equity_curve.map((pt: any, i: number) => {
                      const maxVal = Math.max(
                        ...results.equity_curve.map((p: any) => Math.max(p.portfolio, p.benchmark))
                      );
                      const minVal = Math.min(
                        ...results.equity_curve.map((p: any) => Math.min(p.portfolio, p.benchmark))
                      );
                      const range = maxVal - minVal || 1;
                      const portHeight = Math.max(15, Math.min(100, ((pt.portfolio - minVal) / range) * 100));
                      const benchHeight = Math.max(15, Math.min(100, ((pt.benchmark - minVal) / range) * 100));

                      return (
                        <div key={i} className="flex-1 flex items-end gap-0.5 h-full group relative" title={`${pt.date}\nStrategy: ₹${pt.portfolio.toLocaleString()}\nBenchmark: ₹${pt.benchmark.toLocaleString()}`}>
                          <div
                            className="flex-1 bg-blue-500/80 hover:bg-blue-400 rounded-t transition-all"
                            style={{ height: `${portHeight}%` }}
                          />
                          <div
                            className="flex-1 bg-gray-700/80 hover:bg-gray-600 rounded-t transition-all"
                            style={{ height: `${benchHeight}%` }}
                          />
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex justify-between text-[10px] mt-1.5 text-gray-500 font-mono">
                    <span>{results.from_date}</span>
                    <span>Equity Progress</span>
                    <span>{results.to_date}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Positions Table */}
            <div className="card overflow-hidden">
              <div className="p-4 border-b border-gray-800 flex justify-between items-center">
                <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
                  Simulated Positions ({results.positions?.length || 0} stocks)
                </span>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Sorted by Return %
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Signal</th>
                      <th>Entry Price</th>
                      <th>Exit Price</th>
                      <th>Return %</th>
                      <th>Max Drawdown</th>
                      <th>Fund. Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.positions?.map((p: any) => (
                      <tr
                        key={p.nse_symbol}
                        className="cursor-pointer hover:bg-gray-800/40"
                        onClick={() => router.push(`/stocks/${p.nse_symbol}`)}
                      >
                        <td>
                          <span className="font-semibold text-xs text-blue-400">{p.nse_symbol}</span>
                          {p.company_name && (
                            <div className="text-[11px] text-gray-500 truncate max-w-[180px]">
                              {p.company_name}
                            </div>
                          )}
                        </td>
                        <td>
                          <span
                            className="text-[10px] font-bold px-2 py-0.5 rounded"
                            style={{
                              background:
                                p.signal_at_entry === "GREEN"
                                  ? "rgba(63,185,80,0.15)"
                                  : p.signal_at_entry === "YELLOW"
                                  ? "rgba(227,179,65,0.15)"
                                  : "rgba(110,118,129,0.15)",
                              color:
                                p.signal_at_entry === "GREEN"
                                  ? "#3fb950"
                                  : p.signal_at_entry === "YELLOW"
                                  ? "#e3b341"
                                  : "#8b949e",
                            }}
                          >
                            {p.signal_at_entry || "—"}
                          </span>
                        </td>
                        <td className="font-mono text-xs">₹{p.entry_price?.toFixed(2)}</td>
                        <td className="font-mono text-xs">₹{p.exit_price?.toFixed(2)}</td>
                        <td className="font-mono text-xs">
                          <span className={p.return_pct >= 0 ? "text-green-400 font-bold" : "text-red-400 font-bold"}>
                            {p.return_pct >= 0 ? "+" : ""}{p.return_pct}%
                          </span>
                        </td>
                        <td className="font-mono text-xs text-red-400/90">
                          -{p.max_drawdown}%
                        </td>
                        <td className="font-mono text-xs">
                          {p.fundamental_score ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Disclaimer */}
            <div className="disclaimer-banner">
              {results.disclaimer}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
