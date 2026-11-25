import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../hooks/useAuth";
import type { ScanResponse } from "../lib/types";

const LABEL_CHIP: Record<string, string> = {
  SPAM: "bg-danger/15 text-rose-300",
  HAM: "bg-brand/15 text-emerald-300",
  UNSURE: "bg-warn/15 text-amber-300",
};

export function Scan() {
  const { user, refresh } = useAuth();
  const fileRef = useRef<HTMLInputElement>(null);
  const [data, setData] = useState<ScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [upgrading, setUpgrading] = useState(false);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      setData(await api.scan(file));
    } catch (err) {
      setData(null);
      if (err instanceof ApiError && err.status === 403) setError("Bulk inbox scanning is a Pro feature.");
      else setError(err instanceof Error ? err.message : "Scan failed.");
    } finally {
      setBusy(false);
    }
  }

  async function upgrade() {
    setUpgrading(true);
    setError(null);
    try {
      const co = await api.checkout();
      if (co.provider === "mock") {
        // Demo mode: simulate the payment completing.
        await api.mockComplete(co.session_id);
        await refresh();
      } else {
        window.location.href = co.url; // real Stripe Checkout
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Checkout failed.");
    } finally {
      setUpgrading(false);
    }
  }

  if (!user) {
    return (
      <Gate title="Sign in to scan your inbox" body="Bulk CSV scanning is available after you create a free account.">
        <Link to="/login" className="btn-primary">Sign in</Link>
      </Gate>
    );
  }

  const isPro = user.plan === "pro";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold">Inbox scanner</h1>
        {!isPro && (
          <button className="btn-primary" onClick={upgrade} disabled={upgrading}>
            {upgrading ? "Working…" : "Upgrade to Pro"}
          </button>
        )}
      </div>

      {!isPro && (
        <div className="rounded-xl border border-brand/40 bg-brand/10 p-4 text-sm">
          You're on the <b>{user.trial_limit - user.trial_used} check trial</b>. Bulk scanning needs Pro.{" "}
          <span className="text-muted">(Demo mode: the Upgrade button completes a mock payment so you can see the full flow.)</span>
        </div>
      )}

      <div className="card space-y-3">
        <label className="label">Upload a CSV export (needs a <code>message</code> or <code>text</code> column)</label>
        <input ref={fileRef} type="file" accept=".csv,text/csv" onChange={onFile} disabled={!isPro || busy} className="text-sm" />
        {!isPro && <p className="text-xs text-muted">Enable Pro to upload.</p>}
      </div>

      {error && <div className="rounded-xl bg-danger/10 p-4 text-sm text-rose-300">{error}</div>}

      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Scanned" value={data.summary.scanned} />
            <Stat label="Likely spam" value={data.summary.spam} tone="red" />
            <Stat label="Likely safe" value={data.summary.ham} tone="green" />
            <Stat label="Unsure" value={data.summary.unsure} tone="amber" />
          </div>
          <div className="card overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b text-muted">
                  <th className="py-2 pr-4">Message</th>
                  <th className="py-2 pr-4">Verdict</th>
                  <th className="py-2 pr-4">Spam %</th>
                  <th className="py-2">Signals</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.index} className="border-b last:border-0 align-top">
                    <td className="max-w-md py-2 pr-4"><span className="line-clamp-2">{r.message}</span></td>
                    <td className="py-2 pr-4"><span className={`chip ${LABEL_CHIP[r.label]}`}>{r.label}</span></td>
                    <td className="py-2 pr-4 tabular-nums">{Math.round(r.spam_probability * 100)}%</td>
                    <td className="py-2 text-xs text-muted">{r.safety_signals.join("; ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.truncated && <p className="mt-2 text-xs text-muted">Showing first 200 rows.</p>}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "red" | "green" | "amber" }) {
  const color = tone === "red" ? "text-rose-300" : tone === "green" ? "text-emerald-300" : tone === "amber" ? "text-amber-300" : "text-ink";
  return (
    <div className="card">
      <div className={`text-2xl font-extrabold ${color}`}>{value.toLocaleString()}</div>
      <div className="text-xs text-muted">{label}</div>
    </div>
  );
}

function Gate({ title, body, children }: { title: string; body: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-md text-center">
      <div className="card space-y-3">
        <h1 className="text-xl font-extrabold">{title}</h1>
        <p className="text-sm text-muted">{body}</p>
        {children}
      </div>
    </div>
  );
}
