from __future__ import annotations

import hashlib
import importlib
import math
import re
from collections.abc import Sequence
from functools import lru_cache
from typing import Protocol

from apps.api.app.core.config import settings

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.-]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    raw = [item.lower() for item in TOKEN_PATTERN.findall(text)]
    chinese = [item for item in raw if len(item) == 1 and "\u4e00" <= item <= "\u9fff"]
    bigrams = [chinese[index] + chinese[index + 1] for index in range(len(chinese) - 1)]
    return raw + bigrams


class Embedder(Protocol):
    dimensions: int

    def embed(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Deterministic offline baseline for tests and machines without model weights."""

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        return normalize(vector)

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class SentenceTransformerEmbedder:
    """BGE adapter with stable folding to the schema's 256-dimensional vector."""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5", dimensions: int = 256) -> None:
        try:
            sentence_transformers = importlib.import_module("sentence_transformers")
        except ImportError as exc:
            raise RuntimeError(
                "请安装 local-embedding 可选依赖后再启用 EMBEDDING_PROVIDER=bge"
            ) from exc
        self.model = sentence_transformers.SentenceTransformer(
            model_name, cache_folder=settings.model_cache_dir
        )
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        original = self.model.encode(text, normalize_embeddings=True).tolist()
        return self._fold(original)

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        originals = self.model.encode(list(texts), normalize_embeddings=True).tolist()
        return [self._fold(original) for original in originals]

    def _fold(self, original: Sequence[float]) -> list[float]:
        if len(original) == self.dimensions:
            return [float(item) for item in original]
        folded = [0.0] * self.dimensions
        for index, value in enumerate(original):
            folded[index % self.dimensions] += float(value)
        return normalize(folded)


def normalize(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [float(value / norm) for value in vector]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


def embed_batch(embedder: Embedder, texts: Sequence[str]) -> list[list[float]]:
    batch_method = getattr(embedder, "embed_batch", None)
    if callable(batch_method):
        return list(batch_method(texts))
    return [embedder.embed(text) for text in texts]


@lru_cache
def get_embedder() -> Embedder:
    if settings.embedding_provider.lower() in {"bge", "sentence-transformers"}:
        return SentenceTransformerEmbedder()
    return HashEmbedder()
