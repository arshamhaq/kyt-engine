"""Leakage-safe supervised dataset preparation for the Elliptic++ capstone."""

from dataclasses import dataclass
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from features.download_elliptic import sha256_file
from features.graph_features import audit_target_label_exclusion, derive_graph_features, graph_from_csv
from features.schema import CANONICAL_COLUMNS, GRAPH_COLUMNS, load_classes


SEED = 20260928
TRAIN_FRACTION = 0.70
VALIDATION_FRACTION = 0.15
TEST_FRACTION = 0.15


@dataclass
class DatasetBundle:
    frame: pd.DataFrame
    partitions: pd.Series
    metadata: dict


def id_digest(ids):
    return hashlib.sha256("\n".join(sorted(map(str, ids))).encode("utf-8")).hexdigest()


def stratified_three_way_split(labels, seed=SEED):
    """Return deterministic train/validation/test names for binary targets."""
    labels = np.asarray(labels)
    if not np.isin(labels, ["licit", "illicit"]).all():
        raise ValueError("Only licit and illicit labels may enter the supervised split")
    rng = np.random.default_rng(seed)
    partitions = np.full(len(labels), "train", dtype=object)
    for label in ("licit", "illicit"):
        positions = np.flatnonzero(labels == label)
        if len(positions) < 7:
            raise ValueError("Each class needs at least seven rows for a three-way split")
        shuffled = rng.permutation(positions)
        test_count = max(1, round(len(positions) * TEST_FRACTION))
        validation_count = max(1, round(len(positions) * VALIDATION_FRACTION))
        partitions[shuffled[:test_count]] = "test"
        partitions[shuffled[test_count:test_count + validation_count]] = "validation"
    return partitions


def masked_intelligence_classes(classes, known_wallets):
    """Expose labels only for the training intelligence inventory."""
    masked = pd.Series("3", index=classes.index, dtype=object)
    present = classes.index.intersection(pd.Index(known_wallets), sort=False)
    masked.loc[present] = classes.loc[present]
    return masked


def _class_counts(labels):
    counts = labels.value_counts()
    rows = len(labels)
    illicit = int(counts.get("illicit", 0))
    return {
        "rows": rows,
        "licit": int(counts.get("licit", 0)),
        "illicit": illicit,
        "illicit_prevalence": illicit / rows,
    }


def load_leakage_safe_dataset(input_path, raw_dir, seed=SEED, progress=True):
    """Load labeled targets and rebuild intelligence using training labels only."""
    input_path, raw_dir = Path(input_path), Path(raw_dir)
    parts, all_ids = [], []
    unknown_rows = 0
    if progress:
        print("Loading the canonical table and excluding unknown targets", flush=True)
    with pd.read_csv(input_path, chunksize=100_000, dtype={"wallet_id": str, "label": str}) as reader:
        for chunk in reader:
            if list(chunk.columns) != CANONICAL_COLUMNS:
                raise ValueError("Unexpected canonical schema or column order")
            if not chunk["label"].isin(["licit", "illicit", "unknown"]).all():
                raise ValueError("Invalid target label")
            all_ids.extend(chunk["wallet_id"])
            unknown_rows += int((chunk["label"] == "unknown").sum())
            parts.append(chunk.loc[chunk["label"].isin(["licit", "illicit"])].copy())

    ids = pd.Index(all_ids, name="wallet_id")
    if ids.has_duplicates or ids.isna().any():
        raise ValueError("Canonical wallet IDs must be unique and nonmissing")
    frame = pd.concat(parts, ignore_index=True).set_index("wallet_id")
    partitions = pd.Series(
        stratified_three_way_split(frame["label"], seed), index=frame.index, name="partition"
    )

    classes_path = raw_dir / "wallets_classes.csv"
    edges_path = raw_dir / "AddrAddr_edgelist.csv"
    classes = load_classes(classes_path)
    expected = classes.reindex(frame.index).map({"1": "illicit", "2": "licit", "3": "unknown"})
    if not expected.equals(frame["label"]):
        raise ValueError("Canonical labels differ from the verified raw class table")

    training_wallets = frame.index[partitions == "train"]
    intelligence = masked_intelligence_classes(classes, training_wallets)
    held_out = frame.index[partitions != "train"]
    if not (intelligence.reindex(held_out) == "3").all():
        raise AssertionError("Validation or test labels entered the intelligence inventory")

    if progress:
        print("Building graph topology and training-label-only intelligence", flush=True)
    graph = graph_from_csv(edges_path, ids, intelligence)
    graph_frame = derive_graph_features(graph, progress=progress)
    audit = audit_target_label_exclusion(graph, graph_frame, len(ids), 16)
    original_graph = frame[GRAPH_COLUMNS].copy()
    for column in GRAPH_COLUMNS:
        frame[column] = graph_frame[column].reindex(frame.index)

    changed = {}
    for column in GRAPH_COLUMNS:
        before, after = original_graph[column], frame[column]
        equal = before.eq(after) | (before.isna() & after.isna())
        changed[column] = int((~equal.fillna(False)).sum())

    partition_metadata = {}
    for name in ("train", "validation", "test"):
        selected = partitions == name
        partition_metadata[name] = {
            **_class_counts(frame.loc[selected, "label"]),
            "wallet_id_sha256": id_digest(frame.index[selected]),
        }
    metadata = {
        "seed": seed,
        "algorithm": "class-stratified wallet split; fixed 70/15/15 fractions",
        "unknown_targets_excluded": unknown_rows,
        "partitions": partition_metadata,
        "partitions_disjoint": True,
        "intelligence_source": "training-wallet labels only; validation, test, and unknown labels masked",
        "known_illicit_intelligence_nodes": int((intelligence == "1").sum()),
        "held_out_labels_masked": True,
        "target_self_exclusion_audit": audit,
        "changed_from_full_label_canonical_rows": changed,
        "source_sha256": {
            "canonical_csv": sha256_file(input_path),
            "wallets_classes": sha256_file(classes_path),
            "address_edges": sha256_file(edges_path),
        },
    }
    return DatasetBundle(frame=frame, partitions=partitions, metadata=metadata)
