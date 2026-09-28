package ml

import (
	"fmt"
	"io"
	"math"
	"os"
	"sort"
	"strings"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

const explanationFactorLimit = 8

// Predictor is an immutable native-Go logistic model safe for concurrent use.
type Predictor struct {
	artifact modelArtifact
}

// LoadPredictor loads and validates a portable model artifact from disk.
func LoadPredictor(path string) (*Predictor, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open ML model artifact: %w", err)
	}
	defer file.Close()
	return NewPredictor(file)
}

// NewPredictor decodes and validates a portable model artifact.
func NewPredictor(source io.Reader) (*Predictor, error) {
	if source == nil {
		return nil, fmt.Errorf("ML model artifact reader is required")
	}
	artifact, err := decodeArtifact(source)
	if err != nil {
		return nil, err
	}
	return &Predictor{artifact: artifact}, nil
}

// Predict applies the artifact's preprocessing and logistic equation to one
// complete precomputed vector. It never reads or accepts a target label.
func (predictor *Predictor) Predict(vector domain.FeatureVector) (domain.Prediction, error) {
	if predictor == nil {
		return domain.Prediction{}, fmt.Errorf("ML predictor is nil")
	}
	if strings.TrimSpace(vector.WalletID) == "" {
		return domain.Prediction{}, fmt.Errorf("wallet ID is required")
	}
	if (vector.DistanceToOtherKnownIllicit != nil) != vector.HasOtherKnownIllicitPath {
		return domain.Prediction{}, fmt.Errorf("distance presence and has-other-known-illicit-path flag disagree")
	}
	if err := validateVectorConsistency(vector); err != nil {
		return domain.Prediction{}, err
	}

	logOdds := predictor.artifact.Model.Intercept
	positive := make([]domain.FeatureContribution, 0, explanationFactorLimit)
	negative := make([]domain.FeatureContribution, 0, explanationFactorLimit)
	for index, specification := range predictor.artifact.Preprocessing.Features {
		raw, present, err := featureValue(vector, specification.Name)
		if err != nil {
			return domain.Prediction{}, err
		}
		var rawPointer *float64
		wasImputed := false
		if present {
			if !finite(raw) {
				return domain.Prediction{}, fmt.Errorf("ML feature %s must be finite", specification.Name)
			}
			copy := raw
			rawPointer = &copy
		} else {
			if specification.Imputation == nil {
				return domain.Prediction{}, fmt.Errorf("ML feature %s is missing and the model has no imputation", specification.Name)
			}
			raw = *specification.Imputation
			wasImputed = true
		}
		transformed := raw
		if specification.Transform == "log1p" {
			if raw < 0 {
				return domain.Prediction{}, fmt.Errorf("ML feature %s cannot be negative", specification.Name)
			}
			transformed = math.Log1p(raw)
		}
		standardized := (transformed - specification.Mean) / specification.Scale
		coefficient := predictor.artifact.Model.Coefficients[index]
		contributionValue := standardized * coefficient
		logOdds += contributionValue
		contribution := domain.FeatureContribution{
			Feature: specification.Name, SourceName: sourceName(specification.Name),
			RawValue: rawPointer, WasImputed: wasImputed,
			StandardizedValue: standardized, Coefficient: coefficient,
			Contribution: contributionValue,
		}
		if contributionValue > 0 {
			positive = append(positive, contribution)
		} else if contributionValue < 0 {
			negative = append(negative, contribution)
		}
	}
	if !finite(logOdds) {
		return domain.Prediction{}, fmt.Errorf("ML prediction produced non-finite log-odds")
	}
	probability := sigmoid(logOdds)
	predictedClass := predictor.artifact.NegativeLabel
	if probability >= predictor.artifact.DecisionThreshold {
		predictedClass = predictor.artifact.PositiveLabel
	}
	sort.SliceStable(positive, func(i, j int) bool {
		return positive[i].Contribution > positive[j].Contribution
	})
	sort.SliceStable(negative, func(i, j int) bool {
		return negative[i].Contribution < negative[j].Contribution
	})
	positive = firstContributions(positive, explanationFactorLimit)
	negative = firstContributions(negative, explanationFactorLimit)
	return domain.Prediction{
		WalletID: vector.WalletID, ModelVersion: predictor.artifact.ModelVersion,
		IllicitProbability: probability, DecisionThreshold: predictor.artifact.DecisionThreshold,
		PredictedClass: predictedClass, LogOdds: logOdds,
		TopPositiveFactors: positive, TopNegativeFactors: negative,
	}, nil
}

func validateVectorConsistency(vector domain.FeatureVector) error {
	if !finite(vector.DirectIllicitNeighborRatio) || vector.DirectIllicitNeighborRatio < 0 || vector.DirectIllicitNeighborRatio > 1 {
		return fmt.Errorf("direct illicit-neighbor ratio must be finite and within [0,1]")
	}
	counts := []int64{
		vector.DirectIllicitNeighborCount,
		vector.DirectLicitNeighborCount,
		vector.DirectUnknownNeighborCount,
		vector.UniqueNeighbors,
	}
	for _, count := range counts {
		if count < 0 {
			return fmt.Errorf("direct-neighbor counts and unique neighbors cannot be negative")
		}
	}
	if vector.DirectIllicitNeighborCount+vector.DirectLicitNeighborCount+vector.DirectUnknownNeighborCount != vector.UniqueNeighbors {
		return fmt.Errorf("direct-neighbor label counts must partition unique neighbors")
	}
	if vector.OneHopIllicitCount != vector.DirectIllicitNeighborCount {
		return fmt.Errorf("one-hop illicit count must equal direct illicit-neighbor count")
	}
	wantRatio := 0.0
	if vector.UniqueNeighbors > 0 {
		wantRatio = float64(vector.DirectIllicitNeighborCount) / float64(vector.UniqueNeighbors)
	}
	if math.Abs(vector.DirectIllicitNeighborRatio-wantRatio) > 1e-12 {
		return fmt.Errorf("direct illicit-neighbor ratio differs from the supplied neighbor counts")
	}
	return nil
}

func sigmoid(value float64) float64 {
	if value >= 0 {
		return 1 / (1 + math.Exp(-value))
	}
	exponential := math.Exp(value)
	return exponential / (1 + exponential)
}

func firstContributions(values []domain.FeatureContribution, limit int) []domain.FeatureContribution {
	if len(values) <= limit {
		return values
	}
	return values[:limit]
}
