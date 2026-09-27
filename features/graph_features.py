"""Compact adjacency arrays; undirected, deduplicated neighbor intelligence.

Direction is retained for degrees. Intelligence traverses the simple undirected
graph. Distances use the two nearest distinct illicit sources, excluding self.
"""

from dataclasses import dataclass
from collections import deque

import numpy as np
import pandas as pd

from .schema import GRAPH_COLUMNS, require_schema


@dataclass
class WalletGraph:
    ids: pd.Index
    labels: np.ndarray
    offsets: np.ndarray
    adjacent: np.ndarray
    in_degree: np.ndarray
    out_degree: np.ndarray
    unique_in: np.ndarray
    unique_out: np.ndarray
    statistics: dict

    def neighbors(self, node):
        return self.adjacent[self.offsets[node]:self.offsets[node + 1]]


def _assemble(ids, source, destination, classes):
    n = len(ids)
    if n >= 2**31:
        raise ValueError("Graph exceeds the supported int32 node range")
    nonself = source != destination
    removed = int((~nonself).sum())
    raw_edges = len(source)
    source, destination = source[nonself], destination[nonself]
    in_degree = np.bincount(destination, minlength=n).astype(np.int64)
    out_degree = np.bincount(source, minlength=n).astype(np.int64)
    directed_keys = np.unique(source.astype(np.uint64) * n + destination)
    src = (directed_keys // n).astype(np.int32)
    dst = (directed_keys % n).astype(np.int32)
    unique_in = np.bincount(dst, minlength=n).astype(np.int64)
    unique_out = np.bincount(src, minlength=n).astype(np.int64)
    undirected_keys = np.unique(np.concatenate((directed_keys, dst.astype(np.uint64) * n + src)))
    undirected_source = (undirected_keys // n).astype(np.int32)
    adjacent = (undirected_keys % n).astype(np.int32)
    degrees = np.bincount(undirected_source, minlength=n)
    offsets = np.concatenate(([0], np.cumsum(degrees, dtype=np.int64)))
    codes = classes.reindex(ids).fillna("3").to_numpy(dtype=np.uint8)
    if not np.isin(codes, [1, 2, 3]).all():
        raise ValueError("Graph labels must contain only class codes 1, 2, 3")
    return WalletGraph(ids, codes, offsets, adjacent, in_degree, out_degree, unique_in, unique_out, {
        "nodes": n, "raw_edge_rows": raw_edges, "self_loop_rows_removed": removed,
        "duplicate_directed_nonself_rows": int(len(source) - len(directed_keys)),
        "unique_directed_nonself_edges": len(directed_keys),
        "unique_undirected_edges": len(undirected_keys) // 2,
        "nodes_without_class": int(classes.reindex(ids).isna().sum()),
        "intelligence_direction": "undirected", "degree_direction": "directed",
    })


def graph_from_edges(wallet_ids, edges, classes):
    """Small-graph constructor used by synthetic tests and independent checks."""
    ids = pd.Index(wallet_ids, dtype=object).union(classes.index, sort=False)
    edges = list(edges)
    endpoints = pd.Index([endpoint for edge in edges for endpoint in edge], dtype=object)
    ids = ids.union(endpoints.unique(), sort=False)
    source = ids.get_indexer([edge[0] for edge in edges]).astype(np.int32)
    destination = ids.get_indexer([edge[1] for edge in edges]).astype(np.int32)
    return _assemble(ids, source, destination, classes)


def graph_from_csv(path, wallet_ids, classes, chunksize=100_000):
    require_schema(path)
    ids = wallet_ids.union(classes.index, sort=False)
    source_parts, destination_parts = [], []
    with pd.read_csv(path, chunksize=chunksize, dtype=str, keep_default_na=False) as reader:
        for chunk in reader:
            if (chunk == "").any().any() or any((chunk[name].str.strip() != chunk[name]).any() for name in chunk):
                raise ValueError("Graph contains blank or whitespace-padded IDs")
            endpoints = pd.Index(pd.unique(chunk.to_numpy().ravel()))
            missing = endpoints[ids.get_indexer(endpoints) < 0]
            if len(missing):
                ids = ids.append(missing)
            source_parts.append(ids.get_indexer(chunk["input_address"]).astype(np.int32))
            destination_parts.append(ids.get_indexer(chunk["output_address"]).astype(np.int32))
    source = np.concatenate(source_parts) if source_parts else np.array([], dtype=np.int32)
    destination = np.concatenate(destination_parts) if destination_parts else np.array([], dtype=np.int32)
    return _assemble(ids, source, destination, classes)


def exact_two_hop_illicit_counts(graph, progress=False):
    """Reverse traversal from illicit sources: O(V+E) storage, no A-squared matrix.

    A source marks itself and its direct neighbors before visiting depth two.
    Unique CSR neighbors plus generation marks deduplicate every destination.
    In an undirected graph this gives each target's exact-distance-two source count.
    """
    counts = np.zeros(len(graph.ids), dtype=np.int64)
    marked = np.zeros(len(graph.ids), dtype=np.int32)
    sources = np.flatnonzero(graph.labels == 1)
    for generation, source in enumerate(sources, 1):
        direct = graph.neighbors(source)
        marked[source] = generation
        marked[direct] = generation
        for middle in direct:
            candidates = graph.neighbors(middle)
            fresh = candidates[marked[candidates] != generation]
            marked[fresh] = generation
            counts[fresh] += 1
        if progress and generation % 2000 == 0:
            print(f"  two-hop sources: {generation:,}/{len(sources):,}", flush=True)
    return counts


def distances_to_other_illicit(graph):
    """Linear multi-source BFS retaining two nearest *distinct* source IDs.

    Every node has at most two queue entries. An illicit target uses its second
    source; other targets use their first. Unreachable other sources return -1
    internally, subsequently serialized as nullable distance plus a presence flag.
    """
    n = len(graph.ids)
    nearest = np.full((n, 2), -1, dtype=np.int32)
    distances = np.full((n, 2), -1, dtype=np.int32)
    illicit = np.flatnonzero(graph.labels == 1)
    nearest[illicit, 0] = illicit
    distances[illicit, 0] = 0
    queue = np.empty(2 * n, dtype=np.int64)
    queue[:len(illicit)] = 2 * illicit
    head, tail = 0, len(illicit)
    while head < tail:
        state = int(queue[head])
        head += 1
        node, slot = divmod(state, 2)
        source = nearest[node, slot]
        distance = distances[node, slot] + 1
        for neighbor in graph.neighbors(node):
            if nearest[neighbor, 0] == source or nearest[neighbor, 1] == source:
                continue
            if nearest[neighbor, 0] < 0:
                destination_slot = 0
            elif nearest[neighbor, 1] < 0:
                destination_slot = 1
            else:
                continue
            nearest[neighbor, destination_slot] = source
            distances[neighbor, destination_slot] = distance
            queue[tail] = 2 * int(neighbor) + destination_slot
            tail += 1
    indices = np.arange(n)
    return np.where(nearest[:, 0] == indices, distances[:, 1], distances[:, 0])


def derive_graph_features(graph, progress=False):
    n = len(graph.ids)
    degree = np.diff(graph.offsets)
    direct = {}
    for code, label in ((1, "illicit"), (2, "licit"), (3, "unknown")):
        # Count selected neighbor entries within each CSR row without a Python edge graph.
        cumulative = np.concatenate(([0], np.cumsum(graph.labels[graph.adjacent] == code, dtype=np.int64)))
        direct[label] = cumulative[graph.offsets[1:]] - cumulative[graph.offsets[:-1]]
    ratio = np.divide(direct["illicit"], degree, out=np.zeros(n, dtype=float), where=degree > 0)
    if progress:
        print("Deriving exact two-hop illicit counts", flush=True)
    two_hop = exact_two_hop_illicit_counts(graph, progress)
    if progress:
        print("Deriving distance to OTHER illicit nodes", flush=True)
    distances = distances_to_other_illicit(graph)
    nullable = pd.array(distances, dtype="Int64")
    nullable[distances < 0] = pd.NA
    frame = pd.DataFrame({
        "in_degree": graph.in_degree, "out_degree": graph.out_degree,
        "total_degree": graph.in_degree + graph.out_degree,
        "unique_in_neighbors": graph.unique_in, "unique_out_neighbors": graph.unique_out,
        "unique_neighbors": degree, "direct_illicit_neighbor_count": direct["illicit"],
        "direct_licit_neighbor_count": direct["licit"], "direct_unknown_neighbor_count": direct["unknown"],
        "direct_illicit_neighbor_ratio": ratio, "one_hop_illicit_count": direct["illicit"],
        "two_hop_illicit_count": two_hop, "distance_to_other_known_illicit": nullable,
        "has_other_known_illicit_path": (distances >= 0).astype(np.uint8),
    }, index=graph.ids)
    return frame[GRAPH_COLUMNS]


def reference_intelligence(graph, target, labels=None):
    """Independent per-target set/BFS oracle, excluding the target explicitly."""
    labels = graph.labels if labels is None else labels
    direct = set(map(int, graph.neighbors(target))) - {target}
    second = set()
    for neighbor in direct:
        second.update(map(int, graph.neighbors(neighbor)))
    second.difference_update(direct | {target})
    counts = {name: sum(labels[node] == code for node in direct) for code, name in ((1, "illicit"), (2, "licit"), (3, "unknown"))}
    visited = {target}
    queue = deque([(target, 0)])
    distance = None
    while queue:
        node, hops = queue.popleft()
        if node != target and labels[node] == 1:
            distance = hops
            break
        for neighbor in graph.neighbors(node):
            neighbor = int(neighbor)
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, hops + 1))
    return {
        "direct_illicit_neighbor_count": counts["illicit"],
        "direct_licit_neighbor_count": counts["licit"],
        "direct_unknown_neighbor_count": counts["unknown"],
        "direct_illicit_neighbor_ratio": counts["illicit"] / len(direct) if direct else 0.0,
        "one_hop_illicit_count": counts["illicit"],
        "two_hop_illicit_count": sum(labels[node] == 1 for node in second),
        "distance_to_other_known_illicit": distance,
        "has_other_known_illicit_path": int(distance is not None),
    }


