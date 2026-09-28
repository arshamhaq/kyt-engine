package domain

// FeatureContribution explains one feature's additive effect on model log-odds.
// It is a calculation trace, not causal evidence or an independent risk signal.
type FeatureContribution struct {
	Feature           string   `json:"feature"`
	SourceName        string   `json:"source_name"`
	RawValue          *float64 `json:"raw_value,omitempty"`
	WasImputed        bool     `json:"was_imputed"`
	StandardizedValue float64  `json:"standardized_value"`
	Coefficient       float64  `json:"coefficient"`
	Contribution      float64  `json:"contribution"`
}

// Prediction is the exact output of one versioned binary ML model. The target
// label is deliberately absent; PredictedClass comes only from thresholding the
// supplied feature vector's IllicitProbability.
type Prediction struct {
	WalletID           string                `json:"wallet_id"`
	ModelVersion       string                `json:"model_version"`
	IllicitProbability float64               `json:"illicit_probability"`
	DecisionThreshold  float64               `json:"decision_threshold"`
	PredictedClass     string                `json:"predicted_class"`
	LogOdds            float64               `json:"log_odds"`
	TopPositiveFactors []FeatureContribution `json:"top_positive_factors"`
	TopNegativeFactors []FeatureContribution `json:"top_negative_factors"`
}
