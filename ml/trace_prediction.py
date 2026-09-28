"""Reproduce one exact test-wallet prediction from the portable model artifact."""

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from features.download_elliptic import sha256_file
from ml.dataset import load_leakage_safe_dataset
from ml.export import explain_row, score_row


DEFAULT_WALLET = "15DaavwDvdatJa1dqHRbhAjeJ9nk8bPVqL"
DEFAULT_MODEL = Path("models/elliptic-logistic-v1/model.json")
DEFAULT_OUTPUT = Path("models/elliptic-logistic-v1/example_prediction.json")


def sigmoid(value):
    return 1 / (1 + math.exp(-value)) if value >= 0 else math.exp(value) / (1 + math.exp(value))


def trace(args):
    artifact = json.loads(args.model.read_text(encoding="utf-8"))
    if sha256_file(Path("data/derived/feature_schema.json")) != artifact["feature_schema_sha256"]:
        raise ValueError("Current feature schema differs from the model artifact")
    bundle = load_leakage_safe_dataset(args.input, args.raw_dir, artifact["training"]["seed"], progress=True)
    if bundle.metadata["source_sha256"] != artifact["training"]["source_sha256"]:
        raise ValueError("Current data files differ from the model's training sources")
    if args.wallet_id not in bundle.frame.index:
        raise ValueError(f"Wallet {args.wallet_id} is not a supervised target")
    if bundle.partitions.loc[args.wallet_id] != "test":
        raise ValueError(f"Wallet {args.wallet_id} is not in the fixed test partition")

    row = bundle.frame.loc[args.wallet_id]
    feature_names = [item["name"] for item in artifact["preprocessing"]["features"]]
    feature_values = {
        name: None if pd.isna(row[name]) else float(row[name])
        for name in feature_names
    }
    probability, log_odds, contributions = score_row(artifact, feature_values)
    prediction = explain_row(artifact, feature_values, limit=8)
    threshold = float(artifact["decision_threshold"])
    contribution_sum = sum(item["contribution"] for item in contributions)
    intercept = float(artifact["model"]["intercept"])
    if not math.isclose(intercept + contribution_sum, log_odds, rel_tol=1e-12, abs_tol=1e-12):
        raise AssertionError("Contribution trace does not sum to the prediction log-odds")

    important_inputs = {}
    for name in (
        "elliptic_f_001", "elliptic_f_002", "elliptic_f_006", "elliptic_f_010",
        "elliptic_f_015", "elliptic_f_020", "elliptic_f_025", "in_degree",
        "out_degree", "unique_neighbors", "direct_illicit_neighbor_count",
        "direct_licit_neighbor_count", "direct_unknown_neighbor_count",
        "direct_illicit_neighbor_ratio", "two_hop_illicit_count",
        "distance_to_other_known_illicit",
    ):
        important_inputs[name] = feature_values[name]

    result = {
        "wallet_id": args.wallet_id,
        "partition": "test",
        "target_metadata": str(row["label"]),
        "target_used_for_scoring": False,
        "model_input_feature_count": len(feature_names),
        "important_input_values": important_inputs,
        "prediction": prediction,
        "exact_calculation": {
            "intercept": intercept,
            "baseline_probability_from_intercept": sigmoid(intercept),
            "sum_of_feature_contributions": contribution_sum,
            "log_odds": log_odds,
            "sigmoid_log_odds": probability,
            "decision_threshold": threshold,
            "threshold_comparison": f"{probability:.15f} >= {threshold:.15f}",
        },
        "all_feature_contributions_by_absolute_magnitude": sorted(
            contributions, key=lambda item: abs(item["contribution"]), reverse=True
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "wallet_id": result["wallet_id"],
        "target_metadata": result["target_metadata"],
        "prediction": result["prediction"],
        "exact_calculation": result["exact_calculation"],
        "full_trace": str(args.output),
    }, indent=2, allow_nan=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wallet-id", default=DEFAULT_WALLET)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--input", type=Path, default=Path("data/derived/canonical_feature_dataset.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    trace(parser.parse_args())


if __name__ == "__main__":
    main()
