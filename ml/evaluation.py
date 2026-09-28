"""Metrics and threshold selection for imbalanced binary classification."""

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


MIN_AVERAGE_PRECISION = 0.80
MIN_PRECISION = 0.80
MIN_RECALL = 0.70
MAX_FALSE_POSITIVE_RATE = 0.01


def classification_metrics(target, probability, threshold):
    target = np.asarray(target, dtype=bool)
    probability = np.asarray(probability, dtype=float)
    predicted = probability >= threshold
    tp = int(np.sum(predicted & target))
    fp = int(np.sum(predicted & ~target))
    fn = int(np.sum(~predicted & target))
    tn = int(np.sum(~predicted & ~target))
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    fpr = fp / (fp + tn) if fp + tn else None
    f0_5 = (
        1.25 * precision * recall / (0.25 * precision + recall)
        if precision is not None and recall is not None and precision + recall else 0.0
    )
    return {
        "threshold": float(threshold),
        "accuracy": (tp + tn) / len(target),
        "precision": precision,
        "recall": recall,
        "false_positive_rate": fpr,
        "f0_5": f0_5,
        "support": tp + fp,
        "support_fraction": (tp + fp) / len(target),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def ranking_metrics(target, probability):
    target = np.asarray(target, dtype=bool)
    probability = np.asarray(probability, dtype=float)
    if not np.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any():
        raise ValueError("Probabilities must be finite and within [0,1]")
    return {
        "average_precision": float(average_precision_score(target, probability)),
        "roc_auc": float(roc_auc_score(target, probability)),
        "brier_score": float(brier_score_loss(target, probability)),
        "positive_prevalence": float(target.mean()),
    }


def select_operating_threshold(target, probability, min_precision=MIN_PRECISION, max_fpr=MAX_FALSE_POSITIVE_RATE):
    """Maximize validation F0.5 subject to the predeclared precision/FPR gates."""
    target = np.asarray(target, dtype=bool)
    probability = np.asarray(probability, dtype=float)
    order = np.argsort(-probability, kind="mergesort")
    scores, actual = probability[order], target[order]
    cumulative_tp = np.cumsum(actual)
    cumulative_fp = np.cumsum(~actual)
    ends = np.flatnonzero(np.r_[scores[1:] != scores[:-1], True])
    tp, fp = cumulative_tp[ends], cumulative_fp[ends]
    positives, negatives = int(target.sum()), int((~target).sum())
    precision = tp / (tp + fp)
    recall = tp / positives
    fpr = fp / negatives
    f0_5 = 1.25 * precision * recall / (0.25 * precision + recall)
    eligible = (precision >= min_precision) & (fpr <= max_fpr)
    if not eligible.any():
        raise ValueError("No validation threshold satisfies the precision and false-positive gates")
    candidates = np.flatnonzero(eligible)
    # F0.5 favors precision. Ties prefer recall and then the higher threshold.
    best = max(candidates, key=lambda i: (f0_5[i], recall[i], scores[ends[i]]))
    return classification_metrics(target, probability, float(scores[ends[best]]))


def acceptance(metrics):
    operating = metrics["operating_point"]
    passed = (
        metrics["ranking"]["average_precision"] >= MIN_AVERAGE_PRECISION
        and operating["precision"] is not None and operating["precision"] >= MIN_PRECISION
        and operating["recall"] is not None and operating["recall"] >= MIN_RECALL
        and operating["false_positive_rate"] is not None
        and operating["false_positive_rate"] <= MAX_FALSE_POSITIVE_RATE
    )
    return {
        "passed": bool(passed),
        "requirements": {
            "minimum_average_precision": MIN_AVERAGE_PRECISION,
            "minimum_precision": MIN_PRECISION,
            "minimum_recall": MIN_RECALL,
            "maximum_false_positive_rate": MAX_FALSE_POSITIVE_RATE,
        },
    }
