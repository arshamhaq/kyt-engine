package domain

// RuleEvidence records one observed precomputed feature and its rule threshold.
// Observed values are for explanation only; they are not risk probabilities.
type RuleEvidence struct {
	Feature   string
	Operator  string
	Observed  float64
	Threshold float64
}

// RuleFinding is one matched deterministic condition. Related rules may match
// the same wallet, so findings must not be counted as independent risk signals.
type RuleFinding struct {
	WalletID string
	RuleID   string
	Family   string
	Reason   string
	Evidence []RuleEvidence
}
