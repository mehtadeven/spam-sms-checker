// In-browser port of backend/spamsms/model.py, used by the static demo build
// (VITE_STATIC_DEMO=true, e.g. GitHub Pages) where there is no FastAPI server.
//
// It reproduces predict_message() with the exact numbers of the trained model:
// scripts/export_web_model.py exports the TF-IDF vocabulary + IDF weights and
// the Naive Bayes log-probabilities to public/model.json. Nothing leaves the
// browser, and no link is ever opened.

import type { Driver, Label, Signal } from "./types";

export interface WebModel {
  vectorizer: {
    ngram_range: [number, number];
    sublinear_tf: boolean;
    features: string[];
    idf: number[];
  };
  classifier: {
    classes: string[];
    class_log_prior: number[];
    feature_log_prob: number[][];
  };
  thresholds: { unsure_low: number; unsure_high: number };
}

export interface LocalPrediction {
  label: Label;
  spam_probability: number;
  matched_vocabulary_terms: number;
  drivers: Driver[];
  signals: Signal[];
  domains: string[];
}

export const MAX_MESSAGE_CHARS = 5000;

// --- TF-IDF transform (scikit-learn TfidfVectorizer: lowercase, strip_accents="unicode") ---

const WORD = /[\p{L}\p{N}_]+/gu;

function preprocess(text: string): string {
  // lowercase first, then remove accents (NFKD + drop combining marks), like scikit-learn
  return text.toLowerCase().normalize("NFKD").replace(/\p{Mn}/gu, "");
}

function tokensWithNgrams(text: string, [minN, maxN]: [number, number]): string[] {
  const words = (preprocess(text).match(WORD) ?? []).filter((w) => w.length >= 2);
  const out: string[] = [];
  for (let n = minN; n <= maxN; n++) {
    for (let i = 0; i + n <= words.length; i++) out.push(words.slice(i, i + n).join(" "));
  }
  return out;
}

const indexCache = new WeakMap<WebModel, Map<string, number>>();
function featureIndex(model: WebModel): Map<string, number> {
  let index = indexCache.get(model);
  if (!index) {
    index = new Map(model.vectorizer.features.map((f, i) => [f, i]));
    indexCache.set(model, index);
  }
  return index;
}

function transform(model: WebModel, text: string): Map<number, number> {
  const index = featureIndex(model);
  const counts = new Map<number, number>();
  for (const term of tokensWithNgrams(text, model.vectorizer.ngram_range)) {
    const i = index.get(term);
    if (i !== undefined) counts.set(i, (counts.get(i) ?? 0) + 1);
  }
  const vector = new Map<number, number>();
  let squared = 0;
  for (const [i, count] of counts) {
    const tf = model.vectorizer.sublinear_tf ? 1 + Math.log(count) : count;
    const weight = tf * model.vectorizer.idf[i];
    vector.set(i, weight);
    squared += weight * weight;
  }
  const norm = Math.sqrt(squared);
  if (norm > 0) for (const [i, w] of vector) vector.set(i, w / norm);
  return vector;
}

// --- Threat signals (same rules as inspect_threat_signals) ---

const URL_PATTERN =
  /(?:https?:\/\/|www\.)[^\s<>()]+|(?:\b[\w-]+\.)+(?:com|net|org|io|co|info|biz|app|dev|xyz|me|uk|ca|us|example)(?:\/[^\s<>()]*)?/gi;
