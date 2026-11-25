import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../hooks/useAuth";

const FEATURES = {
  free: ["Single-message checks", "Explainable verdicts", "Offline threat-signal analysis"],
  pro: ["Everything in trial", "Bulk CSV inbox scanning", "Inbox analytics & reports", "API access (keys)", "Priority model updates"],
};

export function Pricing() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function choose() {
    if (!user) {
      navigate("/register");
      return;
    }
    setBusy(true);
    try {
      const co = await api.checkout();
      if (co.provider === "mock") {
        await api.mockComplete(co.session_id);
        await refresh();
        setNote("Demo mode: mock payment completed — you now have Pro. Add real Stripe keys to charge customers.");
      } else {
        window.location.href = co.url;
      }
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Checkout failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h1 className="text-3xl font-extrabold">Simple pricing</h1>
        <p className="mt-2 text-muted">Start free for 14 days. Upgrade only when you need bulk scanning and API access.</p>
      </div>
      <div className="mx-auto grid max-w-4xl gap-5 md:grid-cols-2">
        <div className="card space-y-3">
          <h2 className="text-lg font-bold">Trial</h2>
          <div className="text-3xl font-extrabold">$0<span className="text-base font-normal text-muted"> / 14 days</span></div>
          <ul className="space-y-1 text-sm">{FEATURES.free.map((f) => <li key={f}>✓ {f}</li>)}</ul>
          {!user && <button className="btn-ghost w-full" onClick={() => navigate("/register")}>Start free trial</button>}
          {user && user.plan !== "pro" && <span className="chip bg-brand/10 text-brand">Current plan</span>}
        </div>
        <div className="card space-y-3 border-brand ring-1 ring-brand/20">
          <h2 className="text-lg font-bold">Pro</h2>
          <div className="text-3xl font-extrabold">$8<span className="text-base font-normal text-muted"> / month</span></div>
          <ul className="space-y-1 text-sm">{FEATURES.pro.map((f) => <li key={f}>✓ {f}</li>)}</ul>
          {user?.plan === "pro" ? (
            <span className="chip bg-brand/10 text-emerald-300">Active subscription</span>
          ) : (
            <button className="btn-primary w-full" onClick={choose} disabled={busy}>{busy ? "Working…" : "Upgrade to Pro"}</button>
          )}
        </div>
      </div>
      {note && <p className="mx-auto max-w-2xl rounded-xl bg-warn/10 p-4 text-center text-sm text-amber-200">{note}</p>}
    </div>
  );
}
