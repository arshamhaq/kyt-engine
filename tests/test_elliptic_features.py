"""Explicit tiny-graph expectations, label mutation invariance, and CSV failures."""

import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from features.build_features import build_dataset
from features.graph_features import derive_graph_features, graph_from_edges, reference_intelligence
from features.schema import CANONICAL_COLUMNS, FEATURE_MAP, load_classes
from features.validate_features import validate_dataset

FIXTURE = Path(__file__).resolve().parents[1] / "testdata" / "elliptic_tiny"


def derive(edges, labels, wallets=None):
    classes = pd.Series({wallet: str(code) for wallet, code in labels.items()}, dtype=object)
    graph = graph_from_edges(wallets or list(labels), edges, classes)
    return graph, derive_graph_features(graph)


class GraphFeatureTests(unittest.TestCase):
    def test_direct_and_exact_two_hop_fixture(self):
        _, features = derive([("A", "B"), ("A", "C"), ("B", "D")], {"A": 2, "B": 1, "C": 3, "D": 1})
        row = features.loc["A"]
        expected = {"in_degree": 0, "out_degree": 2, "unique_neighbors": 2,
                    "direct_illicit_neighbor_count": 1, "direct_licit_neighbor_count": 0,
                    "direct_unknown_neighbor_count": 1, "direct_illicit_neighbor_ratio": 0.5,
                    "one_hop_illicit_count": 1, "two_hop_illicit_count": 1,
                    "distance_to_other_known_illicit": 1}
        for name, value in expected.items():
            self.assertEqual(row[name], value, name)

    def test_no_illicit_path_is_missing_not_zero(self):
        _, frame = derive([("A", "B")], {"A": 2, "B": 3})
        self.assertTrue(pd.isna(frame.loc["A", "distance_to_other_known_illicit"]))
        self.assertEqual(frame.loc["A", "has_other_known_illicit_path"], 0)
        self.assertEqual(frame.loc["A", "direct_unknown_neighbor_count"], 1)

    def test_isolated_illicit_target_does_not_supply_its_own_distance(self):
        _, frame = derive([], {"A": 1})
        self.assertEqual(frame.loc["A", "unique_neighbors"], 0)
        self.assertTrue(pd.isna(frame.loc["A", "distance_to_other_known_illicit"]))

    def test_illicit_target_searches_other_source(self):
        _, frame = derive([("A", "B"), ("B", "D")], {"A": 1, "B": 2, "D": 1})
        self.assertEqual(frame.loc["A", "distance_to_other_known_illicit"], 2)
        self.assertEqual(frame.loc["A", "two_hop_illicit_count"], 1)

    def test_duplicate_paths_and_edge_records_count_nodes_once(self):
        graph, frame = derive([("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"), ("B", "D")],
                              {"A": 2, "B": 2, "C": 3, "D": 1})
        self.assertEqual(frame.loc["A", "two_hop_illicit_count"], 1)
        self.assertEqual(frame.loc["A", "distance_to_other_known_illicit"], 2)
        self.assertEqual(frame.loc["B", "out_degree"], 2)
        self.assertEqual(frame.loc["B", "unique_out_neighbors"], 1)
        self.assertEqual(graph.statistics["duplicate_directed_nonself_rows"], 1)

    def test_direct_neighbors_are_excluded_from_exact_two_hops(self):
        _, frame = derive([("A", "B"), ("A", "D"), ("B", "D")], {"A": 2, "B": 2, "D": 1})
        self.assertEqual(frame.loc["A", "one_hop_illicit_count"], 1)
        self.assertEqual(frame.loc["A", "two_hop_illicit_count"], 0)

    def test_cycles_and_self_loops_never_count_target(self):
        graph, frame = derive([("A", "A"), ("A", "B"), ("B", "C"), ("C", "A")], {"A": 1, "B": 2, "C": 3})
        self.assertEqual(graph.statistics["self_loop_rows_removed"], 1)
        self.assertEqual(frame.loc["A", "unique_neighbors"], 2)
        self.assertEqual(frame.loc["A", "one_hop_illicit_count"], 0)
        self.assertEqual(frame.loc["A", "two_hop_illicit_count"], 0)
        self.assertTrue(pd.isna(frame.loc["A", "distance_to_other_known_illicit"]))

    def test_missing_neighbor_label_is_unknown(self):
        _, frame = derive([("A", "B")], {"A": 2}, wallets=["A", "B"])
        self.assertEqual(frame.loc["A", "direct_unknown_neighbor_count"], 1)
        self.assertEqual(frame.loc["A", "direct_licit_neighbor_count"], 0)

    def test_directed_degrees_undirected_intelligence(self):
        _, forward = derive([("A", "B")], {"A": 2, "B": 1})
        _, reverse = derive([("B", "A")], {"A": 2, "B": 1})
        self.assertEqual(forward.loc["A", "out_degree"], 1)
        self.assertEqual(reverse.loc["A", "in_degree"], 1)
        self.assertEqual(reverse.loc["A", "out_degree"], 0)
        self.assertEqual(reverse.loc["A", "direct_illicit_neighbor_count"], 1)
        self.assertEqual(forward.loc["A", "distance_to_other_known_illicit"], reverse.loc["A", "distance_to_other_known_illicit"])

    def test_target_label_mutation_preserves_all_target_graph_features(self):
        rng = np.random.default_rng(17)
        nodes = list("ABCDEFGH")
        for trial in range(20):
            edges = [(a, b) for a in nodes for b in nodes if rng.random() < 0.2]
            labels = {node: int(rng.integers(1, 4)) for node in nodes}
            graph, original = derive(edges, labels)
            for target in nodes:
                target_index = graph.ids.get_loc(target)
                expected = reference_intelligence(graph, target_index)
                for name, value in expected.items():
                    if value is None:
                        self.assertTrue(pd.isna(original.loc[target, name]))
                    else:
                        self.assertEqual(original.loc[target, name], value)
                for code in (1, 2, 3):
                    changed = {**labels, target: code}
                    _, mutated = derive(edges, changed)
                    pd.testing.assert_series_equal(original.loc[target], mutated.loc[target], obj=f"trial {trial}, target {target}, class {code}")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw = self.root / "raw"
        shutil.copytree(FIXTURE, self.raw)
        self.output = self.root / "derived" / "features.csv"

    def tearDown(self):
        self.temp.cleanup()

    def build(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return build_dataset(self.raw, self.output, chunksize=2)

    def test_end_to_end_snapshot_mapping_and_report(self):
        report = self.build()
        frame = pd.read_csv(self.output).set_index("wallet_id")
        self.assertEqual(report["rows"], 4)
        self.assertEqual(report["class_distribution"], {"licit": 1, "illicit": 2, "unknown": 1})
        self.assertEqual(report["supervised_eligible_rows"], 3)
        self.assertEqual(report["provided_numeric_features"], 55)
        self.assertFalse(report["label_is_feature"])
        self.assertTrue(report["target_label_exclusion_audit"]["passed"])
        self.assertEqual(frame.loc["A", "elliptic_f_001"], 2)
        self.assertEqual(frame.loc["A", "timestep"], 3)
        self.assertEqual(frame.loc["A", "wallet_first_timestep"], 1)
        self.assertEqual(frame.loc["A", "wallet_last_timestep"], 3)
        self.assertEqual(frame.loc["A", "wallet_active_span"], 2)
        self.assertEqual(frame.loc["A", "wallet_observed_timestep_count"], 2)
        self.assertEqual(frame.loc["A", "two_hop_illicit_count"], 1)
        self.assertEqual(list(pd.read_csv(self.output, nrows=0)), CANONICAL_COLUMNS)
        self.assertTrue((self.output.parent / "feature_report.json").exists())
        self.assertTrue((self.output.parent / "feature_schema.json").exists())
        self.assertEqual(FEATURE_MAP["elliptic_f_002"], "num_txs_as receiver")

    def test_target_label_mutation_does_not_change_full_feature_row(self):
        self.build()
        original = pd.read_csv(self.output).set_index("wallet_id").loc["A"].drop("label")
        path = self.raw / "wallets_classes.csv"
        path.write_text(path.read_text().replace("A,2", "A,1"))
        self.build()
        modified = pd.read_csv(self.output).set_index("wallet_id").loc["A"].drop("label")
        pd.testing.assert_series_equal(original, modified)

    def test_missing_target_label_stays_unknown(self):
        path = self.raw / "wallets_classes.csv"
        path.write_text(path.read_text().replace("A,2\n", ""))
        report = self.build()
        self.assertEqual(pd.read_csv(self.output).set_index("wallet_id").loc["A", "label"], "unknown")
        self.assertEqual(report["missing_target_classes_defaulted_to_unknown"], 1)
        self.assertEqual(report["supervised_eligible_rows"], 2)

    def test_unverified_class_and_duplicate_class_rejected(self):
        path = self.raw / "wallets_classes.csv"
        original = path.read_text()
        for invalid in (original.replace("A,2", "A,4"), original + "A,2\n"):
            with self.subTest(invalid=invalid):
                path.write_text(invalid)
                with self.assertRaises(ValueError):
                    load_classes(path)

    def test_identical_duplicate_wallet_timestep_collapsed(self):
        path = self.raw / "wallets_features.csv"
        lines = path.read_text().splitlines()
        path.write_text("\n".join(lines + [lines[1]]) + "\n")
        report = self.build()
        self.assertEqual(report["rows"], 4)
        self.assertEqual(report["observations"]["duplicate_wallet_timestep_rows_collapsed"], 1)
        self.assertEqual(report["observations"]["duplicate_wallet_timestep_keys"], 1)
        self.assertEqual(pd.read_csv(self.output).set_index("wallet_id").loc["A", "wallet_observed_timestep_count"], 2)

    def test_conflicting_duplicate_wallet_timestep_rejected(self):
        path = self.raw / "wallets_features.csv"
        frame = pd.read_csv(path)
        duplicate = frame.iloc[[0]].copy()
        duplicate["num_txs_as_sender"] = 99
        pd.concat([frame, duplicate]).to_csv(path, index=False)
        with self.assertRaisesRegex(ValueError, "Conflicting duplicate wallet/timestep"):
            self.build()

    def test_raw_nonfinite_numeric_rejected(self):
        path = self.raw / "wallets_features.csv"
        frame = pd.read_csv(path)
        frame.loc[0, "num_txs_as_sender"] = np.inf
        frame.to_csv(path, index=False)
        with self.assertRaisesRegex(ValueError, "NaN/Inf"):
            self.build()

    def test_label_column_cannot_sneak_into_raw_numeric_features(self):
        path = self.raw / "wallets_features.csv"
        frame = pd.read_csv(path)
        frame["class"] = 1
        frame.to_csv(path, index=False)
        with self.assertRaisesRegex(ValueError, "Unexpected schema"):
            self.build()

    def test_derived_invalid_values_rejected(self):
        self.build()
        original = pd.read_csv(self.output)
        failures = [
            ("in_degree", -1), ("in_degree", 0.5), ("direct_illicit_neighbor_ratio", 1.1),
            ("elliptic_f_001", np.nan), ("elliptic_f_001", np.inf),
            ("distance_to_other_known_illicit", 0), ("distance_to_other_known_illicit", -1),
            ("label", "sanctioned"), ("label", np.nan), ("has_other_known_illicit_path", 0),
        ]
        for column, value in failures:
            with self.subTest(column=column, value=value):
                invalid = original.copy()
                invalid.loc[0, column] = value
                invalid.to_csv(self.output, index=False)
                with self.assertRaises(ValueError):
                    validate_dataset(self.output, chunksize=2)
        pd.concat([original, original.iloc[[0]]]).to_csv(self.output, index=False)
        with self.assertRaisesRegex(ValueError, "Duplicate wallet"):
            validate_dataset(self.output, chunksize=2)


if __name__ == "__main__":
    unittest.main()
