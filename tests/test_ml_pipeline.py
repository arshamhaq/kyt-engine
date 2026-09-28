import json
import math
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from ml.dataset import masked_intelligence_classes, stratified_three_way_split
from ml.evaluation import acceptance, classification_metrics, ranking_metrics, select_operating_threshold
from ml.export import score_row
from ml.preprocessing import (
    ABSOLUTE_TIME_OR_BLOCK_IDENTIFIERS,
    COMBINED_FEATURES,
    INTELLIGENCE_FEATURES,
    fit_preprocessor,
)


class MLPipelineTests(unittest.TestCase):
    def test_split_is_deterministic_disjoint_and_stratified(self):
        labels = np.array(["licit"] * 100 + ["illicit"] * 100)
        first = stratified_three_way_split(labels)
        second = stratified_three_way_split(labels)
        np.testing.assert_array_equal(first, second)
        self.assertEqual({"train", "validation", "test"}, set(first))
        for label in ("licit", "illicit"):
            selected = first[labels == label]
            self.assertEqual(70, int((selected == "train").sum()))
            self.assertEqual(15, int((selected == "validation").sum()))
            self.assertEqual(15, int((selected == "test").sum()))
        with self.assertRaises(ValueError):
            stratified_three_way_split(["licit"] * 10 + ["illicit"] * 10 + ["unknown"])

    def test_held_out_labels_cannot_change_intelligence_inventory(self):
        classes = pd.Series(["1", "2", "1", "2"], index=list("ABCD"), dtype=object)
        first = masked_intelligence_classes(classes, ["A", "B"])
        changed = classes.copy()
        changed.loc[["C", "D"]] = ["2", "1"]
        second = masked_intelligence_classes(changed, ["A", "B"])
        pd.testing.assert_series_equal(first, second)
        self.assertEqual(["1", "2", "3", "3"], first.tolist())

    def test_reviewed_features_exclude_target_identity_and_absolute_time(self):
        self.assertNotIn("label", COMBINED_FEATURES)
        self.assertNotIn("wallet_id", COMBINED_FEATURES)
        self.assertTrue(ABSOLUTE_TIME_OR_BLOCK_IDENTIFIERS.isdisjoint(COMBINED_FEATURES))
        self.assertEqual(len(COMBINED_FEATURES), len(set(COMBINED_FEATURES)))
        self.assertTrue(set(INTELLIGENCE_FEATURES).issubset(COMBINED_FEATURES))

    def test_preprocessor_fits_training_only_and_handles_nullable_distance(self):
        training = pd.DataFrame({
            "elliptic_f_006": [0.0, 3.0],
            "distance_to_other_known_illicit": [1.0, np.nan],
            "has_other_known_illicit_path": [1.0, 0.0],
        })
        features = list(training.columns)
        processor, transformed = fit_preprocessor(training, features)
        self.assertTrue(np.isfinite(transformed).all())
        self.assertEqual(1.0, processor.imputations[1])
        held_out = pd.DataFrame({
            "elliptic_f_006": [1_000_000.0],
            "distance_to_other_known_illicit": [np.nan],
            "has_other_known_illicit_path": [0.0],
        })
        fitted_means = list(processor.means)
        processor.transform(held_out)
        self.assertEqual(fitted_means, processor.means)  # transform cannot refit state
        with self.assertRaises(ValueError):
            fit_preprocessor(pd.DataFrame({"label": [0, 1]}), ["label"])

    def test_threshold_selection_obeys_predeclared_constraints(self):
        target = np.array([1, 1, 1, 0, 0, 0, 0, 0], dtype=bool)
        probability = np.array([0.99, 0.95, 0.90, 0.40, 0.30, 0.20, 0.10, 0.01])
        operating = select_operating_threshold(target, probability)
        self.assertEqual(1.0, operating["precision"])
        self.assertEqual(1.0, operating["recall"])
        self.assertEqual(0.0, operating["false_positive_rate"])
        self.assertEqual(1.0, operating["f0_5"])

    def test_portable_json_math_matches_sklearn(self):
        frame = pd.DataFrame({
            "elliptic_f_006": [0.0, 1.0, 2.0, 5.0],
            "direct_illicit_neighbor_ratio": [0.0, 0.1, 0.5, 1.0],
        })
        target = np.array([0, 0, 1, 1])
        processor, matrix = fit_preprocessor(frame, frame.columns)
        model = LogisticRegression(C=1.0, solver="lbfgs").fit(matrix, target)
        artifact = {
            "model_version": "test",
            "decision_threshold": 0.5,
            "preprocessing": processor.to_dict(),
            "model": {
                "intercept": float(model.intercept_[0]),
                "coefficients": model.coef_[0].tolist(),
            },
        }
        for position, row in frame.iterrows():
            exported, logit, _ = score_row(artifact, row.to_dict())
            expected = model.predict_proba(matrix[position:position + 1])[0, 1]
            self.assertAlmostEqual(expected, exported, places=14)
            self.assertAlmostEqual(exported, 1 / (1 + math.exp(-logit)), places=14)

    def test_acceptance_is_not_accuracy_only(self):
        target = np.array([1] * 5 + [0] * 95, dtype=bool)
        useless = np.full(100, 0.01)
        ranking = ranking_metrics(target, useless)
        operating = classification_metrics(target, useless, 0.5)
        self.assertEqual(0.95, operating["accuracy"])
        self.assertFalse(acceptance({"ranking": ranking, "operating_point": operating})["passed"])

    def test_generated_artifact_passes_recorded_gate_when_present(self):
        path = Path("models/elliptic-logistic-v1/model.json")
        if not path.exists():
            self.skipTest("model artifact has not been generated")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(artifact["evaluation"]["acceptance"]["passed"])
        self.assertEqual(len(artifact["preprocessing"]["features"]),
                         len(artifact["model"]["coefficients"]))

    def test_generated_example_prediction_is_an_exact_complete_trace(self):
        path = Path("models/elliptic-logistic-v1/example_prediction.json")
        if not path.exists():
            self.skipTest("example prediction has not been generated")
        trace = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("test", trace["partition"])
        self.assertEqual("illicit", trace["target_metadata"])
        self.assertFalse(trace["target_used_for_scoring"])
        self.assertEqual(65, trace["model_input_feature_count"])
        self.assertEqual(65, len(trace["all_feature_contributions_by_absolute_magnitude"]))
        calculation = trace["exact_calculation"]
        self.assertAlmostEqual(
            calculation["intercept"] + calculation["sum_of_feature_contributions"],
            calculation["log_odds"], places=12,
        )
        self.assertAlmostEqual(
            calculation["sigmoid_log_odds"], trace["prediction"]["illicit_probability"], places=14,
        )
        self.assertEqual("illicit", trace["prediction"]["predicted_class"])
        self.assertIn("source_name", trace["prediction"]["top_positive_factors"][0])


if __name__ == "__main__":
    unittest.main()
