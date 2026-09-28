"""Reviewed feature groups and portable numeric preprocessing."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from features.schema import ML_COLUMNS


ABSOLUTE_TIME_OR_BLOCK_IDENTIFIERS = {
    "timestep",
    "wallet_first_timestep",
    "wallet_last_timestep",
    "elliptic_f_003",
    "elliptic_f_004",
    "elliptic_f_007",
    "elliptic_f_008",
}
INTELLIGENCE_FEATURES = [
    "direct_illicit_neighbor_count",
    "direct_licit_neighbor_count",
    "direct_unknown_neighbor_count",
    "direct_illicit_neighbor_ratio",
    "two_hop_illicit_count",
    "distance_to_other_known_illicit",
    "has_other_known_illicit_path",
]
REDUNDANT_FEATURES = {
    "total_degree",  # exactly in_degree + out_degree
    "one_hop_illicit_count",  # exactly direct_illicit_neighbor_count
}
BEHAVIOR_FEATURES = [
    column for column in ML_COLUMNS
    if column not in ABSOLUTE_TIME_OR_BLOCK_IDENTIFIERS
    and column not in INTELLIGENCE_FEATURES
    and column not in REDUNDANT_FEATURES
]
COMBINED_FEATURES = [*BEHAVIOR_FEATURES, *INTELLIGENCE_FEATURES]
IDENTITY_TRANSFORMS = {"direct_illicit_neighbor_ratio", "has_other_known_illicit_path"}


@dataclass
class Preprocessor:
    features: list
    transforms: list
    imputations: list
    means: list
    scales: list

    def transform(self, frame):
        if list(frame.columns) != self.features:
            raise ValueError("Feature names or order differ from the fitted preprocessor")
        matrix = frame.apply(pd.to_numeric, errors="raise").to_numpy(dtype=float, na_value=np.nan)
        for index, name in enumerate(self.features):
            missing = ~np.isfinite(matrix[:, index])
            if missing.any():
                imputation = self.imputations[index]
                if imputation is None:
                    raise ValueError(f"Unexpected missing or infinite values in {name}")
                matrix[missing, index] = imputation
            if self.transforms[index] == "log1p":
                if (matrix[:, index] < 0).any():
                    raise ValueError(f"log1p feature {name} contains negative values")
                matrix[:, index] = np.log1p(matrix[:, index])
        return (matrix - np.asarray(self.means)) / np.asarray(self.scales)

    def to_dict(self):
        return {
            "features": [
                {
                    "name": name,
                    "transform": transform,
                    "imputation": imputation,
                    "mean": mean,
                    "scale": scale,
                }
                for name, transform, imputation, mean, scale in zip(
                    self.features, self.transforms, self.imputations, self.means, self.scales
                )
            ]
        }


def fit_preprocessor(frame, features):
    features = list(features)
    if "label" in features or "wallet_id" in features:
        raise ValueError("Target and identity metadata cannot enter preprocessing")
    selected = frame.loc[:, features].apply(pd.to_numeric, errors="raise")
    raw = selected.to_numpy(dtype=float, na_value=np.nan)
    transforms, imputations = [], []
    prepared = raw.copy()
    for index, name in enumerate(features):
        finite = np.isfinite(prepared[:, index])
        if not finite.all():
            if name != "distance_to_other_known_illicit" or not finite.any():
                raise ValueError(f"Unexpected missing or infinite values in {name}")
            imputation = float(np.median(prepared[finite, index]))
            prepared[~finite, index] = imputation
        else:
            imputation = None
        transform = "identity" if name in IDENTITY_TRANSFORMS else "log1p"
        if transform == "log1p":
            if (prepared[:, index] < 0).any():
                raise ValueError(f"log1p feature {name} contains negative values")
            prepared[:, index] = np.log1p(prepared[:, index])
        transforms.append(transform)
        imputations.append(imputation)
    means = prepared.mean(axis=0)
    scales = prepared.std(axis=0)
    scales[scales == 0] = 1.0
    processor = Preprocessor(features, transforms, imputations, means.tolist(), scales.tolist())
    return processor, processor.transform(selected)
