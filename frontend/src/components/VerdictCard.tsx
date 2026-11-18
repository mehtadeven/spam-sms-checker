import type { AnalyzeResponse } from "../lib/types";

const STYLES: Record<string, { box: string; title: string; icon: string }> = {
  SPAM: { box: "border-red-200 bg-red-50", title: "Likely spam", icon: "🚨" },
  HAM: { box: "border-emerald-200 bg-emerald-50", title: "Likely legitimate", icon: "✅" },
  UNSURE: { box: "border-amber-200 bg-amber-50", title: "Not sure — verify manually", icon: "❓" },
};

export function VerdictCard({ result }: { result: AnalyzeResponse }) {
  const s = STYLES[result.label];
  const pct = Math.round(result.spam_probability * 100);

  return (
    <div className="space-y-4">
      <div className={`rounded-2xl border p-5 ${s.box}`}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-lg font-bold">
              {s.icon} {s.title}
            </div>
            <div className="text-sm text-muted">
              Model spam estimate: <span className="font-semibold">{pct}%</span>
            </div>
          </div>
          <span className="chip bg-white/70 text-ink">{result.label}</span>
        </div>
        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-white/60">
          <div
            className={result.label === "SPAM" ? "h-full bg-red-500" : result.label === "HAM" ? "h-full bg-emerald-500" : "h-full bg-amber-400"}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {result.label === "UNSURE" && (
        <p className="text-sm text-muted">
          This message didn't match enough known vocabulary for a confident call. That is not proof it is safe — judge it yourself.
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="card">
          <h4 className="mb-2 font-bold">Safety signals</h4>
          {result.signals.length === 0 ? (
            <p className="text-sm text-muted">No common link or social-engineering indicators detected.</p>
          ) : (
            <ul className="space-y-2">
              {result.signals.map((sig, i) => (
                <li key={i} className="rounded-xl border border-slate-200 p-3">
                  <div className="flex items-center gap-2 font-semibold">
                    <span>{sig.severity === "high" ? "🔴" : "🟠"}</span>
                    {sig.title}
                  </div>
                  <p className="mt-1 text-sm text-muted">{sig.detail}</p>
                </li>
              ))}
            </ul>
          )}
          {result.domains.length > 0 && (
            <p className="mt-3 text-xs text-muted">Link domains: {result.domains.join(", ")}</p>
          )}
        </div>

        <div className="card">
          <h4 className="mb-2 font-bold">Learned text clues</h4>
          {result.drivers.length === 0 ? (
            <p className="text-sm text-muted">No learned clues matched this message.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {result.drivers.map((d, i) => (
                <span key={i} className="chip bg-blue-50 text-brand">
                  {d.word}
                </span>
              ))}
            </div>
          )}
          <p className="mt-3 text-xs text-muted">
            Clues are features the model weighted, not proof of malicious intent.
          </p>
        </div>
      </div>

      {result.label === "SPAM" && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm">
          Do not reply, open links, or share passwords / one-time codes. Verify the sender through a known official channel.
        </div>
      )}
    </div>
  );
}
