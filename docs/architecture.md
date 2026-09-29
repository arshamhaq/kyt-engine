# Capstone boundary

**Input:** a complete, precomputed `FeatureVector` supplied by an upstream system.

**Process:** Rule Engine + ML Predictor -> Risk Aggregator.

**Output:** an explainable `RiskResult`, returned by `KYTScorer` through the HTTP
API or explicit single-vector command.

The Go rule engine now evaluates reviewed thresholds against precomputed features
and returns explainable findings. The offline Python pipeline trains and exports an
accepted Elliptic++ logistic baseline, and the native Go predictor reproduces its
probability and contribution explanations. The Go risk aggregator preserves both
outputs, collapses nested rule findings into primary reasons, and assigns a
low/medium/high policy level from rule/ML agreement. It deliberately does not
invent a blended probability. The separate offline Elliptic++ feature,
rule-analysis, and ML scripts prepare practice artifacts for this boundary. The
HTTP process loads the model once and accepts repeated `POST /v1/score` requests;
`GET /healthz` reports readiness.

For online Go scoring, blockchain ingestion, graph construction and analysis,
Spark, Kafka, data lakes, feature computation and extraction, feature stores,
streaming updates, historical rescoring, and Stridge integration remain out of scope.
