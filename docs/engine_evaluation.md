# Complete engine evaluation

This evaluation runs the final rule, ML, aggregation, and HTTP path on the frozen Elliptic++ test partition. Every row contains the complete feature vector; the target label remains evaluator metadata and is never sent to the API.

## Leakage-safe test population

- Rows: **39,803**
- Licit: **37,663**
- Illicit: **2,140**
- Graph intelligence: training-wallet labels only; validation, test, and unknown labels masked
- ML PR-AUC: **0.9700**; ROC-AUC: **0.9942**; Brier score: **0.0056**

## Operating results

| Output interpreted as a positive flag | Precision | Recall | FPR | Accuracy | Flagged |
| --- | ---: | ---: | ---: | ---: | ---: |
| ML threshold | 97.79% | 89.11% | 0.11% | 99.31% | 1,950 |
| Any active rule | 89.86% | 89.81% | 0.58% | 98.91% | 2,139 |
| Final review: rules OR ML | 89.26% | 92.01% | 0.63% | 98.97% | 2,206 |
| High level: rules AND ML | 98.78% | 86.92% | 0.06% | 99.24% | 1,883 |

## Risk levels by target

| Target | Low | Medium | High |
| --- | ---: | ---: | ---: |
| Licit | 37,426 | 214 | 23 |
| Illicit | 171 | 109 | 1,860 |

## Go HTTP validation

All **39,803** test vectors were posted to `http://localhost:8080/v1/score` using 8 concurrent persistent clients. The API returned 39,803 successful responses with **0 parity failures**. Observed local throughput was 181.7 requests/second; this is a functional development-machine check, not a production load benchmark.

## Assessment

The capstone is good enough for its educational acceptance contract if the final review policy keeps precision ≥80%, recall ≥70%, and FPR ≤1%, the ML model keeps PR-AUC ≥0.80, and every HTTP result matches the frozen offline calculation. Compared with ML alone, the review policy finds 62 additional illicit wallets at the cost of 194 additional licit reviews. The medium disagreement queue contains 109 illicit and 214 licit wallets, while 171 illicit wallets remain low risk. It is not ready for production deployment: Elliptic++ is a static, transductive research dataset; the split is random rather than time- or entity-separated; public labels are not point-in-time intelligence; and the review policy has not been calibrated to a real institution's alert capacity or loss function.
