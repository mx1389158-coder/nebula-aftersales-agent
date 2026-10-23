from __future__ import annotations

import importlib
import math
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, cast

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.models import Chunk, Document
from packages.context.embeddings import Embedder, cosine_similarity, get_embedder, tokenize
from packages.context.external_retrieval import query_lightrag, query_openviking


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    title: str
    section: str
    version: str
    text: str
    score: float
    page: int | None = None


@lru_cache(maxsize=1)
def _get_cross_encoder() -> Any:
    sentence_transformers = importlib.import_module("sentence_transformers")
    return sentence_transformers.CrossEncoder(
        settings.cross_encoder_model, cache_folder=settings.model_cache_dir
    )


def _bm25(
    query: list[str], corpus: list[list[str]], k1: float = 1.5, b: float = 0.75
) -> list[float]:
    if not corpus:
        return []
    average_length = sum(len(doc) for doc in corpus) / len(corpus) or 1.0
    document_frequency: Counter[str] = Counter()
    for doc in corpus:
        document_frequency.update(set(doc))
    scores: list[float] = []
    for doc in corpus:
        frequencies = Counter(doc)
        score = 0.0
        for term in query:
            frequency = frequencies[term]
            if not frequency:
                continue
            inverse = math.log(
                1
                + (len(corpus) - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
            )
            denominator = frequency + k1 * (1 - b + b * len(doc) / average_length)
            score += inverse * frequency * (k1 + 1) / denominator
        scores.append(score)
    return scores


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            fused[item] = fused.get(item, 0.0) + 1.0 / (k + rank)
    return fused


class HybridRetriever:
    def __init__(self, session: Session, embedder: Embedder | None = None) -> None:
        self.session = session
        self.embedder = embedder or get_embedder()

    def _scope_query(
        self,
        tenant_id: str,
        product_id: str,
        model: str | None,
        firmware_version: str | None,
    ) -> Select[Chunk, Document]:
        query = (
            select(Chunk, Document)
            .join(Document, Chunk.document_id == Document.id)
            .where(
                Chunk.tenant_id == tenant_id,
                Chunk.product_id == product_id,
                Document.status == "active",
                Document.effective_at <= datetime.now(UTC),
            )
        )
        if model:
            query = query.where((Chunk.model == model) | (Chunk.model.is_(None)))
        if firmware_version:
            query = query.where(
                (Chunk.firmware_version == firmware_version) | (Chunk.firmware_version.is_(None))
            )
        return query.order_by(Document.effective_at.desc(), Chunk.ordinal.asc())

    def search(
        self,
        query: str,
        *,
        tenant_id: str,
        product_id: str,
        model: str | None = None,
        firmware_version: str | None = None,
        top_k: int = 6,
        variant: str = "hybrid",
    ) -> list[RetrievedChunk]:
        scoped_query = " ".join(
            item for item in (query, product_id, model or "", firmware_version or "") if item
        )
        if variant in {"lightrag", "openviking"}:
            raw = (
                query_lightrag(scoped_query, top_k=top_k)
                if variant == "lightrag"
                else query_openviking(scoped_query, top_k=top_k)
            )
            return [
                RetrievedChunk(
                    chunk_id=str(item["id"]),
                    document_id=str(item["id"]),
                    title=str(item["title"]),
                    section=str(item["section"]),
                    version=str(item["version"]),
                    text=str(item["text"]),
                    score=float(item["score"]),
                )
                for item in raw
            ]
        rows = cast(
            list[tuple[Chunk, Document]],
            self.session.execute(
                self._scope_query(tenant_id, product_id, model, firmware_version)
            ).all(),
        )
        if not rows:
            return []

        ranking_query = query
        query_tokens = tokenize(ranking_query)
        corpus_tokens = [tokenize(chunk.text) for chunk, _ in rows]
        keyword_scores = _bm25(query_tokens, corpus_tokens)
        query_vector: list[float] | None
        try:
            query_vector = self.embedder.embed(ranking_query)
            dense_scores = [
                cosine_similarity(query_vector, chunk.embedding or self.embedder.embed(chunk.text))
                for chunk, _ in rows
            ]
        except (OSError, RuntimeError, ValueError):
            query_vector = None
            dense_scores = [0.0 for _ in rows]
        keyword_ranking = sorted(range(len(rows)), key=lambda i: keyword_scores[i], reverse=True)[
            :20
        ]
        dense_ranking = sorted(range(len(rows)), key=lambda i: dense_scores[i], reverse=True)[:20]
        if (
            query_vector is not None
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            dense_query = self._scope_query(tenant_id, product_id, model, firmware_version)
            dense_query = (
                dense_query.order_by(None)
                .order_by(Chunk.embedding.op("<=>")(query_vector))
                .limit(20)
            )
            dense_rows = self.session.execute(dense_query).all()
            by_id = {chunk.id: index for index, (chunk, _) in enumerate(rows)}
            dense_ranking = [by_id[chunk.id] for chunk, _ in dense_rows if chunk.id in by_id]
        if variant == "dense":
            rankings = [dense_ranking] if query_vector is not None else []
        elif variant == "bm25":
            rankings = [keyword_ranking]
        else:
            rankings = [keyword_ranking]
            if query_vector is not None:
                rankings.append(dense_ranking)
        fused = reciprocal_rank_fusion(rankings)

        # Exact version matches receive a small deterministic boost; general documents remain eligible.
        for index, (chunk, _) in enumerate(rows):
            if firmware_version and chunk.firmware_version == firmware_version:
                fused[index] = fused.get(index, 0.0) + 0.02
            if model and chunk.model == model:
                fused[index] = fused.get(index, 0.0) + 0.01

        candidates = sorted(fused, key=lambda index: fused[index], reverse=True)[
            : max(top_k * 3, top_k)
        ]
        if (settings.cross_encoder_enabled or variant == "hybrid_rerank") and candidates:
            try:
                reranker = _get_cross_encoder()
                scores = reranker.predict([(query, rows[index][0].text) for index in candidates])
                for index, score in zip(candidates, scores, strict=True):
                    fused[index] = fused.get(index, 0.0) + float(score) * 0.05
                candidates.sort(key=lambda index: fused[index], reverse=True)
            except (ImportError, OSError, RuntimeError):
                pass
        selected: list[int] = []
        if query_vector is None:
            selected = candidates[:top_k]
            candidates = []
        while candidates and len(selected) < top_k:
            best = max(
                candidates,
                key=lambda index: (
                    fused[index]
                    - 0.15
                    * max(
                        [
                            cosine_similarity(
                                rows[index][0].embedding
                                or self.embedder.embed(rows[index][0].text),
                                rows[other][0].embedding
                                or self.embedder.embed(rows[other][0].text),
                            )
                            for other in selected
                        ]
                        or [0.0]
                    )
                ),
            )
            selected.append(best)
            candidates.remove(best)

        maximum = max((fused[index] for index in selected), default=1.0) or 1.0
        return [
            RetrievedChunk(
                chunk_id=rows[index][0].id,
                document_id=rows[index][1].id,
                title=rows[index][1].title,
                section=rows[index][0].section,
                version=rows[index][1].doc_version,
                text=rows[index][0].text,
                page=rows[index][0].page,
                score=round(fused[index] / maximum, 4),
            )
            for index in selected
        ]
