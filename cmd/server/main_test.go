package main

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"math"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

func TestRunRiskExamples(t *testing.T) {
	tests := []struct {
		name        string
		input       string
		level       domain.RiskLevel
		action      domain.RecommendedAction
		probability float64
		matched     []string
		primary     []string
	}{
		{"licit agreement", "licit-agreement.json", domain.RiskLevelLow, domain.ActionNoReview, 1.0039666876116033e-7, nil, nil},
		{"disagreement", "disagreement.json", domain.RiskLevelMedium, domain.ActionReview, 0.2981368070288999, []string{"R2"}, []string{"R2"}},
		{"illicit agreement", "illicit-agreement.json", domain.RiskLevelHigh, domain.ActionReview, 0.9998177989609814, []string{"R1", "R2", "R5", "R6", "R7"}, []string{"R1", "R5", "R6", "R7"}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			var output bytes.Buffer
			err := run(context.Background(), []string{
				"-input", filepath.Join("..", "..", "testdata", "risk_examples", test.input),
				"-model", filepath.Join("..", "..", "models", "elliptic-logistic-v1", "model.json"),
			}, strings.NewReader(""), &output, io.Discard)
			if err != nil {
				t.Fatal(err)
			}
			var result domain.RiskResult
			if err := json.Unmarshal(output.Bytes(), &result); err != nil {
				t.Fatal(err)
			}
			if result.Level != test.level || result.RecommendedAction != test.action || math.Abs(result.Prediction.IllicitProbability-test.probability) > 1e-14 {
				t.Fatalf("unexpected result: %+v", result)
			}
			ids := func(findings []domain.RuleFinding) []string {
				var values []string
				for _, finding := range findings {
					values = append(values, finding.RuleID)
				}
				return values
			}
			if matched := ids(result.MatchedFindings); !reflect.DeepEqual(matched, test.matched) {
				t.Fatalf("matched rules = %v, want %v", matched, test.matched)
			}
			if primary := ids(result.PrimaryFindings); !reflect.DeepEqual(primary, test.primary) {
				t.Fatalf("primary rules = %v, want %v", primary, test.primary)
			}
		})
	}
}

func TestRunRiskExampleDirectory(t *testing.T) {
	var output bytes.Buffer
	err := run(context.Background(), []string{
		"-input-dir", filepath.Join("..", "..", "testdata", "risk_examples"),
		"-model", filepath.Join("..", "..", "models", "elliptic-logistic-v1", "model.json"),
	}, strings.NewReader(""), &output, io.Discard)
	if err != nil {
		t.Fatal(err)
	}

	var result batchResult
	if err := json.Unmarshal(output.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.Count != 3 || len(result.Results) != 3 {
		t.Fatalf("count = %d and results = %d, want 3", result.Count, len(result.Results))
	}
	wantNames := []string{"disagreement.json", "illicit-agreement.json", "licit-agreement.json"}
	wantLevels := []domain.RiskLevel{domain.RiskLevelMedium, domain.RiskLevelHigh, domain.RiskLevelLow}
	for index := range result.Results {
		if result.Results[index].Input != wantNames[index] || result.Results[index].Result.Level != wantLevels[index] {
			t.Fatalf("result %d = %+v, want %s/%s", index, result.Results[index], wantNames[index], wantLevels[index])
		}
	}
}

func TestRunRejectsConflictingInputModes(t *testing.T) {
	err := run(context.Background(), []string{"-input", "one.json", "-input-dir", "vectors"}, strings.NewReader(""), io.Discard, io.Discard)
	if err == nil || !strings.Contains(err.Error(), "cannot be used together") {
		t.Fatalf("error = %v, want conflicting input modes", err)
	}
}
