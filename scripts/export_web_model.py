"""Export the classifier for the static browser demo (GitHub Pages).

Trains the same TF-IDF + Multinomial Naive Bayes bundle the backend trains on
first launch (``train_bundle`` on ``data/sample.csv``) and writes the numbers
the browser needs to reproduce ``predict_message`` without a server:
vocabulary, IDF weights, per-class feature log-probabilities and class priors.

    python scripts/export_web_model.py

Output: frontend/public/model.json (read by src/lib/localModel.ts when the
frontend is built with VITE_STATIC_DEMO=true).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from spamsms.model import DATA_PATH, UNSURE_HIGH, UNSURE_LOW, train_bundle  # noqa: E402

OUT_FILE = ROOT / "frontend" / "public" / "model.json"


def main() -> None:
    data = pd.read_csv(DATA_PATH)
    labels = data["label"].astype(str).str.lower().str.strip()
    bundle = train_bundle(data["message"].astype(str), labels)
    vectorizer, classifier = bundle["vectorizer"], bundle["classifier"]

    classes = [str(c) for c in classifier.classes_]
    model = {
        "source": "Exported by scripts/export_web_model.py from data/sample.csv",
        "training_messages": int(len(data)),
        "vectorizer": {
            "lowercase": True,
            "strip_accents": "unicode",
            "ngram_range": list(vectorizer.ngram_range),
            "sublinear_tf": bool(vectorizer.sublinear_tf),
            "features": [str(f) for f in vectorizer.get_feature_names_out()],
            "idf": [float(v) for v in vectorizer.idf_],
        },
        "classifier": {
            "classes": classes,
            "class_log_prior": [float(v) for v in classifier.class_log_prior_],
            "feature_log_prob": [[float(v) for v in row] for row in classifier.feature_log_prob_],
        },
        "thresholds": {"unsure_low": UNSURE_LOW, "unsure_high": UNSURE_HIGH},
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(model, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT_FILE.relative_to(ROOT)} ({len(model['vectorizer']['features'])} features)")


if __name__ == "__main__":
    main()
