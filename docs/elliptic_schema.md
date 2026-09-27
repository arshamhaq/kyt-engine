# Inspected Elliptic++ schema

Source: the authors' [official repository](https://github.com/git-disl/EllipticPlusPlus),
pinned to `08fe6aded83afb97bf5a79a71130f542ca783c2e`. The CSVs are Git LFS objects:
ordinary GitHub raw downloads return pointers, not data. The downloader resolves
the official media endpoint and checks each object against its published SHA-256
and byte size. `data/raw/remote_schema_preview.json` records the actual header and
first three data rows of all eight files. These were read before the builder was written.

| Actual file | Actual columns | Interpretation |
| --- | --- | --- |
| `wallets_features.csv` | `address`, `Time step`, 55 named numeric columns | 57 columns; the published 56 features include the timestep. Multiple observations per wallet. |
| `wallets_classes.csv` | `address`, `class` | Wallet-level target codes, not risk subcategories. |
| `AddrAddr_edgelist.csv` | `input_address`, `output_address` | Directed connectivity; self-loops occur in the actual sample. |
| `AddrTx_edgelist.csv` | `input_address`, `txId` | Address appearing as a transaction input. |
| `TxAddr_edgelist.csv` | `txId`, `output_address` | Transaction output address. |
| `txs_features.csv` | `txId`, `Time step`, `Local_feature_1`–`93`, `Aggregate_feature_1`–`72`, 17 named columns below | 184 columns; 182 numeric features plus timestep and ID. |
| `txs_classes.csv` | `txId`, `class` | Transaction-level target codes. |
| `txs_edgelist.csv` | `txId1`, `txId2` | Directed transaction connectivity only. |

The transaction feature file's 17 named columns are `in_txs_degree`,
`out_txs_degree`, `total_BTC`, `fees`, `size`, `num_input_addresses`,
`num_output_addresses`, `in_BTC_min`, `in_BTC_max`, `in_BTC_mean`, `in_BTC_median`,
`in_BTC_total`, `out_BTC_min`, `out_BTC_max`, `out_BTC_mean`, `out_BTC_median`,
and `out_BTC_total`. The numbered local/aggregate fields remain opaque.
Its actual remote header and rows were inspected, but its additional 694,789,588
bytes are not needed for the wallet builder. The inspection report distinguishes
this remote preview from full local scans.

## Identifiers, classes, time, and values

- Wallet identifier: `address`, a Bitcoin-address string, not an anonymized integer ID.
  Sample: `111112TykSw72ztDN2WJger4cynzWYC5w`. The inspector checks Base58Check
  on sample IDs; syntactic validity does not establish ownership or attribution.
- Transaction identifier: `txId`, a numeric dataset ID such as `230325127`;
  it is not a 64-character blockchain transaction hash.
- Actual class values: `1`, `2`, `3`. The authors define these as illicit,
  licit, and unknown respectively. Full-file class distributions are checked
  independently by `inspect_elliptic.py`; unknown remains unknown.
- Time: `Time step` is discrete dataset time. Block heights and block intervals
  also occur among wallet features. No inspected file contains a wall-clock
  timestamp or an address-edge event time. No conversion to hours/days is justified.
- Values: wallet columns include named BTC aggregates. Transaction feature rows
  also have BTC aggregates. **None of the three actor edge files has an amount,
  output value, timestamp, or allocation weight.** Address membership in a
  transaction does not prove how its BTC was allocated among individual edges.

## Actual example rows

```text
wallets_classes.csv:
address,class
111112TykSw72ztDN2WJger4cynzWYC5w,2
1111DAYXhoxZx2tsRnzimfozo783x1yC2,3
1111VHuXEzHaRCgXbVwojtaP7Co3QABb,2

AddrAddr_edgelist.csv:
input_address,output_address
14YRXHHof4BY1TVxN5FqYPcEdpmXiYT78a,1GASxu5nMntiRKdVtTVRvEbP965G51bhHH
14YRXHHof4BY1TVxN5FqYPcEdpmXiYT78a,14YRXHHof4BY1TVxN5FqYPcEdpmXiYT78a
13Lhad3SAmu2vqYg2dxbNcxH7LE77kJu2w,1GFdrdgtG34GChM8SMpMwcXFc4nYbH1A5G

AddrTx_edgelist.csv:
input_address,txId
14YRXHHof4BY1TVxN5FqYPcEdpmXiYT78a,230325127
13Lhad3SAmu2vqYg2dxbNcxH7LE77kJu2w,230325139
1MAQQZn7EHP6J3erXByCciFiVcgS8ZhWqz,86875675

TxAddr_edgelist.csv:
txId,output_address
230325127,1GASxu5nMntiRKdVtTVRvEbP965G51bhHH
230325127,14YRXHHof4BY1TVxN5FqYPcEdpmXiYT78a
230325139,1GFdrdgtG34GChM8SMpMwcXFc4nYbH1A5G
```

The first wallet feature observation has timestep `25`, `num_txs_as_sender=0`,
`num_txs_as receiver=1`, and `btc_transacted_total=0.0106281`. The next wallet
appears at steps `25` and `29`, with the same numeric features in those two rows.
The complete examples are in the inspection JSON, without truncating feature values.

## Exact wallet feature mapping

The actual wallet headers are descriptive, not numbered anonymous fields. We still
use deterministic aliases `elliptic_f_001`–`elliptic_f_055` for a stable canonical
contract, preserving the exact original headers in `feature_schema.json` and
`features/schema.py`. `Time step` becomes `timestep` separately. The full source
column list is in that mapping and the inspection report; no semantic name is invented.

