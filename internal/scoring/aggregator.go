package scoring

import (
	"fmt"
	"math"
	"strings"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

type rulePolicy struct {
	family   string
	strength int
}

var reviewedRulePolicies = map[string]rulePolicy{
	"R1": {family: "direct_exposure", strength: 1},
	"R2": {family: "two_hop_exposure", strength: 1},
	"R4": {family: "direct_exposure", strength: 2},
	"R5": {family: "two_hop_exposure", strength: 2},
	"R6": {family: "corroborated_graph_exposure", strength: 1},
	"R7": {family: "exposure_with_activity", strength: 1},
}

// Aggregator applies the reviewed v1 agreement policy. It is stateless and safe
// for concurrent use.
type Aggregator struct{}

func NewAggregator() *Aggregator { return &Aggregator{} }

// Aggregate preserves every matched finding for audit, selects the strongest
// finding in each overlapping family as a primary reason, and derives the risk
// level from whether the deterministic rules and ML threshold agree.
func (aggregator *Aggregator) Aggregate(findings []domain.RuleFinding, prediction domain.Prediction) (domain.RiskResult, error) {
	if aggregator == nil {
		return domain.RiskResult{}, fmt.Errorf("risk aggregator is nil")
	}
	if err := validatePrediction(prediction); err != nil {
		return domain.RiskResult{}, err
	}
	primaryIDs, err := selectPrimaryFindingIDs(findings, prediction.WalletID)
	if err != nil {
		return domain.RiskResult{}, err
	}

	matched := append([]domain.RuleFinding{}, findings...)
	primary := make([]domain.RuleFinding, 0, len(primaryIDs))
	for _, finding := range findings {
		if primaryIDs[finding.RuleID] {
			primary = append(primary, finding)
		}
	}

	mlTriggered := prediction.IllicitProbability >= prediction.DecisionThreshold
	rulesTriggered := len(primary) > 0
	level := domain.RiskLevelMedium
	action := domain.ActionReview
	switch {
	case !rulesTriggered && !mlTriggered:
		level = domain.RiskLevelLow
		action = domain.ActionNoReview
	case rulesTriggered && mlTriggered:
		level = domain.RiskLevelHigh
	}

	reasons := make([]string, 0, len(primary)+2)
	comparison := "was below"
	if mlTriggered {
		comparison = "met or exceeded"
	}
	reasons = append(reasons, fmt.Sprintf(
		"ML probability %.4f%% %s the %.4f%% decision threshold.",
		prediction.IllicitProbability*100, comparison, prediction.DecisionThreshold*100,
	))
	if !rulesTriggered {
		reasons = append(reasons, "No deterministic rules matched.")
	} else {
		for _, finding := range primary {
			reasons = append(reasons, fmt.Sprintf("Rule %s: %s", finding.RuleID, finding.Reason))
		}
	}
	switch level {
	case domain.RiskLevelLow:
		reasons = append(reasons, "Rules and ML agree that this wallet is not flagged.")
	case domain.RiskLevelHigh:
		reasons = append(reasons, "Rules and ML both flag risk; review is recommended.")
	default:
		reasons = append(reasons, "Rules and ML disagree; review is recommended.")
	}

	return domain.RiskResult{
		WalletID: prediction.WalletID, Level: level, RecommendedAction: action,
		ReviewRecommended: action == domain.ActionReview,
		MLTriggered:       mlTriggered, RulesTriggered: rulesTriggered,
		Prediction: prediction, MatchedFindings: matched, PrimaryFindings: primary,
		Reasons: reasons,
	}, nil
}

func validatePrediction(prediction domain.Prediction) error {
	if strings.TrimSpace(prediction.WalletID) == "" {
		return fmt.Errorf("prediction wallet ID is required")
	}
	if strings.TrimSpace(prediction.ModelVersion) == "" {
		return fmt.Errorf("prediction model version is required")
	}
	if !finite(prediction.IllicitProbability) || prediction.IllicitProbability < 0 || prediction.IllicitProbability > 1 {
		return fmt.Errorf("prediction probability must be finite and within [0,1]")
	}
	if !finite(prediction.DecisionThreshold) || prediction.DecisionThreshold <= 0 || prediction.DecisionThreshold >= 1 {
		return fmt.Errorf("prediction threshold must be finite and within (0,1)")
	}
	wantClass := "licit"
	if prediction.IllicitProbability >= prediction.DecisionThreshold {
		wantClass = "illicit"
	}
	if prediction.PredictedClass != wantClass {
		return fmt.Errorf("prediction class %q disagrees with probability and threshold", prediction.PredictedClass)
	}
	return nil
}

func selectPrimaryFindingIDs(findings []domain.RuleFinding, walletID string) (map[string]bool, error) {
	selectedByFamily := make(map[string]domain.RuleFinding)
	seenIDs := make(map[string]bool)
	for _, finding := range findings {
		policy, known := reviewedRulePolicies[finding.RuleID]
		if !known {
			return nil, fmt.Errorf("unknown rule finding %q", finding.RuleID)
		}
		if seenIDs[finding.RuleID] {
			return nil, fmt.Errorf("duplicate rule finding %q", finding.RuleID)
		}
		seenIDs[finding.RuleID] = true
		if finding.WalletID != walletID {
			return nil, fmt.Errorf("rule %s wallet %q differs from prediction wallet %q", finding.RuleID, finding.WalletID, walletID)
		}
		if finding.Family != policy.family {
			return nil, fmt.Errorf("rule %s family %q differs from reviewed family %q", finding.RuleID, finding.Family, policy.family)
		}
		if strings.TrimSpace(finding.Reason) == "" || len(finding.Evidence) == 0 {
			return nil, fmt.Errorf("rule %s finding is not explainable", finding.RuleID)
		}
		current, exists := selectedByFamily[policy.family]
		if !exists || policy.strength > reviewedRulePolicies[current.RuleID].strength {
			selectedByFamily[policy.family] = finding
		}
	}
	selected := make(map[string]bool, len(selectedByFamily))
	for _, finding := range selectedByFamily {
		selected[finding.RuleID] = true
	}
	return selected, nil
}

func finite(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0)
}
