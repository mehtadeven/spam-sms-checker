// Typed fetch client. Bearer token auth (not cookies) — see backend/security.py.
// In dev, Vite proxies /api to the backend so this is same-origin; in prod the
// SPA is served by FastAPI itself. apiBase defaults to "" (same origin).

import type {
  AnalyzeResponse,
  AuthResponse,
  CheckoutResponse,
  EntitlementResponse,
  ScanResponse,
  UserOut,
} from "./types";
import { loadWebModel, predictMessage } from "./localModel";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

// Static browser demo (GitHub Pages): no backend. Single-message analysis runs
// on an in-browser copy of the trained model; server-only features are off.
export const STATIC_DEMO = import.meta.env.VITE_STATIC_DEMO === "true";
export const DEMO_UNAVAILABLE =
  "This browser demo has no server, so accounts, inbox scans and billing are switched off. Run the full app locally to try them.";
const TOKEN_KEY = "spamsms_token";
const DEVICE_KEY = "spamsms_device_id";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getDeviceId(): string {
  let id = localStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = "web_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (STATIC_DEMO) throw new ApiError(503, DEMO_UNAVAILABLE);
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", "Bearer " + token);
  headers.set("X-Device-Id", getDeviceId());

  const res = await fetch(API_BASE + path, { ...options, headers });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data && typeof data.detail === "string" ? data.detail : res.statusText;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

export const api = {
  analyze: (text: string) =>
    STATIC_DEMO
      ? analyzeInBrowser(text)
      : request<AnalyzeResponse>("/api/analyze", { method: "POST", body: JSON.stringify({ text }) }),

  register: (email: string, password: string) =>
    request<AuthResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    request<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),

  me: () => request<UserOut>("/api/auth/me"),

  entitlement: () => request<EntitlementResponse>("/api/billing/status"),

  checkout: (plan = "pro_monthly") =>
    request<CheckoutResponse>("/api/billing/checkout", {
      method: "POST",
      body: JSON.stringify({ plan }),
    }),

  mockComplete: (sessionId: string) =>
    request<{ ok: boolean; paid_until: string }>(
      "/api/billing/mock/complete?session_id=" + encodeURIComponent(sessionId),
      { method: "POST" }
    ),

  // CSV sent as raw bytes (no multipart) — matches backend scan router.
  scan: (file: File) =>
    request<ScanResponse>("/api/scan", {
      method: "POST",
      body: file,
      headers: { "Content-Type": "text/csv" },
    }),
};

async function analyzeInBrowser(text: string): Promise<AnalyzeResponse> {
  const model = await loadWebModel();
  try {
    const result = predictMessage(model, text.trim());
    return { ...result, quota: { kind: "anonymous", remaining: null, limit: null, pays_wall: false } };
  } catch (e) {
    throw new ApiError(400, e instanceof Error ? e.message : "Could not analyze this message.");
  }
}
