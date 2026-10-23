from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from apps.api.app.core.config import PROJECT_ROOT, settings
from apps.api.app.core.database import SessionLocal, create_schema
from apps.api.app.models import Chunk
from packages.context.embeddings import embed_batch, get_embedder


def _sqlite_path() -> Path | None:
    prefix = "sqlite:///"
    if not settings.database_url.startswith(prefix):
        return None
    value = Path(settings.database_url.removeprefix(prefix))
    return value if value.is_absolute() else PROJECT_ROOT / value


def _backup_sqlite() -> Path | None:
    source = _sqlite_path()
    if source is None or not source.exists():
        return None
    backup_dir = PROJECT_ROOT / "artifacts" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"aftersales-before-bge-{stamp}.db"
    with sqlite3.connect(source) as source_connection, sqlite3.connect(target) as target_connection:
        source_connection.backup(target_connection)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild chunk and memory embeddings in place.")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")
    if settings.embedding_provider.lower() not in {"bge", "sentence-transformers"}:
        raise SystemExit("Set EMBEDDING_PROVIDER=bge before rebuilding embeddings")

    create_schema()
    backup = _backup_sqlite()
    if backup:
        print(f"backup={backup}")

    embedder = get_embedder()
    updated_chunks = 0
    with SessionLocal() as session:
        chunks = list(session.scalars(select(Chunk).order_by(Chunk.id)))
        try:
            for offset in range(0, len(chunks), args.batch_size):
                batch = chunks[offset : offset + args.batch_size]
                vectors = embed_batch(embedder, [row.text for row in batch])
                for row, vector in zip(batch, vectors, strict=True):
                    if len(vector) != embedder.dimensions:
                        raise ValueError(f"unexpected embedding dimensions: {len(vector)}")
                    row.embedding = vector
                    updated_chunks += 1
                session.flush()
                print(f"progress={min(offset + len(batch), len(chunks))}/{len(chunks)}")
            session.commit()
        except Exception:
            session.rollback()
            raise

    print(f"chunks={updated_chunks}")
    print(f"dimensions={embedder.dimensions}")


if __name__ == "__main__":
    main()
