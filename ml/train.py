"""Train, validate, evaluate, explain, and export the offline ML baseline."""

import argparse
import hashlib
import json
import platform
from pathlib import Path
import time

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from features.download_elliptic import sha256_file
from ml.dataset import SEED, load_leakage_safe_dataset
from ml.evaluation import acceptance, ranking_metrics, select_operating_threshold, classification_metrics
from ml.export import explain_row, score_row
from ml.preprocessing import (
    BEHAVIOR_FEATURES, COMBINED_FEATURES, INTELLIGENCE_FEATURES, fit_preprocessor,
)


MODEL_VERSION = "elliptic-logistic-v1"
CANDIDATE_C = (0.1, 1.0, 10.0)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _target(frame):
    return (frame["label"] == "illicit").to_numpy(dtype=np.uint8)


def _fit_logistic(matrix, target, c):
    model = LogisticRegression(
        C=c, penalty="l2", solver="lbfgs", max_iter=1_000, random_state=SEED
    )
    model.fit(matrix, target)
    if int(model.n_iter_[0]) >= model.max_iter:
        raise RuntimeError("Logistic regression did not converge")
    return model


def _feature_set_diagnostic(frame, partitions, features, c):
    train = partitions == "train"
    validation = partitions == "validation"
    processor, train_matrix = fit_preprocessor(frame.loc[train], features)
    validation_matrix = processor.transform(frame.loc[validation, features])
    model = _fit_logistic(train_matrix, _target(frame.loc[train]), c)
    probability = model.predict_proba(validation_matrix)[:, 1]
    return {
        "feature_count": len(features),
        "C": c,
        "validation": ranking_metrics(_target(frame.loc[validation]), probability),
    }


