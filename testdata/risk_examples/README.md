# End-to-end risk examples

Each input is one complete JSON `FeatureVector` copied from the local canonical
Elliptic++ table. The dataset target is recorded here only; it is deliberately
absent from the input and cannot enter rule or ML inference.

| Input | Dataset target metadata | Rules | ML class | Aggregate level |
| --- | --- | --- | --- | --- |
| `licit-agreement.json` | licit | no match | licit | low |
| `disagreement.json` | licit | R2 | licit | medium / review |
| `illicit-agreement.json` | illicit | R1, R2, R5, R6, R7 | illicit | high / review |

`results/` contains the complete JSON emitted by `cmd/server` for each input.
