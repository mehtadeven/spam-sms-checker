"""Model core tests (ported from old tests/test_utils.py) + tie-break regression."""

from __future__ import annotations

import pandas as pd
import pytest

from spamsms.model import (
    DATA_PATH,
    decide_label,
    inspect_threat_signals,
    predict_message,
    train_bundle,
)


@pytest.fixture(scope="module")
def bundle():
    data = pd.read_csv(DATA_PATH)
    return train_bundle(
        data["message"].astype(str),
        data["label"].astype(str).str.lower(),
    )


class TestThreatSignals:
    def test_flags_shortened_links_and_code_requests(self):
        inspection = inspect_threat_signals(
            "URGENT: send this code to verify your account at https://bit.ly/claim"
        )
        titles = {s["title"] for s in inspection["signals"]}
        assert "Link uses a URL shortener" in titles
        assert "Requests a secret or verification code" in titles
        assert inspection["domains"] == ["bit.ly"]

    def test_detects_example_domain(self):
        inspection = inspect_threat_signals("Check your account at https://secure-login.example")
        assert inspection["domains"] == ["secure-login.example"]
        assert inspection["signals"]

    def test_ignores_malformed_link_without_crashing(self):
        assert inspect_threat_signals("Look at https://[::1")["domains"] == []


class TestPredictions:
    def test_spam_fixture_is_spam_with_clues_and_signals(self, bundle):
        result = predict_message(
            "URGENT! Your account is locked. Verify your PIN at https://bit.ly/account", bundle
        )
        assert result["label"] == "SPAM"
        assert result["spam_probability"] >= 0.5
        assert result["drivers"]
        assert "Link uses a URL shortener" in {s["title"] for s in result["signals"]}

    def test_rejects_over_limit(self, bundle):
        with pytest.raises(ValueError, match="5,000"):
            predict_message("x" * 5001, bundle)

    def test_rejects_blank(self, bundle):
        with pytest.raises(ValueError):
            predict_message("   ", bundle)


class TestTieBreakFix:
    """Regression: OOV text used to hit the exact-0.5 tie and be labeled SPAM."""

    @pytest.mark.parametrize("word", ["ok", "sure", "k", "later", "omw", "hmm"])
    def test_benign_oov_reply_is_not_spam(self, bundle, word):
        result = predict_message(word, bundle)
        assert result["label"] == "UNSURE"
        assert result["matched_vocabulary_terms"] == 0

    def test_decide_label_boundaries(self):
        assert decide_label(0.500, 0) == "UNSURE"      # zero vocab -> unsure
        assert decide_label(0.500, 5) == "UNSURE"      # mid band -> unsure
        assert decide_label(0.70, 5) == "SPAM"
        assert decide_label(0.20, 5) == "HAM"
