package rules

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

func testVector(ratio float64, twoHop int64, totalTransactions float64) domain.FeatureVector {
	vector := domain.FeatureVector{
		WalletID: "example-wallet", DirectIllicitNeighborRatio: ratio,
		TwoHopIllicitCount: twoHop,
	}
	vector.EllipticNumeric[domain.EllipticTotalTransactionsIndex] = totalTransactions
	return vector
}

func findingIDs(findings []domain.RuleFinding) []string {
	ids := make([]string, 0, len(findings))
	for _, finding := range findings {
		ids = append(ids, finding.RuleID)
	}
	return ids
}

func TestRuleThresholdBoundaries(t *testing.T) {
	tests := []struct {
		name     string
		vector   domain.FeatureVector
		wantRule []string
	}{
		{"R1 at 20 percent", testVector(0.20, 0, 1), []string{"R1"}},
		{"below R1", testVector(math.Nextafter(0.20, 0), 0, 1), nil},
		{"R2 at 50 other illicit two-hop nodes", testVector(0, 50, 1), []string{"R2"}},
		{"below R2", testVector(0, 49, 1), nil},
		{"R4 at 60 percent also matches R1", testVector(0.60, 0, 1), []string{"R1", "R4"}},
		{"below R4", testVector(math.Nextafter(0.60, 0), 0, 1), []string{"R1"}},
		{"R5 at 100 also matches R2", testVector(0, 100, 1), []string{"R2", "R5"}},
		{"below R5", testVector(0, 99, 1), []string{"R2"}},
		{"R6 both checks at boundary", testVector(0.10, 2, 1), []string{"R6"}},
		{"R6 needs ratio", testVector(math.Nextafter(0.10, 0), 2, 1), nil},
		{"R6 needs two-hop nodes", testVector(0.10, 1, 1), nil},
		{"R7 at two transactions", testVector(0.10, 0, 2), []string{"R7"}},
		{"R7 needs two transactions", testVector(0.10, 0, 1), nil},
		{"R7 needs ratio", testVector(math.Nextafter(0.10, 0), 0, 2), nil},
	}
	engine := NewRuleEngine()
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			findings, err := engine.Evaluate(test.vector)
			if err != nil {
				t.Fatal(err)
			}
			if got := findingIDs(findings); !reflect.DeepEqual(got, append([]string{}, test.wantRule...)) {
				t.Fatalf("matching rule IDs = %v, want %v", got, test.wantRule)
			}
		})
	}
}

func TestAllRuleFindingsAreOrderedAndExplainTheirEvidence(t *testing.T) {
	vector := testVector(0.70, 100, 3)
	findings, err := NewRuleEngine().Evaluate(vector)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"R1", "R2", "R4", "R5", "R6", "R7"}
	if got := findingIDs(findings); !reflect.DeepEqual(got, want) {
		t.Fatalf("matching rule IDs = %v, want %v", got, want)
	}
	for _, finding := range findings {
		if finding.WalletID != vector.WalletID || finding.Reason == "" || finding.Family == "" || len(finding.Evidence) == 0 {
			t.Fatalf("incomplete explainable finding: %+v", finding)
		}
		for _, evidence := range finding.Evidence {
			if evidence.Operator != ">=" || evidence.Observed < evidence.Threshold {
				t.Fatalf("evidence does not justify match: %+v", evidence)
			}
		}
	}
	if findings[0].Family != findings[2].Family || findings[1].Family != findings[3].Family {
		t.Fatal("strict and broad rules must declare their shared signal family")
	}
	if got := findings[5].Evidence[1]; got.Feature != "elliptic_f_006" || got.Observed != 3 || got.Threshold != 2 {
		t.Fatalf("R7 must explain the provided total_txs input: %+v", got)
	}
}

