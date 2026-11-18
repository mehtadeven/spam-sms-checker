"""Model loading, SMS classification, feature explanations, and threat signals.

This is the offline-first ML core. It performs NO network I/O: predictions run
entirely from a locally trained scikit-learn bundle and local regex checks.
URLs are inspected structurally (never opened or sent to a reputation service).
"""

from __future__ import annotations

import ipaddress
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

# --- Paths -----------------------------------------------------------------
# The project root is two levels up from this file (backend/spamsms/model.py ->
# repo root). DATA_DIR can be overridden by env so tests/deployments can point
# elsewhere without editing code. This relocation matters: when this module lived
# at repo root, Path(__file__).parent WAS the root; inside the package it is not.
PACKAGE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

DATA_DIR = Path(os.environ.get("SPAMSMS_DATA_DIR", PROJECT_ROOT / "data"))
MODELS_DIR = Path(os.environ.get("SPAMSMS_MODELS_DIR", PROJECT_ROOT / "models"))
DATA_PATH = DATA_DIR / "sample.csv"
MODEL_PATH = MODELS_DIR / "model.joblib"

MAX_MESSAGE_CHARS = 5000

# Presentation thresholds for the decision policy. These are deliberately
# conservative display bands, NOT calibrated probabilities (see README).
UNSURE_LOW = 0.35
UNSURE_HIGH = 0.65

URL_PATTERN = re.compile(
    r"(?i)(?:https?://|www\.)[^\s<>()]+|(?:\b[\w-]+\.)+(?:com|net|org|io|co|info|biz|app|dev|xyz|me|uk|ca|us|example)(?:/[^\s<>()]*)?"
)
SHORTENER_DOMAINS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "is.gd",
    "ow.ly",
    "buff.ly",
    "rebrand.ly",
}


def inspect_threat_signals(text):
    """Detect transparent, offline warning signs without contacting URLs."""
    signals = []
    urls = [match.rstrip(".,!?;:") for match in URL_PATTERN.findall(text)]
    domains = []
    for url in urls:
        candidate = url if "://" in url else "https://" + url
        try:
            hostname = (urlsplit(candidate).hostname or "").lower()
        except ValueError:
            continue
        if hostname and hostname not in domains:
            domains.append(hostname)

    if urls:
        signals.append(
            {
                "title": "Contains a link",
                "detail": "Unexpected links can lead to fake sign-in or payment pages. Check the destination independently.",
                "severity": "caution",
            }
        )
    if any(domain in SHORTENER_DOMAINS for domain in domains):
        signals.append(
            {
                "title": "Link uses a URL shortener",
                "detail": "The final destination is hidden. Avoid opening it unless you can verify it another way.",
                "severity": "high",
            }
        )
    for domain in domains:
        try:
            ipaddress.ip_address(domain)
        except ValueError:
            continue
        signals.append(
            {
                "title": "Link points to a raw IP address",
                "detail": "A numeric IP address instead of a recognizable site name deserves extra caution.",
                "severity": "high",
            }
        )
        break

    if re.search(
        r"\b(password|passcode|pin|otp|one[- ]time code|verification code|security code|login details)\b|\b(?:send|share|tell|enter|reply with|provide|confirm)\b.{0,30}\b(?:code|pin|password|otp)\b|\b(?:code|pin|password|otp)\b.{0,30}\b(?:send|share|tell|enter|reply|provide|confirm)\b",
        text,
        re.IGNORECASE,
    ):
        signals.append(
            {
                "title": "Requests a secret or verification code",
                "detail": "Legitimate organizations should not ask you to disclose passwords, PINs, or one-time codes by text.",
                "severity": "high",
            }
        )
    if re.search(r"\b(urgent|immediately|act now|final notice|expires today|within \d+ hours)\b", text, re.IGNORECASE):
        signals.append(
            {
                "title": "Creates time pressure",
                "detail": "Urgency can be used to discourage careful verification.",
                "severity": "caution",
            }
        )
    if re.search(r"\b(pay|payment|fee|bank details|gift card|prize|won|winner|reward|refund)\b", text, re.IGNORECASE):
        signals.append(
            {
                "title": "Mentions money, payment, or a reward",
                "detail": "Unexpected payment demands and prize claims are common social-engineering tactics.",
                "severity": "caution",
            }
        )

    return {"signals": signals, "domains": domains}


