from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from apps.api.app.services.documents import DocumentIngestor
from packages.context.retrieval import HybridRetriever


def test_future_document_is_not_retrievable(session: Session) -> None:
    service = DocumentIngestor(session)
    document = service.ingest(
        tenant_id="tenant-1",
        filename="future.md",
        content="# 排查\n检查设备电源与网络连接。".encode(),
        product_id="router",
        model="X9",
        firmware_version="9.0.0",
        doc_version="future-v1",
    )
    document.effective_at = datetime.now(UTC) + timedelta(days=1)
    service.publish(document)
    result = HybridRetriever(session).search(
        "如何检查网络",
        tenant_id="tenant-1",
        product_id="router",
        model="X9",
        firmware_version="9.0.0",
    )
    assert result == []
