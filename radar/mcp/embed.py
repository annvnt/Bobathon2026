"""Shared embedding model — same vectors for regulations and taxonomy (stdlib)."""

from __future__ import annotations

import math
import re
from collections import Counter

TOKEN = re.compile(r"[a-z0-9]{3,}")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


class Embedder:
    """ponytail: bag-of-words L2 vectors; upgrade path is sentence-transformers."""

    def __init__(self) -> None:
        self.vocab: dict[str, int] = {}

    def fit(self, texts: list[str]) -> None:
        for text in texts:
            for tok in set(tokenize(text)):
                if tok not in self.vocab:
                    self.vocab[tok] = len(self.vocab)

    def embed(self, text: str) -> list[float]:
        if not self.vocab:
            self.fit([text])
        vec = [0.0] * len(self.vocab)
        for tok, count in Counter(tokenize(text)).items():
            idx = self.vocab.get(tok)
            if idx is not None:
                vec[idx] = float(count)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def to_dict(self) -> dict:
        return {"vocab": self.vocab}

    @classmethod
    def from_dict(cls, data: dict) -> Embedder:
        e = cls()
        e.vocab = data.get("vocab", {})
        return e


def cosine_similarity(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return sum(a[i] * b[i] for i in range(n))


def cluster_by_similarity(
    items: list[tuple[str, list[float]]],
    threshold: float = 0.82,
) -> dict[str, str]:
    """Assign cluster_id per item id via greedy cosine clustering."""
    clusters: dict[str, str] = {}
    centroids: list[tuple[str, list[float]]] = []
    for item_id, vec in items:
        assigned = None
        best_sim = threshold
        for cid, cent in centroids:
            sim = cosine_similarity(vec, cent)
            if sim >= best_sim:
                best_sim = sim
                assigned = cid
        if assigned is None:
            assigned = f"cluster-{len(centroids) + 1}"
            centroids.append((assigned, vec))
        clusters[item_id] = assigned
    return clusters
