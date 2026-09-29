package scoring

import (
	"reflect"
	"testing"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

func testPrediction(probability float64) domain.Prediction {
	class := "licit"
	if probability >= 0.70 {
		class = "illicit"
	}
	return domain.Prediction{
		WalletID: "wallet-A", ModelVersion: "test-model",
		IllicitProbability: probability, DecisionThreshold: 0.70,
		PredictedClass: class,
	}
}

func testFinding(id, family string) domain.RuleFinding {
	return domain.RuleFinding{
		WalletID: "wallet-A", RuleID: id, Family: family, Reason: "test reason",
		Evidence: []domain.RuleEvidence{{Feature: "test", Operator: ">=", Observed: 1, Threshold: 1}},
	}
}

func TestAgreementMatrix(t *testing.T) {
	rule := testFinding("R1", "direct_exposure")
	tests := []struct {
		name        string
		findings    []domain.RuleFinding
		probability float64
		level       domain.RiskLevel
		action      domain.RecommendedAction
	}{
		{"rules and ML do not flag", nil, 0.10, domain.RiskLevelLow, domain.ActionNoReview},
		{"rules only", []domain.RuleFinding{rule}, 0.10, domain.RiskLevelMedium, domain.ActionReview},
		{"ML only", nil, 0.90, domain.RiskLevelMedium, domain.ActionReview},
		{"rules and ML flag", []domain.RuleFinding{rule}, 0.90, domain.RiskLevelHigh, domain.ActionReview},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			result, err := NewAggregator().Aggregate(test.findings, testPrediction(test.probability))
			if err != nil {
				t.Fatal(err)
			}
			if result.Level != test.level || result.RecommendedAction != test.action || result.ReviewRecommended != (test.action == domain.ActionReview) {
				t.Fatalf("unexpected policy result: %+v", result)
			}
			if result.RulesTriggered != (len(test.findings) > 0) || result.MLTriggered != (test.probability >= 0.70) {
				t.Fatalf("unexpected trigger state: %+v", result)
			}
		})
	}
}

func TestNestedRulesRemainAuditableButDoNotDoubleCount(t *testing.T) {
	findings := []domain.RuleFinding{
		testFinding("R1", "direct_exposure"),
		testFinding("R2", "two_hop_exposure"),
		testFinding("R4", "direct_exposure"),
		testFinding("R5", "two_hop_exposure"),
		testFinding("R6", "corroborated_graph_exposure"),
		testFinding("R7", "exposure_with_activity"),
	}
	result, err := NewAggregator().Aggregate(findings, testPrediction(0.90))
	if err != nil {
		t.Fatal(err)
	}
	if len(result.MatchedFindings) != 6 {
		t.Fatalf("matched findings were not preserved: %+v", result.MatchedFindings)
	}
	var primary []string
	for _, finding := range result.PrimaryFindings {
		primary = append(primary, finding.RuleID)
	}
	if want := []string{"R4", "R5", "R6", "R7"}; !reflect.DeepEqual(primary, want) {
		t.Fatalf("primary rules = %v, want %v", primary, want)
	}
}

func TestAggregatorRejectsInconsistentInputs(t *testing.T) {
	tests := []struct {
		name       string
		findings   []domain.RuleFinding
		prediction domain.Prediction
	}{
		{"unknown rule", []domain.RuleFinding{testFinding("R99", "unknown")}, testPrediction(0.1)},
		{"duplicate rule", []domain.RuleFinding{testFinding("R1", "direct_exposure"), testFinding("R1", "direct_exposure")}, testPrediction(0.1)},
		{"wrong family", []domain.RuleFinding{testFinding("R1", "two_hop_exposure")}, testPrediction(0.1)},
		{"wrong wallet", []domain.RuleFinding{func() domain.RuleFinding {
			f := testFinding("R1", "direct_exposure")
			f.WalletID = "wallet-B"
			return f
		}()}, testPrediction(0.1)},
		{"class mismatch", nil, func() domain.Prediction { p := testPrediction(0.9); p.PredictedClass = "licit"; return p }()},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if result, err := NewAggregator().Aggregate(test.findings, test.prediction); err == nil {
				t.Fatalf("invalid input produced result %+v", result)
			}
		})
	}
}