def train_bundle(messages, labels):
    """Fit a compact TF-IDF and Naive Bayes model."""
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        max_features=1500,
        sublinear_tf=True,
    )
    features = vectorizer.fit_transform(messages)
    classifier = MultinomialNB(alpha=0.35)
    classifier.fit(features, labels)
    return {"vectorizer": vectorizer, "classifier": classifier}


def load_bundle():
    """Load the trained model, or train an offline demo model on first run."""
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)

    data = pd.read_csv(DATA_PATH)
    if not {"label", "message"}.issubset(data.columns):
        raise ValueError("The training CSV must contain label and message columns.")
    if data.empty or data["message"].isna().any() or data["label"].isna().any():
        raise ValueError("The training CSV must contain non-empty messages and labels.")

    labels = data["label"].astype(str).str.lower().str.strip()
    if set(labels) != {"ham", "spam"}:
        raise ValueError("The training CSV must contain both ham and spam labels.")
    bundle = train_bundle(data["message"].astype(str), labels)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODEL_PATH, compress=3)
    return bundle


def decide_label(spam_probability, matched_feature_count):
    """Map a raw NB posterior + vocabulary coverage to SPAM/HAM/UNSURE.

    Fixes a real defect: with out-of-vocabulary text the TF-IDF row is all-zero,
    Naive Bayes posteriors are exactly equal (0.5000), and a naive
    ``>= 0.5`` rule breaks the tie toward SPAM — so benign replies like "ok" or
    "sure" were flagged as spam. We surface UNSURE instead of guessing, and we
    only trust the classifier when it actually matched known vocabulary.
    """
    if matched_feature_count == 0:
        return "UNSURE"
    if spam_probability >= UNSURE_HIGH:
        return "SPAM"
    if spam_probability <= UNSURE_LOW:
        return "HAM"
    return "UNSURE"


def predict_message(text, bundle):
    """Return a label, spam probability, and the strongest matched features."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Enter a non-empty SMS message.")
    if len(text) > MAX_MESSAGE_CHARS:
        raise ValueError("Messages must be 5,000 characters or fewer.")

    vectorizer = bundle["vectorizer"]
    classifier = bundle["classifier"]
    features = vectorizer.transform([text])
    spam_index = list(classifier.classes_).index("spam")
    spam_probability = float(classifier.predict_proba(features)[0, spam_index])
    matched = int(features.getnnz())
    label = decide_label(spam_probability, matched)

    feature_names = vectorizer.get_feature_names_out()
    spam_log_prob = classifier.feature_log_prob_[spam_index]
    ham_index = list(classifier.classes_).index("ham")
    contributions = features.toarray()[0] * (
        spam_log_prob - classifier.feature_log_prob_[ham_index]
    )
    # Rank learned clues by the direction that supports the call. For UNSURE we
    # still report the strongest contributors but the UI leads with threat signals.
    if label == "SPAM":
        ranked_indices = contributions.argsort()[::-1]
        drivers = [
            {"word": str(feature_names[index]), "impact": float(contributions[index])}
            for index in ranked_indices
            if contributions[index] > 0
        ][:6]
    elif label == "HAM":
        ranked_indices = contributions.argsort()
        drivers = [
            {"word": str(feature_names[index]), "impact": float(-contributions[index])}
            for index in ranked_indices
            if contributions[index] < 0
        ][:6]
    else:
        # UNSURE: no confident direction. Report magnitude-only top terms.
        ranked_indices = contributions.argsort()[::-1]
        drivers = [
            {"word": str(feature_names[index]), "impact": abs(float(contributions[index]))}
            for index in ranked_indices
            if abs(contributions[index]) > 0
        ][:6]

    threat_inspection = inspect_threat_signals(text)
    return {
        "label": label,
        "spam_probability": spam_probability,
        "matched_vocabulary_terms": matched,
        "drivers": drivers,
        "signals": threat_inspection["signals"],
        "domains": threat_inspection["domains"],
    }


def predict_messages(messages, bundle):
    """Classify a list of messages while keeping explanations per row."""
    return [predict_message(message, bundle) for message in messages]
