package scoring

import (
	"errors"
	"testing"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

type stubRules struct {
	findings []domain.RuleFinding
	err      error
}

func (stub stubRules) Evaluate(domain.FeatureVector) ([]domain.RuleFinding, error) {
	return stub.findings, stub.err
}

type stubPredictor struct {
	prediction domain.Prediction
	err        error
}

func (stub stubPredictor) Predict(domain.FeatureVector) (domain.Prediction, error) {
	return stub.prediction, stub.err
}

func TestScorerOrchestratesRulesPredictorAndAggregator(t *testing.T) {
	prediction := testPrediction(0.9)
	finding := testFinding("R1", "direct_exposure")
	scorer, err := NewScorer(stubRules{findings: []domain.RuleFinding{finding}}, stubPredictor{prediction: prediction}, NewAggregator())
	if err != nil {
		t.Fatal(err)
	}
	result, err := scorer.Score(domain.FeatureVector{WalletID: "wallet-A"})
	if err != nil {
		t.Fatal(err)
	}
	if result.Level != domain.RiskLevelHigh || result.WalletID != "wallet-A" {
		t.Fatalf("unexpected result: %+v", result)
	}
}

func TestScorerStopsAtComponentErrors(t *testing.T) {
	prediction := testPrediction(0.1)
	tests := []struct {
		name      string
		rules     RuleEvaluator
		predictor Predictor
	}{
		{"rule error", stubRules{err: errors.New("rules failed")}, stubPredictor{prediction: prediction}},
		{"predictor error", stubRules{}, stubPredictor{err: errors.New("predictor failed")}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			scorer, err := NewScorer(test.rules, test.predictor, NewAggregator())
			if err != nil {
				t.Fatal(err)
			}
			if result, err := scorer.Score(domain.FeatureVector{WalletID: "wallet-A"}); err == nil {
				t.Fatalf("component error produced result %+v", result)
			}
		})
	}
}
