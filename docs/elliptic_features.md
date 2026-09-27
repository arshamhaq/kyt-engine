# Elliptic++ canonical wallet features

This step only extracts an offline, educational feature dataset:

```text
Official Elliptic++ Actors CSVs -> schema inspection -> feature derivation
                              -> canonical_feature_dataset.csv
                              -> future Go rules and future ML model
```

There is no rule evaluation, training, scoring, API, blockchain ingestion,
sanctions/OFAC lookup, ransomware/mixer attribution, Kafka, Spark, or Stridge code.
The existing Go FeatureVector placeholder and all `concepts/` files remain untouched.

## Sources and row selection

The builder uses `wallets_features.csv` for provided numerical values and discrete
observations, `wallets_classes.csv` for class metadata and simulated neighbor
intelligence, and `AddrAddr_edgelist.csv` for connectivity. The official release
and exact inspected headers/examples are documented in [elliptic_schema.md](elliptic_schema.md).
`AddrTx_edgelist.csv`, `TxAddr_edgelist.csv`, and transaction files were inspected
for context. They are not feature-builder inputs. The large transaction feature
file was inspected only through its actual header and three remote rows.

There is **one row per wallet**, in first-observed input order. Numeric fields come
from that wallet's latest `Time step` row, chosen without consulting labels. The
provided wallet fields may themselves summarize the complete historical dataset;
selecting a latest observation does not make them a point-in-time reconstruction.

The full source has repeated wallet/timestep keys. Numerically identical repeated
observations are collapsed. All 55 values must agree, including across CSV chunks;
conflicting repeats cause an error. Timesteps are counted distinctly, so repeated
rows do not inflate activity. NaN/Inf in provided numerical fields cause an error;
there is no silent imputation, clipping, amount allocation, or normalization.

## Canonical schema

The exact ordered 76 columns are in `data/derived/feature_schema.json`:

```text
wallet_id
timestep
elliptic_f_001 ... elliptic_f_055
wallet_first_timestep
wallet_last_timestep
wallet_active_span
wallet_observed_timestep_count
in_degree
out_degree
total_degree
unique_in_neighbors
unique_out_neighbors
unique_neighbors
direct_illicit_neighbor_count
direct_licit_neighbor_count
direct_unknown_neighbor_count
direct_illicit_neighbor_ratio
one_hop_illicit_count
two_hop_illicit_count
distance_to_other_known_illicit
has_other_known_illicit_path
label
```

`wallet_id` is identifier metadata. `label` is target metadata and is always last.
The remaining **74 columns** are candidate features: 55 provided numeric values,
5 discrete temporal fields (including `timestep`), and 14 graph fields. Of these,
73 are required finite numeric values; distance is intentionally nullable. Future
ML should explicitly select this reviewed list and exclude the target/identifier.

## Feature definitions

| Column | Meaning |
| --- | --- |
| `wallet_id` | Original Bitcoin address string; no attribution beyond the dataset class. |
| `timestep` | Latest discrete dataset timestep observed for the wallet. |
| `elliptic_f_001`–`elliptic_f_055` | Unmodified provided numeric values, aliased in original CSV order. Exact original headers are preserved in the schema JSON and schema documentation. The actual wallet columns are named, not anonymized; opaque transaction columns are not imported. |
| `wallet_first_timestep` | Minimum observed dataset step. |
| `wallet_last_timestep` | Maximum observed dataset step; equals `timestep`. |
| `wallet_active_span` | Last minus first observed step; a single-step wallet has span 0. This is a discrete interval, not elapsed seconds. |
| `wallet_observed_timestep_count` | Number of distinct observed steps, not number of transactions. |
| `in_degree` | Incoming non-self edge-record count; duplicate edge records count. |
| `out_degree` | Outgoing non-self edge-record count; duplicate edge records count. |
| `total_degree` | Sum of incoming and outgoing edge-record counts. |
| `unique_in_neighbors` | Distinct incoming counterparty nodes. |
| `unique_out_neighbors` | Distinct outgoing counterparty nodes. |
| `unique_neighbors` | Distinct union of incoming/outgoing counterparties. |
| `direct_illicit_neighbor_count` | Distinct direct neighbors whose dataset class is illicit. |
| `direct_licit_neighbor_count` | Distinct direct neighbors whose dataset class is licit. |
| `direct_unknown_neighbor_count` | Distinct direct neighbors whose class is unknown or missing. |
| `direct_illicit_neighbor_ratio` | Illicit direct-neighbor count divided by all unique neighbors, including unknown; 0 for no neighbors. **Graph-neighbor exposure**, not monetary exposure. |
| `one_hop_illicit_count` | Alias of the direct illicit-neighbor count, kept for the requested hop schema. |
| `two_hop_illicit_count` | Number of distinct illicit nodes at shortest undirected distance exactly 2. Target and all direct neighbors are excluded. |
| `distance_to_other_known_illicit` | Shortest undirected path length to an illicit node other than the target. Positive integer when reachable; empty CSV field otherwise. Never 0. |
| `has_other_known_illicit_path` | 1 when that other-node distance exists, 0 otherwise. Distinguishes absence without substituting a misleading zero distance. |
| `label` | `licit`, `illicit`, or `unknown`; supervised target/metadata, never a feature. |

