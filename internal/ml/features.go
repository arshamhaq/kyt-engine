package ml

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/arshamhaq/kyt-engine/internal/domain"
)

func expectedFeatureNames() []string {
	names := make([]string, 0, 65)
	for index := 1; index <= 55; index++ {
		if index == 3 || index == 4 || index == 7 || index == 8 {
			continue
		}
		names = append(names, fmt.Sprintf("elliptic_f_%03d", index))
	}
	return append(names,
		"wallet_active_span", "wallet_observed_timestep_count",
		"in_degree", "out_degree", "unique_in_neighbors", "unique_out_neighbors", "unique_neighbors",
		"direct_illicit_neighbor_count", "direct_licit_neighbor_count", "direct_unknown_neighbor_count",
		"direct_illicit_neighbor_ratio", "two_hop_illicit_count",
		"distance_to_other_known_illicit", "has_other_known_illicit_path",
	)
}

func featureValue(vector domain.FeatureVector, name string) (float64, bool, error) {
	if strings.HasPrefix(name, "elliptic_f_") {
		index, err := strconv.Atoi(strings.TrimPrefix(name, "elliptic_f_"))
		if err != nil || index < 1 || index > len(vector.EllipticNumeric) {
			return 0, false, fmt.Errorf("unsupported ML feature %q", name)
		}
		return vector.EllipticNumeric[index-1], true, nil
	}
	var value int64
	switch name {
	case "wallet_active_span":
		value = vector.WalletActiveSpan
	case "wallet_observed_timestep_count":
		value = vector.WalletObservedTimestepCount
	case "in_degree":
		value = vector.InDegree
	case "out_degree":
		value = vector.OutDegree
	case "unique_in_neighbors":
		value = vector.UniqueInNeighbors
	case "unique_out_neighbors":
		value = vector.UniqueOutNeighbors
	case "unique_neighbors":
		value = vector.UniqueNeighbors
	case "direct_illicit_neighbor_count":
		value = vector.DirectIllicitNeighborCount
	case "direct_licit_neighbor_count":
		value = vector.DirectLicitNeighborCount
	case "direct_unknown_neighbor_count":
		value = vector.DirectUnknownNeighborCount
	case "direct_illicit_neighbor_ratio":
		return vector.DirectIllicitNeighborRatio, true, nil
	case "two_hop_illicit_count":
		value = vector.TwoHopIllicitCount
	case "distance_to_other_known_illicit":
		if vector.DistanceToOtherKnownIllicit == nil {
			return 0, false, nil
		}
		value = *vector.DistanceToOtherKnownIllicit
	case "has_other_known_illicit_path":
		if vector.HasOtherKnownIllicitPath {
			return 1, true, nil
		}
		return 0, true, nil
	default:
		return 0, false, fmt.Errorf("unsupported ML feature %q", name)
	}
	if value < 0 {
		return 0, false, fmt.Errorf("ML feature %s cannot be negative", name)
	}
	if value > 1<<53 {
		return 0, false, fmt.Errorf("ML feature %s exceeds exact float64 integer range", name)
	}
	return float64(value), true, nil
}

func sourceName(name string) string {
	if !strings.HasPrefix(name, "elliptic_f_") {
		return name
	}
	index, err := strconv.Atoi(strings.TrimPrefix(name, "elliptic_f_"))
	if err != nil || index < 1 || index > len(ellipticSourceNames) {
		return name
	}
	return ellipticSourceNames[index-1]
}

var ellipticSourceNames = [...]string{
	"num_txs_as_sender", "num_txs_as receiver", "first_block_appeared_in",
	"last_block_appeared_in", "lifetime_in_blocks", "total_txs",
	"first_sent_block", "first_received_block", "num_timesteps_appeared_in",
	"btc_transacted_total", "btc_transacted_min", "btc_transacted_max",
	"btc_transacted_mean", "btc_transacted_median", "btc_sent_total",
	"btc_sent_min", "btc_sent_max", "btc_sent_mean", "btc_sent_median",
	"btc_received_total", "btc_received_min", "btc_received_max",
	"btc_received_mean", "btc_received_median", "fees_total", "fees_min",
	"fees_max", "fees_mean", "fees_median", "fees_as_share_total",
	"fees_as_share_min", "fees_as_share_max", "fees_as_share_mean",
	"fees_as_share_median", "blocks_btwn_txs_total", "blocks_btwn_txs_min",
	"blocks_btwn_txs_max", "blocks_btwn_txs_mean", "blocks_btwn_txs_median",
	"blocks_btwn_input_txs_total", "blocks_btwn_input_txs_min",
	"blocks_btwn_input_txs_max", "blocks_btwn_input_txs_mean",
	"blocks_btwn_input_txs_median", "blocks_btwn_output_txs_total",
	"blocks_btwn_output_txs_min", "blocks_btwn_output_txs_max",
	"blocks_btwn_output_txs_mean", "blocks_btwn_output_txs_median",
	"num_addr_transacted_multiple", "transacted_w_address_total",
	"transacted_w_address_min", "transacted_w_address_max",
	"transacted_w_address_mean", "transacted_w_address_median",
}
