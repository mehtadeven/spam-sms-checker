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
        <p className="eyebrow text-xs font-bold uppercase tracking-widest text-brand">Personal SMS security</p>
        <h1 className="mx-auto mt-2 max-w-3xl text-4xl font-extrabold leading-tight md:text-5xl">
          A second look before you tap.
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
            <button key={name} className="chip border border-slate-200 bg-white text-ink hover:bg-slate-50" onClick={() => { setText(sample); void analyze(sample); }}>
              Try: {name}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <div className="mx-auto max-w-3xl rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm">
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
