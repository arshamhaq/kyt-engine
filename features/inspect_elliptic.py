"""Inspect actual local CSVs; distinguish full scans from remote header previews."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from .download_elliptic import ACTOR_FILES, TRANSACTION_FILES, sha256_file
from .schema import CLASS_LABELS, FEATURE_MAP, require_schema


def base58check_address(value):
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    try:
        number = 0
        for character in value:
            number = number * 58 + alphabet.index(character)
        decoded = b"\0" * (len(value) - len(value.lstrip("1"))) + number.to_bytes((number.bit_length() + 7) // 8, "big")
        checksum = hashlib.sha256(hashlib.sha256(decoded[:-4]).digest()).digest()[:4]
        return len(decoded) == 25 and decoded[0] in (0, 5) and decoded[-4:] == checksum
    except (ValueError, OverflowError):
        return False


def inspect_file(path, chunksize=100_000):
    require_schema(path)
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        header = next(reader)
        examples = [row for _, row in zip(range(3), reader)]
    record = {
        "inspection": "full_local_csv", "header": header, "example_rows": examples,
        "size_bytes": path.stat().st_size, "sha256": sha256_file(path), "rows": 0,
    }
    ids = set()
    steps = set()
    class_counts = Counter()
    missing = Counter()
    nonfinite = Counter()
    identifiers = [name for name in header if name in {"address", "input_address", "output_address", "txId", "txId1", "txId2", "class"}]
    with pd.read_csv(path, chunksize=chunksize, dtype={name: str for name in identifiers}) as reader:
        for chunk in reader:
            record["rows"] += len(chunk)
            missing.update({name: int(count) for name, count in chunk.isna().sum().items() if count})
            for name in chunk.select_dtypes(include="number"):
                count = int(np.isinf(chunk[name].to_numpy()).sum())
                if count:
                    nonfinite[name] += count
            if "address" in chunk:
                ids.update(chunk["address"])
            if "txId" in chunk and path.name.startswith("txs_"):
                ids.update(chunk["txId"])
            if "Time step" in chunk:
                steps.update(int(value) for value in chunk["Time step"].dropna().unique())
            if "class" in chunk:
                class_counts.update(chunk["class"])
    if ids:
        record["unique_identifiers"] = len(ids)
    if steps:
        record["timestep_values"] = sorted(steps)
    if class_counts:
        if not set(class_counts).issubset(CLASS_LABELS):
            raise ValueError(f"Unverified class values in {path}: {class_counts}")
        record["class_code_distribution"] = dict(class_counts)
        record["class_distribution"] = {CLASS_LABELS[code]: count for code, count in class_counts.items()}
    if "address" in header:
        record["example_wallet_base58check_valid"] = [base58check_address(row[header.index("address")]) for row in examples]
    record["missing_values"] = dict(missing)
    record["infinite_values"] = dict(nonfinite)
    return record


def inspect_dataset(raw_dir):
    raw_dir = Path(raw_dir)
    preview_path = raw_dir / "remote_schema_preview.json"
    previews = {}
    if preview_path.exists():
        preview = json.loads(preview_path.read_text(encoding="utf-8"))
        previews = {item["filename"]: item for item in preview["files"]}
    report = {"files": {}, "provided_numeric_feature_count": len(FEATURE_MAP), "provided_feature_mapping": FEATURE_MAP}
    for filename in ACTOR_FILES + TRANSACTION_FILES:
        path = raw_dir / filename
        if path.exists():
            print(f"Inspecting {filename}", flush=True)
            report["files"][filename] = inspect_file(path)
        elif filename in previews:
            item = previews[filename]
            report["files"][filename] = {
                "inspection": "remote_header_and_three_rows_only", "header": item["first_four_csv_rows"][0],
                "example_rows": item["first_four_csv_rows"][1:], "sha256": item["sha256"],
                "size_bytes": item["size_bytes"], "rows": None,
            }
        else:
            report["files"][filename] = {"inspection": "not_available"}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("data/derived/elliptic_schema_report.json"))
    args = parser.parse_args()
    report = inspect_dataset(args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
