import { Link, NavLink, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../hooks/useAuth";
import { STATIC_DEMO } from "../lib/api";

const REPO_URL = "https://github.com/mehtadeven/spam-sms-checker";

const navClass = ({ isActive }: { isActive: boolean }) =>
  "rounded-lg px-3 py-2 text-sm font-semibold transition " +
  (isActive ? "bg-brand/10 text-brand" : "text-muted hover:text-ink");

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function onLogout() {
    await logout();
    navigate("/");
  }

  return (
    <div className="min-h-screen">
      {STATIC_DEMO && (
        <div className="border-b border-brand/30 bg-brand/10 px-4 py-2 text-center font-mono text-xs text-emerald-200">
          🌐 Live browser demo — the trained model runs right here in your browser. Accounts, inbox scan and billing need the
          Python backend:{" "}
          <a href={REPO_URL} className="font-semibold underline">run the full app from GitHub</a>.
        </div>
      )}
      <header className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2 text-lg font-extrabold">
            <span className="grid h-8 w-8 place-items-center rounded-lg border border-brand/40 bg-brand/10 text-base">🛡️</span> SpamSMS <span className="text-brand">Guardian</span>
          </Link>
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={navClass}>Check a message</NavLink>
            {!STATIC_DEMO && <NavLink to="/scan" className={navClass}>Inbox scan</NavLink>}
            {!STATIC_DEMO && <NavLink to="/pricing" className={navClass}>Pricing</NavLink>}
            <NavLink to="/about" className={navClass}>How it works</NavLink>
          </nav>
          <div className="flex items-center gap-2">
            {STATIC_DEMO ? (
              <>
                <a href="https://mehtadeven.github.io/" className="rounded-lg px-3 py-2 text-sm font-semibold text-muted hover:text-ink">Portfolio</a>
                <a href={REPO_URL} className="btn-primary px-3 py-1.5 text-sm">Source code</a>
              </>
            ) : user ? (
              <>
                <span className="chip bg-panel2 text-ink">{user.plan === "pro" ? "Pro" : "Trial"}</span>
                <button className="btn-ghost px-3 py-1.5 text-sm" onClick={onLogout}>Sign out</button>
              </>
            ) : (
              <>
                <NavLink to="/login" className={navClass}>Sign in</NavLink>
                <Link to="/register" className="btn-primary px-3 py-1.5 text-sm">Get started</Link>
              </>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      <footer className="mx-auto max-w-6xl px-4 py-8 text-center text-xs text-muted">
        {STATIC_DEMO
          ? "Browser demo · Your messages are analyzed by a model running in this tab — nothing is sent anywhere."
          : "Offline-first · Your messages are analyzed locally by this app server, never sent to a third-party AI or URL-reputation service."}
      </footer>
    </div>
  );
}
