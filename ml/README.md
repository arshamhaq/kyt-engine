# Offline ML

The offline pipeline trains an explainable binary classifier on Elliptic++
wallets whose targets are `licit` or `illicit`. Unknown targets remain graph
nodes but never become negative examples.

The pipeline creates a fixed 70/15/15 wallet split, masks validation and test
labels before rebuilding graph-intelligence features, compares reviewed model
candidates on validation data, freezes a logistic model and threshold, and
evaluates the test partition once. Accuracy is reported but is not the gate
because the supervised data are imbalanced.

Install the reproducible environment and run training from the repository root:

```sh
python -m pip install -r requirements-ml.txt
python -m ml.train
```

Outputs:

- `models/elliptic-logistic-v1/model.json`: portable coefficients and preprocessing
- `models/elliptic-logistic-v1/metrics.json`: model-selection and test metrics
- `models/elliptic-logistic-v1/split_manifest.json`: split and leakage audit
- `docs/ml_analysis.md`: readable methodology, result, and example explanation

The JSON scorer in `ml/export.py` independently reproduces scikit-learn output.
The [native Go predictor](../docs/ml_predictor.md) loads the same artifact and is
covered by an exact Python/Go parity test.

Trace one fixed illicit test wallet through all transformations, coefficients,
and the final threshold with:

```sh
python -m ml.trace_prediction
```

See the [prediction walkthrough](../docs/ml_prediction_walkthrough.md).
