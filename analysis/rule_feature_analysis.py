"""Select interpretable rule thresholds on training wallets, then validate once.

Run from the repository root with ``python -m analysis.rule_feature_analysis``.
Validation-wallet labels never enter the simulated graph intelligence source.
The canonical feature table is read-only; recomputed values stay in analysis.
"""

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path

import numpy as np
import pandas as pd

from features.download_elliptic import sha256_file
from features.graph_features import audit_target_label_exclusion, derive_graph_features, graph_from_csv
from features.schema import CANONICAL_COLUMNS, FEATURE_MAP, GRAPH_COLUMNS, load_classes

SEED = 20260928
VALIDATION_FRACTION = 0.20
MIN_SUPPORT = 100
MIN_TRUE_POSITIVES = 50
MIN_PRECISION = 0.80
MAX_FPR = 0.01
QUANTILES = [0.05, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
RATIO_GRID = [0.05, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 0.95, 1.0]
TIME_OR_BLOCK_IDENTIFIERS = {
    "timestep", "wallet_first_timestep", "wallet_last_timestep",
    "elliptic_f_003", "elliptic_f_004", "elliptic_f_007", "elliptic_f_008",
}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def stratified_split(labels, seed=SEED, fraction=VALIDATION_FRACTION):
    """One wallet per row; fixed class-stratified split, never unknown targets."""
    if not 0 < fraction < 1:
        raise ValueError("Validation fraction must be between zero and one")
    labels = np.asarray(labels)
    if not np.isin(labels, ["licit", "illicit"]).all():
        raise ValueError("Only licit and illicit labels may enter the split")
    rng = np.random.default_rng(seed)
    validation = np.zeros(len(labels), dtype=bool)
    for label in ("licit", "illicit"):
        positions = np.flatnonzero(labels == label)
        if len(positions) < 2:
            raise ValueError("Both classes need at least two rows")
        count = min(len(positions) - 1, max(1, round(len(positions) * fraction)))
        validation[rng.permutation(positions)[:count]] = True
    return ~validation, validation


def intelligence_classes(classes, training_wallets):
    """Mask ALL nontraining labels, including every validation-wallet label."""
    masked = pd.Series("3", index=classes.index, dtype=object)
    present = classes.index.intersection(pd.Index(training_wallets), sort=False)
    masked.loc[present] = classes.loc[present]
    return masked


def id_digest(ids):
    return hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()


def prepare_data(input_path, raw_dir, seed, fraction):
    print("Loading canonical rows and excluding unknown targets", flush=True)
    parts, all_ids = [], []
    unknown_rows = 0
    with pd.read_csv(input_path, chunksize=100_000, dtype={"wallet_id": str, "label": str}) as reader:
        for chunk in reader:
            if list(chunk.columns) != CANONICAL_COLUMNS:
                raise ValueError("Unexpected canonical schema/order")
            if not chunk["label"].isin(["licit", "illicit", "unknown"]).all():
                raise ValueError("Invalid target label")
            all_ids.extend(chunk["wallet_id"])
            unknown_rows += int((chunk["label"] == "unknown").sum())
            parts.append(chunk.loc[chunk["label"].isin(["licit", "illicit"])].copy())
    ids = pd.Index(all_ids, name="wallet_id")
    if ids.has_duplicates or ids.isna().any():
        raise ValueError("Wallet IDs must be unique and nonmissing")
    frame = pd.concat(parts, ignore_index=True).set_index("wallet_id")
    train, validation = stratified_split(frame["label"], seed, fraction)
    classes = load_classes(Path(raw_dir) / "wallets_classes.csv")
    mapped = classes.reindex(frame.index).map({"1": "illicit", "2": "licit", "3": "unknown"})
    if not mapped.equals(frame["label"]):
        raise ValueError("Canonical targets differ from the raw class table")
    known = intelligence_classes(classes, frame.index[train])
    if not (known.reindex(frame.index[validation]) == "3").all():
        raise AssertionError("Held-out labels entered the intelligence source")
    print("Rebuilding graph intelligence from training-wallet labels ONLY", flush=True)
    graph = graph_from_csv(Path(raw_dir) / "AddrAddr_edgelist.csv", ids, known)
    graph_frame = derive_graph_features(graph, progress=True)
    audit = audit_target_label_exclusion(graph, graph_frame, len(ids), 16)
    # Preserve the original canonical table; replace only this in-memory analysis copy.
    original = frame[GRAPH_COLUMNS].copy()
    for name in GRAPH_COLUMNS:
        frame[name] = graph_frame[name].reindex(frame.index)
    changed = {}
    for name in GRAPH_COLUMNS:
        before, after = original[name], frame[name]
        equal = before.eq(after) | (before.isna() & after.isna())
        changed[name] = int((~equal.fillna(False)).sum())
    metadata = {
        "seed": seed, "validation_fraction": fraction, "unknown_targets_excluded": unknown_rows,
        "rows": len(frame), "train": class_counts(frame.loc[train, "label"]),
        "validation": class_counts(frame.loc[validation, "label"]),
        "training_wallet_id_sha256": id_digest(frame.index[train]),
        "validation_wallet_id_sha256": id_digest(frame.index[validation]),
        "intelligence_source": "training-wallet labels only; all other labels masked to unknown",
        "known_illicit_intelligence_nodes": int((known == "1").sum()),
        "held_out_labels_masked": True, "target_self_exclusion_audit": audit,
        "changed_from_full_label_canonical_rows": changed,
        "source_sha256": {"canonical_csv": sha256_file(input_path),
                          "wallets_classes": sha256_file(Path(raw_dir) / "wallets_classes.csv"),
                          "address_edges": sha256_file(Path(raw_dir) / "AddrAddr_edgelist.csv")},
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
    }
    return frame, train, validation, metadata


def class_counts(labels):
    counts = labels.value_counts()
    return {"rows": len(labels), "licit": int(counts.get("licit", 0)),
            "illicit": int(counts.get("illicit", 0)), "illicit_prevalence": float((labels == "illicit").mean())}


def wilson_interval(successes, trials):
    if not trials:
        return [None, None]
    z = 1.959963984540054
    proportion = successes / trials
    divisor = 1 + z * z / trials
    center = (proportion + z * z / (2 * trials)) / divisor
    spread = z * math.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials * trials)) / divisor
    return [max(0.0, center - spread), min(1.0, center + spread)]


