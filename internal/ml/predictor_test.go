package ml

import (
	"bytes"
	"encoding/json"
	"errors"
	"math"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"testing"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

type predictionTrace struct {
	WalletID               string            `json:"wallet_id"`
	Partition              string            `json:"partition"`
	TargetMetadata         string            `json:"target_metadata"`
	TargetUsedForScoring   bool              `json:"target_used_for_scoring"`
	ModelInputFeatureCount int               `json:"model_input_feature_count"`
	Prediction             domain.Prediction `json:"prediction"`
	ExactCalculation       struct {
		LogOdds           float64 `json:"log_odds"`
		SigmoidLogOdds    float64 `json:"sigmoid_log_odds"`
		DecisionThreshold float64 `json:"decision_threshold"`
	} `json:"exact_calculation"`
	Contributions []domain.FeatureContribution `json:"all_feature_contributions_by_absolute_magnitude"`
}

func realArtifactPath() string {
	return filepath.Join("..", "..", "models", "elliptic-logistic-v1", "model.json")
}

func realTracePath() string {
	return filepath.Join("..", "..", "models", "elliptic-logistic-v1", "example_prediction.json")
}

func loadTraceVector(t *testing.T) (domain.FeatureVector, predictionTrace) {
	t.Helper()
	data, err := os.ReadFile(realTracePath())
	if err != nil {
		t.Fatal(err)
	}
	var trace predictionTrace
	if err := json.Unmarshal(data, &trace); err != nil {
		t.Fatal(err)
	}
	vector := domain.FeatureVector{WalletID: trace.WalletID}
	for _, item := range trace.Contributions {
		if item.RawValue == nil {
			continue
		}
		setVectorFeature(t, &vector, item.Feature, *item.RawValue)
	}
	return vector, trace
}

func setVectorFeature(t *testing.T, vector *domain.FeatureVector, name string, value float64) {
	t.Helper()
	if strings.HasPrefix(name, "elliptic_f_") {
		index, err := strconv.Atoi(strings.TrimPrefix(name, "elliptic_f_"))
		if err != nil || index < 1 || index > len(vector.EllipticNumeric) {
			t.Fatalf("bad fixture feature %s", name)
		}
		vector.EllipticNumeric[index-1] = value
		return
	}
	integer := func() int64 {
		if value != math.Trunc(value) {
			t.Fatalf("fixture feature %s must be integral: %v", name, value)
		}
		return int64(value)
	}
	switch name {
	case "wallet_active_span":
		vector.WalletActiveSpan = integer()
	case "wallet_observed_timestep_count":
		vector.WalletObservedTimestepCount = integer()
	case "in_degree":
		vector.InDegree = integer()
	case "out_degree":
		vector.OutDegree = integer()
	case "unique_in_neighbors":
		vector.UniqueInNeighbors = integer()
	case "unique_out_neighbors":
		vector.UniqueOutNeighbors = integer()
	case "unique_neighbors":
		vector.UniqueNeighbors = integer()
	case "direct_illicit_neighbor_count":
		vector.DirectIllicitNeighborCount = integer()
		vector.OneHopIllicitCount = integer()
	case "direct_licit_neighbor_count":
		vector.DirectLicitNeighborCount = integer()
	case "direct_unknown_neighbor_count":
		vector.DirectUnknownNeighborCount = integer()
	case "direct_illicit_neighbor_ratio":
		vector.DirectIllicitNeighborRatio = value
	case "two_hop_illicit_count":
		vector.TwoHopIllicitCount = integer()
	case "distance_to_other_known_illicit":
		distance := integer()
		vector.DistanceToOtherKnownIllicit = &distance
	case "has_other_known_illicit_path":
		vector.HasOtherKnownIllicitPath = integer() == 1
	default:
		t.Fatalf("unsupported fixture feature %s", name)
	}
}

func TestGoPredictionMatchesExactPythonTrace(t *testing.T) {
	predictor, err := LoadPredictor(realArtifactPath())
	if err != nil {
		t.Fatal(err)
	}
	vector, trace := loadTraceVector(t)
	if trace.TargetMetadata != "illicit" || trace.TargetUsedForScoring || trace.Partition != "test" {
		t.Fatalf("invalid independent target metadata in fixture: %+v", trace)
	}
	if trace.ModelInputFeatureCount != 65 || len(trace.Contributions) != 65 {
		t.Fatalf("expected complete 65-feature trace")
	}
	prediction, err := predictor.Predict(vector)
	if err != nil {
		t.Fatal(err)
	}
	if prediction.WalletID != vector.WalletID || prediction.ModelVersion != "elliptic-logistic-v1" || prediction.PredictedClass != "illicit" {
		t.Fatalf("unexpected prediction identity/class: %+v", prediction)
	}
	closeEnough(t, "probability", prediction.IllicitProbability, trace.ExactCalculation.SigmoidLogOdds, 1e-14)
	closeEnough(t, "log-odds", prediction.LogOdds, trace.ExactCalculation.LogOdds, 1e-12)
	closeEnough(t, "threshold", prediction.DecisionThreshold, trace.ExactCalculation.DecisionThreshold, 0)
	if len(prediction.TopPositiveFactors) != 8 || len(prediction.TopNegativeFactors) != 8 {
		t.Fatalf("expected eight factors in each explanation direction")
	}
	want := trace.Prediction.TopPositiveFactors[0]
	got := prediction.TopPositiveFactors[0]
	if got.Feature != want.Feature || got.SourceName != want.SourceName || got.RawValue == nil {
		t.Fatalf("unexpected leading positive factor: %+v", got)
	}
	closeEnough(t, "leading contribution", got.Contribution, want.Contribution, 1e-13)
	closeEnough(t, "leading standardized value", got.StandardizedValue, want.StandardizedValue, 1e-13)
	output, err := json.MarshalIndent(prediction, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	t.Logf("exact Go prediction:\n%s", output)
}

func TestPredictionJSONIsExplainableAndContainsNoTarget(t *testing.T) {
	predictor, err := LoadPredictor(realArtifactPath())
	if err != nil {
		t.Fatal(err)
	}
	vector, _ := loadTraceVector(t)
	prediction, err := predictor.Predict(vector)
	if err != nil {
		t.Fatal(err)
	}
	data, err := json.Marshal(prediction)
	if err != nil {
		t.Fatal(err)
	}
	text := string(data)
	for _, required := range []string{"illicit_probability", "decision_threshold", "top_positive_factors", "standardized_value", "coefficient", "contribution"} {
		if !strings.Contains(text, `"`+required+`"`) {
			t.Fatalf("prediction JSON lacks %s: %s", required, text)
		}
	}
	if strings.Contains(text, "target_metadata") || strings.Contains(text, `"label"`) {
		t.Fatalf("prediction JSON leaked target metadata: %s", text)
	}
}

func TestArtifactValidationRejectsContractDrift(t *testing.T) {
	data, err := os.ReadFile(realArtifactPath())
	if err != nil {
		t.Fatal(err)
	}
	tests := []struct {
		name   string
		change func(map[string]any)
	}{
		{"format version", func(root map[string]any) { root["format_version"] = 2 }},
		{"model type", func(root map[string]any) { root["model_type"] = "tree" }},
		{"schema hash", func(root map[string]any) { root["feature_schema_sha256"] = "wrong" }},
		{"threshold", func(root map[string]any) { root["decision_threshold"] = 1.0 }},
		{"feature order", func(root map[string]any) {
			features := root["preprocessing"].(map[string]any)["features"].([]any)
			features[0].(map[string]any)["name"] = "elliptic_f_002"
		}},
		{"transform", func(root map[string]any) {
			features := root["preprocessing"].(map[string]any)["features"].([]any)
			features[0].(map[string]any)["transform"] = "identity"
		}},
		{"scale", func(root map[string]any) {
			features := root["preprocessing"].(map[string]any)["features"].([]any)
			features[0].(map[string]any)["scale"] = 0.0
		}},
		{"coefficient count", func(root map[string]any) {
			model := root["model"].(map[string]any)
			coefficients := model["coefficients"].([]any)
			model["coefficients"] = coefficients[:len(coefficients)-1]
		}},
		{"unknown field", func(root map[string]any) { root["unexpected"] = true }},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			var root map[string]any
			if err := json.Unmarshal(data, &root); err != nil {
				t.Fatal(err)
			}
			test.change(root)
			mutated, err := json.Marshal(root)
			if err != nil {
				t.Fatal(err)
			}
			if _, err := NewPredictor(bytes.NewReader(mutated)); err == nil {
				t.Fatal("invalid artifact was accepted")
			}
		})
	}
	if _, err := NewPredictor(nil); err == nil {
		t.Fatal("nil artifact reader was accepted")
	}
}

