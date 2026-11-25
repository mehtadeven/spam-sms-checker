export function About() {
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <h1 className="text-3xl font-extrabold">How it works</h1>
      <p className="text-muted">A transparent, offline-first pipeline — no message text is ever sent to a third-party AI or URL-reputation service.</p>

      <ol className="space-y-4">
        {[
          ["Text classification", "TF-IDF represents word and phrase patterns; Multinomial Naive Bayes estimates whether the text resembles labeled spam."],
          ["Explainability", "The app surfaces the learned text features that contributed most to each verdict."],
          ["Threat-signal checks", "Local pattern checks flag links, URL shorteners, raw-IP links, requests for secrets, urgency, and money/reward language. No link is opened."],
          ["Honest uncertainty", "If a message matches too little known vocabulary, or sits near the decision boundary, we say UNSURE instead of guessing."],
        ].map(([title, body], i) => (
          <li key={i} className="card">
            <h3 className="font-bold">{i + 1} · {title}</h3>
            <p className="mt-1 text-sm text-muted">{body}</p>
          </li>
        ))}
      </ol>

      <pre className="overflow-x-auto rounded-xl border border-line bg-console p-4 font-mono text-xs text-emerald-200">{`SMS → TF-IDF + Naive Bayes → learned clues
     ↘ Local safety checks → warning signals
     → Verdict (SPAM / HAM / UNSURE) + inbox analytics`}</pre>

      <div className="rounded-xl border border-warn/40 bg-warn/10 p-4 text-sm">
        The bundled model trains on a small demo corpus. Scammers evolve quickly: predictions and signals are guidance, not proof that a message is safe or malicious.
      </div>
    </div>
  );
}
