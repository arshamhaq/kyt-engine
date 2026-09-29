package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

type stubScorer struct {
	calls int
}

func (scorer *stubScorer) Score(vector domain.FeatureVector) (domain.RiskResult, error) {
	scorer.calls++
	return domain.RiskResult{WalletID: vector.WalletID, Level: domain.RiskLevelLow}, nil
}

func TestHealthAndRepeatedScoring(t *testing.T) {
	scorer := &stubScorer{}
	handler, err := NewHandler(scorer)
	if err != nil {
		t.Fatal(err)
	}

	health := httptest.NewRecorder()
	handler.ServeHTTP(health, httptest.NewRequest(http.MethodGet, "/healthz", nil))
	if health.Code != http.StatusOK || health.Header().Get("Content-Type") != "application/json" {
		t.Fatalf("unexpected health response: %d %s", health.Code, health.Body.String())
	}

	for range 3 {
		request := httptest.NewRequest(http.MethodPost, "/v1/score", bytes.NewReader(validVectorJSON(t)))
		request.Header.Set("Content-Type", "application/json")
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, request)
		if response.Code != http.StatusOK {
			t.Fatalf("unexpected scoring response: %d %s", response.Code, response.Body.String())
		}
		var result domain.RiskResult
		if err := json.Unmarshal(response.Body.Bytes(), &result); err != nil {
			t.Fatal(err)
		}
		if result.WalletID != "111112TykSw72ztDN2WJger4cynzWYC5w" {
			t.Fatalf("unexpected result: %+v", result)
		}
	}
	if scorer.calls != 3 {
		t.Fatalf("scorer calls = %d, want 3", scorer.calls)
	}
}

func TestScoringRejectsInvalidTransportInput(t *testing.T) {
	scorer := &stubScorer{}
	handler, err := NewHandler(scorer)
	if err != nil {
		t.Fatal(err)
	}
	tests := []struct {
		name        string
		contentType string
		body        string
		status      int
	}{
		{"wrong content type", "text/plain", `{}`, http.StatusUnsupportedMediaType},
		{"target leakage", "application/json", `{"label":"illicit"}`, http.StatusBadRequest},
		{"malformed JSON", "application/json", `{`, http.StatusBadRequest},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			request := httptest.NewRequest(http.MethodPost, "/v1/score", bytes.NewBufferString(test.body))
			request.Header.Set("Content-Type", test.contentType)
			response := httptest.NewRecorder()
			handler.ServeHTTP(response, request)
			if response.Code != test.status || response.Header().Get("Content-Type") != "application/json" {
				t.Fatalf("unexpected response: %d %s", response.Code, response.Body.String())
			}
		})
	}
	if scorer.calls != 0 {
		t.Fatalf("invalid requests reached scorer %d times", scorer.calls)
	}
}
