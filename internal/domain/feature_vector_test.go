package domain

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestTotalTransactionsMatchesReviewedCanonicalColumn(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "..", "data", "derived", "feature_schema.json"))
	if err != nil {
		t.Fatal(err)
	}
	var schema struct {
		Mapping map[string]string `json:"provided_feature_mapping"`
	}
	if err := json.Unmarshal(data, &schema); err != nil {
		t.Fatal(err)
	}
	if got := schema.Mapping["elliptic_f_006"]; got != "total_txs" {
		t.Fatalf("reviewed source meaning changed: elliptic_f_006 = %q", got)
	}
	if EllipticTotalTransactionsIndex != 5 {
		t.Fatalf("array offset changed: %d", EllipticTotalTransactionsIndex)
	}
	vector := FeatureVector{}
	vector.EllipticNumeric[EllipticTotalTransactionsIndex] = 3
	if vector.TotalTransactions() != 3 {
		t.Fatal("Go accessor does not read the reviewed total_txs column")
	}
	if _, exists := reflect.TypeOf(vector).FieldByName("Label"); exists {
		t.Fatal("the prediction target must not be a FeatureVector field")
	}
}
