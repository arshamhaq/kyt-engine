# Capstone boundary

**Input:** a complete, precomputed `FeatureVector` supplied by an upstream system.

**Process:** Rule Engine + ML Predictor -> Risk Aggregator.

**Output:** an explainable `RiskResult`, returned through the future KYTScorer and HTTP API.

The Go rule engine now evaluates reviewed thresholds against precomputed features
and returns explainable findings. ML inference, risk aggregation, scoring formulas,
and HTTP handlers remain future components. The separate offline Elliptic++
feature and rule-analysis scripts prepare practice data for this boundary.

For online Go scoring, blockchain ingestion, graph construction and analysis,
Spark, Kafka, data lakes, feature computation and extraction, feature stores,
streaming updates, historical rescoring, and Stridge integration remain out of scope.
