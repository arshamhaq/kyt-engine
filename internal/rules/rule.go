package rules

import "github.com/arshamhaq/kyt-engine/internal/domain"

// Rule evaluates already-computed features. A nonmatch returns false and no
// finding; the engine validates its input before calling any rule.
type Rule interface {
	ID() string
	Evaluate(*domain.FeatureVector) (domain.RuleFinding, bool)
}

type condition struct {
	feature   string
	operator  string
	threshold float64
}

// thresholdRule keeps the v1 catalog declarative and its execution path small.
// Definitions are private so callers cannot silently change reviewed thresholds.
type thresholdRule struct {
	id         string
	family     string
	reason     string
	conditions []condition
}

func (r thresholdRule) ID() string { return r.id }

func (r thresholdRule) Evaluate(vector *domain.FeatureVector) (domain.RuleFinding, bool) {
	evidence := make([]domain.RuleEvidence, 0, len(r.conditions))
	for _, check := range r.conditions {
		observed := featureValue(vector, check.feature)
		if !meetsThreshold(observed, check.operator, check.threshold) {
			return domain.RuleFinding{}, false
		}
		evidence = append(evidence, domain.RuleEvidence{
			Feature: check.feature, Operator: check.operator,
			Observed: observed, Threshold: check.threshold,
		})
	}
	return domain.RuleFinding{
		WalletID: vector.WalletID, RuleID: r.id, Family: r.family,
		Reason: r.reason, Evidence: evidence,
	}, true
}

func featureValue(vector *domain.FeatureVector, feature string) float64 {
	switch feature {
	case "direct_illicit_neighbor_ratio":
		return vector.DirectIllicitNeighborRatio
	case "two_hop_illicit_count":
		return float64(vector.TwoHopIllicitCount)
	case "elliptic_f_006":
		return vector.TotalTransactions()
	default:
		panic("unrecognized reviewed rule feature: " + feature)
	}
}

func meetsThreshold(value float64, operator string, threshold float64) bool {
	switch operator {
	case ">=":
		return value >= threshold
	default:
		panic("unrecognized reviewed rule operator: " + operator)
	}
}
