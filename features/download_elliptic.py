"""Download hash-verified CSVs from the official, pinned Elliptic++ release."""

import argparse
import csv
import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

REPOSITORY = "git-disl/EllipticPlusPlus"
REVISION = "08fe6aded83afb97bf5a79a71130f542ca783c2e"
ACTOR_FILES = (
    "wallets_features.csv", "wallets_classes.csv", "AddrAddr_edgelist.csv",
    "AddrTx_edgelist.csv", "TxAddr_edgelist.csv",
)
TRANSACTION_FILES = ("txs_features.csv", "txs_classes.csv", "txs_edgelist.csv")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_metadata(filename):
    folder = "Actors Dataset" if filename in ACTOR_FILES else "Transactions Dataset"
    relative = quote(f"{folder}/{filename}")
    pointer_url = f"https://raw.githubusercontent.com/{REPOSITORY}/{REVISION}/{relative}"
    with urlopen(pointer_url, timeout=90) as response:
        pointer = response.read().decode("utf-8")
    if not pointer.startswith("version https://git-lfs.github.com/spec/v1\n"):
        raise ValueError(f"Expected an official Git LFS pointer for {filename}")
    fields = dict(line.split(" ", 1) for line in pointer.strip().splitlines())
    return {
        "filename": filename, "repository_path": f"{folder}/{filename}",
        "sha256": fields["oid"].removeprefix("sha256:"),
        "size_bytes": int(fields["size"]),
        "url": f"https://media.githubusercontent.com/media/{REPOSITORY}/{REVISION}/{relative}",
    }


def preview(metadata):
    with urlopen(metadata["url"], timeout=90) as response:
        reader = csv.reader(io.TextIOWrapper(response, encoding="utf-8-sig", newline=""))
        return [next(reader) for _ in range(4)]


def download(metadata, raw_dir):
    destination = raw_dir / metadata["filename"]
    if destination.exists():
        if sha256_file(destination) != metadata["sha256"]:
            raise ValueError(f"Existing {destination} differs from the pinned official file")
        print(f"Verified existing {destination.name}", flush=True)
        return
    partial = destination.with_suffix(".csv.part")
    digest = hashlib.sha256()
    received = 0
    next_progress = 32 * 1024 * 1024
    print(f"Downloading {destination.name}: {metadata['size_bytes']:,} bytes", flush=True)
    with urlopen(metadata["url"], timeout=90) as response, partial.open("wb") as output:
        while block := response.read(4 * 1024 * 1024):
            output.write(block)
            digest.update(block)
            received += len(block)
            if received >= next_progress:
                print(f"  {destination.name}: {received:,} bytes", flush=True)
                next_progress += 32 * 1024 * 1024
    if received != metadata["size_bytes"] or digest.hexdigest() != metadata["sha256"]:
        raise ValueError(f"Incomplete or corrupt download: {partial}")
    partial.replace(destination)
    print(f"Verified {destination.name}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--include-transactions", action="store_true")
    parser.add_argument("--inspect-only", action="store_true", help="Read remote headers and three rows, without downloading full CSVs")
    parser.add_argument("--files", nargs="+", choices=ACTOR_FILES + TRANSACTION_FILES, help="Download or inspect only these official files")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    if args.workers < 1:
        parser.error("--workers must be positive")
    files = args.files or ACTOR_FILES + (TRANSACTION_FILES if args.include_transactions else ())
    manifest = {"repository": REPOSITORY, "revision": REVISION, "files": []}
    for filename in files:
        metadata = source_metadata(filename)
        if args.inspect_only:
            metadata["first_four_csv_rows"] = preview(metadata)
            print(json.dumps(metadata, ensure_ascii=False), flush=True)
        manifest["files"].append(metadata)
    if not args.inspect_only:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(lambda metadata: download(metadata, args.raw_dir), manifest["files"]))
    name = "remote_schema_preview.json" if args.inspect_only else "source_manifest.json"
    (args.raw_dir / name).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