def audit_target_label_exclusion(graph, frame, target_count, sample_size=16):
    candidates = []
    for code in (1, 2, 3):
        candidates.extend(np.flatnonzero(graph.labels[:target_count] == code)[:4].tolist())
    candidates.extend([int(np.argmax(np.diff(graph.offsets)[:target_count]))])
    candidates.extend(np.linspace(0, target_count - 1, max(1, sample_size), dtype=int).tolist())
    targets = list(dict.fromkeys(candidates))[:sample_size]
    for target in targets:
        expected = reference_intelligence(graph, target)
        mutated_labels = graph.labels.copy()
        mutated_labels[target] = 2 if mutated_labels[target] == 1 else 1
        if reference_intelligence(graph, target, mutated_labels) != expected:
            raise ValueError("Target-label mutation influenced the reference features")
        actual = frame.iloc[target]
        for column, value in expected.items():
            if value is None:
                matches = pd.isna(actual[column])
            else:
                matches = actual[column] == value
            if not matches:
                raise ValueError(f"Graph/leakage audit failed for {graph.ids[target]}: {column}")
    return {
        "passed": True, "method": "independent per-target set/BFS oracle and target-label mutation",
        "audited_targets": len(targets), "wallet_ids": graph.ids[targets].tolist(),
        "all_rows_distance_zero_forbidden": True,
        "note": "Full-graph label-mutation invariance is also tested on synthetic/random graphs; the real-data oracle audit is sampled.",
    }
