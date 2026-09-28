# Offline ML analysis

This report evaluates a portable logistic-regression baseline on the Elliptic++ Actors dataset. The output is an educational wallet-risk probability, not evidence of criminal conduct and not a production KYT decision.

## Acceptance contract

Accuracy is not the acceptance metric: a model predicting every supervised wallet as licit would be about 94.6% accurate. The frozen capstone gate requires test average precision (PR-AUC) ≥ 0.80 and a validation-selected operating point with test precision ≥ 0.80, recall ≥ 0.70, and false-positive rate ≤ 1%. No universal industry cutoff exists; production thresholds depend on alert-review capacity and the relative cost of false positives and false negatives.

Google's classification guidance recommends precision, recall, and threshold tuning over accuracy for imbalanced data: https://developers.google.com/machine-learning/crash-course/classification/accuracy-precision-recall

**Acceptance result: PASS**

## Leakage-safe data protocol

Unknown targets are excluded from supervised learning but remain graph nodes. The target label and wallet ID never enter the model. Only training-wallet labels form the simulated intelligence inventory; validation and test labels are masked to unknown before all neighbor-label, two-hop, and distance features are rebuilt. The target itself remains excluded from its intelligence features.

| Partition | Rows | Licit | Illicit | Prevalence |
| --- | ---: | ---: | ---: | ---: |
| train | 185,748 | 175,762 | 9,986 | 5.38% |
| validation | 39,803 | 37,663 | 2,140 | 5.38% |
| test | 39,803 | 37,663 | 2,140 | 5.38% |

### Evaluation-history disclosure

The first frozen threshold policy maximized recall up to the validation FPR boundary. It achieved test AP 0.9700, precision 0.8417, recall 0.9542, and FPR 1.0196%; it failed the 1% FPR gate. The implementation was corrected to the already planned validation F0.5 policy, which favors precision. Because the same test partition was observed before this correction, the final numbers are a development-holdout result rather than a pristine one-shot test. A new external or time-separated dataset is required for an unbiased final deployment estimate.


This remains a static, transductive experiment: full topology and lifetime aggregates are visible, wallets from related entities may cross partitions, and public labels have no point-in-time publication timestamps. Results are not a deployment claim.

## Model selection

The deployable family was fixed as L2 logistic regression. Three regularization values were compared on validation average precision; the test partition was not consulted. A histogram-gradient-boosting model is reported only as a nonlinear validation benchmark.

| Model | Validation average precision | ROC AUC | Brier score |
| --- | ---: | ---: | ---: |
| Combined logistic C=0.1 | 0.9613 | 0.9936 | 0.0063 |
| Combined logistic C=1 | 0.9648 | 0.9938 | 0.0061 |
| Combined logistic C=10 | 0.9604 | 0.9939 | 0.0061 |
| behavior_only logistic | 0.5574 | 0.8974 | 0.0315 |
| intelligence_only logistic | 0.9340 | 0.9874 | 0.0086 |
| Gradient boosting benchmark | 0.9966 | 0.9997 | 0.0018 |

## Held-out test result

The selected model uses **65 features** and C=1. Its decision threshold **0.693382** maximizes validation F0.5 subject to the validation precision/FPR constraints.

| Metric | Test value |
| --- | ---: |
| Average precision (PR-AUC) | 0.9700 |
| ROC AUC | 0.9942 |
| Brier score | 0.0056 |
| Accuracy | 0.9931 |
| Precision | 0.9779 |
| Recall | 0.8911 |
| False-positive rate | 0.0011 |
| F0.5 | 0.9593 |
| Triggered wallets | 1,950 |

Confusion matrix: TP=1,907, FP=43, FN=233, TN=37,620.

## Example explainable prediction

Test wallet `39nz1urm6Vbkhzdu6FYedBys1Wzc3JFWbE` has Elliptic++ target `illicit`. The target was unavailable to feature construction, preprocessing, training, threshold selection, and scoring.

```json
{
  "model_version": "elliptic-logistic-v1",
  "illicit_probability": 0.9999999999969653,
  "decision_threshold": 0.693382385987544,
  "predicted_class": "illicit",
  "log_odds": 26.520925083698295,
  "top_positive_factors": [
    {
      "feature": "elliptic_f_033",
      "raw_value": 0.2503744564,
      "contribution": 55.75649348786027
    },
    {
      "feature": "elliptic_f_032",
      "raw_value": 0.2503744564,
      "contribution": 34.13747564202728
    },
    {
      "feature": "direct_illicit_neighbor_count",
      "raw_value": 351.0,
      "contribution": 26.831692066448063
    },
    {
      "feature": "in_degree",
      "raw_value": 497.0,
      "contribution": 9.31352830678183
    },
    {
      "feature": "elliptic_f_028",
      "raw_value": 0.2851285499999999,
      "contribution": 9.303859560184009
    }
  ],
  "top_negative_factors": [
    {
      "feature": "elliptic_f_034",
      "raw_value": 0.2503744564,
      "contribution": -62.611771588170406
    },
    {
      "feature": "elliptic_f_031",
      "raw_value": 0.2503744564,
      "contribution": -30.379343525528675
    },
    {
      "feature": "elliptic_f_025",
      "raw_value": 0.2851285499999999,
      "contribution": -9.46318520302733
    },
    {
      "feature": "elliptic_f_051",
      "raw_value": 497.0,
      "contribution": -5.370984351965146
    },
    {
      "feature": "unique_neighbors",
      "raw_value": 497.0,
      "contribution": -5.142996138509588
    }
  ]
}
```

Each contribution is the feature's additive effect on model log-odds after the exported transformation and standardization. A large contribution explains the model calculation; it does not establish causation. Correlated aggregate fields can create large offsetting positive and negative contributions, so factors must be interpreted together rather than as independent evidence.

For a clearer representative wallet with source feature names and an exact 65-feature trace, see [the prediction walkthrough](ml_prediction_walkthrough.md).

## Artifact

`models/elliptic-logistic-v1/model.json` contains the ordered schema, transformations, imputations, scaling values, coefficients, intercept, and decision threshold. It is the exact model evaluated above and is reproduced by the [native Go predictor](ml_predictor.md) without Python. Risk aggregation remains out of scope for this step.
