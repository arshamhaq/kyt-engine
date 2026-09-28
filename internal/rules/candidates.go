package rules

// These thresholds are the six stronger training-selected candidates in
// analysis/results/frozen_rules.json. docs/rule_analysis.md reports their
// held-out behavior. R3 and R8 remain analysis candidates, not active rules.
// The catalog deliberately has no severity or score weights.
func candidateRules() []Rule {
	return []Rule{
		thresholdRule{
			id: "R1", family: "direct_exposure",
			reason:     "At least 20% of distinct graph neighbors are labeled illicit.",
			conditions: []condition{{feature: "direct_illicit_neighbor_ratio", operator: ">=", threshold: 0.20}},
		},
		thresholdRule{
			id: "R2", family: "two_hop_exposure",
			reason:     "At least 50 distinct illicit wallets are exactly two undirected graph hops away.",
			conditions: []condition{{feature: "two_hop_illicit_count", operator: ">=", threshold: 50}},
		},
		thresholdRule{
			id: "R4", family: "direct_exposure",
			reason:     "At least 60% of distinct graph neighbors are labeled illicit; stricter than R1.",
			conditions: []condition{{feature: "direct_illicit_neighbor_ratio", operator: ">=", threshold: 0.60}},
		},
		thresholdRule{
			id: "R5", family: "two_hop_exposure",
			reason:     "At least 100 distinct illicit wallets are exactly two hops away; stricter than R2.",
			conditions: []condition{{feature: "two_hop_illicit_count", operator: ">=", threshold: 100}},
		},
		thresholdRule{
			id: "R6", family: "corroborated_graph_exposure",
			reason: "At least 10% illicit neighbors and at least two distinct illicit wallets exactly two hops away.",
			conditions: []condition{
				{feature: "direct_illicit_neighbor_ratio", operator: ">=", threshold: 0.10},
				{feature: "two_hop_illicit_count", operator: ">=", threshold: 2},
			},
		},
		thresholdRule{
			id: "R7", family: "exposure_with_activity",
			reason: "At least 10% illicit neighbors and at least two total transactions in the provided wallet features.",
			conditions: []condition{
				{feature: "direct_illicit_neighbor_ratio", operator: ">=", threshold: 0.10},
				{feature: "elliptic_f_006", operator: ">=", threshold: 2},
			},
		},
	}
}
