import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import type { AnalyzeResponse } from "../lib/types";
import { VerdictCard } from "../components/VerdictCard";

const SAMPLES: [string, string][] = [
  ["Bank warning", "URGENT: Your bank account is locked. Verify your PIN now at secure-login.example"],
  ["Prize claim", "Congratulations! You won a free gift card. Claim your prize now!"],
  ["Everyday text", "Are we still meeting for lunch tomorrow? I can bring coffee."],
];

export function Landing() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function analyze(value?: string) {
    const message = (value ?? text).trim();
    if (!message) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.analyze(message));
    } catch (e) {
      setResult(null);
      if (e instanceof ApiError && e.status === 402) {
        setError("You've used your free checks. Create an account to keep going — it's free for 14 days.");
      } else {
        setError(e instanceof Error ? e.message : "Something went wrong.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="text-center">
        <p className="eyebrow inline-flex items-center gap-2 rounded-full border border-brand/30 bg-brand/10 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-brand">
          <span className="h-2 w-2 animate-pulse rounded-full bg-brand" /> Personal SMS security
        </p>
        <h1 className="mx-auto mt-4 max-w-3xl text-4xl font-bold leading-tight tracking-tight md:text-6xl">
          A second look <span className="bg-gradient-to-r from-emerald-300 to-teal-200 bg-clip-text text-transparent">before you tap.</span>
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-muted">
          Paste a suspicious text and get an explainable verdict — offline, with no third-party scanning service.
        </p>
      </section>

      <section className="card mx-auto max-w-3xl space-y-3">
        <textarea
          className="input h-36 resize-none"
          placeholder="Paste or type a text message here…"
          value={text}
          maxLength={5000}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-primary" onClick={() => analyze()} disabled={busy || !text.trim()}>
            {busy ? "Analyzing…" : "Analyze message →"}
          </button>
          <span className="text-xs text-muted">🔒 No external API · No link is opened</span>
        </div>
        <div className="flex flex-wrap gap-2 pt-1">
          {SAMPLES.map(([name, sample]) => (
            <button key={name} className="chip border border-line bg-panel text-ink hover:bg-panel2" onClick={() => { setText(sample); void analyze(sample); }}>
              Try: {name}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <div className="mx-auto max-w-3xl rounded-xl border border-warn/40 bg-warn/10 p-4 text-sm">
          {error}{" "}
          <Link to="/register" className="font-semibold text-brand underline">Create a free account</Link>
        </div>
      )}

      {result && (
        <section className="mx-auto max-w-3xl">
          <VerdictCard result={result} />
          {result.quota.kind === "anonymous" && result.quota.remaining !== null && (
            <p className="mt-3 text-center text-xs text-muted">
              {result.quota.remaining} of {result.quota.limit} free checks left.
            </p>
          )}
        </section>
      )}
    </div>
  );
}
