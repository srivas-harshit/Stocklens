"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { ArrowLeft, Bell, Plus, Trash2, CheckCircle, Clock } from "lucide-react";
import { alertsApi } from "@/lib/api";

const ALERT_TYPES = [
  { value: "PRICE_ABOVE", label: "Price Rises Above" },
  { value: "PRICE_BELOW", label: "Price Falls Below" },
  { value: "SIGNAL_CHANGE_GREEN", label: "Signal Changes to Green" },
  { value: "SIGNAL_CHANGE_RED", label: "Signal Changes to Red" },
  { value: "UPSIDE_PCT_ABOVE", label: "Upside % Rises Above" },
  { value: "RISK_SCORE_ABOVE", label: "Risk Score Rises Above" },
];

export default function AlertsPage() {
  const router = useRouter();
  const { data, mutate, isLoading } = useSWR("alerts", () => alertsApi.get() as any);
  const [form, setForm] = useState({ nse_symbol: "", alert_type: "PRICE_ABOVE", condition_value: "" });
  const [adding, setAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const alerts: any[] = data?.alerts || [];

  const handleAdd = async () => {
    const sym = form.nse_symbol.trim().toUpperCase();
    if (!sym || !form.alert_type) { setError("Symbol and alert type are required"); return; }
    setAdding(true);
    setError("");
    try {
      await alertsApi.create({
        nse_symbol: sym,
        alert_type: form.alert_type,
        condition_value: form.condition_value ? parseFloat(form.condition_value) : null,
      });
      setForm({ nse_symbol: "", alert_type: "PRICE_ABOVE", condition_value: "" });
      await mutate();
    } catch (e: any) {
      setError(e.message || "Failed to create alert");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await alertsApi.remove(id);
      await mutate();
    } catch (e: any) {
      alert(e.message || "Failed to delete alert");
    } finally {
      setDeletingId(null);
    }
  };

  const needsValue = ["PRICE_ABOVE", "PRICE_BELOW", "UPSIDE_PCT_ABOVE", "RISK_SCORE_ABOVE"].includes(form.alert_type);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <div className="topbar">
        <button className="btn btn-ghost" onClick={() => router.push("/")}>
          <ArrowLeft className="w-4 h-4" /> Dashboard
        </button>
        <Bell className="w-5 h-5 text-yellow-400" />
        <span className="font-bold" style={{ color: "var(--text-primary)" }}>Alerts</span>
      </div>

      <div className="main-content max-w-4xl mx-auto">
        {/* Create alert */}
        <div className="card p-5 mb-6">
          <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Create New Alert</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <div>
              <label className="metric-label">NSE Symbol *</label>
              <input className="input mt-1" placeholder="RELIANCE"
                value={form.nse_symbol}
                onChange={(e) => setForm(f => ({ ...f, nse_symbol: e.target.value.toUpperCase().slice(0, 30) }))} />
            </div>
            <div>
              <label className="metric-label">Alert Type *</label>
              <select className="input mt-1" value={form.alert_type}
                onChange={(e) => setForm(f => ({ ...f, alert_type: e.target.value }))}>
                {ALERT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            {needsValue && (
              <div>
                <label className="metric-label">Trigger Value *</label>
                <input className="input mt-1" type="number" placeholder="e.g. 2500.00"
                  value={form.condition_value}
                  onChange={(e) => setForm(f => ({ ...f, condition_value: e.target.value }))} />
              </div>
            )}
          </div>
          {error && <div className="text-sm text-red-400 mb-2">{error}</div>}
          <button className="btn btn-primary" onClick={handleAdd} disabled={adding}>
            <Plus className="w-4 h-4" /> {adding ? "Creating..." : "Create Alert"}
          </button>
        </div>

        {/* Active alerts */}
        <div className="card overflow-hidden">
          <div className="px-5 py-3 border-b flex justify-between items-center" style={{ borderColor: "var(--bg-border)" }}>
            <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Active Alerts ({alerts.length})</span>
          </div>
          {isLoading ? (
            <div className="p-8 text-center" style={{ color: "var(--text-muted)" }}>Loading alerts...</div>
          ) : alerts.length === 0 ? (
            <div className="p-12 text-center" style={{ color: "var(--text-muted)" }}>
              <Bell className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p className="text-sm">No active alerts.</p>
              <p className="text-xs mt-1">Alerts are evaluated every 30 minutes during market hours.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Condition</th>
                    <th>Value</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((a: any) => (
                    <tr key={a.id}>
                      <td className="primary">
                        <button
                          className="font-semibold text-sm hover:underline"
                          style={{ color: "#2188ff" }}
                          onClick={() => router.push(`/stocks/${a.nse_symbol}`)}
                        >
                          {a.nse_symbol}
                        </button>
                      </td>
                      <td style={{ fontSize: 12 }}>
                        {ALERT_TYPES.find(t => t.value === a.alert_type)?.label || a.alert_type}
                      </td>
                      <td className="font-mono text-xs">
                        {a.condition_value != null ? a.condition_value : "—"}
                      </td>
                      <td>
                        <span className={`text-xs px-2 py-0.5 rounded font-medium ${a.is_triggered ? "bg-yellow-500/20 text-yellow-400" : a.is_active ? "bg-green-500/20 text-green-400" : "bg-gray-500/20 text-gray-400"}`}>
                          {a.is_triggered ? "Triggered" : a.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td style={{ fontSize: 11, color: "var(--text-muted)" }}>
                        {a.created_at ? new Date(a.created_at).toLocaleDateString("en-IN") : "—"}
                      </td>
                      <td>
                        <button
                          className="btn btn-ghost text-xs"
                          style={{ color: "var(--signal-red)" }}
                          onClick={() => handleDelete(a.id)}
                          disabled={deletingId === a.id}
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="disclaimer-banner mt-6 text-xs">
          ⚠️ Alerts are evaluated against model data and live prices. Not a substitute for real-time broker alerts.
        </div>
      </div>
    </div>
  );
}