func TestInvalidRuleInputsFailBeforeAnyRuleRuns(t *testing.T) {
	base := testVector(0.20, 2, 2)
	tests := []struct {
		name   string
		change func(*domain.FeatureVector)
	}{
		{"missing wallet ID", func(v *domain.FeatureVector) { v.WalletID = " " }},
		{"negative ratio", func(v *domain.FeatureVector) { v.DirectIllicitNeighborRatio = -0.1 }},
		{"ratio above one", func(v *domain.FeatureVector) { v.DirectIllicitNeighborRatio = 1.1 }},
		{"not-a-number ratio", func(v *domain.FeatureVector) { v.DirectIllicitNeighborRatio = math.NaN() }},
		{"infinite ratio", func(v *domain.FeatureVector) { v.DirectIllicitNeighborRatio = math.Inf(1) }},
		{"negative count", func(v *domain.FeatureVector) { v.TwoHopIllicitCount = -1 }},
		{"negative transactions", func(v *domain.FeatureVector) { v.EllipticNumeric[5] = -1 }},
		{"fractional transactions", func(v *domain.FeatureVector) { v.EllipticNumeric[5] = 1.5 }},
		{"not-a-number transactions", func(v *domain.FeatureVector) { v.EllipticNumeric[5] = math.NaN() }},
		{"infinite transactions", func(v *domain.FeatureVector) { v.EllipticNumeric[5] = math.Inf(1) }},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			vector := base
			test.change(&vector)
			findings, err := NewRuleEngine().Evaluate(vector)
			if err == nil || findings != nil {
				t.Fatalf("bad input yielded findings %v and error %v", findings, err)
			}
		})
	}
	if _, err := (&RuleEngine{}).Evaluate(base); err == nil {
		t.Fatal("unconfigured engine must fail explicitly")
	}
}

func TestGoCatalogMatchesFrozenTrainingRules(t *testing.T) {
	// This artifact was written BEFORE held-out validation and records the data-
	// selected thresholds. The test catches any Go threshold or operator drift.
	data, err := os.ReadFile(filepath.Join("..", "..", "analysis", "results", "frozen_rules.json"))
	if err != nil {
		t.Fatal(err)
	}
	var frozen struct {
		Rules []struct {
			ID         string `json:"id"`
			Conditions []struct {
				Feature   string  `json:"feature"`
				Operator  string  `json:"operator"`
				Threshold float64 `json:"threshold"`
			} `json:"conditions"`
		} `json:"rules"`
	}
	if err := json.Unmarshal(data, &frozen); err != nil {
		t.Fatal(err)
	}
	byID := make(map[string][]condition)
	for _, selected := range frozen.Rules {
		if _, exists := byID[selected.ID]; exists {
			t.Fatalf("duplicate frozen rule ID %s", selected.ID)
		}
		for _, item := range selected.Conditions {
			byID[selected.ID] = append(byID[selected.ID], condition{item.Feature, item.Operator, item.Threshold})
		}
	}
	if len(byID) != 8 {
		t.Fatalf("expected eight reviewed candidates, got %d", len(byID))
	}
	engine := NewRuleEngine()
	if len(engine.rules) != 6 {
		t.Fatalf("expected six selected Go rules, got %d", len(engine.rules))
	}
	for _, candidate := range engine.rules {
		actual := candidate.(thresholdRule)
		if !reflect.DeepEqual(actual.conditions, byID[actual.ID()]) {
			t.Fatalf("Go rule %s differs from frozen training conditions: %+v vs %+v", actual.ID(), actual.conditions, byID[actual.ID()])
		}
	}
	for _, excluded := range []string{"R3", "R8"} {
		for _, candidate := range engine.rules {
			if candidate.ID() == excluded {
				t.Fatalf("weaker candidate %s activated without review", excluded)
			}
		}
	}
}

func TestFeatureVectorWalkthrough(t *testing.T) {
	// A readable call-site for following one vector through each rule. The server
	// is deliberately not wired to the engine yet.
	vector := testVector(0.25, 3, 1)
	findings, err := NewRuleEngine().Evaluate(vector)
	if err != nil {
		t.Fatal(err)
	}
	if got, want := findingIDs(findings), []string{"R1", "R6"}; !reflect.DeepEqual(got, want) {
		t.Fatalf("findings %v, want %v", got, want)
	}
	for _, finding := range findings {
		t.Logf("%s: %s", finding.RuleID, finding.Reason)
		for _, evidence := range finding.Evidence {
			t.Logf("  %s: observed %.3g %s threshold %.3g", evidence.Feature, evidence.Observed, evidence.Operator, evidence.Threshold)
		}
	}
}