def _render_report(path, results, example):
    split = results["split"]["partitions"]
    candidates = results["model_selection"]["combined_logistic_candidates"]
    test = results["test"]
    operating = test["operating_point"]
    lines = [
        "# Offline ML analysis", "",
        "This report evaluates a portable logistic-regression baseline on the Elliptic++ Actors dataset. "
        "The output is an educational wallet-risk probability, not evidence of criminal conduct and not a production KYT decision.", "",
        "## Acceptance contract", "",
        "Accuracy is not the acceptance metric: a model predicting every supervised wallet as licit would be about 94.6% accurate. "
        "The frozen capstone gate requires test average precision (PR-AUC) ≥ 0.80 and a validation-selected operating point with "
        "test precision ≥ 0.80, recall ≥ 0.70, and false-positive rate ≤ 1%. No universal industry cutoff exists; production thresholds "
        "depend on alert-review capacity and the relative cost of false positives and false negatives.", "",
        "Google's classification guidance recommends precision, recall, and threshold tuning over accuracy for imbalanced data: "
        "https://developers.google.com/machine-learning/crash-course/classification/accuracy-precision-recall", "",
        f"**Acceptance result: {'PASS' if results['acceptance']['passed'] else 'FAIL'}**", "",
        "## Leakage-safe data protocol", "",
        "Unknown targets are excluded from supervised learning but remain graph nodes. The target label and wallet ID never enter the model. "
        "Only training-wallet labels form the simulated intelligence inventory; validation and test labels are masked to unknown before all "
        "neighbor-label, two-hop, and distance features are rebuilt. The target itself remains excluded from its intelligence features.", "",
        "| Partition | Rows | Licit | Illicit | Prevalence |", "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name in ("train", "validation", "test"):
        item = split[name]
        lines.append(f"| {name} | {item['rows']:,} | {item['licit']:,} | {item['illicit']:,} | {item['illicit_prevalence']:.2%} |")
    history = results.get("development_history", [])
    if history:
        first = history[0]
        lines.extend([
            "", "### Evaluation-history disclosure", "",
            "The first frozen threshold policy maximized recall up to the validation FPR boundary. It achieved "
            f"test AP {first['average_precision']:.4f}, precision {first['precision']:.4f}, recall {first['recall']:.4f}, and "
            f"FPR {first['false_positive_rate']:.4%}; it failed the 1% FPR gate. The implementation was corrected to the already planned "
            "validation F0.5 policy, which favors precision. Because the same test partition was observed before this correction, the final "
            "numbers are a development-holdout result rather than a pristine one-shot test. A new external or time-separated dataset is "
            "required for an unbiased final deployment estimate.", "",
        ])
    lines.extend([
        "", "This remains a static, transductive experiment: full topology and lifetime aggregates are visible, wallets from related entities "
        "may cross partitions, and public labels have no point-in-time publication timestamps. Results are not a deployment claim.", "",
        "## Model selection", "",
        "The deployable family was fixed as L2 logistic regression. Three regularization values were compared on validation average precision; "
        "the test partition was not consulted. A histogram-gradient-boosting model is reported only as a nonlinear validation benchmark.", "",
        "| Model | Validation average precision | ROC AUC | Brier score |", "| --- | ---: | ---: | ---: |",
    ])
    for candidate in candidates:
        metric = candidate["validation"]
        lines.append(f"| Combined logistic C={candidate['C']:g} | {metric['average_precision']:.4f} | {metric['roc_auc']:.4f} | {metric['brier_score']:.4f} |")
    for name, item in results["model_selection"]["feature_set_diagnostics"].items():
        metric = item["validation"]
        lines.append(f"| {name} logistic | {metric['average_precision']:.4f} | {metric['roc_auc']:.4f} | {metric['brier_score']:.4f} |")
    tree = results["model_selection"]["nonlinear_benchmark"]["validation"]
    lines.append(f"| Gradient boosting benchmark | {tree['average_precision']:.4f} | {tree['roc_auc']:.4f} | {tree['brier_score']:.4f} |")
    lines.extend([
        "", "## Held-out test result", "",
        f"The selected model uses **{results['selected_model']['feature_count']} features** and C={results['selected_model']['C']:g}. "
        f"Its decision threshold **{operating['threshold']:.6f}** maximizes validation F0.5 subject to the validation precision/FPR constraints.", "",
        "| Metric | Test value |", "| --- | ---: |",
        f"| Average precision (PR-AUC) | {test['ranking']['average_precision']:.4f} |",
        f"| ROC AUC | {test['ranking']['roc_auc']:.4f} |",
        f"| Brier score | {test['ranking']['brier_score']:.4f} |",
        f"| Accuracy | {operating['accuracy']:.4f} |",
        f"| Precision | {operating['precision']:.4f} |",
        f"| Recall | {operating['recall']:.4f} |",
        f"| False-positive rate | {operating['false_positive_rate']:.4f} |",
        f"| F0.5 | {operating['f0_5']:.4f} |",
        f"| Triggered wallets | {operating['support']:,} |", "",
        f"Confusion matrix: TP={operating['tp']:,}, FP={operating['fp']:,}, FN={operating['fn']:,}, TN={operating['tn']:,}.", "",
        "## Example explainable prediction", "",
        f"Test wallet `{example['wallet_id']}` has Elliptic++ target `{example['target_label']}`. The target was unavailable to feature "
        "construction, preprocessing, training, threshold selection, and scoring.", "",
        "```json", json.dumps(example["prediction"], indent=2, allow_nan=False), "```", "",
        "Each contribution is the feature's additive effect on model log-odds after the exported transformation and standardization. "
        "A large contribution explains the model calculation; it does not establish causation. Correlated aggregate fields can create large "
        "offsetting positive and negative contributions, so factors must be interpreted together rather than as independent evidence.", "",
        "## Artifact", "",
        "`models/elliptic-logistic-v1/model.json` contains the ordered schema, transformations, imputations, scaling values, coefficients, "
        "intercept, and decision threshold. It is the exact model evaluated above and is reproduced by the native Go predictor without Python. "
        "Risk aggregation remains out of scope for this step.", "",
    ])
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def run(args):
    started = time.perf_counter()
    output_dir = Path(args.output_dir)
    previous_metrics_path = output_dir / "metrics.json"
    development_history = []
    if previous_metrics_path.exists():
        previous = json.loads(previous_metrics_path.read_text(encoding="utf-8"))
        development_history.extend(previous.get("development_history", []))
        if not development_history and not previous.get("acceptance", {}).get("passed", False):
            prior = previous["test"]
            development_history.append({
                "reason": "initial recall-maximizing threshold policy failed the strict FPR gate",
                "average_precision": prior["ranking"]["average_precision"],
                "precision": prior["operating_point"]["precision"],
                "recall": prior["operating_point"]["recall"],
                "false_positive_rate": prior["operating_point"]["false_positive_rate"],
                "threshold": prior["operating_point"]["threshold"],
            })
    bundle = load_leakage_safe_dataset(args.input, args.raw_dir, args.seed, progress=True)
    frame, partitions = bundle.frame, bundle.partitions
    train = partitions == "train"
    validation = partitions == "validation"
    test = partitions == "test"
    y_train = _target(frame.loc[train])
    y_validation = _target(frame.loc[validation])
    y_test = _target(frame.loc[test])

    print("Fitting portable combined logistic candidates", flush=True)
    processor, train_matrix = fit_preprocessor(frame.loc[train], COMBINED_FEATURES)
    validation_matrix = processor.transform(frame.loc[validation, COMBINED_FEATURES])
    test_matrix = processor.transform(frame.loc[test, COMBINED_FEATURES])
    fitted, candidates = {}, []
    for c in CANDIDATE_C:
        model = _fit_logistic(train_matrix, y_train, c)
        probability = model.predict_proba(validation_matrix)[:, 1]
        item = {"C": c, "validation": ranking_metrics(y_validation, probability)}
        candidates.append(item)
        fitted[c] = (model, probability)
        print(f"  C={c:g}: validation AP={item['validation']['average_precision']:.4f}", flush=True)
    selected = max(candidates, key=lambda item: (item["validation"]["average_precision"], -item["C"]))
    model, validation_probability = fitted[selected["C"]]
    validation_operating = select_operating_threshold(y_validation, validation_probability)
    threshold = validation_operating["threshold"]

    print("Fitting feature-family diagnostics and nonlinear benchmark", flush=True)
    diagnostics = {
        "behavior_only": _feature_set_diagnostic(frame, partitions, BEHAVIOR_FEATURES, selected["C"]),
        "intelligence_only": _feature_set_diagnostic(frame, partitions, INTELLIGENCE_FEATURES, selected["C"]),
    }
    tree = HistGradientBoostingClassifier(
        learning_rate=0.08, max_iter=150, max_leaf_nodes=31,
        l2_regularization=1.0, random_state=args.seed,
    ).fit(train_matrix, y_train)
    tree_probability = tree.predict_proba(validation_matrix)[:, 1]
    tree_metrics = ranking_metrics(y_validation, tree_probability)

    schema_hash = sha256_file(Path("data/derived/feature_schema.json"))
    artifact = {
        "format_version": 1,
        "model_version": MODEL_VERSION,
        "model_type": "binary_logistic_regression",
        "positive_label": "illicit",
        "negative_label": "licit",
        "decision_threshold": threshold,
        "feature_schema_sha256": schema_hash,
        "preprocessing": processor.to_dict(),
        "model": {
            "intercept": float(model.intercept_[0]),
            "coefficients": model.coef_[0].astype(float).tolist(),
        },
        "training": {
            "seed": args.seed,
            "C": selected["C"],
            "fit_partition": "train",
            "intelligence_inventory": "training labels only",
            "validation_selected_threshold": threshold,
            "threshold_selection": "maximize validation F0.5 subject to precision >= 0.80 and FPR <= 0.01",
            "source_sha256": bundle.metadata["source_sha256"],
        },
    }

    # Freeze the exact model and threshold in memory before test scoring.
    frozen_digest = hashlib.sha256(
        json.dumps(artifact, sort_keys=True, allow_nan=False).encode("utf-8")
    ).hexdigest()
    print("Evaluating the frozen model once on the test partition", flush=True)
    test_probability = model.predict_proba(test_matrix)[:, 1]
    test_ranking = ranking_metrics(y_test, test_probability)
    test_operating = classification_metrics(y_test, test_probability, threshold)
    test_results = {"ranking": test_ranking, "operating_point": test_operating}
    gate = acceptance(test_results)

    test_frame = frame.loc[test]
    positive_candidates = np.flatnonzero((y_test == 1) & (test_probability >= threshold))
    if not len(positive_candidates):
        positive_candidates = np.flatnonzero(y_test == 1)
    example_position = int(positive_candidates[np.argmax(test_probability[positive_candidates])])
    example_row = test_frame.iloc[example_position]
    row_mapping = {
        name: (None if pd.isna(example_row[name]) else float(example_row[name]))
        for name in COMBINED_FEATURES
    }
    exported_probability, _, _ = score_row(artifact, row_mapping)
    if not np.isclose(exported_probability, test_probability[example_position], rtol=1e-12, atol=1e-12):
        raise AssertionError("Portable scorer differs from scikit-learn")
    example = {
        "wallet_id": str(test_frame.index[example_position]),
        "target_label": str(example_row["label"]),
        "prediction": explain_row(artifact, row_mapping),
    }

    results = {
        "acceptance": gate,
        "split": bundle.metadata,
        "selected_model": {
            "model_version": MODEL_VERSION,
            "C": selected["C"],
            "feature_count": len(COMBINED_FEATURES),
            "frozen_before_test": True,
            "frozen_artifact_sha256_before_test": frozen_digest,
        },
        "model_selection": {
            "selection_metric": "validation average precision",
            "threshold_selection_metric": "validation F0.5 subject to precision >= 0.80 and FPR <= 0.01",
            "combined_logistic_candidates": candidates,
            "selected_validation_operating_point": validation_operating,
            "feature_set_diagnostics": diagnostics,
            "nonlinear_benchmark": {"name": "histogram_gradient_boosting", "validation": tree_metrics},
            "test_used_for_selection": False,
        },
        "test": test_results,
        "development_history": development_history,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "duration_seconds": round(time.perf_counter() - started, 3),
    }
    artifact["evaluation"] = {
        "acceptance": gate,
        "test": test_results,
        "frozen_artifact_sha256_before_test": frozen_digest,
    }

    write_json(output_dir / "model.json", artifact)
    write_json(output_dir / "metrics.json", results)
    write_json(output_dir / "split_manifest.json", bundle.metadata)
    _render_report(args.report, results, example)
    print(f"Test AP={test_ranking['average_precision']:.4f}; precision={test_operating['precision']:.4f}; "
          f"recall={test_operating['recall']:.4f}; FPR={test_operating['false_positive_rate']:.4f}", flush=True)
    print(f"Acceptance: {'PASS' if gate['passed'] else 'FAIL'}", flush=True)
    if not gate["passed"]:
        raise SystemExit("The frozen model did not meet the predeclared capstone acceptance gate")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/derived/canonical_feature_dataset.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("models/elliptic-logistic-v1"))
    parser.add_argument("--report", type=Path, default=Path("docs/ml_analysis.md"))
    parser.add_argument("--seed", type=int, default=SEED)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
