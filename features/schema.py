"""Contracts verified against the pinned official Elliptic++ CSV headers."""

import csv
from pathlib import Path

import pandas as pd

CLASS_LABELS = {"1": "illicit", "2": "licit", "3": "unknown"}
WALLET_FEATURE_COLUMNS = (
    "num_txs_as_sender", "num_txs_as receiver", "first_block_appeared_in",
    "last_block_appeared_in", "lifetime_in_blocks", "total_txs",
    "first_sent_block", "first_received_block", "num_timesteps_appeared_in",
    "btc_transacted_total", "btc_transacted_min", "btc_transacted_max",
    "btc_transacted_mean", "btc_transacted_median", "btc_sent_total",
    "btc_sent_min", "btc_sent_max", "btc_sent_mean", "btc_sent_median",
    "btc_received_total", "btc_received_min", "btc_received_max",
    "btc_received_mean", "btc_received_median", "fees_total", "fees_min",
    "fees_max", "fees_mean", "fees_median", "fees_as_share_total",
    "fees_as_share_min", "fees_as_share_max", "fees_as_share_mean",
    "fees_as_share_median", "blocks_btwn_txs_total", "blocks_btwn_txs_min",
    "blocks_btwn_txs_max", "blocks_btwn_txs_mean", "blocks_btwn_txs_median",
    "blocks_btwn_input_txs_total", "blocks_btwn_input_txs_min",
    "blocks_btwn_input_txs_max", "blocks_btwn_input_txs_mean",
    "blocks_btwn_input_txs_median", "blocks_btwn_output_txs_total",
    "blocks_btwn_output_txs_min", "blocks_btwn_output_txs_max",
    "blocks_btwn_output_txs_mean", "blocks_btwn_output_txs_median",
    "num_addr_transacted_multiple", "transacted_w_address_total",
    "transacted_w_address_min", "transacted_w_address_max",
    "transacted_w_address_mean", "transacted_w_address_median",
)
FEATURE_MAP = {f"elliptic_f_{i:03d}": name for i, name in enumerate(WALLET_FEATURE_COLUMNS, 1)}
EXPECTED_HEADERS = {
    "wallets_features.csv": ["address", "Time step", *WALLET_FEATURE_COLUMNS],
    "wallets_classes.csv": ["address", "class"],
    "AddrAddr_edgelist.csv": ["input_address", "output_address"],
    "AddrTx_edgelist.csv": ["input_address", "txId"],
    "TxAddr_edgelist.csv": ["txId", "output_address"],
    "txs_classes.csv": ["txId", "class"],
    "txs_edgelist.csv": ["txId1", "txId2"],
    "txs_features.csv": ["txId", "Time step"]
    + [f"Local_feature_{i}" for i in range(1, 94)]
    + [f"Aggregate_feature_{i}" for i in range(1, 73)]
    + ["in_txs_degree", "out_txs_degree", "total_BTC", "fees", "size",
       "num_input_addresses", "num_output_addresses", "in_BTC_min",
       "in_BTC_max", "in_BTC_mean", "in_BTC_median", "in_BTC_total",
       "out_BTC_min", "out_BTC_max", "out_BTC_mean", "out_BTC_median", "out_BTC_total"],
}
TEMPORAL_COLUMNS = ["wallet_first_timestep", "wallet_last_timestep", "wallet_active_span", "wallet_observed_timestep_count"]
GRAPH_COLUMNS = [
    "in_degree", "out_degree", "total_degree", "unique_in_neighbors",
    "unique_out_neighbors", "unique_neighbors", "direct_illicit_neighbor_count",
    "direct_licit_neighbor_count", "direct_unknown_neighbor_count",
    "direct_illicit_neighbor_ratio", "one_hop_illicit_count", "two_hop_illicit_count",
    "distance_to_other_known_illicit", "has_other_known_illicit_path",
]
CANONICAL_COLUMNS = ["wallet_id", "timestep", *FEATURE_MAP, *TEMPORAL_COLUMNS, *GRAPH_COLUMNS, "label"]
NULLABLE_COLUMN = "distance_to_other_known_illicit"
ML_COLUMNS = CANONICAL_COLUMNS[1:-1]
REQUIRED_ML_COLUMNS = [column for column in ML_COLUMNS if column != NULLABLE_COLUMN]


def csv_header(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        header = next(csv.reader(source))
    if not header or len(set(header)) != len(header):
        raise ValueError(f"Empty or duplicate CSV header in {path}")
    if header[0].startswith("version https://git-lfs"):
        raise ValueError(f"{path} is a Git LFS pointer, not the dataset")
    return header


def require_schema(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Missing {path}; run python -m features.download_elliptic")
    if csv_header(path) != EXPECTED_HEADERS[path.name]:
        raise ValueError(f"Unexpected schema in {path}; inspect the actual headers before adapting the pipeline")


def load_classes(path):
    require_schema(path)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if (frame["address"].str.strip() != frame["address"]).any() or (frame["address"] == "").any():
        raise ValueError("Wallet labels contain blank or whitespace-padded IDs")
    if frame["address"].duplicated().any():
        raise ValueError("Duplicate wallet labels")
    if not frame["class"].isin(CLASS_LABELS).all():
        raise ValueError("Wallet classes must contain only verified codes 1, 2, 3")
    return frame.set_index("address")["class"]
