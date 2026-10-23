from __future__ import annotations

import hashlib
import io
import re
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import update
from sqlalchemy.orm import Session

from apps.api.app.models import Chunk, Document
from packages.context.chunking import recursive_chunks
from packages.context.embeddings import Embedder, get_embedder

MALICIOUS_DOCUMENT = re.compile(
    r"(?:忽略(?:之前|以上).{0,20}(?:指令|要求)|system\s+prompt|读取其他用户|api[_ -]?key)",
    re.IGNORECASE,
)


def _plain_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "\n", value)).strip()


class DocumentIngestor:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.embedder: Embedder = get_embedder()

    def _pages(self, filename: str, content: bytes) -> list[tuple[int | None, str]]:
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            reader = PdfReader(io.BytesIO(content))
            return [
                (index + 1, page.extract_text() or "") for index, page in enumerate(reader.pages)
            ]
        decoded = content.decode("utf-8", errors="replace")
        if suffix in {".html", ".htm"}:
            decoded = _plain_html(decoded)
        return [(None, decoded)]

    def ingest(
        self,
        *,
        tenant_id: str,
        filename: str,
        content: bytes,
        product_id: str,
        model: str | None,
        firmware_version: str | None,
        doc_version: str,
        title: str | None = None,
    ) -> Document:
        if not content:
            raise ValueError("文档内容为空")
        if len(content) > 20 * 1024 * 1024:
            raise ValueError("文档超过 20MB 限制")
        if Path(filename).suffix.lower() not in {".pdf", ".md", ".txt", ".html", ".htm"}:
            raise ValueError("仅支持 PDF、Markdown、TXT 和 HTML")
        preview = content.decode("utf-8", errors="ignore")
        if MALICIOUS_DOCUMENT.search(preview):
            raise ValueError("文档包含疑似提示注入或越权指令，已拒绝入库")
        digest = hashlib.sha256(content).hexdigest()
        document = Document(
            tenant_id=tenant_id,
            product_id=product_id,
            model=model,
            firmware_version=firmware_version,
            title=title or Path(filename).stem,
            source=filename,
            doc_version=doc_version,
            content_hash=digest,
            status="draft",
            effective_at=datetime.now(UTC),
        )
        self.session.add(document)
        self.session.flush()
        ordinal = 0
        for page, text in self._pages(filename, content):
            for item in recursive_chunks(text, page=page):
                document.chunks.append(
                    Chunk(
                        tenant_id=tenant_id,
                        product_id=product_id,
                        model=model,
                        firmware_version=firmware_version,
                        section=item.section,
                        page=page,
                        ordinal=ordinal,
                        text=item.text,
                        embedding=self.embedder.embed(item.text),
                    )
                )
                ordinal += 1
        if not ordinal:
            raise ValueError("文档没有可索引文本")
        self.session.commit()
        self.session.refresh(document)
        return document

    def publish(self, document: Document) -> Document:
        if not document.chunks:
            raise ValueError("文档没有可发布的索引分块")
        if any(not chunk.embedding or not chunk.text.strip() for chunk in document.chunks):
            raise ValueError("文档索引不完整，不能发布")
        self.session.execute(
            update(Document)
            .where(
                Document.tenant_id == document.tenant_id,
                Document.product_id == document.product_id,
                Document.model == document.model,
                Document.firmware_version == document.firmware_version,
                Document.doc_version != document.doc_version,
                Document.status == "active",
            )
            .values(status="archived")
        )
        document.status = "active"
        self.session.commit()
        self.session.refresh(document)
        return document
