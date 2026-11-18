import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function Auth({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password);
      navigate("/scan");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <div className="card space-y-4">
        <h1 className="text-2xl font-extrabold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
        <p className="text-sm text-muted">
          {mode === "login"
            ? "Sign in to continue your trial and unlock Pro features."
            : "Start a free 14-day trial. No card required to begin."}
        </p>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </div>
          <div>
            <label className="label" htmlFor="password">Password</label>
            <input id="password" type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoComplete={mode === "login" ? "current-password" : "new-password"} />
            {mode === "register" && <p className="mt-1 text-xs text-muted">At least 8 characters.</p>}
          </div>
          {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
          <button className="btn-primary w-full" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
        </form>
        <p className="text-center text-sm text-muted">
          {mode === "login" ? (
            <>New here? <Link to="/register" className="font-semibold text-brand">Create an account</Link></>
          ) : (
            <>Already registered? <Link to="/login" className="font-semibold text-brand">Sign in</Link></>
          )}
        </p>
      </div>
    </div>
  );
}
