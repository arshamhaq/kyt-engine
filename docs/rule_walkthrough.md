# A real wallet through the rule engine

The [76-column fixture](../testdata/elliptic_rule_walkthrough.csv) is one exact
row from `data/derived/canonical_feature_dataset.csv`. Its wallet ID is
`114H4VXXRicqSRhgjDorRidu6NJXsqBfan`. The dataset's recorded target `label`
is `illicit`; that label is **kept outside** the Go `FeatureVector` and is not a
rule input. The [walkthrough test](../internal/rules/walkthrough_test.go) reads
every column, maps all 74 feature columns to the vector, and passes that vector
to the [Go engine](../internal/rules/engine.go).

| Input group | Values in this row | Used by current rules? |
| --- | --- | --- |
| Identity/time | wallet ID above; timestep 24; first/last timestep 24; active span 0; one observed timestep | No; wallet ID is required for the finding |
| Supplied Elliptic++ numeric data | All 55 fields are loaded. Examples: `elliptic_f_006` = 2 total transactions; `f_010` = 0.0142 BTC transacted; `f_015` = 0.0071 BTC sent; `f_020` = 0.0071 BTC received; `f_025` ≈ 0.002664 total fees | Only `f_006` |
| Directed topology | in-degree 1, out-degree 1, total-degree 2; unique in/out neighbors 1 each; unique neighbors 2 | No |
| Undirected neighbor labels | one illicit, zero licit, one unknown; direct illicit-neighbor ratio = 1/2 = 0.5 | Only the precomputed ratio |
| Wider graph intelligence | one distinct illicit neighbor at one hop; 147 distinct illicit nodes exactly two hops away; another known illicit node is at distance 1 | Only the two-hop count |
| Target metadata | `label = illicit` | Never |

The current six rules deliberately inspect only **three distinct feature
values**: `direct_illicit_neighbor_ratio`, `two_hop_illicit_count`, and
`elliptic_f_006` (total transactions). The earlier boundary test populated
only those three values to isolate threshold behavior. It was not a full
feature-vector example. The real-row test loads all 74 features, even though
the other 71 do not affect these six rules.

| Rule | Check on this row | Result |
| --- | --- | --- |
| R1 | Direct illicit-neighbor ratio 0.5 ≥ 0.2 | Match |
| R2 | Two-hop illicit count 147 ≥ 50 | Match |
| R4 | Direct illicit-neighbor ratio 0.5 < 0.6 | No match |
| R5 | Two-hop illicit count 147 ≥ 100 | Match |
| R6 | Ratio 0.5 ≥ 0.1 **and** two-hop count 147 ≥ 2 | Match |
| R7 | Ratio 0.5 ≥ 0.1 **and** total transactions 2 ≥ 2 | Match |

The output is **five explainable `RuleFinding` records**: R1, R2, R5, R6,
and R7. Each includes the rule ID, a human-readable reason, and observed values
beside thresholds. The engine does **not** output `illicit`, a probability, or
a risk score. `illicit` is the dataset's separate target for this example.
Some findings reuse the same graph evidence: R5 is a stricter R2, while R1,
R6, and R7 all use the direct ratio. Five matches are not five independent
pieces of evidence.

## Exact explainable output

Serialized as JSON, the exact `[]RuleFinding` result returned by
`RuleEngine.Evaluate` is:

```json
[
  {
    "WalletID": "114H4VXXRicqSRhgjDorRidu6NJXsqBfan",
    "RuleID": "R1",
    "Family": "direct_exposure",
    "Reason": "At least 20% of distinct graph neighbors are labeled illicit.",
    "Evidence": [
      {
        "Feature": "direct_illicit_neighbor_ratio",
        "Operator": ">=",
        "Observed": 0.5,
        "Threshold": 0.2
      }
    ]
  },
  {
    "WalletID": "114H4VXXRicqSRhgjDorRidu6NJXsqBfan",
    "RuleID": "R2",
    "Family": "two_hop_exposure",
    "Reason": "At least 50 distinct illicit wallets are exactly two undirected graph hops away.",
    "Evidence": [
      {
        "Feature": "two_hop_illicit_count",
        "Operator": ">=",
        "Observed": 147,
        "Threshold": 50
      }
    ]
  },
  {
    "WalletID": "114H4VXXRicqSRhgjDorRidu6NJXsqBfan",
    "RuleID": "R5",
    "Family": "two_hop_exposure",
    "Reason": "At least 100 distinct illicit wallets are exactly two hops away; stricter than R2.",
    "Evidence": [
      {
        "Feature": "two_hop_illicit_count",
        "Operator": ">=",
        "Observed": 147,
        "Threshold": 100
      }
    ]
  },
  {
    "WalletID": "114H4VXXRicqSRhgjDorRidu6NJXsqBfan",
    "RuleID": "R6",
    "Family": "corroborated_graph_exposure",
    "Reason": "At least 10% illicit neighbors and at least two distinct illicit wallets exactly two hops away.",
    "Evidence": [
      {
        "Feature": "direct_illicit_neighbor_ratio",
        "Operator": ">=",
        "Observed": 0.5,
        "Threshold": 0.1
      },
      {
        "Feature": "two_hop_illicit_count",
        "Operator": ">=",
        "Observed": 147,
        "Threshold": 2
      }
    ]
  },
  {
    "WalletID": "114H4VXXRicqSRhgjDorRidu6NJXsqBfan",
    "RuleID": "R7",
    "Family": "exposure_with_activity",
    "Reason": "At least 10% illicit neighbors and at least two total transactions in the provided wallet features.",
    "Evidence": [
      {
        "Feature": "direct_illicit_neighbor_ratio",
        "Operator": ">=",
        "Observed": 0.5,
        "Threshold": 0.1
      },
      {
        "Feature": "elliptic_f_006",
        "Operator": ">=",
        "Observed": 2,
        "Threshold": 2
      }
    ]
  }
]
```

This is the complete rule-engine result for the example. It contains findings
and their evidence; it does not contain a final classification, probability,
or risk score. Those outputs require the future risk aggregator.

Run the example with:

```sh
go test ./internal/rules -run TestFullIllicitWalletWalkthrough -v
```

The canonical CSV's graph features use static public labels. They are not
point-in-time intelligence, and this row cannot demonstrate what would have
been known when the wallet was active. The held-out rule metrics in
[the analysis](rule_analysis.md) masked validation labels when rebuilding
neighbor intelligence, so those metrics do not describe this CSV replay.
