package domain

// RiskLevel is the policy outcome produced from rule/ML agreement. It is not a
// probability and does not assert that the wallet is illicit.
type RiskLevel string

const (
	RiskLevelLow    RiskLevel = "low"
	RiskLevelMedium RiskLevel = "medium"
	RiskLevelHigh   RiskLevel = "high"
)

// RecommendedAction describes what the capstone policy recommends downstream.
// It does not execute or block a transaction.
type RecommendedAction string

const (
	ActionNoReview RecommendedAction = "no_review"
	ActionReview   RecommendedAction = "review"
)

// RiskResult keeps the model probability, deterministic evidence, and policy
// outcome separate so callers can explain exactly how the result was reached.
type RiskResult struct {
	WalletID          string            `json:"wallet_id"`
	Level             RiskLevel         `json:"level"`
	RecommendedAction RecommendedAction `json:"recommended_action"`
	ReviewRecommended bool              `json:"review_recommended"`
	MLTriggered       bool              `json:"ml_triggered"`
	RulesTriggered    bool              `json:"rules_triggered"`
	Prediction        Prediction        `json:"prediction"`
	MatchedFindings   []RuleFinding     `json:"matched_findings"`
	PrimaryFindings   []RuleFinding     `json:"primary_findings"`
	Reasons           []string          `json:"reasons"`
}
