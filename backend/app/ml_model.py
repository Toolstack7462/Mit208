"""Placeholder for the FUTURE DistilBERT-based phishing classifier.

The MVP ships with the transparent rule engine in ``scoring.py``. This module
documents the intended integration point so the advanced model can be dropped
in later without touching the API contract.

Planned approach
----------------
* Fine-tune ``distilbert-base-uncased`` on a labelled phishing/ham corpus.
* Expose ``predict(subject, body) -> (probability, label)``.
* Blend with the rule score, e.g. ``final = 0.6 * model + 0.4 * rules`` or use
  the model probability to adjust the rule score and surface as an extra
  "ML confidence" reason.

This is intentionally NOT wired into the running app for the MVP demo — it has
no heavyweight dependencies (torch/transformers) so the project stays light.
"""
from __future__ import annotations

MODEL_NAME = "distilbert-base-uncased"
ENABLED = False  # flip on once a fine-tuned checkpoint is available


def predict(subject: str, body: str) -> tuple[float, str]:  # pragma: no cover - stub
    raise NotImplementedError(
        "DistilBERT classifier is a planned future enhancement. "
        "The MVP uses the rule-based engine in scoring.py."
    )
