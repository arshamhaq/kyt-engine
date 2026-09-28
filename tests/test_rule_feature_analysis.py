"""Meaningful safeguards for offline threshold analysis and held-out evaluation."""

import copy
import unittest

import numpy as np
import pandas as pd

from analysis.rule_feature_analysis import (
    condition, evaluate_frozen, id_digest, intelligence_classes, metrics,
    nice_thresholds, rule_mask, stratified_split, univariate_analysis,
)
from features.graph_features import derive_graph_features, graph_from_edges
from features.schema import CANONICAL_COLUMNS


class RuleAnalysisTests(unittest.TestCase):
    def test_confusion_metrics_use_actual_negative_denominator(self):
        result = metrics([True, True, False, True, False, False], [True, True, True, False, False, False])
        self.assertEqual([result[key] for key in ("tp", "fp", "fn", "tn")], [2, 1, 1, 2])
        self.assertAlmostEqual(result["precision"], 2 / 3)
        self.assertAlmostEqual(result["recall"], 2 / 3)
        self.assertAlmostEqual(result["false_positive_rate"], 1 / 3)
        self.assertEqual(result["support"], 3)

    def test_no_triggers_have_undefined_precision_not_perfect_precision(self):
        result = metrics([False, False], [True, False])
        self.assertIsNone(result["precision"])
        self.assertEqual(result["recall"], 0)
        self.assertEqual(result["false_positive_rate"], 0)

    def test_stratified_wallet_split_is_disjoint_deterministic_and_excludes_unknown(self):
        labels = np.array(["licit"] * 20 + ["illicit"] * 10)
        train, validation = stratified_split(labels)
        self.assertFalse((train & validation).any())
        self.assertTrue((train | validation).all())
        self.assertEqual(int((validation & (labels == "licit")).sum()), 4)
        self.assertEqual(int((validation & (labels == "illicit")).sum()), 2)
        np.testing.assert_array_equal(train, stratified_split(labels)[0])
        with self.assertRaises(ValueError):
            stratified_split(["licit", "illicit", "unknown"])

    def test_validation_label_changes_cannot_change_intelligence_features(self):
        original = pd.Series({"A": "2", "B": "1", "C": "1", "D": "2"})
        changed = original.copy()
        changed.loc[["C", "D"]] = ["2", "1"]
        a = intelligence_classes(original, ["A", "B"])
        b = intelligence_classes(changed, ["A", "B"])
        pd.testing.assert_series_equal(a, b)
        self.assertEqual(a.loc["C"], "3")
        self.assertEqual(a.loc["D"], "3")
        edges = [("A", "C"), ("C", "B"), ("B", "D")]
        first = derive_graph_features(graph_from_edges(list(original.index), edges, a))
        second = derive_graph_features(graph_from_edges(list(original.index), edges, b))
        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(first.loc["A", "direct_illicit_neighbor_count"], 0)
        self.assertEqual(first.loc["A", "two_hop_illicit_count"], 1)

    def test_absent_distance_never_matches_a_nearby_rule(self):
        frame = pd.DataFrame({"distance_to_other_known_illicit": [None, 1, 2, 3]})
        np.testing.assert_array_equal(rule_mask(frame, [condition("distance_to_other_known_illicit", 2, "<=")]),
                                      [False, True, True, False])
        with self.assertRaises(ValueError):
            rule_mask(frame, [condition("label", 1)])

    def test_threshold_grids_use_only_supplied_training_values(self):
        values = pd.Series([0, 1, 2, 10])
        thresholds = nice_thresholds(values, "total_degree")
        self.assertTrue(all(0 <= value <= 10 for value in thresholds))
        self.assertNotIn(1000, thresholds)

    def test_rank_auc_respects_ties_and_both_directions(self):
        rows = 6
        frame = pd.DataFrame({column: np.zeros(rows) for column in CANONICAL_COLUMNS[1:-1]})
        frame["label"] = ["licit"] * 3 + ["illicit"] * 3
        frame["elliptic_f_001"] = [0, 0, 0, 2, 2, 2]
        frame["elliptic_f_002"] = [2, 2, 2, 0, 0, 0]
        _, rankings, _ = univariate_analysis(frame)
        rank = {item["feature"]: item for item in rankings}
        self.assertEqual(rank["elliptic_f_001"]["auc_increasing"], 1)
        self.assertEqual(rank["elliptic_f_002"]["auc_increasing"], 0)
        self.assertEqual(rank["elliptic_f_002"]["auc_separation"], 1)
        self.assertEqual(rank["elliptic_f_010"]["auc_separation"], .5)

    def test_frozen_conditions_remain_fixed_when_validation_labels_change(self):
        frame = pd.DataFrame({"signal": [0, 1, 1, 0], "label": ["licit", "illicit", "illicit", "licit"]}, index=list("ABCD"))
        train = np.array([True, True, False, False])
        validation = ~train
        conditions = [condition("signal", 1)]
        training = metrics(rule_mask(frame.loc[train], conditions), frame.loc[train, "label"] == "illicit")
        frozen = {"split": {"training_wallet_id_sha256": id_digest(frame.index[train]),
                            "validation_wallet_id_sha256": id_digest(frame.index[validation])},
                  "selection_policy": {}, "rules": [{"id": "R1", "conditions": conditions, "training": training}]}
        before = copy.deepcopy(frozen)
        original = evaluate_frozen(frame, train, validation, frozen)
        frame.loc[["C", "D"], "label"] = ["licit", "illicit"]
        changed = evaluate_frozen(frame, train, validation, frozen)
        self.assertEqual(frozen, before)
        self.assertEqual(original["rules"][0]["validation"]["precision"], 1)
        self.assertEqual(changed["rules"][0]["validation"]["precision"], 0)
        self.assertEqual(original["rules"][0]["conditions"], changed["rules"][0]["conditions"])


if __name__ == "__main__":
    unittest.main()
