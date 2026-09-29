package scoring

import (
	"fmt"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

type RuleEvaluator interface {
	Evaluate(domain.FeatureVector) ([]domain.RuleFinding, error)
}

type Predictor interface {
	Predict(domain.FeatureVector) (domain.Prediction, error)
}

// Scorer orchestrates the rule engine, ML predictor, and risk aggregator for
// one already-computed FeatureVector.
type Scorer struct {
	rules      RuleEvaluator
	predictor  Predictor
	aggregator *Aggregator
}

func NewScorer(rules RuleEvaluator, predictor Predictor, aggregator *Aggregator) (*Scorer, error) {
	if rules == nil {
		return nil, fmt.Errorf("rule evaluator is required")
	}
	if predictor == nil {
		return nil, fmt.Errorf("ML predictor is required")
	}
	if aggregator == nil {
		return nil, fmt.Errorf("risk aggregator is required")
	}
	return &Scorer{rules: rules, predictor: predictor, aggregator: aggregator}, nil
}

func (scorer *Scorer) Score(vector domain.FeatureVector) (domain.RiskResult, error) {
	if scorer == nil {
		return domain.RiskResult{}, fmt.Errorf("KYT scorer is nil")
	}
	findings, err := scorer.rules.Evaluate(vector)
	if err != nil {
		return domain.RiskResult{}, fmt.Errorf("evaluate deterministic rules: %w", err)
	}
	prediction, err := scorer.predictor.Predict(vector)
	if err != nil {
		return domain.RiskResult{}, fmt.Errorf("run ML predictor: %w", err)
	}
	result, err := scorer.aggregator.Aggregate(findings, prediction)
	if err != nil {
		return domain.RiskResult{}, fmt.Errorf("aggregate risk: %w", err)
	}
	return result, nil
}
