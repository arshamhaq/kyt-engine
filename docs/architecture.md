# Capstone boundary

**Input:** a complete, precomputed `FeatureVector` supplied by an upstream system.

**Process:** Rule Engine + ML Predictor -> Risk Aggregator.

**Output:** an explainable `RiskResult`, returned through the future KYTScorer and HTTP API.

The Go rule engine now evaluates reviewed thresholds against precomputed features
and returns explainable findings. The offline Python pipeline trains and exports an
accepted Elliptic++ logistic baseline, and the native Go predictor reproduces its
probability and contribution explanations. Risk aggregation, scoring formulas, and
HTTP handlers remain future components. The separate offline Elliptic++ feature,
rule-analysis, and ML scripts prepare practice artifacts for this boundary.

For online Go scoring, blockchain ingestion, graph construction and analysis,
Spark, Kafka, data lakes, feature computation and extraction, feature stores,
streaming updates, historical rescoring, and Stridge integration remain out of scope.
