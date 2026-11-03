"""Opt-in cluster diversity priority; no workload-specific target knowledge.

Distances stay within a fingerprint family. Normalize each family's squared
Euclidean distances by its mean off-diagonal squared distance. This is one
fixed scale per family, not a score fitted to anomaly labels or display caps.
"""
import numpy as np


class ClusterGeometry:
    def __init__(self, centers, families=None):
        self.ids = tuple(centers)
        self.index = {c: i for i, c in enumerate(self.ids)}
        families = {c: 0 for c in self.ids} if families is None else families
        if set(families) != set(centers):
            raise ValueError('Need a family for each cluster center')
        self.families = dict(families)
        self.blocks = []
        self.scales = {}
        for family in dict.fromkeys(families[c] for c in self.ids):
            ids = [c for c in self.ids if families[c] == family]
            values = np.asarray([centers[c] for c in ids], dtype=np.float64)
            if values.ndim != 2 or not np.isfinite(values).all():
                raise ValueError('Centers must be finite vectors of equal size within a family')
            # Direct differences avoid cancellation of nearly identical centers.
            # Keep only one K-by-D temporary rather than a K-by-K-by-D tensor.
            distances = np.empty((len(ids), len(ids)), dtype=np.float64)
            for i, vector in enumerate(values):
                differences = values - vector
                distances[i] = np.einsum('ij,ij->i', differences, differences)
            scale = distances.sum() / (len(ids)*(len(ids)-1)) if len(ids) > 1 else 0.0
            if scale > 0:
                distances /= scale
            self.scales[family] = float(scale)
            self.blocks.append((ids, distances))
        self.bytes = sum(distances.nbytes for _, distances in self.blocks)

    def state(self, clusters):
        if set(clusters) != set(self.ids):
            raise ValueError('Geometry and cluster membership must have identical IDs')
        return DiversityState(self, clusters)


class DiversityState:
    def __init__(self, geometry, clusters):
        self.geometry = geometry
        self.sizes = {c: len(set(pages)) for c, pages in clusters.items()}
        self.nearest = {c: float('inf') for c in geometry.ids}
        self.seen = set()
        self.seeded = set()

    def choose(self, pending, covered):
        """Update distances once per newly represented cluster; preserve tie order."""
        new = set(covered) - self.seen
        if not set(covered) <= set(self.geometry.ids):
            raise ValueError('Unknown represented cluster')
        if new:
            for ids, distances in self.geometry.blocks:
                columns = [i for i, c in enumerate(ids) if c in new]
                if columns:
                    minima = distances[:, columns].min(axis=1)
                    for c, distance in zip(ids, minima):
                        self.nearest[c] = min(self.nearest[c], float(distance))
                    self.seeded.add(self.geometry.families[ids[0]])
            self.seen.update(new)
        candidates = [c for c in pending if c not in covered]
        if not candidates:
            return None
        # Give each as-yet-unrepresented family a common-layout seed. A chosen
        # page can seed several families through its overlapping memberships.
        unseeded = [c for c in candidates if self.geometry.families[c] not in self.seeded]
        if unseeded:
            return max(unseeded, key=lambda c: self.sizes[c])
        return max(candidates, key=lambda c: (self.nearest[c], -self.sizes[c]))