Wallet feature families present in the header are transaction counts; first/last
block heights and lifetime; BTC sent/received/transacted aggregates; fees and fee
shares; block intervals between transactions; and repeated-counterparty statistics.
These are provided historical aggregates, not point-in-time reconstructed features.

## Completed full-file inspection

| Local file | Data rows | Unique identifiers when applicable |
| --- | ---: | ---: |
| `wallets_features.csv` | 1,268,260 | 822,942 addresses |
| `wallets_classes.csv` | 822,942 | 822,942 addresses |
| `AddrAddr_edgelist.csv` | 2,868,964 | Edge records |
| `AddrTx_edgelist.csv` | 477,117 | Membership records |
| `TxAddr_edgelist.csv` | 837,124 | Membership records |
| `txs_classes.csv` | 203,769 | 203,769 transaction IDs |
| `txs_edgelist.csv` | 234,355 | Edge records |

The actual wallet steps are the integers 1 through 49. Wallet classes contain
14,266 illicit, 251,088 licit, and 557,588 unknown records. Transaction classes
contain 4,545 illicit, 42,019 licit, and 157,205 unknown records. All seven fully
scanned files have no missing CSV fields or infinite numeric values.

There are 920,691 distinct wallet/timestep observations. The remaining 347,569
feature rows repeat 246,545 keys with identical numeric values; the builder verifies
all 55 values before collapsing them. There are 61,487 wallets observed at multiple
steps. Address edges contain 45,981 self-loop records and 47,346 repeated non-self
directed records. After self removal and deduplication, 2,775,637 directed edges
or 2,772,474 undirected edges remain. All graph nodes have a class record in this release.

`data/derived/elliptic_schema_report.json` records each full header, three complete
example rows, exact byte size, verified source hash, and scan statistics. The
transaction feature file remains explicitly marked as a remote preview, with no
claimed full-file row count or missing-value scan.

## Complete provided-column mapping

The literal space in `num_txs_as receiver` is part of the actual header.

| Canonical column | Actual source header |
| --- | --- |
| `elliptic_f_001` | `num_txs_as_sender` |
| `elliptic_f_002` | `num_txs_as receiver` |
| `elliptic_f_003` | `first_block_appeared_in` |
| `elliptic_f_004` | `last_block_appeared_in` |
| `elliptic_f_005` | `lifetime_in_blocks` |
| `elliptic_f_006` | `total_txs` |
| `elliptic_f_007` | `first_sent_block` |
| `elliptic_f_008` | `first_received_block` |
| `elliptic_f_009` | `num_timesteps_appeared_in` |
| `elliptic_f_010` | `btc_transacted_total` |
| `elliptic_f_011` | `btc_transacted_min` |
| `elliptic_f_012` | `btc_transacted_max` |
| `elliptic_f_013` | `btc_transacted_mean` |
| `elliptic_f_014` | `btc_transacted_median` |
| `elliptic_f_015` | `btc_sent_total` |
| `elliptic_f_016` | `btc_sent_min` |
| `elliptic_f_017` | `btc_sent_max` |
| `elliptic_f_018` | `btc_sent_mean` |
| `elliptic_f_019` | `btc_sent_median` |
| `elliptic_f_020` | `btc_received_total` |
| `elliptic_f_021` | `btc_received_min` |
| `elliptic_f_022` | `btc_received_max` |
| `elliptic_f_023` | `btc_received_mean` |
| `elliptic_f_024` | `btc_received_median` |
| `elliptic_f_025` | `fees_total` |
| `elliptic_f_026` | `fees_min` |
| `elliptic_f_027` | `fees_max` |
| `elliptic_f_028` | `fees_mean` |
| `elliptic_f_029` | `fees_median` |
| `elliptic_f_030` | `fees_as_share_total` |
| `elliptic_f_031` | `fees_as_share_min` |
| `elliptic_f_032` | `fees_as_share_max` |
| `elliptic_f_033` | `fees_as_share_mean` |
| `elliptic_f_034` | `fees_as_share_median` |
| `elliptic_f_035` | `blocks_btwn_txs_total` |
| `elliptic_f_036` | `blocks_btwn_txs_min` |
| `elliptic_f_037` | `blocks_btwn_txs_max` |
| `elliptic_f_038` | `blocks_btwn_txs_mean` |
| `elliptic_f_039` | `blocks_btwn_txs_median` |
| `elliptic_f_040` | `blocks_btwn_input_txs_total` |
| `elliptic_f_041` | `blocks_btwn_input_txs_min` |
| `elliptic_f_042` | `blocks_btwn_input_txs_max` |
| `elliptic_f_043` | `blocks_btwn_input_txs_mean` |
| `elliptic_f_044` | `blocks_btwn_input_txs_median` |
| `elliptic_f_045` | `blocks_btwn_output_txs_total` |
| `elliptic_f_046` | `blocks_btwn_output_txs_min` |
| `elliptic_f_047` | `blocks_btwn_output_txs_max` |
| `elliptic_f_048` | `blocks_btwn_output_txs_mean` |
| `elliptic_f_049` | `blocks_btwn_output_txs_median` |
| `elliptic_f_050` | `num_addr_transacted_multiple` |
| `elliptic_f_051` | `transacted_w_address_total` |
| `elliptic_f_052` | `transacted_w_address_min` |
| `elliptic_f_053` | `transacted_w_address_max` |
| `elliptic_f_054` | `transacted_w_address_mean` |
| `elliptic_f_055` | `transacted_w_address_median` |
