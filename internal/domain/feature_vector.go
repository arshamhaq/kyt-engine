package domain

// FeatureVector is the precomputed wallet-level input reviewed in the Elliptic++
// feature schema. The target label is deliberately absent. The rule engine reads
// only a small subset; the other fields preserve the contract for later consumers.
type FeatureVector struct {
	WalletID        string      `json:"wallet_id"`
	Timestep        int64       `json:"timestep"`
	EllipticNumeric [55]float64 `json:"elliptic_numeric"` // index 0 = elliptic_f_001; index 54 = elliptic_f_055

	WalletFirstTimestep         int64 `json:"wallet_first_timestep"`
	WalletLastTimestep          int64 `json:"wallet_last_timestep"`
	WalletActiveSpan            int64 `json:"wallet_active_span"`
	WalletObservedTimestepCount int64 `json:"wallet_observed_timestep_count"`

	InDegree           int64 `json:"in_degree"`
	OutDegree          int64 `json:"out_degree"`
	TotalDegree        int64 `json:"total_degree"`
	UniqueInNeighbors  int64 `json:"unique_in_neighbors"`
	UniqueOutNeighbors int64 `json:"unique_out_neighbors"`
	UniqueNeighbors    int64 `json:"unique_neighbors"`

	DirectIllicitNeighborCount  int64   `json:"direct_illicit_neighbor_count"`
	DirectLicitNeighborCount    int64   `json:"direct_licit_neighbor_count"`
	DirectUnknownNeighborCount  int64   `json:"direct_unknown_neighbor_count"`
	DirectIllicitNeighborRatio  float64 `json:"direct_illicit_neighbor_ratio"`
	OneHopIllicitCount          int64   `json:"one_hop_illicit_count"`
	TwoHopIllicitCount          int64   `json:"two_hop_illicit_count"`
	DistanceToOtherKnownIllicit *int64  `json:"distance_to_other_known_illicit"`
	HasOtherKnownIllicitPath    bool    `json:"has_other_known_illicit_path"`
}

// EllipticTotalTransactionsIndex is the zero-based position of elliptic_f_006,
// whose original Elliptic++ header is total_txs.
const EllipticTotalTransactionsIndex = 5

// TotalTransactions reads the supplied total_txs feature without deriving it.
func (v FeatureVector) TotalTransactions() float64 {
	return v.EllipticNumeric[EllipticTotalTransactionsIndex]
}
