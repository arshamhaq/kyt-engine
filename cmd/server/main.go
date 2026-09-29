// Command server runs the KYT HTTP API or scores JSON FeatureVectors in
// explicit one-shot or batch mode.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/arshamhaq/kyt-engine/internal/api"
	"github.com/arshamhaq/kyt-engine/internal/domain"
	"github.com/arshamhaq/kyt-engine/internal/ml"
	"github.com/arshamhaq/kyt-engine/internal/rules"
	"github.com/arshamhaq/kyt-engine/internal/scoring"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if err := run(ctx, os.Args[1:], os.Stdin, os.Stdout, os.Stderr); err != nil {
		fmt.Fprintln(os.Stderr, "kyt-engine:", err)
		os.Exit(1)
	}
}

func run(ctx context.Context, arguments []string, stdin io.Reader, stdout, stderr io.Writer) error {
	flags := flag.NewFlagSet("server", flag.ContinueOnError)
	flags.SetOutput(stderr)
	inputPath := flags.String("input", "", "score one FeatureVector file and exit; use - for stdin")
	inputDirectory := flags.String("input-dir", "", "score every .json FeatureVector in a directory and exit")
	modelPath := flags.String("model", "models/elliptic-logistic-v1/model.json", "portable ML model artifact")
	listenAddress := flags.String("listen", ":8080", "HTTP listen address")
	if err := flags.Parse(arguments); err != nil {
		return err
	}
	if flags.NArg() != 0 {
		return fmt.Errorf("unexpected positional arguments")
	}
	if *inputPath != "" && *inputDirectory != "" {
		return fmt.Errorf("-input and -input-dir cannot be used together")
	}
	predictor, err := ml.LoadPredictor(*modelPath)
	if err != nil {
		return err
	}
	scorer, err := scoring.NewScorer(rules.NewRuleEngine(), predictor, scoring.NewAggregator())
	if err != nil {
		return err
	}
	if *inputPath != "" {
		return scoreOnce(*inputPath, stdin, stdout, scorer)
	}
	if *inputDirectory != "" {
		return scoreDirectory(*inputDirectory, stdout, scorer)
	}
	handler, err := api.NewHandler(scorer)
	if err != nil {
		return err
	}
	server := &http.Server{
		Addr:              *listenAddress,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
	fmt.Fprintf(stderr, "kyt-engine listening on %s\n", *listenAddress)
	return serve(ctx, server)
}

type batchItem struct {
	Input  string            `json:"input"`
	Result domain.RiskResult `json:"result"`
}

type batchResult struct {
	Count   int         `json:"count"`
	Results []batchItem `json:"results"`
}

func scoreDirectory(inputDirectory string, stdout io.Writer, scorer *scoring.Scorer) error {
	entries, err := os.ReadDir(inputDirectory)
	if err != nil {
		return fmt.Errorf("read input directory: %w", err)
	}

	result := batchResult{Results: make([]batchItem, 0)}
	for _, entry := range entries {
		if entry.IsDir() || !strings.EqualFold(filepath.Ext(entry.Name()), ".json") {
			continue
		}
		path := filepath.Join(inputDirectory, entry.Name())
		file, err := os.Open(path)
		if err != nil {
			return fmt.Errorf("open %s: %w", entry.Name(), err)
		}
		vector, decodeErr := api.DecodeFeatureVector(file)
		closeErr := file.Close()
		if decodeErr != nil {
			return fmt.Errorf("decode %s: %w", entry.Name(), decodeErr)
		}
		if closeErr != nil {
			return fmt.Errorf("close %s: %w", entry.Name(), closeErr)
		}
		riskResult, err := scorer.Score(vector)
		if err != nil {
			return fmt.Errorf("score %s: %w", entry.Name(), err)
		}
		result.Results = append(result.Results, batchItem{Input: entry.Name(), Result: riskResult})
	}
	if len(result.Results) == 0 {
		return fmt.Errorf("input directory contains no .json files")
	}
	result.Count = len(result.Results)
	return encodeJSON(stdout, result, "batch result")
}

func scoreOnce(inputPath string, stdin io.Reader, stdout io.Writer, scorer *scoring.Scorer) error {
	input := stdin
	if inputPath != "-" {
		file, err := os.Open(inputPath)
		if err != nil {
			return fmt.Errorf("open feature vector: %w", err)
		}
		defer file.Close()
		input = file
	}
	vector, err := api.DecodeFeatureVector(input)
	if err != nil {
		return err
	}
	result, err := scorer.Score(vector)
	if err != nil {
		return err
	}
	return encodeJSON(stdout, result, "risk result")
}

func encodeJSON(output io.Writer, value any, name string) error {
	encoder := json.NewEncoder(output)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(value); err != nil {
		return fmt.Errorf("encode %s: %w", name, err)
	}
	return nil
}

func serve(ctx context.Context, server *http.Server) error {
	errors := make(chan error, 1)
	go func() {
		errors <- server.ListenAndServe()
	}()
	select {
	case err := <-errors:
		if err == http.ErrServerClosed {
			return nil
		}
		return fmt.Errorf("serve HTTP: %w", err)
	case <-ctx.Done():
		shutdownContext, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdownContext); err != nil {
			return fmt.Errorf("shut down HTTP server: %w", err)
		}
		err := <-errors
		if err != nil && err != http.ErrServerClosed {
			return fmt.Errorf("serve HTTP: %w", err)
		}
		return nil
	}
}