The counts partition unique neighbors; unknown neighbors remain in the denominator.
Missing label records default explicitly to unknown and are counted in the report.
The real release has a class record for every canonical wallet. For supervised ML
later, only licit and illicit target rows are eligible. Unknown is neither licit
nor proof of innocence, and is never silently converted into a negative class.

## Graph semantics and implementation

Directed edge direction is preserved for degree and unique-in/out counts.
Intelligence uses a **simple undirected topology**, a deliberate v1 simplification.
An incoming illicit counterparty and an outgoing illicit counterparty both count
as neighbor exposure; this does not distinguish funding from payment direction.
The graph is the union of the supplied edges, not a temporal snapshot.

All self-loop records are removed before any degree or intelligence computation.
Duplicate records remain in raw directed degrees, but are deduplicated for unique
neighbors, ratios, hop sets, and distances. Raw degree therefore describes CSV
records, not inferred transaction counts or blockchain multiedge semantics.
Nodes appearing only in labels or edges are retained in the graph; those missing
class records are unknown. Only wallets with feature observations get output rows.

For target T, the two-hop set is the union of neighbors of its direct neighbors,
minus T and all direct neighbors. Multiple routes count a node once. Cycles cannot
introduce T, and triangles do not put one-hop nodes into the two-hop count.

Memory is proportional to graph nodes/edges rather than all possible two-hop pairs.
The implementation uses integer-indexed NumPy CSR adjacency arrays. Two-hop counts
are accumulated by reversing the undirected traversal from each illicit source,
with generation markers deduplicating destinations. Distance uses a multi-source
BFS that keeps the two nearest distinct illicit sources per node. An illicit
target uses the other source; any target's own source cannot contribute. High-degree
neighborhoods can increase two-hop runtime, although no dense squared matrix or
per-wallet Python graph object is allocated.

## Labels as simulated intelligence and leakage limitations

`1 = illicit`, `2 = licit`, and `3 = unknown` are the authors' verified class mapping.
Here illicit means only the dataset's coarse class. No inspected actor label field
identifies sanctions, ransomware, mixers, OFAC, or a particular criminal activity.
We do not infer these categories or name features after them.

Neighbor labels act as an **educational approximation of upstream historical
intelligence**. The target's own class is excluded from direct sets, two-hop sets,
ratios, and distance candidates. Provided/temporal values never consult labels.
The target label is joined after feature construction. Changing only a target's
class must leave all its feature values unchanged; other wallets' intelligence
features may change because they observe that wallet as a neighbor.

Synthetic/random tests rebuild graph features under all three possible target
classes and compare unchanged target rows. The builder also compares a deterministic
sample of real wallets against an independent per-target set/BFS implementation,
with explicit self exclusion and target-class mutation. The report gives the
sample size; this is not an exhaustive real-graph label-mutation audit. Structural
CSV validation alone cannot establish which labels were used in construction.

**This table is not guaranteed free of historical or evaluation leakage.** Public
labels are static and are not point-in-time intelligence snapshots. Full graph
connectivity, latest observations, and provided lifetime aggregates may reveal
information from after an earlier decision time. Labels of future evaluation
wallets must not automatically become known neighbor intelligence in a later
supervised benchmark. Before training, define a held-out split and restrict the
intelligence source to permitted historical/training labels, or evaluate this
explicitly as a transductive experiment. The current table accepts stronger static
knowledge for educational feature/schema review, not claimed production accuracy.
No training or split protocol is implemented in this step.

