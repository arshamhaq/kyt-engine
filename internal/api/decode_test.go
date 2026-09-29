package api

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func validVectorJSON(t *testing.T) []byte {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("..", "..", "testdata", "risk_examples", "licit-agreement.json"))
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func TestDecodeFeatureVectorRequiresAllEllipticValues(t *testing.T) {
	var input map[string]any
	if err := json.Unmarshal(validVectorJSON(t), &input); err != nil {
		t.Fatal(err)
	}
	input["elliptic_numeric"] = []float64{0, 1}
	data, err := json.Marshal(input)
	if err != nil {
		t.Fatal(err)
	}
	if vector, err := DecodeFeatureVector(bytes.NewReader(data)); err == nil {
		t.Fatalf("short feature array produced vector %+v", vector)
	}
}

func TestDecodeFeatureVectorRejectsTargetAndIncompleteRows(t *testing.T) {
	for name, input := range map[string]string{
		"target label":   `{"wallet_id":"wallet-A","label":"illicit"}`,
		"missing fields": `{"wallet_id":"wallet-A","elliptic_numeric":[]}`,
	} {
		t.Run(name, func(t *testing.T) {
			if vector, err := DecodeFeatureVector(strings.NewReader(input)); err == nil {
				t.Fatalf("invalid input produced vector %+v", vector)
			}
		})
	}
}