def metrics(predicted, positive):
    predicted, positive = np.asarray(predicted, dtype=bool), np.asarray(positive, dtype=bool)
    if predicted.shape != positive.shape:
        raise ValueError("Prediction and target sizes differ")
    tp = int(np.sum(predicted & positive))
    fp = int(np.sum(predicted & ~positive))
    fn, tn = int(np.sum(~predicted & positive)), int(np.sum(~predicted & ~positive))
    support = tp + fp
    precision = tp / support if support else None
    recall = tp / (tp + fn) if tp + fn else None
    fpr = fp / (fp + tn) if fp + tn else None
    f05 = 1.25 * tp / (1.25 * tp + 0.25 * fn + fp) if tp + fn + fp else 0.0
    return {"precision": precision, "recall": recall, "false_positive_rate": fpr,
            "support": support, "support_fraction": support / len(positive) if len(positive) else 0,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn, "f0_5": f05,
            "precision_wilson_95": wilson_interval(tp, support)}


def rule_mask(frame, conditions):
    triggered = np.ones(len(frame), dtype=bool)
    for condition in conditions:
        column, operator, threshold = condition["feature"], condition["operator"], condition["threshold"]
        if column in {"label", "wallet_id"}:
            raise ValueError("Target/identity cannot be a rule condition")
        values = pd.to_numeric(frame[column]).to_numpy(dtype=float, na_value=np.nan)
        if operator == ">=":
            match = values >= threshold
        elif operator == "<=":
            match = values <= threshold
        else:
            raise ValueError("Only >= and <= conditions are supported")
        triggered &= np.isfinite(values) & match
    return triggered


def nice_thresholds(series, column):
    values = pd.to_numeric(series).to_numpy(dtype=float, na_value=np.nan)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return []
    if column == "direct_illicit_neighbor_ratio":
        return [value for value in RATIO_GRID if values.min() <= value <= values.max()]
    if column == "distance_to_other_known_illicit":
        return list(range(1, min(int(values.max()), 10) + 1))
    finite_positive = values[values > 0]
    if len(finite_positive) == 0:
        return [0.0]
    probes = np.quantile(finite_positive, [0, .01, .05, .10, .25, .50, .75, .90, .95, .99, 1])
    result = {0.0}
    for value in probes:
        power = math.floor(math.log10(float(value)))
        for factor in (1, 2, 5, 10):
            threshold = float(factor * 10.0**power)
            if values.min() <= threshold <= values.max():
                result.add(threshold)
    if np.all(values == np.floor(values)):
        result = {value for value in result if value == math.floor(value)}
        result.update(value for value in [1, 2, 3, 5, 10, 20, 50, 100, 200, 500, 1000] if values.min() <= value <= values.max())
    return sorted(result)


