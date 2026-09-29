"""Evaluate the complete rule + ML + aggregation path on the frozen test split."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import math
from pathlib import Path
import time
from urllib.parse import urlparse

import numpy as np

from ml.dataset import load_leakage_safe_dataset
from ml.evaluation import ranking_metrics


INT_FIELDS = [
    "timestep",
    "wallet_first_timestep",
    "wallet_last_timestep",
    "wallet_active_span",
    "wallet_observed_timestep_count",
    "in_degree",
    "out_degree",
    "total_degree",
    "unique_in_neighbors",
    "unique_out_neighbors",
    "unique_neighbors",
    "direct_illicit_neighbor_count",
    "direct_licit_neighbor_count",
    "direct_unknown_neighbor_count",
    "one_hop_illicit_count",
    "two_hop_illicit_count",
]


def probabilities(frame, artifact):
    specifications = artifact["preprocessing"]["features"]
    names = [item["name"] for item in specifications]
    matrix = frame.loc[:, names].to_numpy(dtype=float, na_value=np.nan)
    for index, specification in enumerate(specifications):
        missing = ~np.isfinite(matrix[:, index])
        if missing.any():
            imputation = specification["imputation"]
            if imputation is None:
                raise ValueError(f"Missing non-imputable feature {specification['name']}")
            matrix[missing, index] = imputation
        if specification["transform"] == "log1p":
            if (matrix[:, index] < 0).any():
                raise ValueError(f"Negative log1p feature {specification['name']}")
            matrix[:, index] = np.log1p(matrix[:, index])
        matrix[:, index] = (
            matrix[:, index] - specification["mean"]
        ) / specification["scale"]
    logits = matrix @ np.asarray(artifact["model"]["coefficients"], dtype=float)
    logits += float(artifact["model"]["intercept"])
    output = np.empty_like(logits)
    positive = logits >= 0
    output[positive] = 1 / (1 + np.exp(-logits[positive]))
    exponential = np.exp(logits[~positive])
    output[~positive] = exponential / (1 + exponential)
    return output


def rule_masks(frame):
    ratio = frame["direct_illicit_neighbor_ratio"].to_numpy(dtype=float)
    two_hop = frame["two_hop_illicit_count"].to_numpy(dtype=float)
    transactions = frame["elliptic_f_006"].to_numpy(dtype=float)
    return {
        "R1": ratio >= 0.20,
        "R2": two_hop >= 50,
        "R4": ratio >= 0.60,
        "R5": two_hop >= 100,
        "R6": (ratio >= 0.10) & (two_hop >= 2),
        "R7": (ratio >= 0.10) & (transactions >= 2),
    }


def classification_metrics(target, triggered):
    target, triggered = np.asarray(target, dtype=bool), np.asarray(triggered, dtype=bool)
    tp = int((target & triggered).sum())
    fp = int((~target & triggered).sum())
    fn = int((target & ~triggered).sum())
    tn = int((~target & ~triggered).sum())
    return {
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "accuracy": (tp + tn) / len(target),
        "support": tp + fp,
        "support_fraction": (tp + fp) / len(target),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def rule_ids(masks, position):
    return [rule_id for rule_id in ("R1", "R2", "R4", "R5", "R6", "R7") if masks[rule_id][position]]


def primary_rule_ids(matched):
    selected = set(matched)
    if "R4" in selected:
        selected.discard("R1")
    if "R5" in selected:
        selected.discard("R2")
    return [rule_id for rule_id in matched if rule_id in selected]


def vector_payload(wallet_id, row):
    payload = {
        "wallet_id": str(wallet_id),
        "timestep": int(row["timestep"]),
        "elliptic_numeric": [float(row[f"elliptic_f_{index:03d}"]) for index in range(1, 56)],
    }
    for name in INT_FIELDS[1:]:
        payload[name] = int(row[name])
    payload["direct_illicit_neighbor_ratio"] = float(row["direct_illicit_neighbor_ratio"])
    distance = row["distance_to_other_known_illicit"]
    payload["distance_to_other_known_illicit"] = None if not math.isfinite(float(distance)) else int(distance)
    payload["has_other_known_illicit_path"] = bool(row["has_other_known_illicit_path"])
    return payload


def verify_http(url, payloads, expected, workers):
    parsed = urlparse(url)
    if parsed.scheme != "http" or not parsed.hostname:
        raise ValueError("The evaluator currently supports an http:// scoring URL")
    port = parsed.port or 80
    path = parsed.path or "/v1/score"
    chunks = np.array_split(np.arange(len(payloads)), workers)

    def run_chunk(positions):
        connection = http.client.HTTPConnection(parsed.hostname, port, timeout=15)
        failures = []
        completed = 0
        try:
            for position in map(int, positions):
                body = json.dumps(payloads[position], separators=(",", ":"))
                connection.request("POST", path, body=body, headers={"Content-Type": "application/json"})
                response = connection.getresponse()
                content = response.read()
                if response.status != 200:
                    failures.append({"position": position, "status": response.status, "body": content.decode("utf-8", "replace")[:500]})
                    continue
                result = json.loads(content)
                want = expected[position]
                got_matched = [item["rule_id"] for item in result["matched_findings"]]
                got_primary = [item["rule_id"] for item in result["primary_findings"]]
                checks = {
                    "wallet_id": result["wallet_id"] == want["wallet_id"],
                    "probability": abs(result["prediction"]["illicit_probability"] - want["probability"]) <= 1e-12,
                    "predicted_class": result["prediction"]["predicted_class"] == want["predicted_class"],
                    "matched_rules": got_matched == want["matched_rules"],
                    "primary_rules": got_primary == want["primary_rules"],
                    "level": result["level"] == want["level"],
                    "action": result["recommended_action"] == want["action"],
                }
                if not all(checks.values()):
                    failures.append({"position": position, "failed_checks": [name for name, passed in checks.items() if not passed]})
                completed += 1
        finally:
            connection.close()
        return completed, failures

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(run_chunk, chunks))
    duration = time.perf_counter() - started
    failures = [failure for _, items in results for failure in items]
    completed = sum(count for count, _ in results)
    return {
        "url": url,
        "requests": len(payloads),
        "successful_responses": completed,
        "parity_failures": len(failures),
        "failure_examples": failures[:20],
        "workers": workers,
        "duration_seconds": duration,
        "requests_per_second": len(payloads) / duration,
    }


def render_report(path, report):
    metrics = report["metrics"]
    ranking = report["ml_ranking"]
    levels = report["risk_levels_by_target"]
    http = report["http_validation"]
    lines = [
        "# Complete engine evaluation",
        "",
        "This evaluation runs the final rule, ML, aggregation, and HTTP path on the frozen Elliptic++ test partition. "
        "Every row contains the complete feature vector; the target label remains evaluator metadata and is never sent to the API.",
        "",
        "## Leakage-safe test population",
        "",
        f"- Rows: **{report['test_rows']:,}**",
        f"- Licit: **{report['licit']:,}**",
        f"- Illicit: **{report['illicit']:,}**",
        "- Graph intelligence: training-wallet labels only; validation, test, and unknown labels masked",
        f"- ML PR-AUC: **{ranking['average_precision']:.4f}**; ROC-AUC: **{ranking['roc_auc']:.4f}**; Brier score: **{ranking['brier_score']:.4f}**",
        "",
        "## Operating results",
        "",
        "| Output interpreted as a positive flag | Precision | Recall | FPR | Accuracy | Flagged |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, title in [
        ("ml", "ML threshold"),
        ("rules", "Any active rule"),
        ("review", "Final review: rules OR ML"),
        ("high", "High level: rules AND ML"),
    ]:
        item = metrics[key]
        lines.append(
            f"| {title} | {item['precision']:.2%} | {item['recall']:.2%} | "
            f"{item['false_positive_rate']:.2%} | {item['accuracy']:.2%} | {item['support']:,} |"
        )
    lines += [
        "",
        "## Risk levels by target",
        "",
        "| Target | Low | Medium | High |",
        "| --- | ---: | ---: | ---: |",
        f"| Licit | {levels['licit']['low']:,} | {levels['licit']['medium']:,} | {levels['licit']['high']:,} |",
        f"| Illicit | {levels['illicit']['low']:,} | {levels['illicit']['medium']:,} | {levels['illicit']['high']:,} |",
        "",
        "## Go HTTP validation",
        "",
        f"All **{http['requests']:,}** test vectors were posted to `{http['url']}` using {http['workers']} concurrent persistent clients. "
        f"The API returned {http['successful_responses']:,} successful responses with **{http['parity_failures']} parity failures**. "
        f"Observed local throughput was {http['requests_per_second']:.1f} requests/second; this is a functional development-machine check, not a production load benchmark.",
        "",
        "## Assessment",
        "",
        "The capstone is good enough for its educational acceptance contract if the final review policy keeps precision ≥80%, "
        "recall ≥70%, and FPR ≤1%, the ML model keeps PR-AUC ≥0.80, and every HTTP result matches the frozen offline calculation. "
        f"Compared with ML alone, the review policy finds {metrics['review']['tp'] - metrics['ml']['tp']} additional illicit wallets at the cost of "
        f"{metrics['review']['fp'] - metrics['ml']['fp']} additional licit reviews. The medium disagreement queue contains "
        f"{levels['illicit']['medium']} illicit and {levels['licit']['medium']} licit wallets, while {levels['illicit']['low']} illicit wallets remain low risk. "
        "It is not ready for production deployment: "
        "Elliptic++ is a static, transductive research dataset; the split is random rather than time- or entity-separated; public labels are not point-in-time intelligence; "
        "and the review policy has not been calibrated to a real institution's alert capacity or loss function.",
        "",
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/derived/canonical_feature_dataset.csv")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--model", default="models/elliptic-logistic-v1/model.json")
    parser.add_argument("--url", default="http://localhost:8080/v1/score")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", default="analysis/results/engine_evaluation.json")
    parser.add_argument("--report", default="docs/engine_evaluation.md")
    args = parser.parse_args()

    artifact = json.loads(Path(args.model).read_text(encoding="utf-8"))
    bundle = load_leakage_safe_dataset(args.input, args.raw_dir, progress=True)
    selected = bundle.partitions == "test"
    frame = bundle.frame.loc[selected].copy()
    target = (frame["label"] == "illicit").to_numpy(dtype=bool)
    probability = probabilities(frame, artifact)
    ml = probability >= float(artifact["decision_threshold"])
    masks = rule_masks(frame)
    rules = np.logical_or.reduce(list(masks.values()))
    review = rules | ml
    high = rules & ml
    levels = np.where(high, "high", np.where(review, "medium", "low"))

    expected, payloads = [], []
    for position, (wallet_id, row) in enumerate(frame.iterrows()):
        matched = rule_ids(masks, position)
        primary = primary_rule_ids(matched)
        payloads.append(vector_payload(wallet_id, row))
        expected.append({
            "wallet_id": str(wallet_id),
            "probability": float(probability[position]),
            "predicted_class": "illicit" if ml[position] else "licit",
            "matched_rules": matched,
            "primary_rules": primary,
            "level": str(levels[position]),
            "action": "no_review" if levels[position] == "low" else "review",
        })

    level_counts = {}
    for label in ("licit", "illicit"):
        label_mask = frame["label"].to_numpy() == label
        level_counts[label] = {
            level: int((label_mask & (levels == level)).sum()) for level in ("low", "medium", "high")
        }
    report = {
        "dataset": bundle.metadata,
        "test_rows": len(frame),
        "licit": int((~target).sum()),
        "illicit": int(target.sum()),
        "model_version": artifact["model_version"],
        "decision_threshold": artifact["decision_threshold"],
        "metrics": {
            "ml": classification_metrics(target, ml),
            "rules": classification_metrics(target, rules),
            "review": classification_metrics(target, review),
            "high": classification_metrics(target, high),
        },
        "ml_ranking": ranking_metrics(target.astype(np.uint8), probability),
        "risk_levels_by_target": level_counts,
        "http_validation": verify_http(args.url, payloads, expected, args.workers),
        "acceptance": {},
    }
    review_metrics = report["metrics"]["review"]
    requirements = {
        "minimum_average_precision": 0.80,
        "minimum_precision": 0.80,
        "minimum_recall": 0.70,
        "maximum_false_positive_rate": 0.01,
    }
    report["acceptance"] = {
        "requirements": requirements,
        "passed": (
            report["ml_ranking"]["average_precision"] >= requirements["minimum_average_precision"]
            and review_metrics["precision"] >= requirements["minimum_precision"]
            and review_metrics["recall"] >= requirements["minimum_recall"]
            and review_metrics["false_positive_rate"] <= requirements["maximum_false_positive_rate"]
            and report["http_validation"]["parity_failures"] == 0
        ),
        "scope": "educational capstone only",
    }
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    render_report(args.report, report)
    print(json.dumps({
        "test_rows": report["test_rows"],
        "metrics": report["metrics"],
        "http_validation": report["http_validation"],
        "acceptance": report["acceptance"],
    }, indent=2))


if __name__ == "__main__":
    main()
