# Elliptic++ data setup

This directory holds local raw CSVs and generated feature tables. Large files are
excluded from Git. The small schema, inspection, and validation JSON reports are
kept for review. Python 3.10+ and `requirements-features.txt` are required; this
pipeline uses pandas, NumPy, and compact adjacency arrays, without NetworkX.

The source is the authors' [official Elliptic++ repository](https://github.com/git-disl/EllipticPlusPlus),
pinned to `08fe6aded83afb97bf5a79a71130f542ca783c2e`. Its CSVs use Git LFS.
Downloading an ordinary GitHub raw URL can produce a pointer instead of a CSV.
Our downloader fetches the official LFS media objects and verifies their SHA-256
and byte size against the pointers. Verified existing files are reused; mismatched
files cause an error rather than being overwritten. Incomplete downloads have a
`.part` suffix and are retried from the beginning on the next invocation.

From the repository root, use an activated Python virtual environment:

```sh
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements-features.txt

# Inspect the actual remote headers and three rows from all eight files.
python -m features.download_elliptic --raw-dir data/raw --inspect-only --include-transactions

# Download the five actor files; these total about 895 MB.
python -m features.download_elliptic --raw-dir data/raw

# Optional small transaction files used in the checked-in inspection report.
python -m features.download_elliptic --raw-dir data/raw --files wallets_features.csv wallets_classes.csv AddrAddr_edgelist.csv AddrTx_edgelist.csv TxAddr_edgelist.csv txs_classes.csv txs_edgelist.csv

# Full local schema inspection. Absent transaction features remain a marked preview.
python -m features.inspect_elliptic --raw-dir data/raw

python -m features.build_features --raw-dir data/raw --output data/derived/canonical_feature_dataset.csv
python -m features.validate_features --input data/derived/canonical_feature_dataset.csv
python -W error::ResourceWarning -m unittest discover -s tests -v
```

`--include-transactions` on a download also fetches the approximately 695 MB
`txs_features.csv`; it is optional and unused by this wallet feature builder.
The three required build inputs are `wallets_features.csv`, `wallets_classes.csv`,
and `AddrAddr_edgelist.csv`. Address/transaction membership and transaction labels
are inspected for schema context, never used to manufacture edge values or target
features. No blockchain node or external attribution service is needed.

Allow several GB of free disk space for raw data, the canonical table, and temporary
output, and several GB of RAM for the wallet matrix. Numeric parsing and validation
are chunked; the final 822,942-by-55 numeric matrix and compact graph remain in RAM.
`--chunksize` controls parsing/validation batches, not total matrix memory. Two-hop
work depends on high-degree neighborhoods, so runtime is not strictly linear.

Outputs:

- `raw/source_manifest.json`: pinned official source, sizes, and verified hashes.
- `raw/remote_schema_preview.json`: actual remote headers and three example rows.
- `derived/elliptic_schema_report.json`: full local scans, plus clearly marked previews.
- `derived/canonical_feature_dataset.csv`: one row per wallet; target `label` last.
- `derived/feature_schema.json`: exact column order and 55 original-header mappings.
- `derived/feature_report.json`: row/class counts, missing values, graph statistics,
  source verification, structural validation, and sampled target-exclusion audit.

The canonical CSV is published only after validation succeeds. A failed build can
leave a `.csv.part` for diagnosis. Standalone validation checks the table's structure;
only the builder also audits graph derivation against independent traversals.

For later supervised learning, select `label.isin(["licit", "illicit"])`, keep
`label` as y, and use the explicit `feature_columns` from `feature_schema.json`
for X. Do not silently relabel unknown wallets or treat `wallet_id` as a predictor.
The distance column is intentionally nullable; consult the feature documentation
before choosing a downstream model's missing-value representation.

Read [the inspected schema](../docs/elliptic_schema.md) and
[feature definitions, leakage limitations, and proposed Go contract](../docs/elliptic_features.md)
before using the dataset.