def univariate_analysis(training):
    positive = (training["label"] == "illicit").to_numpy()
    distributions, rankings, candidates = [], [], []
    for column in CANONICAL_COLUMNS[1:-1]:
        numeric = pd.to_numeric(training[column]).astype(float)
        for label in ("licit", "illicit"):
            values = numeric[training["label"] == label]
            finite = values[np.isfinite(values)]
            row = {"feature": column, "source_name": FEATURE_MAP.get(column, column), "label": label,
                   "rows": len(values), "missing": int(values.isna().sum()),
                   "zero_fraction": float((finite == 0).mean()) if len(finite) else None,
                   "mean": float(finite.mean()) if len(finite) else None,
                   "minimum": float(finite.min()) if len(finite) else None,
                   "maximum": float(finite.max()) if len(finite) else None}
            row.update({f"q{int(q * 100):02d}": float(finite.quantile(q)) if len(finite) else None for q in QUANTILES})
            distributions.append(row)
        finite = np.isfinite(numeric.to_numpy())
        y = positive[finite]
        ranks = numeric[finite].rank(method="average").to_numpy()
        positives, negatives = int(y.sum()), int((~y).sum())
        auc = float((ranks[y].sum() - positives * (positives + 1) / 2) / (positives * negatives)) if positives and negatives else None
        best = None
        for threshold in nice_thresholds(numeric, column):
            for operator in (">=", "<="):
                conditions = [{"feature": column, "operator": operator, "threshold": threshold}]
                performance = metrics(rule_mask(training, conditions), positive)
                record = {"feature": column, "operator": operator, "threshold": threshold,
                          **{key: value for key, value in performance.items() if key != "precision_wilson_95"}}
                candidates.append(record)
                if performance["support"] < MIN_SUPPORT or performance["tp"] < MIN_TRUE_POSITIVES:
                    continue
                if best is None or performance["f0_5"] > best["f0_5"]:
                    best = record
        ranking = {"feature": column, "source_name": FEATURE_MAP.get(column, column),
                   "auc_increasing": auc, "auc_separation": max(auc, 1-auc) if auc is not None else None,
                   "threshold_eligible": column not in TIME_OR_BLOCK_IDENTIFIERS,
                   "best_training_threshold": best}
        rankings.append(ranking)
    return distributions, rankings, candidates


def condition(feature, threshold, operator=">="):
    return {"feature": feature, "operator": operator, "threshold": float(threshold)}


def rule_templates(training):
    """A small, declared library; no arbitrary all-feature conjunction search."""
    ratio = nice_thresholds(training["direct_illicit_neighbor_ratio"], "direct_illicit_neighbor_ratio")
    one = [v for v in nice_thresholds(training["one_hop_illicit_count"], "one_hop_illicit_count") if v >= 1]
    two = [v for v in nice_thresholds(training["two_hop_illicit_count"], "two_hop_illicit_count") if v >= 1]
    transactions = [v for v in nice_thresholds(training["elliptic_f_006"], "elliptic_f_006") if v >= 2]
    sent = [v for v in nice_thresholds(training["elliptic_f_015"], "elliptic_f_015") if v > 0]
    return [
        {"id": "R1", "name": "Direct illicit-neighbor concentration", "precision_floor": .80, "objective": "f0_5",
         "conditions": [[condition("direct_illicit_neighbor_ratio", v)] for v in ratio],
         "rationale": "Concentration captures a high share of attributed illicit counterparties; broad screening candidate."},
        {"id": "R2", "name": "Broad second-hop illicit neighborhood", "precision_floor": .80, "objective": "f0_5",
         "conditions": [[condition("two_hop_illicit_count", v)] for v in two],
         "rationale": "Captures many distinct illicit nodes at exact distance two, including wallets with weaker direct exposure."},
        {"id": "R3", "name": "Multiple direct illicit neighbors", "precision_floor": .80, "objective": "f0_5",
         "conditions": [[condition("one_hop_illicit_count", v)] for v in one],
         "rationale": "Simple counterpart-count alternative. Larger counts are not assumed to be monotonically riskier."},
        {"id": "R4", "name": "Strict direct-neighbor concentration", "precision_floor": .95, "objective": "recall",
         "conditions": [[condition("direct_illicit_neighbor_ratio", v)] for v in ratio],
         "rationale": "Alternative operating point targeting at least 95% training precision; trades coverage for confidence."},
        {"id": "R5", "name": "Strict second-hop illicit neighborhood", "precision_floor": .999, "objective": "recall",
         "conditions": [[condition("two_hop_illicit_count", v)] for v in two],
         "rationale": "Alternative operating point targeting at least 99.9% training precision, rather than a separate additive finding."},
        {"id": "R6", "name": "Direct concentration with second-hop corroboration", "precision_floor": .95, "objective": "recall",
         "conditions": [[condition("direct_illicit_neighbor_ratio", r), condition("two_hop_illicit_count", t)] for r in ratio for t in two],
         "rationale": "Requires evidence in both direct and exact two-hop neighborhoods; may suppress incidental direct connections."},
        {"id": "R7", "name": "Direct concentration with repeated transaction activity", "precision_floor": .95, "objective": "recall",
         "conditions": [[condition("direct_illicit_neighbor_ratio", r), condition("elliptic_f_006", t)] for r in ratio for t in transactions],
         "rationale": "Tests whether multiple provided transactions improve a graph-based condition. Activity alone is not illicit evidence."},
        {"id": "R8", "name": "Direct concentration with BTC sent", "precision_floor": .95, "objective": "recall",
         "conditions": [[condition("direct_illicit_neighbor_ratio", r), condition("elliptic_f_015", t)] for r in ratio for t in sent],
         "rationale": "Tests a wallet-level BTC-sent guard on graph concentration. This is not an illicit-funds amount or monetary-exposure ratio."},
    ]


