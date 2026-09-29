package domain

// RuleEvidence records one observed precomputed feature and its rule threshold.
// Observed values are for explanation only; they are not risk probabilities.
type RuleEvidence struct {
	Feature   string  `json:"feature"`
	Operator  string  `json:"operator"`
	Observed  float64 `json:"observed"`
	Threshold float64 `json:"threshold"`
}

// RuleFinding is one matched deterministic condition. Related rules may match
// the same wallet, so findings must not be counted as independent risk signals.
type RuleFinding struct {
	WalletID string         `json:"wallet_id"`
	RuleID   string         `json:"rule_id"`
	Family   string         `json:"family"`
	Reason   string         `json:"reason"`
	Evidence []RuleEvidence `json:"evidence"`
}