const SHORTENER_DOMAINS = new Set(["bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "ow.ly", "buff.ly", "rebrand.ly"]);
const SECRET_PATTERN =
  /\b(password|passcode|pin|otp|one[- ]time code|verification code|security code|login details)\b|\b(?:send|share|tell|enter|reply with|provide|confirm)\b.{0,30}\b(?:code|pin|password|otp)\b|\b(?:code|pin|password|otp)\b.{0,30}\b(?:send|share|tell|enter|reply|provide|confirm)\b/i;
const URGENCY_PATTERN = /\b(urgent|immediately|act now|final notice|expires today|within \d+ hours)\b/i;
const MONEY_PATTERN = /\b(pay|payment|fee|bank details|gift card|prize|won|winner|reward|refund)\b/i;

// Mirrors Python's urlsplit(candidate).hostname: text between "//" and the
// next / ? #, minus any "user@" and ":port", lowercased.
function hostnameOf(url: string): string | null {
  const candidate = url.includes("://") ? url : "https://" + url;
  const match = candidate.match(/^[a-z][a-z0-9+.-]*:\/\/([^/?#]*)/i);
  if (!match) return null;
  const netloc = match[1].slice(match[1].lastIndexOf("@") + 1);
  let host: string;
  if (netloc.startsWith("[")) {
    const end = netloc.indexOf("]");
    if (end === -1) return null;
    host = netloc.slice(1, end);
  } else {
    host = netloc.split(":")[0];
  }
  return host ? host.toLowerCase() : null;
}

function isIpAddress(host: string): boolean {
  const v4 = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (v4) return v4.slice(1).every((part) => Number(part) <= 255 && !(part.length > 1 && part.startsWith("0")));
  return host.includes(":") && /^[0-9a-f:.]+$/i.test(host);
}

export function inspectThreatSignals(text: string): { signals: Signal[]; domains: string[] } {
  const signals: Signal[] = [];
  const urls = (text.match(URL_PATTERN) ?? []).map((u) => u.replace(/[.,!?;:]+$/, ""));
  const domains: string[] = [];
  for (const url of urls) {
    const host = hostnameOf(url);
    if (host && !domains.includes(host)) domains.push(host);
  }

  if (urls.length) {
    signals.push({
      title: "Contains a link",
      detail: "Unexpected links can lead to fake sign-in or payment pages. Check the destination independently.",
      severity: "caution",
    });
  }
  if (domains.some((d) => SHORTENER_DOMAINS.has(d))) {
    signals.push({
      title: "Link uses a URL shortener",
      detail: "The final destination is hidden. Avoid opening it unless you can verify it another way.",
      severity: "high",
    });
  }
  if (domains.some(isIpAddress)) {
    signals.push({
      title: "Link points to a raw IP address",
      detail: "A numeric IP address instead of a recognizable site name deserves extra caution.",
      severity: "high",
    });
  }
  if (SECRET_PATTERN.test(text)) {
    signals.push({
      title: "Requests a secret or verification code",
      detail: "Legitimate organizations should not ask you to disclose passwords, PINs, or one-time codes by text.",
      severity: "high",
    });
  }
  if (URGENCY_PATTERN.test(text)) {
    signals.push({
      title: "Creates time pressure",
      detail: "Urgency can be used to discourage careful verification.",
      severity: "caution",
    });
  }
  if (MONEY_PATTERN.test(text)) {
    signals.push({
      title: "Mentions money, payment, or a reward",
      detail: "Unexpected payment demands and prize claims are common social-engineering tactics.",
      severity: "caution",
    });
  }
  return { signals, domains };
}

// --- Decision policy + prediction (same as decide_label / predict_message) ---

export function decideLabel(model: WebModel, spamProbability: number, matched: number): Label {
  if (matched === 0) return "UNSURE";
  if (spamProbability >= model.thresholds.unsure_high) return "SPAM";
  if (spamProbability <= model.thresholds.unsure_low) return "HAM";
  return "UNSURE";
}

export function predictMessage(model: WebModel, text: string): LocalPrediction {
  if (typeof text !== "string" || !text.trim()) throw new Error("Enter a non-empty SMS message.");
  if (text.length > MAX_MESSAGE_CHARS) throw new Error("Messages must be 5,000 characters or fewer.");

  const { classes, class_log_prior: prior, feature_log_prob: flp } = model.classifier;
  const spam = classes.indexOf("spam");
  const ham = classes.indexOf("ham");
  const x = transform(model, text);

  // Multinomial Naive Bayes: joint log-likelihood, then softmax.
  const jll = classes.map((_, c) => {
    let sum = prior[c];
    for (const [i, w] of x) sum += w * flp[c][i];
    return sum;
  });
  const top = Math.max(...jll);
  const total = jll.reduce((acc, v) => acc + Math.exp(v - top), 0);
  const spamProbability = Math.exp(jll[spam] - top) / total;
  const matched = x.size;
  const label = decideLabel(model, spamProbability, matched);

  const contributions = [...x].map(([i, w]) => ({
    word: model.vectorizer.features[i],
    value: w * (flp[spam][i] - flp[ham][i]),
  }));
  let drivers: Driver[];
  if (label === "SPAM") {
    drivers = contributions
      .filter((c) => c.value > 0)
      .sort((a, b) => b.value - a.value)
      .map((c) => ({ word: c.word, impact: c.value }));
  } else if (label === "HAM") {
    drivers = contributions
      .filter((c) => c.value < 0)
      .sort((a, b) => a.value - b.value)
      .map((c) => ({ word: c.word, impact: -c.value }));
  } else {
    drivers = contributions
      .filter((c) => c.value !== 0)
      .sort((a, b) => b.value - a.value)
      .map((c) => ({ word: c.word, impact: Math.abs(c.value) }));
  }

  const threats = inspectThreatSignals(text);
  return {
    label,
    spam_probability: spamProbability,
    matched_vocabulary_terms: matched,
    drivers: drivers.slice(0, 6),
    signals: threats.signals,
    domains: threats.domains,
  };
}

let modelPromise: Promise<WebModel> | null = null;
export function loadWebModel(): Promise<WebModel> {
  modelPromise ??= fetch(import.meta.env.BASE_URL + "model.json").then((res) => {
    if (!res.ok) throw new Error("Could not load the model file.");
    return res.json() as Promise<WebModel>;
  });
  return modelPromise;
}
