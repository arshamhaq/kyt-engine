package ml

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
)

// ReviewedFeatureSchemaSHA256 binds inference to the feature schema used to
// train elliptic-logistic-v1.
const ReviewedFeatureSchemaSHA256 = "3a83670568f35e977db523f5721f878ee082d82644bd639453e759b803d34220"

type featureSpecification struct {
	Name       string   `json:"name"`
	Transform  string   `json:"transform"`
	Imputation *float64 `json:"imputation"`
	Mean       float64  `json:"mean"`
	Scale      float64  `json:"scale"`
}

type modelArtifact struct {
	FormatVersion       int     `json:"format_version"`
	ModelVersion        string  `json:"model_version"`
	ModelType           string  `json:"model_type"`
	PositiveLabel       string  `json:"positive_label"`
	NegativeLabel       string  `json:"negative_label"`
	DecisionThreshold   float64 `json:"decision_threshold"`
	FeatureSchemaSHA256 string  `json:"feature_schema_sha256"`
	Preprocessing       struct {
		Features []featureSpecification `json:"features"`
	} `json:"preprocessing"`
	Model struct {
		Intercept    float64   `json:"intercept"`
		Coefficients []float64 `json:"coefficients"`
	} `json:"model"`
	Training   json.RawMessage `json:"training"`
	Evaluation json.RawMessage `json:"evaluation"`
}

func decodeArtifact(source io.Reader) (modelArtifact, error) {
	decoder := json.NewDecoder(source)
	decoder.DisallowUnknownFields()
	var artifact modelArtifact
	if err := decoder.Decode(&artifact); err != nil {
		return modelArtifact{}, fmt.Errorf("decode ML model artifact: %w", err)
	}
	var trailing any
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		if err == nil {
			return modelArtifact{}, errors.New("decode ML model artifact: trailing JSON value")
		}
		return modelArtifact{}, fmt.Errorf("decode ML model artifact trailer: %w", err)
	}
	if err := validateArtifact(artifact); err != nil {
		return modelArtifact{}, err
	}
	return artifact, nil
}

func validateArtifact(artifact modelArtifact) error {
	if artifact.FormatVersion != 1 {
		return fmt.Errorf("unsupported ML model format version %d", artifact.FormatVersion)
	}
	if artifact.ModelVersion == "" {
		return errors.New("ML model version is required")
	}
	if artifact.ModelType != "binary_logistic_regression" {
		return fmt.Errorf("unsupported ML model type %q", artifact.ModelType)
	}
	if artifact.PositiveLabel != "illicit" || artifact.NegativeLabel != "licit" {
		return errors.New("ML model must map the positive class to illicit and negative class to licit")
	}
	if artifact.FeatureSchemaSHA256 != ReviewedFeatureSchemaSHA256 {
		return errors.New("ML model feature-schema hash differs from the reviewed Go contract")
	}
	if !finite(artifact.DecisionThreshold) || artifact.DecisionThreshold <= 0 || artifact.DecisionThreshold >= 1 {
		return errors.New("ML model decision threshold must be finite and strictly within (0,1)")
	}
	if !finite(artifact.Model.Intercept) {
		return errors.New("ML model intercept must be finite")
	}
	expected := expectedFeatureNames()
	if len(artifact.Preprocessing.Features) != len(expected) || len(artifact.Model.Coefficients) != len(expected) {
		return fmt.Errorf("ML model must contain exactly %d aligned features and coefficients", len(expected))
	}
	for index, specification := range artifact.Preprocessing.Features {
		if specification.Name != expected[index] {
			return fmt.Errorf("ML feature %d is %q, want %q", index, specification.Name, expected[index])
		}
		wantTransform := "log1p"
		if specification.Name == "direct_illicit_neighbor_ratio" || specification.Name == "has_other_known_illicit_path" {
			wantTransform = "identity"
		}
		if specification.Transform != wantTransform {
			return fmt.Errorf("ML feature %s transform is %q, want %q", specification.Name, specification.Transform, wantTransform)
		}
		if !finite(specification.Mean) || !finite(specification.Scale) || specification.Scale <= 0 {
			return fmt.Errorf("ML feature %s has invalid scaling parameters", specification.Name)
		}
		if specification.Imputation != nil {
			if !finite(*specification.Imputation) || (specification.Transform == "log1p" && *specification.Imputation < 0) {
				return fmt.Errorf("ML feature %s has invalid imputation", specification.Name)
			}
		}
		if !finite(artifact.Model.Coefficients[index]) {
			return fmt.Errorf("ML feature %s has a non-finite coefficient", specification.Name)
		}
	}
	return nil
}

func finite(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0)
}
