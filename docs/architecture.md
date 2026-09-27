# Capstone boundary

**Input:** a complete, precomputed `FeatureVector` supplied by an upstream system.

**Process:** Rule Engine + ML Predictor -> Risk Aggregator.

**Output:** an explainable `RiskResult`, returned through the future KYTScorer and HTTP API.

This version is scaffold only. Domain fields, component contracts, rules, scoring
formulas, ML inference, and HTTP handlers will be designed one component at a time.

Blockchain ingestion, graph construction and analysis, Spark, Kafka, data lakes,
feature computation and extraction, feature stores, streaming updates, historical
rescoring, and Stridge integration are out of scope for this capstone version.
