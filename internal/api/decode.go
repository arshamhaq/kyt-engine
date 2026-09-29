package api

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

const maxFeatureVectorBytes = 64 << 10

var requiredFeatureVectorFields = []string{
	"wallet_id", "timestep", "elliptic_numeric",
	"wallet_first_timestep", "wallet_last_timestep", "wallet_active_span", "wallet_observed_timestep_count",
	"in_degree", "out_degree", "total_degree", "unique_in_neighbors", "unique_out_neighbors", "unique_neighbors",
	"direct_illicit_neighbor_count", "direct_licit_neighbor_count", "direct_unknown_neighbor_count",
	"direct_illicit_neighbor_ratio", "one_hop_illicit_count", "two_hop_illicit_count",
	"distance_to_other_known_illicit", "has_other_known_illicit_path",
}

// DecodeFeatureVector accepts exactly one complete, label-free JSON vector.
func DecodeFeatureVector(source io.Reader) (domain.FeatureVector, error) {
	if source == nil {
		return domain.FeatureVector{}, fmt.Errorf("feature vector body is required")
	}
	data, err := io.ReadAll(io.LimitReader(source, maxFeatureVectorBytes+1))
	if err != nil {
		return domain.FeatureVector{}, fmt.Errorf("read feature vector: %w", err)
	}
	if len(data) > maxFeatureVectorBytes {
		return domain.FeatureVector{}, fmt.Errorf("feature vector exceeds %d bytes", maxFeatureVectorBytes)
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	var vector domain.FeatureVector
	if err := decoder.Decode(&vector); err != nil {
		return domain.FeatureVector{}, fmt.Errorf("decode feature vector: %w", err)
	}
	var trailing any
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		if err == nil {
			return domain.FeatureVector{}, fmt.Errorf("decode feature vector: trailing JSON value")
		}
		return domain.FeatureVector{}, fmt.Errorf("decode feature vector trailer: %w", err)
	}

	var fields map[string]json.RawMessage
	if err := json.Unmarshal(data, &fields); err != nil {
		return domain.FeatureVector{}, fmt.Errorf("inspect feature vector shape: %w", err)
	}
	for _, name := range requiredFeatureVectorFields {
		value, exists := fields[name]
		if !exists {
			return domain.FeatureVector{}, fmt.Errorf("complete feature vector is missing %q", name)
		}
		if name != "distance_to_other_known_illicit" && bytes.Equal(bytes.TrimSpace(value), []byte("null")) {
			return domain.FeatureVector{}, fmt.Errorf("complete feature vector field %q cannot be null", name)
		}
	}
	var ellipticNumeric []float64
	if err := json.Unmarshal(fields["elliptic_numeric"], &ellipticNumeric); err != nil {
		return domain.FeatureVector{}, fmt.Errorf("inspect elliptic_numeric shape: %w", err)
	}
	if len(ellipticNumeric) != len(vector.EllipticNumeric) {
		return domain.FeatureVector{}, fmt.Errorf("elliptic_numeric must contain exactly %d values", len(vector.EllipticNumeric))
	}
	return vector, nil
}
