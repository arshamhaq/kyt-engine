"""Validate canonical Elliptic++ feature CSVs without loading the whole table."""

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from .schema import (
    CANONICAL_COLUMNS, FEATURE_MAP, GRAPH_COLUMNS, ML_COLUMNS, NULLABLE_COLUMN,
    REQUIRED_ML_COLUMNS, TEMPORAL_COLUMNS, csv_header,
)

INTEGER_COLUMNS = ["timestep", *TEMPORAL_COLUMNS] + [
    name for name in GRAPH_COLUMNS if name not in {"direct_illicit_neighbor_ratio", NULLABLE_COLUMN}
]


def validate_dataset(path, chunksize=100_000):
    path = Path(path)
    if csv_header(path) != CANONICAL_COLUMNS:
        raise ValueError("Canonical columns/order differ from the reviewed schema; label must be last")
    rows = 0
    seen = set()
    classes = Counter()
    missing = Counter({column: 0 for column in CANONICAL_COLUMNS})
    distance_min, distance_max = None, None
    with pd.read_csv(path, chunksize=chunksize, dtype={"wallet_id": str, "label": str}) as reader:
        for chunk in reader:
            ids = chunk["wallet_id"]
            if ids.isna().any() or (ids.str.strip() != ids).any() or (ids == "").any():
                raise ValueError("Missing or whitespace-padded wallet ID")
            if ids.duplicated().any() or seen.intersection(ids):
                raise ValueError("Duplicate wallet rows")
            seen.update(ids)
            labels = chunk["label"]
            if not labels.isin(["licit", "illicit", "unknown"]).all():
                raise ValueError("Missing or invalid target label")
            classes.update(labels)
            missing.update({column: int(count) for column, count in chunk.isna().sum().items()})
            numeric = chunk[ML_COLUMNS].apply(pd.to_numeric, errors="raise")
            if not np.isfinite(numeric[REQUIRED_ML_COLUMNS].to_numpy(dtype=float)).all():
                raise ValueError("NaN/Inf in required ML features")
            integer_values = numeric[INTEGER_COLUMNS].to_numpy(dtype=float)
            if (integer_values < 0).any() or (integer_values != np.floor(integer_values)).any():
                raise ValueError("Counts, degrees, timesteps, and path flags must be nonnegative integers")
            ratio = numeric["direct_illicit_neighbor_ratio"]
            if not ratio.between(0, 1).all():
                raise ValueError("Graph exposure ratio outside [0,1]")
            degree = numeric["unique_neighbors"]
            counts = numeric[["direct_illicit_neighbor_count", "direct_licit_neighbor_count", "direct_unknown_neighbor_count"]].sum(axis=1)
            if not (counts == degree).all():
                raise ValueError("Direct label counts do not partition unique neighbors")
            expected_ratio = np.divide(numeric["direct_illicit_neighbor_count"], degree,
                                       out=np.zeros(len(chunk), dtype=float), where=degree.to_numpy() > 0)
            if not np.allclose(ratio, expected_ratio, rtol=1e-12, atol=1e-12):
                raise ValueError("Graph exposure ratio differs from its declared denominator")
            if not (numeric["one_hop_illicit_count"] == numeric["direct_illicit_neighbor_count"]).all():
                raise ValueError("One-hop count is inconsistent with direct illicit neighbors")
            if not (numeric["total_degree"] == numeric["in_degree"] + numeric["out_degree"]).all():
                raise ValueError("Total directed degree is inconsistent")
            if not (numeric["unique_in_neighbors"] <= numeric["in_degree"]).all() or not (numeric["unique_out_neighbors"] <= numeric["out_degree"]).all():
                raise ValueError("Unique directed neighbor counts exceed edge degrees")
            lower = numeric[["unique_in_neighbors", "unique_out_neighbors"]].max(axis=1)
            upper = numeric["unique_in_neighbors"] + numeric["unique_out_neighbors"]
            if not ((degree >= lower) & (degree <= upper)).all():
                raise ValueError("Undirected neighbor count inconsistent with directed neighbors")
            distance = numeric[NULLABLE_COLUMN]
            present = distance.notna()
            finite_distance = distance[present].to_numpy(dtype=float)
            if not np.isfinite(finite_distance).all() or (finite_distance < 1).any() or (finite_distance != np.floor(finite_distance)).any():
                raise ValueError("Distance to OTHER illicit nodes must be a positive integer or missing; zero leaks the target")
            flags = numeric["has_other_known_illicit_path"]
            if not flags.isin([0, 1]).all() or not (flags == present.astype(int)).all():
                raise ValueError("Distance presence flag is inconsistent")
            if len(finite_distance):
                smallest, largest = int(finite_distance.min()), int(finite_distance.max())
                distance_min = smallest if distance_min is None else min(distance_min, smallest)
                distance_max = largest if distance_max is None else max(distance_max, largest)
            first, last = numeric["wallet_first_timestep"], numeric["wallet_last_timestep"]
            span = numeric["wallet_active_span"]
            observed = numeric["wallet_observed_timestep_count"]
            if not ((first >= 1) & (last >= first) & (span == last - first) & (numeric["timestep"] == last) & (observed >= 1) & (observed <= span + 1)).all():
                raise ValueError("Invalid discrete temporal summary")
            rows += len(chunk)
    if rows == 0:
        raise ValueError("Canonical dataset is empty")
    distribution = {label: int(classes[label]) for label in ("licit", "illicit", "unknown")}
    return {
        "rows": rows, **distribution, "class_distribution": distribution,
        "supervised_eligible_rows": distribution["licit"] + distribution["illicit"],
        "features": len(ML_COLUMNS), "provided_numeric_features": len(FEATURE_MAP),
        "feature_columns": ML_COLUMNS, "required_ml_feature_columns": REQUIRED_ML_COLUMNS,
        "nullable_feature_columns": [NULLABLE_COLUMN], "missing_values": dict(missing),
        "required_feature_missing_values": sum(missing[column] for column in REQUIRED_ML_COLUMNS),
        "label_is_feature": False, "target_column": "label", "identifier_column": "wallet_id",
        "distance_summary": {"minimum_present": distance_min, "maximum_present": distance_max,
                             "no_other_known_illicit_path_rows": missing[NULLABLE_COLUMN]},
        "validation": {"passed": True, "duplicate_wallet_rows": 0, "invalid_labels": 0,
                       "required_nonfinite_values": 0, "zero_other_illicit_distances": 0},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Optional structural validation report; graph leakage audit requires the builder")
    args = parser.parse_args()
    report = validate_dataset(args.input)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("rows", "class_distribution", "features", "validation")}, indent=2))


if __name__ == "__main__":
    main()
