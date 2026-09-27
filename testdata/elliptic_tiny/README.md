# Synthetic Elliptic++ schema fixture

These are artificial A/B/C/D IDs and numeric values, not real Elliptic++ records.
The CSV headers match the inspected official actor schema exactly.

Edges: A -> B, A -> C, B -> D. Labels: A licit, B illicit, C unknown, D illicit.
A has observations at timesteps 1 and 3; its latest first numeric value is 2.

For A: two outgoing edge records, two unique neighbors, one direct illicit and
one direct unknown neighbor, illicit-neighbor ratio 0.5, one distinct illicit node
at exactly two hops (D), and distance 1 to another known illicit node (B).

Used by tests; derived output is created in temporary directories.