## Amounts and unavailable production features

Named wallet fields include BTC sent, received, and transacted aggregates; we
preserve them as provided. Transaction features also contain aggregate BTC values.
However, address/address and address/transaction edges have **no amount or allocation
weight**. Membership alone cannot allocate transaction funds to counterparties.

Consequently we do not derive `direct_illicit_volume`, `direct_illicit_amount_ratio`,
`one_hop_illicit_volume`, weighted illicit monetary exposure, or funds-origin
proportions. Neighbor exposure may describe connectivity even when monetary
exposure is tiny, large, or unknown. No monetary claim follows from this ratio.

There are no edge/event wall-clock timestamps, so `recent_activity_count` in a
fixed time window, 24-hour volume spikes, and rapid-forwarding ratios are not
derived. The available discrete steps support first/last/span/observed-step
summaries only. Coarse classes cannot yield category-specific attribution,
sanctions proximity, ransomware exposure, mixer ratios, or verified ownership.

## Validation and review

The builder rejects unexpected headers, blank IDs, invalid classes, conflicting
observations, and nonfinite raw numeric values. The output validator checks global
wallet uniqueness across chunks, target existence/allowed values, nonnegative
integer degrees/counts, ratio bounds and denominator, degree/count consistency,
finite required features, coherent discrete-time summaries, and positive-or-null
other-node distances with a matching presence flag. No absent distance is encoded
as 0. Report/schema JSONs use strict JSON without NaN/Infinity.

The synthetic A→B, A→C, B→D fixture has A licit, B/D illicit, C unknown. A has one
direct illicit and one direct unknown neighbor, ratio 0.5, one exact two-hop illicit
node (D), and distance 1 to another illicit node. Tests additionally cover isolated
illicit targets, no illicit paths, cycles, self-loops, duplicate routes, missing
labels, edge reversal, target mutations, and malformed raw/derived data.

See [data/README.md](../data/README.md) for reproducible commands and
`data/derived/feature_report.json` for the completed full-data run.

The completed run produced 822,942 unique wallets and 76 columns, with 251,088
licit, 14,266 illicit, and 557,588 unknown targets. Only 265,354 rows are eligible
for later binary supervised learning. All 73 required feature columns are finite
and complete; seven nullable distances indicate no path to another illicit node.
Present distances range from 1 to 52. Structural validation and the independent
16-wallet real-graph audit passed. The 19 synthetic/pipeline tests pass, including
480 target-class mutations across 20 random eight-node graphs.

## Proposed Go FeatureVector — review only

The following is a proposal, not Go implementation. `internal/domain/feature_vector.go`
has not been changed. An ordered fixed array avoids 55 arbitrary semantic names;
the future CSV adapter maps index 0 to `elliptic_f_001` through index 54 to
`elliptic_f_055` using the reviewed schema. Integer types match discrete counts.
The path flag is a Boolean interpretation of CSV 0/1, and nil distance means no
path to another illicit node. Label stays outside the scoring FeatureVector.

```go
type FeatureVector struct {
    WalletID string
    Timestep int64
    EllipticNumeric [55]float64 // CSV elliptic_f_001 ... elliptic_f_055, in order

    WalletFirstTimestep         int64
    WalletLastTimestep          int64
    WalletActiveSpan            int64
    WalletObservedTimestepCount int64

    InDegree           int64
    OutDegree          int64
    TotalDegree        int64
    UniqueInNeighbors  int64
    UniqueOutNeighbors int64
    UniqueNeighbors    int64

    DirectIllicitNeighborCount int64
    DirectLicitNeighborCount   int64
    DirectUnknownNeighborCount int64
    DirectIllicitNeighborRatio float64
    OneHopIllicitCount         int64
    TwoHopIllicitCount         int64
    DistanceToOtherKnownIllicit *int64
    HasOtherKnownIllicitPath    bool
}
```

This maps every feature in the final table, with `WalletID` carried as identity
metadata. It does not introduce monetary exposure or unobserved attribution fields.
Review the schema before implementing the Go contract or choosing a model's
nullable-distance handling. Unknown-target filtering and any later normalization
belong to a future training step, not this extraction pipeline.
