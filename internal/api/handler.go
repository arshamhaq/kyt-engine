package api

import (
	"encoding/json"
	"fmt"
	"mime"
	"net/http"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

// Scorer is the application boundary required by the HTTP transport.
type Scorer interface {
	Score(domain.FeatureVector) (domain.RiskResult, error)
}

type Handler struct {
	mux *http.ServeMux
}

func NewHandler(scorer Scorer) (*Handler, error) {
	if scorer == nil {
		return nil, fmt.Errorf("API scorer is required")
	}
	mux := http.NewServeMux()
	handler := &Handler{mux: mux}
	mux.HandleFunc("GET /healthz", handler.health)
	mux.HandleFunc("POST /v1/score", handler.score(scorer))
	return handler, nil
}

func (handler *Handler) ServeHTTP(response http.ResponseWriter, request *http.Request) {
	handler.mux.ServeHTTP(response, request)
}

func (handler *Handler) health(response http.ResponseWriter, _ *http.Request) {
	writeJSON(response, http.StatusOK, map[string]string{"status": "ok"})
}

func (handler *Handler) score(scorer Scorer) http.HandlerFunc {
	return func(response http.ResponseWriter, request *http.Request) {
		mediaType, _, err := mime.ParseMediaType(request.Header.Get("Content-Type"))
		if err != nil || mediaType != "application/json" {
			writeError(response, http.StatusUnsupportedMediaType, "unsupported_media_type", "Content-Type must be application/json")
			return
		}
		vector, err := DecodeFeatureVector(request.Body)
		if err != nil {
			writeError(response, http.StatusBadRequest, "invalid_request", err.Error())
			return
		}
		result, err := scorer.Score(vector)
		if err != nil {
			writeError(response, http.StatusUnprocessableEntity, "invalid_feature_vector", err.Error())
			return
		}
		writeJSON(response, http.StatusOK, result)
	}
}

type errorResponse struct {
	Error struct {
		Code    string `json:"code"`
		Message string `json:"message"`
	} `json:"error"`
}

func writeError(response http.ResponseWriter, status int, code, message string) {
	payload := errorResponse{}
	payload.Error.Code = code
	payload.Error.Message = message
	writeJSON(response, status, payload)
}

func writeJSON(response http.ResponseWriter, status int, value any) {
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	_ = json.NewEncoder(response).Encode(value)
}
