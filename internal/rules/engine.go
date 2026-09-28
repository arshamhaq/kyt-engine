package rules

import (
	"errors"
	"fmt"
	"math"
	"strings"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

// RuleEngine evaluates the reviewed catalog against one precomputed vector.
type RuleEngine struct {
	rules []Rule
}

// NewRuleEngine constructs the fixed, data-backed v1 rule catalog.
func NewRuleEngine() *RuleEngine {
	return &RuleEngine{rules: candidateRules()}
}

// Evaluate checks rule inputs, evaluates every rule in catalog order, and
// returns only matched findings. It does not aggregate or score them.
func (engine *RuleEngine) Evaluate(vector domain.FeatureVector) ([]domain.RuleFinding, error) {
	if engine == nil || len(engine.rules) == 0 {
		return nil, errors.New("rule engine has no configured rules; use NewRuleEngine")
	}
	if err := validateRuleInputs(vector); err != nil {
		return nil, err
	}
	findings := make([]domain.RuleFinding, 0, len(engine.rules))
	for _, rule := range engine.rules {
		if finding, matched := rule.Evaluate(&vector); matched {
			findings = append(findings, finding)
		}
	}
	return findings, nil
}

func validateRuleInputs(vector domain.FeatureVector) error {
	if strings.TrimSpace(vector.WalletID) == "" {
		return errors.New("wallet ID is required")
	}
	ratio := vector.DirectIllicitNeighborRatio
	if math.IsNaN(ratio) || math.IsInf(ratio, 0) || ratio < 0 || ratio > 1 {
		return fmt.Errorf("direct illicit-neighbor ratio must be finite and within [0,1]: %v", ratio)
	}
	if vector.TwoHopIllicitCount < 0 {
		return errors.New("two-hop illicit count cannot be negative")
	}
	totalTransactions := vector.TotalTransactions()
	if math.IsNaN(totalTransactions) || math.IsInf(totalTransactions, 0) ||
		totalTransactions < 0 || totalTransactions != math.Trunc(totalTransactions) {
		return errors.New("elliptic_f_006 (total_txs) must be a finite nonnegative integer")
	}
	return nil
}
