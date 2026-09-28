"""Portable logistic-regression artifact and independent scorer."""

import math

from features.schema import FEATURE_MAP


def score_row(artifact, row):
    """Score one mapping without importing pandas, NumPy, or scikit-learn."""
    logit = float(artifact["model"]["intercept"])
    contributions = []
    for specification, coefficient in zip(
        artifact["preprocessing"]["features"], artifact["model"]["coefficients"]
    ):
        name = specification["name"]
        raw = row[name]
        value = float(raw) if raw is not None else math.nan
        if not math.isfinite(value):
            value = specification["imputation"]
            if value is None:
                raise ValueError(f"Missing non-imputable feature {name}")
        if specification["transform"] == "log1p":
            if value < 0:
                raise ValueError(f"Negative log1p feature {name}")
            value = math.log1p(value)
        standardized = (value - specification["mean"]) / specification["scale"]
        contribution = standardized * coefficient
        logit += contribution
        contributions.append({
            "feature": name,
            "source_name": FEATURE_MAP.get(name, name),
            "raw_value": None if raw is None or not math.isfinite(float(raw)) else float(raw),
            "standardized_value": standardized,
            "coefficient": coefficient,
            "contribution": contribution,
        })
    probability = 1 / (1 + math.exp(-logit)) if logit >= 0 else math.exp(logit) / (1 + math.exp(logit))
    return probability, logit, contributions


def explain_row(artifact, row, limit=5):
    probability, logit, contributions = score_row(artifact, row)
    positive = sorted((item for item in contributions if item["contribution"] > 0),
                      key=lambda item: item["contribution"], reverse=True)[:limit]
    negative = sorted((item for item in contributions if item["contribution"] < 0),
                      key=lambda item: item["contribution"])[:limit]
    threshold = artifact["decision_threshold"]
    return {
        "model_version": artifact["model_version"],
        "illicit_probability": probability,
        "decision_threshold": threshold,
        "predicted_class": "illicit" if probability >= threshold else "licit",
        "log_odds": logit,
        "top_positive_factors": positive,
        "top_negative_factors": negative,
    }