func TestPredictRejectsInvalidVectors(t *testing.T) {
	predictor, err := LoadPredictor(realArtifactPath())
	if err != nil {
		t.Fatal(err)
	}
	valid, _ := loadTraceVector(t)
	tests := []struct {
		name   string
		change func(*domain.FeatureVector)
	}{
		{"missing wallet ID", func(vector *domain.FeatureVector) { vector.WalletID = " " }},
		{"nonfinite numeric", func(vector *domain.FeatureVector) { vector.EllipticNumeric[0] = math.NaN() }},
		{"negative numeric", func(vector *domain.FeatureVector) { vector.EllipticNumeric[4] = -1 }},
		{"integer exceeds exact float range", func(vector *domain.FeatureVector) { vector.TwoHopIllicitCount = 1<<53 + 1 }},
		{"ratio above one", func(vector *domain.FeatureVector) { vector.DirectIllicitNeighborRatio = 1.1 }},
		{"counts do not partition neighbors", func(vector *domain.FeatureVector) { vector.DirectUnknownNeighborCount++ }},
		{"one-hop duplicate disagrees", func(vector *domain.FeatureVector) { vector.OneHopIllicitCount++ }},
		{"path flag disagrees", func(vector *domain.FeatureVector) { vector.HasOtherKnownIllicitPath = false }},
		{"missing distance has no model imputation", func(vector *domain.FeatureVector) {
			vector.DistanceToOtherKnownIllicit = nil
			vector.HasOtherKnownIllicitPath = false
		}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			vector := valid
			test.change(&vector)
			if prediction, err := predictor.Predict(vector); err == nil {
				t.Fatalf("invalid vector produced prediction %+v", prediction)
			}
		})
	}
	var nilPredictor *Predictor
	if _, err := nilPredictor.Predict(valid); err == nil {
		t.Fatal("nil predictor accepted a vector")
	}
}

func TestPredictorSupportsConcurrentPredictions(t *testing.T) {
	predictor, err := LoadPredictor(realArtifactPath())
	if err != nil {
		t.Fatal(err)
	}
	vector, trace := loadTraceVector(t)
	var wait sync.WaitGroup
	failures := make(chan error, 32)
	for range 32 {
		wait.Add(1)
		go func() {
			defer wait.Done()
			prediction, err := predictor.Predict(vector)
			if err != nil {
				failures <- err
				return
			}
			if math.Abs(prediction.IllicitProbability-trace.ExactCalculation.SigmoidLogOdds) > 1e-14 {
				failures <- errors.New("probability differs from the Python trace")
			}
		}()
	}
	wait.Wait()
	close(failures)
	for err := range failures {
		t.Fatalf("concurrent prediction failed: %v", err)
	}
}

func closeEnough(t *testing.T, name string, got, want, tolerance float64) {
	t.Helper()
	if math.Abs(got-want) > tolerance {
		t.Fatalf("%s = %.17g, want %.17g (tolerance %g)", name, got, want, tolerance)
	}
}
