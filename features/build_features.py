"""Build one canonical feature row per wallet from inspected Elliptic++ files."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .download_elliptic import sha256_file
from .graph_features import audit_target_label_exclusion, derive_graph_features, graph_from_csv
from .schema import (
    CANONICAL_COLUMNS, CLASS_LABELS, FEATURE_MAP, GRAPH_COLUMNS, ML_COLUMNS,
    NULLABLE_COLUMN, REQUIRED_ML_COLUMNS, WALLET_FEATURE_COLUMNS, load_classes, require_schema,
)
from .validate_features import validate_dataset


def wallet_observations(path):
    require_schema(path)
    observations = pd.read_csv(path, usecols=["address", "Time step"],
                               dtype={"address": str, "Time step": np.int64}, keep_default_na=False)
    if len(observations) == 0:
        raise ValueError("Wallet feature file is empty")
    if (observations["address"] == "").any() or (observations["address"].str.strip() != observations["address"]).any():
        raise ValueError("Blank or whitespace-padded wallet IDs")
    if (observations["Time step"] < 1).any():
        raise ValueError("Dataset timesteps must be positive integers")
    raw_rows = len(observations)
    duplicate_rows = observations.duplicated(["address", "Time step"])
    duplicate_keys = pd.MultiIndex.from_frame(observations.loc[duplicate_rows, ["address", "Time step"]]).unique()
    observations = observations.drop_duplicates(["address", "Time step"])
    wallet_ids = pd.Index(observations["address"].unique(), name="wallet_id")
    temporal = observations.groupby("address", sort=False)["Time step"].agg(["min", "max", "nunique"]).reindex(wallet_ids)
    result = pd.DataFrame({
        "wallet_first_timestep": temporal["min"], "wallet_last_timestep": temporal["max"],
        "wallet_active_span": temporal["max"] - temporal["min"],
        "wallet_observed_timestep_count": temporal["nunique"],
    }, index=wallet_ids)
    return wallet_ids, result, {
        "raw_feature_rows": raw_rows, "unique_wallet_timestep_rows": len(observations), "wallet_rows": len(wallet_ids),
        "wallets_with_multiple_timesteps": int((temporal["nunique"] > 1).sum()),
        "timestep_min": int(temporal["min"].min()), "timestep_max": int(temporal["max"].max()),
        "duplicate_wallet_timestep_rows_collapsed": int(duplicate_rows.sum()),
        "duplicate_wallet_timestep_keys": len(duplicate_keys),
        "duplicate_policy": "collapse only numerically identical rows; reject conflicting values",
        "numeric_row_selection": "latest observed dataset timestep, without consulting labels",
    }, duplicate_keys


def latest_numeric_features(path, wallet_ids, temporal, chunksize, duplicate_keys=None):
    values = np.empty((len(wallet_ids), len(FEATURE_MAP)), dtype=np.float64)
    filled = np.zeros(len(wallet_ids), dtype=bool)
    duplicate_keys = pd.MultiIndex.from_tuples([], names=["address", "Time step"]) if duplicate_keys is None else duplicate_keys
    duplicate_values = np.empty((len(duplicate_keys), len(FEATURE_MAP)), dtype=np.float64)
    duplicate_filled = np.zeros(len(duplicate_keys), dtype=bool)
    last = temporal["wallet_last_timestep"].to_numpy()
    dtypes = {name: np.float64 for name in WALLET_FEATURE_COLUMNS}
    dtypes.update({"address": str, "Time step": np.int64})
    with pd.read_csv(path, chunksize=chunksize, dtype=dtypes) as reader:
        for chunk in reader:
            numeric = chunk[list(WALLET_FEATURE_COLUMNS)].to_numpy(dtype=float)
            if not np.isfinite(numeric).all():
                raise ValueError("Provided wallet numeric features contain NaN/Inf; no silent imputation is permitted")
            if len(duplicate_keys):
                keys = pd.MultiIndex.from_frame(chunk[["address", "Time step"]])
                duplicate_positions = duplicate_keys.get_indexer(keys)
                repeated = duplicate_positions >= 0
                positions_in_duplicate_table = duplicate_positions[repeated]
                repeated_values = numeric[repeated]
                if len(repeated_values):
                    unique_positions, first, inverse = np.unique(positions_in_duplicate_table, return_index=True, return_inverse=True)
                    if not np.array_equal(repeated_values, repeated_values[first[inverse]]):
                        raise ValueError("Conflicting duplicate wallet/timestep numeric observations")
                    already_filled = duplicate_filled[positions_in_duplicate_table]
                    if not np.array_equal(repeated_values[already_filled], duplicate_values[positions_in_duplicate_table[already_filled]]):
                        raise ValueError("Conflicting duplicate wallet/timestep numeric observations")
                    duplicate_values[unique_positions] = repeated_values[first]
                    duplicate_filled[unique_positions] = True
            positions = wallet_ids.get_indexer(chunk["address"])
            if (positions < 0).any():
                raise ValueError("Wallet feature IDs changed between inspection passes")
            selected = chunk["Time step"].to_numpy() == last[positions]
            values[positions[selected]] = numeric[selected]
            filled[positions[selected]] = True
    if not filled.all():
        raise ValueError("Some wallets have no selected numeric observation")
    return pd.DataFrame(values, columns=list(FEATURE_MAP), index=wallet_ids)


def source_provenance(raw_dir):
    manifest_path = raw_dir / "source_manifest.json"
    if not manifest_path.exists():
        return {"verified_manifest": False, "note": "Schemas verified; source hashes are not asserted for manually supplied/synthetic inputs."}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verified = []
    for entry in manifest["files"]:
        path = raw_dir / entry["filename"]
        if not path.exists() or path.stat().st_size != entry["size_bytes"] or sha256_file(path) != entry["sha256"]:
            raise ValueError(f"Source differs from the download manifest: {path}")
        verified.append({key: entry[key] for key in ("filename", "sha256", "size_bytes")})
    return {"verified_manifest": True, "repository": manifest["repository"],
            "revision": manifest["revision"], "files": verified}


def build_dataset(raw_dir, output, chunksize=100_000, audit_targets=16):
    if chunksize < 1 or audit_targets < 1:
        raise ValueError("chunksize and audit_targets must be positive")
    started = time.perf_counter()
    raw_dir, output = Path(raw_dir), Path(output)
    if output.resolve().is_relative_to(raw_dir.resolve()):
        raise ValueError("Derived output must not overwrite raw inputs")
    provenance = source_provenance(raw_dir)
    print("Inspecting wallet observations and loading labels", flush=True)
    ids, temporal, observation_report, duplicate_keys = wallet_observations(raw_dir / "wallets_features.csv")
    classes = load_classes(raw_dir / "wallets_classes.csv")
    print(f"Selecting numeric observations for {len(ids):,} wallets", flush=True)
    numeric = latest_numeric_features(raw_dir / "wallets_features.csv", ids, temporal, chunksize, duplicate_keys)
    print("Loading compact directed/undirected adjacency arrays", flush=True)
    graph = graph_from_csv(raw_dir / "AddrAddr_edgelist.csv", ids, classes, chunksize)
    graph_frame = derive_graph_features(graph, progress=True)
    print("Auditing graph features against independent per-target traversals", flush=True)
    audit = audit_target_label_exclusion(graph, graph_frame, len(ids), audit_targets)
    # Target labels are joined only after all numeric, temporal, and graph features exist.
    features = pd.concat([numeric, temporal, graph_frame.reindex(ids)], axis=1)
    features.insert(0, "timestep", temporal["wallet_last_timestep"])
    features.insert(0, "wallet_id", ids)
    target_codes = classes.reindex(ids)
    missing_target_classes = int(target_codes.isna().sum())
    features["label"] = target_codes.fillna("3").map(CLASS_LABELS)
    features = features[CANONICAL_COLUMNS]
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".part")
    print(f"Writing and validating {output}", flush=True)
    features.to_csv(partial, index=False, chunksize=25_000, float_format="%.17g", na_rep="")
    report = validate_dataset(partial, chunksize)
    schema = {
        "schema_version": 1, "row_granularity": "one latest observation per wallet",
        "columns": CANONICAL_COLUMNS, "feature_columns": ML_COLUMNS,
        "required_ml_feature_columns": REQUIRED_ML_COLUMNS, "target_column": "label",
        "identifier_column": "wallet_id", "provided_feature_mapping": FEATURE_MAP,
        "provided_numeric_type": "float64", "integer_feature_type": "int64",
        "nullable_distance": {"column": NULLABLE_COLUMN, "type": "nullable positive integer",
                              "missing_serialization": "empty CSV field", "presence_flag": "has_other_known_illicit_path"},
        "graph_intelligence_direction": "undirected", "degree_direction": "directed",
        "target_label_excluded": True, "class_mapping": CLASS_LABELS,
    }
    report.update({
        "dataset": "Elliptic++ Actors", "output_file": output.name,
        "source_provenance": provenance, "observations": observation_report,
        "graph": graph.statistics, "missing_target_classes_defaulted_to_unknown": missing_target_classes,
        "target_label_exclusion_audit": audit, "duration_seconds": round(time.perf_counter() - started, 3),
        "limitations": [
            "Static public neighbor labels are simulated historical intelligence, not point-in-time attribution.",
            "Provided wallet aggregates and the union graph may include future information relative to an observation timestep.",
            "Graph neighbor exposure is not monetary exposure; actor edges have no transferred value.",
        ],
    })
    partial.replace(output)
    (output.parent / "feature_schema.json").write_text(json.dumps(schema, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output.parent / "feature_report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("rows", "class_distribution", "features", "distance_summary", "duration_seconds")}, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("data/derived/canonical_feature_dataset.csv"))
    parser.add_argument("--chunksize", type=int, default=100_000)
    parser.add_argument("--audit-targets", type=int, default=16)
    args = parser.parse_args()
    build_dataset(args.raw_dir, args.output, args.chunksize, args.audit_targets)


if __name__ == "__main__":
    main()