def select_rules(training):
    positive = (training["label"] == "illicit").to_numpy()
    selected, search = [], []
    for template in rule_templates(training):
        best, best_score = None, None
        for conditions in template["conditions"]:
            performance = metrics(rule_mask(training, conditions), positive)
            eligible = (performance["support"] >= MIN_SUPPORT and performance["tp"] >= MIN_TRUE_POSITIVES
                        and performance["precision"] >= template["precision_floor"]
                        and performance["false_positive_rate"] <= MAX_FPR)
            search.append({"template": template["id"], "conditions": conditions, "eligible": eligible, "training": performance})
            if not eligible:
                continue
            score = (performance[template["objective"]], performance["precision"], -performance["fp"])
            if best_score is None or score > best_score:
                best, best_score = {key: value for key, value in template.items() if key != "conditions"}, score
                best.update({"conditions": conditions, "training": performance})
        if best is not None:
            best["status"] = "candidate for review; not a production rule"
            selected.append(best)
    if not 6 <= len(selected) <= 10:
        raise ValueError(f"Only {len(selected)} templates met the training constraints; do not invent extra successful rules")
    return selected, search


def load_cache(args):
    cache = args.output_dir.parent / ".cache"
    metadata = json.loads((args.output_dir / "training_inspection.json").read_text(encoding="utf-8"))["split"]
    if metadata["seed"] != args.seed or metadata["validation_fraction"] != args.validation_fraction:
        raise ValueError("Cached split configuration differs; rerun inspect-train or all")
    paths = {"canonical_csv": args.input, "wallets_classes": args.raw_dir / "wallets_classes.csv",
             "address_edges": args.raw_dir / "AddrAddr_edgelist.csv"}
    if any(sha256_file(path) != metadata["source_sha256"][key] for key, path in paths.items()):
        raise ValueError("Analysis inputs changed; rebuild the masked feature analysis")
    frame = pd.read_csv(cache / "supervised_features.csv", dtype={"wallet_id": str}, float_precision="round_trip").set_index("wallet_id")
    partition = frame.pop("analysis_split")
    if not partition.isin(["train", "validation"]).all() or not frame["label"].isin(["licit", "illicit"]).all():
        raise ValueError("Invalid cached target/split")
    train, validation = (partition == "train").to_numpy(), (partition == "validation").to_numpy()
    expected_train, expected_validation = stratified_split(frame["label"], args.seed, args.validation_fraction)
    if not np.array_equal(train, expected_train) or not np.array_equal(validation, expected_validation):
        raise ValueError("Cached partition differs from the reproducible split")
    if id_digest(frame.index[train]) != metadata["training_wallet_id_sha256"] or id_digest(frame.index[validation]) != metadata["validation_wallet_id_sha256"]:
        raise ValueError("Cached wallet membership changed")
    cache_hash = sha256_file(cache / "supervised_features.csv")
    if metadata.get("analysis_cache_sha256", cache_hash) != cache_hash:
        raise ValueError("Cached features changed; rebuild the analysis")
    metadata["analysis_cache_sha256"] = cache_hash
    return frame, train, validation, metadata


def condition_text(conditions, semantic=False):
    return " AND ".join(f"{FEATURE_MAP.get(c['feature'], c['feature']) if semantic else c['feature']} {c['operator']} {c['threshold']:g}" for c in conditions)


def evaluate_frozen(frame, train, validation, frozen):
    if frozen["split"]["training_wallet_id_sha256"] != id_digest(frame.index[train]) or frozen["split"]["validation_wallet_id_sha256"] != id_digest(frame.index[validation]):
        raise ValueError("Frozen rules use a different split")
    positive = (frame["label"] == "illicit").to_numpy()
    rules, masks = [], []
    for selected in frozen["rules"]:
        mask = rule_mask(frame, selected["conditions"])
        # This confirms the frozen selection was based on these exact training rows.
        training_metrics = metrics(mask[train], positive[train])
        if training_metrics != selected["training"]:
            raise ValueError("Training rule metrics differ from the frozen artifact")
        rules.append({**selected, "validation": metrics(mask[validation], positive[validation])})
        masks.append(mask)
    overlaps = []
    for i, first in enumerate(rules):
        for j in range(i + 1, len(rules)):
            a, b = masks[i][validation], masks[j][validation]
            union = int((a | b).sum())
            overlaps.append({"first": first["id"], "second": rules[j]["id"],
                             "intersection": int((a & b).sum()), "union": union,
                             "jaccard": float((a & b).sum() / union) if union else 0.0})
    # Core pair chosen from training behavior and complementary feature families.
    core = [i for i, rule in enumerate(rules) if rule["id"] in {"R1", "R2"}]
    combined = np.logical_or.reduce([masks[i] for i in core])
    combined_metrics = {"rules": [rules[i]["id"] for i in core],
                        "training": metrics(combined[train], positive[train]),
                        "validation": metrics(combined[validation], positive[validation])}
    reference_conditions = {f"one_hop_ge_{k}": [condition("one_hop_illicit_count", k)] for k in [1, 2, 3, 5]}
    reference_conditions["distance_le_2"] = [condition("distance_to_other_known_illicit", 2, "<=")]
    # Fixed training diagnostics; no threshold selection uses validation results.
    diagnostics = {name: metrics(rule_mask(frame.loc[train], conditions), positive[train])
                   for name, conditions in reference_conditions.items() if all(c["feature"] in frame for c in conditions)}
    return {"split": frozen["split"], "selection_policy": frozen["selection_policy"], "rules": rules,
            "validation_overlap": overlaps, "core_pair_or": combined_metrics,
            "training_reference_cutoffs": diagnostics,
            "frozen_before_validation": True, "validation_used_for_threshold_selection": False}


