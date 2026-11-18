"""Evaluate and save the SMS spam classifier.

Run from the repo root:  python train_model.py
Place a larger, appropriately licensed CSV with label,message columns at
data/sample.csv before retraining. Writes models/metrics.json and models/model.joblib.
"""

import json
import sys
from pathlib import Path

# Make the backend package importable when run from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from spamsms.model import (
    DATA_PATH,
    MODEL_PATH,
    UNSURE_HIGH,
    UNSURE_LOW,
    decide_label,
    train_bundle,
)


def main():
    data = pd.read_csv(DATA_PATH)
    required = {"label", "message"}
    if not required.issubset(data.columns):
        raise ValueError("Training data must have label and message columns.")
    data = data.dropna(subset=["label", "message"]).copy()
    data["label"] = data["label"].astype(str).str.lower().str.strip()
    data["message"] = data["message"].astype(str).str.strip()
    data = data[data["label"].isin(["ham", "spam"]) & data["message"].ne("")]
    if data["label"].nunique() != 2 or data["label"].value_counts().min() < 2:
        raise ValueError("Training data needs at least two messages for each label.")

    train_messages, test_messages, train_labels, test_labels = train_test_split(
        data["message"],
        data["label"],
        test_size=0.25,
        random_state=42,
        stratify=data["label"],
    )
    evaluation_bundle = train_bundle(train_messages, train_labels)
    vectorizer = evaluation_bundle["vectorizer"]
    classifier = evaluation_bundle["classifier"]
    test_features = vectorizer.transform(test_messages)
    predicted = classifier.predict(test_features)

    # Binary argmax metrics keep their original meaning (unchanged by the band).
    spam_index = list(classifier.classes_).index("spam")
    probabilities = classifier.predict_proba(test_features)[:, spam_index]
    nnz = test_features.getnnz(axis=1)
    decided = [decide_label(p, int(n)) for p, n in zip(probabilities, nnz)]
    unsure_count = sum(1 for d in decided if d == "UNSURE")

    metrics = {
        "accuracy": float(accuracy_score(test_labels, predicted)),
        "report": classification_report(
            test_labels, predicted, output_dict=True, zero_division=0
        ),
        "confusion_matrix": confusion_matrix(
            test_labels, predicted, labels=["ham", "spam"]
        ).tolist(),
        "test_size": int(len(test_labels)),
        "training_size": int(len(train_labels)),
        # New: the presentation decision policy is separate from binary training.
        "decision_policy": {
            "low": UNSURE_LOW,
            "high": UNSURE_HIGH,
            "unsure_count_on_holdout": unsure_count,
            "note": "accuracy/report/confusion_matrix are binary argmax; unsure_* describe the SPAM/HAM/UNSURE display band.",
        },
    }

    bundle = train_bundle(data["message"], data["label"])
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODEL_PATH, compress=3)
    metrics_path = MODEL_PATH.parent / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print("Model saved to:", MODEL_PATH)
    print("Evaluation accuracy: {:.1%}".format(metrics["accuracy"]))
    print("Unsure on holdout: {} / {}".format(unsure_count, len(test_labels)))
    print("Metrics saved to:", metrics_path)


if __name__ == "__main__":
    main()
