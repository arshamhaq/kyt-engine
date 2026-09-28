# Native Go ML predictor

The Go predictor loads the portable artifact produced by `python -m ml.train`
and performs the same calculation without Python or a native ML runtime:

```text
FeatureVector
  -> select the reviewed 65 fields in artifact order
  -> apply artifact imputation (when available)
  -> log1p or identity transform
  -> training mean/scale standardization
  -> coefficient multiplication
  -> sum with intercept
  -> sigmoid probability
  -> validation-selected threshold
  -> explainable Prediction
```

Load the model once at application startup and reuse the immutable predictor:

```go
predictor, err := ml.LoadPredictor("models/elliptic-logistic-v1/model.json")
if err != nil {
    return err
}

prediction, err := predictor.Predict(featureVector)
if err != nil {
    return err
}
```

`Prediction` contains the wallet ID, model version, illicit probability, decision
threshold, predicted class, log-odds, and the eight strongest positive and negative
feature contributions. Each contribution includes the raw value, source name,
standardized value, coefficient, and additive log-odds contribution. It never
contains or accepts the target label.

## Artifact validation

Loading fails before inference if the artifact has an unsupported format or model
type, an unexpected class mapping, a different feature-schema hash, a reordered or
missing feature, a different transform, invalid scaling, non-finite coefficients,
or an invalid threshold. Prediction also rejects non-finite/negative model inputs
and inconsistent graph counts or distance flags.

The current artifact learned no imputation for
`distance_to_other_known_illicit` because that value was present for every training
row. A vector with no known-illicit path is therefore rejected. Silently filling it
would create inference behavior that was never evaluated in Python.

## Python/Go parity

The cross-language test rebuilds the exact 65-feature Python trace for wallet
`15DaavwDvdatJa1dqHRbhAjeJ9nk8bPVqL`. Go reproduces:

```json
{
  "model_version": "elliptic-logistic-v1",
  "illicit_probability": 0.979978711595712,
  "decision_threshold": 0.693382385987544,
  "predicted_class": "illicit",
  "log_odds": 3.8907347208922918
}
```

Run the parity walkthrough with:

```sh
go test ./internal/ml -run TestGoPredictionMatchesExactPythonTrace -v
```

The test also compares the leading feature's standardized value and contribution
to the Python trace. Separate tests reject artifact contract drift and malformed
feature vectors. The predictor is not yet called by `KYTScorer`, HTTP, or the risk
aggregator.
