from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.models import AuditLog, Memory
from packages.context.embeddings import Embedder, cosine_similarity, get_embedder

SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{6}\b"),
    re.compile(r"\b\d{17}[0-9Xx]\b"),
    re.compile(r"(?:密码|验证码|password|otp)[:：]?\s*\S+", re.IGNORECASE),
]


def contains_sensitive_data(text: str) -> bool:
    return any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)


class GovernedMemoryStore:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.embedder: Embedder = get_embedder()

    def add(
        self,
        *,
        tenant_id: str,
        user_id: str,
        fact: str,
        kind: str = "fact",
        confidence: float = 1.0,
        consent: bool = True,
        source_message_id: str | None = None,
        valid_to: datetime | None = None,
    ) -> Memory:
        if contains_sensitive_data(fact):
            raise ValueError("检测到密码、验证码或完整身份证号，禁止写入长期记忆")
        if not consent:
            raise ValueError("未取得用户同意，不能写入长期记忆")
        normalized = fact.strip()
        existing = self.session.scalar(
            select(Memory).where(
                Memory.tenant_id == tenant_id,
                Memory.user_id == user_id,
                Memory.kind == kind,
                Memory.fact == normalized,
                Memory.status == "active",
            )
        )
        if existing:
            existing.confidence = max(existing.confidence, confidence)
            existing.valid_to = valid_to or existing.valid_to
            self.session.commit()
            self.session.refresh(existing)
            return existing
        memory = Memory(
            tenant_id=tenant_id,
            user_id=user_id,
            fact=normalized,
            kind=kind,
            confidence=confidence,
            consent=consent,
            source_message_id=source_message_id,
            valid_to=valid_to,
        )
        self.session.add(memory)
        self.session.commit()
        self.session.refresh(memory)
        return memory

    def update(
        self,
        memory: Memory,
        *,
        actor_id: str,
        changes: dict[str, object],
    ) -> Memory:
        new_fact = changes.get("fact")
        if isinstance(new_fact, str) and contains_sensitive_data(new_fact):
            raise ValueError("检测到密码、验证码或完整身份证号，禁止写入长期记忆")
        if changes.get("consent") is False and changes.get("status") in {None, "active"}:
            changes["status"] = "deleted"
        for key, value in changes.items():
            setattr(memory, key, value)
        self.session.add(
            AuditLog(
                tenant_id=memory.tenant_id,
                actor_id=actor_id,
                action="memory.update",
                entity_type="memory",
                entity_id=memory.id,
                detail={"fields": sorted(changes)},
            )
        )
        self.session.commit()
        self.session.refresh(memory)
        return memory

    def search(
        self,
        query: str,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 4,
        governed: bool = True,
    ) -> list[Memory]:
        now = datetime.now(UTC)
        rows = list(
            self.session.scalars(
                select(Memory).where(
                    Memory.tenant_id == tenant_id,
                    Memory.user_id == user_id,
                    Memory.status == "active",
                    Memory.consent.is_(True),
                )
            )
        )
        active = rows
        if governed:
            superseded = {item.supersedes_id for item in rows if item.supersedes_id}

            def still_valid(item: Memory) -> bool:
                if item.valid_to is None:
                    return True
                valid_to = item.valid_to
                if valid_to.tzinfo is None:
                    valid_to = valid_to.replace(tzinfo=UTC)
                return valid_to > now

            active = [item for item in rows if still_valid(item) and item.id not in superseded]
        query_vector = self.embedder.embed(query)
        query_identifiers = {
            token.lower() for token in re.findall(r"\b[A-Za-z]+[-_]?\d+\b", query)
        }

        def rank(item: Memory) -> tuple[bool, float]:
            item_identifiers = {
                token.lower() for token in re.findall(r"\b[A-Za-z]+[-_]?\d+\b", item.fact)
            }
            semantic_score = (
                cosine_similarity(query_vector, self.embedder.embed(item.fact)) * 0.7
                + item.confidence * 0.2
                + item.updated_at.timestamp() / 1e11
            )
            # Explicit device, firmware, ticket and memory identifiers are stronger
            # evidence than a merely similar preference sentence.
            return (bool(query_identifiers & item_identifiers), semantic_score)

        active.sort(
            key=rank,
            reverse=True,
        )
        return active[:limit]

    def recent(self, *, tenant_id: str, user_id: str, limit: int = 4) -> list[Memory]:
        return list(
            self.session.scalars(
                select(Memory)
                .where(
                    Memory.tenant_id == tenant_id,
                    Memory.user_id == user_id,
                    Memory.status == "active",
                    Memory.consent.is_(True),
                )
                .order_by(Memory.updated_at.desc())
                .limit(limit)
            )
        )