def percent(value, places=2):
    return "n/a" if value is None else f"{100 * value:.{places}f}%"


def markdown_report(report, distributions, rankings, frozen_hash):
    split = report["split"]
    diagnostics = report["training_reference_cutoffs"]
    count_precisions = "/".join(percent(diagnostics[f"one_hop_ge_{k}"]["precision"]) for k in [1, 2, 3, 5])
    distance_two = diagnostics["distance_le_2"]
    missed = [rule for rule in report["rules"] if rule["validation"]["precision"] is None or rule["validation"]["precision"] < rule["precision_floor"]]
    lines = [
        "# Training-only rule threshold analysis", "",
        "This is offline analyst research, not a Go rule implementation or ML training.",
        "Candidates describe coarse graph-neighbor intelligence; none proves criminal activity.", "",
        "## Data and split", "",
        f"The canonical table has {split['rows']:,} labeled targets. {split['unknown_targets_excluded']:,} unknown targets were excluded, not converted to licit.",
        f"One wallet per row; a deterministic {100 * (1 - split['validation_fraction']):g}/{100 * split['validation_fraction']:g} class-stratified wallet split uses NumPy seed `{split['seed']}`.", "",
        "| Partition | Wallets | Licit | Illicit | Illicit prevalence |", "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name in ("train", "validation"):
        row = split[name]
        lines.append(f"| {name} | {row['rows']:,} | {row['licit']:,} | {row['illicit']:,} | {percent(row['illicit_prevalence'])} |")
    lines.extend([
        "", "## Leakage controls and remaining limitations", "",
        "The original canonical graph features use all public labels. Simply splitting those rows would expose validation labels through neighbors. Here all neighbor-label features are rebuilt using only training-wallet labels. Validation labels and all other nontraining labels are masked to unknown BEFORE any graph-intelligence calculation. The canonical CSV is never modified.", "",
        f"Unknown wallets remain unlabeled topology/bridge nodes, but never enter class distributions, threshold selection, or performance denominators. Directed degrees are preserved; intelligence traverses the deduplicated undirected graph. Target self-label exclusion is retained and independently audited on {split['target_self_exclusion_audit']['audited_targets']} graph nodes, with synthetic invariance tests.", "",
        f"This masks validation labels from an intelligence source containing {split['known_illicit_intelligence_nodes']:,} illicit training nodes. Training and validation use the same intelligence inventory; no held-out label is revealed to tune or recompute it.", "",
        "This remains a STATIC, TRANSDUCTIVE, wallet-level experiment. Full topology, lifetime wallet aggregates, and latest observations are available across the graph. Wallets can belong to correlated entities or components across the split. Labels have no publication timestamps. The random split is not entity-disjoint, chronological, or a real-time deployment test; unusually strong graph results may reflect dense illicit clusters. A later untouched entity/time-aware test is needed before deployment. Validation is now a reported development holdout, not a reusable final test.", "",
        "## Threshold selection protocol", "",
        "All class-distribution comparisons, AUC rankings, candidate grids, template choices, and thresholds use TRAINING rows only. Rounded grids use powers of ten and 1/2/5 multipliers plus small integer/ratio grids; no arbitrary exact-value cutoffs or exhaustive cross-feature search are used. All 74 features are inspected, but absolute timesteps/block identifiers are excluded from rule conditions because they can encode dataset-era artifacts.", "",
        f"Every selected candidate requires at least {MIN_SUPPORT} triggered training rows, {MIN_TRUE_POSITIVES} true positives, and training FPR <= {percent(MAX_FPR)}. R1-R3 maximize F0.5 subject to precision >= 80%. R4/R6-R8 maximize recall subject to precision >= 95%; R5 uses >= 99.9%. Ties prefer precision, then fewer false positives. These analyst operating targets are experimental, not business-approved tolerances.", "",
        "F0.5 weights precision more than recall. Quantile probes construct the grids from training values; the template library is small and listed in the script. A threshold is a measured candidate, not a universally correct KYT boundary.", "",
        f"Selected conditions and training metrics were saved to `analysis/results/frozen_rules.json` BEFORE validation metrics were calculated. Its SHA-256 is `{frozen_hash}`. The validation phase reads that artifact and cannot select new thresholds. Precision/recall/FPR are reported for every frozen rule, without selecting winners after inspecting validation.", "",
        "## Training class distributions", "",
        "The table below gives class medians and 90th percentiles. `feature_distributions.csv` additionally contains means, zero rates, missing counts, extrema, and q05/q25/q50/q75/q90/q95/q99 for every feature and class. Mean alone is misleading for these skewed wallet distributions.", "",
        "| Feature / source name | Licit median | Illicit median | Licit p90 | Illicit p90 | Direction-free AUC separation |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    features = ["direct_illicit_neighbor_ratio", "one_hop_illicit_count", "two_hop_illicit_count", "distance_to_other_known_illicit",
                "in_degree", "out_degree", "total_degree", "unique_neighbors", "elliptic_f_001", "elliptic_f_002", "elliptic_f_006",
                "elliptic_f_010", "elliptic_f_015", "elliptic_f_020", "elliptic_f_025", "elliptic_f_027", "elliptic_f_030",
                "elliptic_f_036", "elliptic_f_038", "elliptic_f_043", "elliptic_f_048"]
    lookup = {(item['feature'], item['label']): item for item in distributions}
    ranked = {item["feature"]: item for item in rankings}
    for column in features:
        a, b = lookup[column, "licit"], lookup[column, "illicit"]
        auc = ranked[column]["auc_separation"]
        lines.append(f"| `{column}` ({FEATURE_MAP.get(column, column)}) | {a['q50']:.6g} | {b['q50']:.6g} | {a['q90']:.6g} | {b['q90']:.6g} | {auc:.3f} |")
    lines.extend([
        "", "AUC here is a training-only univariate ranking diagnostic with average-rank ties; we report max(AUC, 1-AUC) to allow either direction. It is not validation model performance. Nullable distances are excluded from that feature's numeric summaries/AUC and reported separately, never filled with zero. 0.5 indicates little rank separation; a high AUC alone does not establish a useful low-FPR cutoff.", "",
        "## Useful and weak signals", "",
        "- Direct illicit-neighbor ratio and exact two-hop illicit count provide the strongest useful single-feature cutoffs. They rely on the simulated attribution inventory, not behavioral proof.",
        "- One-hop count and distance <= 1 have IDENTICAL trigger sets. `one_hop_illicit_count` also equals `direct_illicit_neighbor_count`. Do not implement all three as independent findings. Distance <= 2 expands into many licit neighborhoods and is much weaker.",
        f"- More attributed neighbors are not assumed to be monotonically more predictive: training precision for one-hop count >=1/2/3/5 is {count_precisions}. Large hubs can have many illicit connections without being illicit themselves. Distance <=2 has training precision {percent(distance_two['precision'])} and FPR {percent(distance_two['false_positive_rate'])}; its high AUC does not justify that broad proximity rule.",
        "- Raw degree, unique-neighbor counts, BTC totals, and transaction counts have substantial class overlap. High activity or high value alone is not a defensible illicit rule. Absolute date/block identifiers can be dataset artifacts and are excluded.",
        "- Fees can isolate a small enriched subset, but an enriched minority is not a general KYT detector. Intervals are in blocks, not hours; zero intervals often accompany limited activity and do not prove rapid forwarding.",
        "- The complete training cutoff results below make weak-feature assessments quantitative. Behavior-guarded graph candidates are evaluated to see whether they add value beyond attribution, without interpreting total BTC sent as illicit exposure.", "",
        "| Feature | Best training F0.5 cutoff (support >=100, TP >=50) | Precision | Recall | FPR | Triggered |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ])
    for column in features:
        best = ranked[column]["best_training_threshold"]
        if best:
            lines.append(f"| `{FEATURE_MAP.get(column, column)}` | `{best['operator']} {best['threshold']:g}` | {percent(best['precision'])} | {percent(best['recall'])} | {percent(best['false_positive_rate'], 4)} | {best['support']:,} |")
    lines.extend(["", "## Frozen candidate rules", "",
                  "| ID | Exact condition (AND where shown) | Train precision | Train recall | Train FPR | Train triggers |",
                  "| --- | --- | ---: | ---: | ---: | ---: |"])
    for rule in report["rules"]:
        m = rule["training"]
        lines.append(f"| {rule['id']} | `{condition_text(rule['conditions'], True)}` | {percent(m['precision'])} | {percent(m['recall'])} | {percent(m['false_positive_rate'], 4)} | {m['support']:,} |")
    lines.extend(["", "For preserved fields, the exact CSV aliases are in each machine-readable condition and the source mapping in `data/derived/feature_schema.json`.", "",
                  "## Held-out validation (thresholds unchanged)", "",
                  f"Positive means illicit. Precision = TP/(TP+FP), recall = TP/(TP+FN), FPR = FP/(FP+TN). Support is triggered validation rows, with TP/FP shown separately. Denominators exclude unknown targets. Percentages reflect this dataset's {percent(split['validation']['illicit_prevalence'])} illicit prevalence and will change with production prevalence.", "",
                  "| ID | Precision | Recall | FPR | Triggered | TP | FP | Approximate precision 95% Wilson interval |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"])
    for rule in report["rules"]:
        m = rule["validation"]
        interval = m["precision_wilson_95"]
        lines.append(f"| {rule['id']} | {percent(m['precision'])} | {percent(m['recall'])} | {percent(m['false_positive_rate'], 4)} | {m['support']:,} | {m['tp']:,} | {m['fp']:,} | {percent(interval[0])} to {percent(interval[1])} |")
    lines.extend(["", "Intervals are descriptive binomial intervals, not guarantees: graph-linked wallets are correlated, and selection searched many training thresholds. Rounding to 100% precision does not mean zero future false positives.", "",
                  "## Why these candidates and how to review them", ""])
    for rule in report["rules"]:
        lines.append(f"- **{rule['id']} — {rule['name']}:** {rule['rationale']}")
    combined = report["core_pair_or"]["validation"]
    lines.extend([
        "", "R1 and R2 are the simplest complementary core candidates, chosen from training results before validation. The remaining rules are alternatives or refinements. R4 is nested within R1; R5 is nested within R2. Many compound rules overlap heavily. Do not sum their recalls or multiply confidence as though independent.", "",
        f"For the fixed R1 OR R2 core pair, validation precision is {percent(combined['precision'])}, recall {percent(combined['recall'])}, FPR {percent(combined['false_positive_rate'], 4)}, with {combined['support']:,} triggers ({combined['tp']:,} TP and {combined['fp']:,} FP). This reports overlap-aware coverage, not a scoring formula. Pairwise overlap counts are in the JSON report.", "",
        "Validation point estimates below their TRAINING selection floors: " + (", ".join(f"{r['id']} ({percent(r['validation']['precision'])}, floor {percent(r['precision_floor'])})" for r in missed) or "none") + ". We retain all frozen candidates and report them instead of retuning thresholds on validation. Count-only alternatives and BTC guards need review before adoption. The labeled population is selective, so unknown-wallet performance and production false-positive burden remain unmeasured.", "",
        "A behavior condition that adds little validation benefit should not be added to the eventual engine merely to increase rule count. These eight candidates meet training selection constraints; they are not eight independent risk factors or approved production controls. Six stronger candidates (R1, R2, R4, R5, R6, R7) are now implemented as Go rules; R3 and R8 remain under review. No numeric weight, risk score, or block decision is implemented.", "",
        "## Reproduce and artifacts", "",
        "```sh", "python -m analysis.rule_feature_analysis --phase all", "python -m unittest discover -s tests -v", "```", "",
        "The existing pandas/NumPy feature requirements suffice. Optional `--plot` additionally needs matplotlib and writes training-only distribution plots. The `inspect-train`, `select`, and `evaluate` phases expose the frozen sequence for review; select/evaluate reuse the ignored scratch table only after verifying input hashes and split membership. Evaluation additionally checks the frozen cache hash and training metrics.", "",
        "- `analysis/results/training_inspection.json`: split configuration, source hashes, all training feature rankings, label masking and self-exclusion audit.",
        "- `analysis/results/feature_distributions.csv`: both training class distributions for all 74 features.",
        "- `analysis/results/threshold_candidates.csv`: all one-condition training threshold results, including weak features.",
        "- `analysis/results/template_search.json`: the declared conjunction/operating-point searches and their training metrics.",
        "- `analysis/results/frozen_rules.json`: selected conditions and training metrics, created before validation.",
        "- `analysis/results/rule_analysis_report.json`: frozen rules, held-out metrics, overlap counts and fixed core-pair coverage.",
        "- `analysis/.cache/supervised_features.csv`: ignored, recomputable analysis table; canonical input stays untouched.", "",
        "The [Go rule catalog](../internal/rules/candidates.go) implements the six selected threshold conditions and returns findings only. Rule semantics and operating tolerances still need review before production use; no ML fit, scoring formula, or API is included.", "",
    ])
    return "\n".join(lines)


def plot_distributions(training, path):
    """Optional exported scientific figure; each class is normalized separately."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    specifications = [
        ("direct_illicit_neighbor_ratio", False), ("two_hop_illicit_count", True),
        ("distance_to_other_known_illicit", False), ("total_degree", True),
        ("elliptic_f_006", True), ("elliptic_f_010", True),
    ]
    figure, axes = plt.subplots(2, 3, figsize=(13, 7.5), constrained_layout=True)
    for axis, (column, transform) in zip(axes.flat, specifications):
        all_values = pd.to_numeric(training[column]).to_numpy(dtype=float, na_value=np.nan)
        finite = all_values[np.isfinite(all_values)]
        if transform:
            finite = np.log1p(finite)
        low, high = float(finite.min()), float(finite.max())
        bins = np.linspace(low, high if high > low else low + 1, 31)
        for label, color in [("licit", "#2563eb"), ("illicit", "#c2410c")]:
            values = pd.to_numeric(training.loc[training["label"] == label, column]).to_numpy(dtype=float, na_value=np.nan)
            values = values[np.isfinite(values)]
            if transform:
                values = np.log1p(values)
            axis.hist(values, bins=bins, weights=np.ones(len(values)) * 100 / len(values),
                      histtype="step", linewidth=1.7, color=color, label=label)
        axis.set_title(FEATURE_MAP.get(column, column), fontsize=10)
        axis.set_xlabel("ln(1 + feature value)" if transform else "Feature value")
        axis.set_ylabel("Percent of class per bin")
        axis.grid(alpha=0.18)
    axes.flat[0].legend(frameon=False)
    figure.suptitle("Elliptic++ training distributions — held-out labels masked from graph intelligence", fontsize=13)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, format="svg", metadata={"Date": None})
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/derived/canonical_feature_dataset.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("analysis/results"))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--validation-fraction", type=float, default=VALIDATION_FRACTION)
    parser.add_argument("--phase", choices=["inspect-train", "select", "evaluate", "all"], default="all")
    parser.add_argument("--report", type=Path, default=Path("docs/rule_analysis.md"))
    parser.add_argument("--plot", action="store_true", help="Optional matplotlib training-only distribution figure")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.phase in {"inspect-train", "all"}:
        frame, train, validation, metadata = prepare_data(args.input, args.raw_dir, args.seed, args.validation_fraction)
        print("Comparing distributions and thresholds on training rows only", flush=True)
        distributions, rankings, candidates = univariate_analysis(frame.loc[train])
        cache = args.output_dir.parent / ".cache"
        cache.mkdir(parents=True, exist_ok=True)
        cache_path = cache / "supervised_features.csv"
        frame.assign(analysis_split=np.where(train, "train", "validation")).to_csv(cache_path, index=True)
        metadata["analysis_cache_sha256"] = sha256_file(cache_path)
        write_json(args.output_dir / "training_inspection.json", {"split": metadata, "rankings": rankings})
        pd.DataFrame(distributions).to_csv(args.output_dir / "feature_distributions.csv", index=False)
        pd.DataFrame(candidates).to_csv(args.output_dir / "threshold_candidates.csv", index=False)
    else:
        frame, train, validation, metadata = load_cache(args)
        inspection = json.loads((args.output_dir / "training_inspection.json").read_text(encoding="utf-8"))
        rankings = inspection["rankings"]
        distributions = pd.read_csv(args.output_dir / "feature_distributions.csv").to_dict("records")
    if args.phase in {"select", "all"}:
        print("Selecting rule templates on training wallets only", flush=True)
        selected, search = select_rules(frame.loc[train])
        policy = {"min_support": MIN_SUPPORT, "min_true_positives": MIN_TRUE_POSITIVES,
                  "max_fpr": MAX_FPR, "threshold_selection_split": "train",
                  "core_pair_chosen_before_validation": ["R1", "R2"],
                  "objectives_and_precision_floors": {r["id"]: {"objective": r["objective"], "precision_floor": r["precision_floor"]} for r in selected}}
        write_json(args.output_dir / "template_search.json", search)
        write_json(args.output_dir / "frozen_rules.json", {"split": metadata, "selection_policy": policy, "rules": selected})
        for rule in selected:
            print(rule["id"], condition_text(rule["conditions"], True), json.dumps(rule["training"]))
    if args.phase in {"evaluate", "all"}:
        path = args.output_dir / "frozen_rules.json"
        frozen = json.loads(path.read_text(encoding="utf-8"))
        if frozen["split"]["source_sha256"] != metadata["source_sha256"] or frozen["split"]["analysis_cache_sha256"] != metadata["analysis_cache_sha256"]:
            raise ValueError("Frozen input/cache hashes differ")
        print("Evaluating the frozen candidates on held-out validation wallets", flush=True)
        frozen_hash = sha256_file(path)
        report = evaluate_frozen(frame, train, validation, frozen)
        report["frozen_rule_sha256"] = frozen_hash
        write_json(args.output_dir / "rule_analysis_report.json", report)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(markdown_report(report, distributions, rankings, frozen_hash), encoding="utf-8")
        if args.plot:
            figure_path = args.report.parent / "assets" / "rule-feature-distributions.svg"
            plot_distributions(frame.loc[train], figure_path)
            with args.report.open("a", encoding="utf-8") as destination:
                destination.write("\n![Training-only class distributions](assets/rule-feature-distributions.svg)\n")
        if sha256_file(path) != frozen_hash:
            raise AssertionError("Evaluation changed the frozen rule conditions")
        for rule in report["rules"]:
            print(rule["id"], condition_text(rule["conditions"], True), json.dumps(rule["validation"]))
        print("Fixed core pair OR:", json.dumps(report["core_pair_or"]["validation"]))
        print(f"Wrote {args.report}")


if __name__ == "__main__":
    main()
