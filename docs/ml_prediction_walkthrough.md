# Exact ML prediction walkthrough

This walkthrough reproduces one real wallet from the fixed Elliptic++ test
partition. The wallet is `15DaavwDvdatJa1dqHRbhAjeJ9nk8bPVqL`; its dataset
target metadata is `illicit`. The target is read only after scoring for evaluation
and never enters the 65-feature model input.

Run the trace from the repository root:

```sh
python -m ml.trace_prediction
```

The complete machine-readable trace, including all 65 raw inputs and contributions,
is [example_prediction.json](../models/elliptic-logistic-v1/example_prediction.json).

## Important input values

| Feature | Value |
| --- | ---: |
| Transactions as sender / receiver | 1 / 1 |
| Total transactions | 2 |
| BTC transacted / sent / received | 0.36142212 / 0.18071106 / 0.18071106 |
| Total fees | 0.00095604 |
| In-degree / out-degree | 1 / 1 |
| Unique neighbors | 2 |
| Direct illicit / licit / unknown neighbors | 1 / 1 / 0 |
| Direct illicit-neighbor ratio | 0.5 |
| Exact two-hop illicit count | 4 |
| Distance to another known illicit wallet | 1 |

The graph intelligence above was rebuilt using training-wallet labels only. The
test wallet's own `illicit` target and every other held-out target were masked.

## Exact calculation and result

Each raw feature is transformed exactly as recorded in `model.json`, standardized
with training-only statistics, and multiplied by its logistic coefficient:

```text
feature contribution = standardized feature value × coefficient
log-odds             = intercept + sum(all 65 contributions)
probability          = sigmoid(log-odds)
```

For this wallet:

```json
{
  "wallet_id": "15DaavwDvdatJa1dqHRbhAjeJ9nk8bPVqL",
  "target_metadata": "illicit",
  "target_used_for_scoring": false,
  "intercept": -8.772131602282693,
  "sum_of_feature_contributions": 12.662866323174983,
  "log_odds": 3.8907347208922918,
  "illicit_probability": 0.979978711595712,
  "decision_threshold": 0.693382385987544,
  "predicted_class": "illicit"
}
```

The exact threshold comparison is:

```text
0.979978711595712 >= 0.693382385987544
```

The prediction is therefore `illicit`, matching the separately stored test target.

## Strongest positive factors

| Feature | Raw value | Standardized value | Coefficient | Log-odds contribution |
| --- | ---: | ---: | ---: | ---: |
| Direct illicit-neighbor count | 1 | 3.0063 | 0.9966 | +2.9962 |
| Direct illicit-neighbor ratio | 0.5 | 3.6858 | 0.7626 | +2.8107 |
| Transactions as sender (`elliptic_f_001`) | 1 | 0.9201 | 2.3896 | +2.1987 |
| Exact two-hop illicit count | 4 | 0.9268 | 1.7741 | +1.6442 |
| Total transactions (`elliptic_f_006`) | 2 | 1.1842 | 0.9553 | +1.1313 |

These factors provide a readable high-level explanation: half of the wallet's two
direct neighbors are in the training intelligence inventory as illicit, four more
known illicit wallets are exactly two hops away, and the wallet has observable
transaction activity.

The direct licit-neighbor count also contributes `+1.0465`, which initially looks
counterintuitive. Its raw value is below the training mean after transformation,
so its standardized value is negative (`-0.3700`). The learned coefficient is also
negative (`-2.8285`); multiplying two negatives produces a positive contribution.
This illustrates why an explanation must include transformed values and coefficients,
not only raw inputs.

## Strongest negative factors

| Feature | Raw value | Log-odds contribution |
| --- | ---: | ---: |
| In-degree | 1 | -0.5670 |
| Mean blocks between output transactions | 0 | -0.4837 |
| Mean fee | 0.00047802 | -0.4143 |
| BTC sent total | 0.18071106 | -0.3112 |
| Mean blocks between input transactions | 0 | -0.2728 |

These reduce the illicit score, but together they are much smaller than the main
positive graph and activity contributions.

## Explainability assessment

This is sufficient for the educational capstone: the result is deterministic,
the target is excluded, the calculation sums exactly, source feature names are
shown, and an analyst can see which observations increased or decreased the score.

It is not yet sufficient for a production analyst decision. Several inputs are
correlated or overlapping—for example direct illicit count, direct illicit ratio,
and two-hop exposure—so individual coefficients are not independent evidence.
The rule engine uses some of the same graph signals, meaning the future aggregator
must not count rule and ML outputs as unrelated corroboration. Static Elliptic++
labels are also not point-in-time intelligence, and contributions explain the
model calculation rather than causation or criminal attribution.

Before production use, explanations should group correlated fields into behavior,
direct intelligence, and wider-graph families; show those group effects to analysts;
and be validated on external, time-separated, entity-aware data.
