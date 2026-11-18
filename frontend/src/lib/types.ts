// Types mirroring the FastAPI response models in backend/spamsms/schemas.py.

export type Label = "SPAM" | "HAM" | "UNSURE";
export type Severity = "high" | "caution";

export interface Driver {
  word: string;
  impact: number;
}

export interface Signal {
  title: string;
  detail: string;
  severity: Severity;
}

export interface QuotaStatus {
  kind: "anonymous" | "trial" | "paid" | "pro";
  remaining: number | null;
  limit: number | null;
  pays_wall: boolean;
}

export interface AnalyzeResponse {
  label: Label;
  spam_probability: number;
  matched_vocabulary_terms: number;
  drivers: Driver[];
  signals: Signal[];
  domains: string[];
  quota: QuotaStatus;
}

export interface UserOut {
  id: number;
  email: string;
  plan: "trial" | "pro";
  trial_used: number;
  trial_limit: number;
  paid_until: string | null;
}

export interface AuthResponse {
  token: string;
  user: UserOut;
}

export interface ScanSummary {
  scanned: number;
  spam: number;
  ham: number;
  unsure: number;
  top_signals: [string, number][];
}

export interface ScanRow {
  index: number;
  message: string;
  label: Label;
  spam_probability: number;
  trigger_words: string[];
  safety_signals: string[];
}

export interface ScanResponse {
  summary: ScanSummary;
  rows: ScanRow[];
  truncated: boolean;
}

export interface CheckoutResponse {
  provider: "mock" | "stripe";
  url: string;
  session_id: string;
}

export interface EntitlementResponse {
  plan: "free" | "trial" | "pro";
  anonymous_remaining: number | null;
  trial_remaining: number | null;
  paid_until: string | null;
  can_bulk_scan: boolean;
}
