package rules_test

import (
	"encoding/csv"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"strconv"
	"testing"

	"github.com/arshamhaq/kyt-engine/internal/domain"
	"github.com/arshamhaq/kyt-engine/internal/rules"
)

// This adapter exists only in the test: production scoring starts with an
// already-populated FeatureVector, and label is never passed to the rules.
func readWalkthroughRow(t *testing.T) (domain.FeatureVector, string) {
	t.Helper()
	file, err := os.Open(filepath.Join("..", "..", "testdata", "elliptic_rule_walkthrough.csv"))
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()

	rows, err := csv.NewReader(file).ReadAll()
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 2 || len(rows[0]) != 76 || len(rows[1]) != len(rows[0]) {
		t.Fatalf("expected one complete 76-column canonical row, got %d CSV rows", len(rows))
	}
	values := make(map[string]string, len(rows[0]))
	for i, name := range rows[0] {
		if _, exists := values[name]; exists {
			t.Fatalf("duplicate CSV column %q", name)
		}
		values[name] = rows[1][i]
	}
	used := make(map[string]bool, len(values))
	get := func(name string) string {
		t.Helper()
		value, exists := values[name]
		if !exists {
			t.Fatalf("missing CSV column %q", name)
		}
		used[name] = true
		return value
	}
	integer := func(name string) int64 {
		t.Helper()
		value, err := strconv.ParseInt(get(name), 10, 64)
		if err != nil {
			t.Fatalf("parse %s: %v", name, err)
		}
		return value
	}
	numeric := func(name string) float64 {
		t.Helper()
		value, err := strconv.ParseFloat(get(name), 64)
		if err != nil {
			t.Fatalf("parse %s: %v", name, err)
		}
		return value
	}

	vector := domain.FeatureVector{
		WalletID:                    get("wallet_id"),
		Timestep:                    integer("timestep"),
		WalletFirstTimestep:         integer("wallet_first_timestep"),
		WalletLastTimestep:          integer("wallet_last_timestep"),
		WalletActiveSpan:            integer("wallet_active_span"),
		WalletObservedTimestepCount: integer("wallet_observed_timestep_count"),
		InDegree:                    integer("in_degree"),
		OutDegree:                   integer("out_degree"),
		TotalDegree:                 integer("total_degree"),
		UniqueInNeighbors:           integer("unique_in_neighbors"),
		UniqueOutNeighbors:          integer("unique_out_neighbors"),
		UniqueNeighbors:             integer("unique_neighbors"),
		DirectIllicitNeighborCount:  integer("direct_illicit_neighbor_count"),
		DirectLicitNeighborCount:    integer("direct_licit_neighbor_count"),
		DirectUnknownNeighborCount:  integer("direct_unknown_neighbor_count"),
		DirectIllicitNeighborRatio:  numeric("direct_illicit_neighbor_ratio"),
		OneHopIllicitCount:          integer("one_hop_illicit_count"),
		TwoHopIllicitCount:          integer("two_hop_illicit_count"),
		HasOtherKnownIllicitPath:    integer("has_other_known_illicit_path") == 1,
		DistanceToOtherKnownIllicit: nil,
	}
	for i := range vector.EllipticNumeric {
		vector.EllipticNumeric[i] = numeric(fmt.Sprintf("elliptic_f_%03d", i+1))
	}
	if distance := get("distance_to_other_known_illicit"); distance != "" {
		value, err := strconv.ParseInt(distance, 10, 64)
		if err != nil {
			t.Fatalf("parse distance_to_other_known_illicit: %v", err)
		}
		vector.DistanceToOtherKnownIllicit = &value
	}
	label := get("label") // Ground truth metadata, not a FeatureVector field.
	if len(used) != len(values) {
		t.Fatalf("mapped %d of %d CSV columns", len(used), len(values))
	}
	return vector, label
}

func TestFullIllicitWalletWalkthrough(t *testing.T) {
	vector, targetLabel := readWalkthroughRow(t)
	if targetLabel != "illicit" || vector.WalletID != "114H4VXXRicqSRhgjDorRidu6NJXsqBfan" {
		t.Fatalf("unexpected fixture wallet %q with target %q", vector.WalletID, targetLabel)
	}
	if vector.Timestep != 24 || math.Abs(vector.EllipticNumeric[9]-0.0142) > 1e-12 ||
		math.Abs(vector.EllipticNumeric[24]-0.00266398) > 1e-12 || vector.UniqueNeighbors != 2 ||
		vector.DirectIllicitNeighborCount != 1 || vector.DirectUnknownNeighborCount != 1 ||
		vector.OneHopIllicitCount != 1 || vector.DistanceToOtherKnownIllicit == nil ||
		*vector.DistanceToOtherKnownIllicit != 1 {
		t.Fatalf("full row was not mapped correctly: %+v", vector)
	}
	t.Logf("wallet=%s dataset target=%s (kept outside FeatureVector)", vector.WalletID, targetLabel)
	t.Logf("all 55 numeric fields loaded; timestep=%d, total_txs=%.0f, BTC total=%.4f, fees total=%.8f",
		vector.Timestep, vector.TotalTransactions(), vector.EllipticNumeric[9], vector.EllipticNumeric[24])
	t.Logf("in=%d out=%d unique neighbors=%d: illicit=%d, licit=%d, unknown=%d; ratio=%.2f; one-hop=%d two-hop=%d distance=%d",
		vector.InDegree, vector.OutDegree, vector.UniqueNeighbors, vector.DirectIllicitNeighborCount,
		vector.DirectLicitNeighborCount, vector.DirectUnknownNeighborCount, vector.DirectIllicitNeighborRatio,
		vector.OneHopIllicitCount, vector.TwoHopIllicitCount, *vector.DistanceToOtherKnownIllicit)

	findings, err := rules.NewRuleEngine().Evaluate(vector)
	if err != nil {
		t.Fatal(err)
	}
	var got []string
	for _, finding := range findings {
		got = append(got, finding.RuleID)
		t.Logf("MATCH %s: %s", finding.RuleID, finding.Reason)
		for _, evidence := range finding.Evidence {
			t.Logf("  %s: %.4g %s %.4g", evidence.Feature, evidence.Observed, evidence.Operator, evidence.Threshold)
		}
	}
	if want := []string{"R1", "R2", "R5", "R6", "R7"}; !reflect.DeepEqual(got, want) {
		t.Fatalf("matched rules = %v, want %v", got, want)
	}
	t.Log("NO MATCH R4: direct illicit-neighbor ratio 0.5 < 0.6")
	t.Log("Result is five rule findings, not a predicted illicit label or risk score")
}
