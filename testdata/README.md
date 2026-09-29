# Test fixtures

`elliptic_rule_walkthrough.csv` is one complete, 76-column row copied from the
local Elliptic++ canonical dataset. The [walkthrough](../docs/rule_walkthrough.md)
shows how its 74 feature columns enter the Go rule engine while its target
`label` remains outside the feature vector.

`elliptic_tiny/` contains synthetic source files for the Python feature tests.

`risk_examples/` contains three complete, label-free JSON `FeatureVector` inputs
copied from the local canonical dataset. Their committed result files demonstrate
licit agreement, rule/ML disagreement, and illicit agreement. Dataset target labels
are documented separately and never enter runtime scoring.
