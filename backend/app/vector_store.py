"""ChromaDB vector store for chunked regulation texts.

Uses a fully-offline, deterministic embedding function (hashed bag-of-words)
so the demo never needs a model download or network access. Swap
`_OfflineEmbeddingFunction` for a sentence-transformers / watsonx embedder for
production-grade retrieval — the rest of the code is unchanged.
"""
from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from .config import settings

COLLECTION_NAME = "regulations_vector_store"
_DIM = 384
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class _OfflineEmbeddingFunction(EmbeddingFunction):
    """Deterministic hashed bag-of-words embedding (no external deps)."""

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * _DIM
        tokens = _TOKEN_RE.findall(text.lower())
        for tok in tokens:
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            idx = h % _DIM
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 (chroma API)
        return [self._embed_one(doc) for doc in input]

    def name(self) -> str:  # required by chromadb >=0.5
        return "offline-hashed-bow"


@lru_cache
def get_client() -> chromadb.ClientAPI:
    from chromadb.config import Settings as ChromaSettings

    return chromadb.PersistentClient(
        path=settings.CHROMA_DIR,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


@lru_cache
def get_collection():
    return get_client().get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_OfflineEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


def count() -> int:
    try:
        return get_collection().count()
    except Exception:  # noqa: BLE001
        return 0


def reset() -> None:
    client = get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:  # noqa: BLE001
        pass
    get_collection.cache_clear()
