import { Link, NavLink, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../hooks/useAuth";

const navClass = ({ isActive }: { isActive: boolean }) =>
  "rounded-lg px-3 py-2 text-sm font-semibold transition " +
  (isActive ? "bg-blue-50 text-brand" : "text-muted hover:text-ink");

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function onLogout() {
    await logout();
    navigate("/");
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2 text-lg font-extrabold">
            🛡️ SpamSMS <span className="text-brand">Guardian</span>
          </Link>
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={navClass}>Check a message</NavLink>
            <NavLink to="/scan" className={navClass}>Inbox scan</NavLink>
            <NavLink to="/pricing" className={navClass}>Pricing</NavLink>
            <NavLink to="/about" className={navClass}>How it works</NavLink>
          </nav>
          <div className="flex items-center gap-2">
            {user ? (
              <>
                <span className="chip bg-slate-100 text-ink">{user.plan === "pro" ? "Pro" : "Trial"}</span>
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
        Offline-first · Your messages are analyzed locally by this app server, never sent to a third-party AI or URL-reputation service.
      </footer>
    </div>
  );
}
