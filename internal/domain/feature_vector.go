package domain

// FeatureVector is the precomputed wallet-level input reviewed in the Elliptic++
// feature schema. The target label is deliberately absent. The rule engine reads
// only a small subset; the other fields preserve the contract for later consumers.
type FeatureVector struct {
	WalletID        string
	Timestep        int64
	EllipticNumeric [55]float64 // index 0 = elliptic_f_001; index 54 = elliptic_f_055

	WalletFirstTimestep         int64
	WalletLastTimestep          int64
	WalletActiveSpan            int64
	WalletObservedTimestepCount int64

	InDegree           int64
	OutDegree          int64
	TotalDegree        int64
	UniqueInNeighbors  int64
	UniqueOutNeighbors int64
	UniqueNeighbors    int64

	DirectIllicitNeighborCount  int64
	DirectLicitNeighborCount    int64
	DirectUnknownNeighborCount  int64
	DirectIllicitNeighborRatio  float64
	OneHopIllicitCount          int64
	TwoHopIllicitCount          int64
	DistanceToOtherKnownIllicit *int64
	HasOtherKnownIllicitPath    bool
}

// EllipticTotalTransactionsIndex is the zero-based position of elliptic_f_006,
// whose original Elliptic++ header is total_txs.
const EllipticTotalTransactionsIndex = 5

// TotalTransactions reads the supplied total_txs feature without deriving it.
func (v FeatureVector) TotalTransactions() float64 {
	return v.EllipticNumeric[EllipticTotalTransactionsIndex]
}
