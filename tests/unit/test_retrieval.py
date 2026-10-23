from sqlalchemy.orm import Session

from apps.api.app.services.documents import DocumentIngestor
from packages.context.retrieval import HybridRetriever


class BrokenEmbedder:
    dimensions = 256

    def embed(self, text: str) -> list[float]:
        del text
        raise RuntimeError("embedding service unavailable")


def _add_document(session: Session, version: str, content: str) -> None:
    service = DocumentIngestor(session)
    document = service.ingest(
        tenant_id="tenant-1",
        filename=f"x2-{version}.md",
        content=content.encode(),
        product_id="router",
        model="X2",
        firmware_version=version,
        doc_version=f"doc-{version}",
    )
    service.publish(document)


def test_retrieval_never_crosses_firmware_version(session: Session) -> None:
    _add_document(session, "1.0.0", "# 拨号\n旧版本需要重新输入拨号密码。")
    _add_document(session, "2.0.0", "# 网络状态\n新版本需要检查 WAN 地址。")
    results = HybridRetriever(session).search(
        "无法联网怎么排查",
        tenant_id="tenant-1",
        product_id="router",
        model="X2",
        firmware_version="2.0.0",
    )
    assert results
    assert all(item.version == "doc-2.0.0" for item in results)
    assert "WAN" in results[0].text


def test_retrieval_is_tenant_scoped(session: Session) -> None:
    _add_document(session, "2.0.0", "# 网络状态\n检查 WAN 地址。")
    assert (
        HybridRetriever(session).search(
            "WAN",
            tenant_id="another-tenant",
            product_id="router",
            model="X2",
            firmware_version="2.0.0",
        )
        == []
    )


def test_hybrid_retrieval_falls_back_to_bm25_when_embedding_is_unavailable(
    session: Session,
) -> None:
    _add_document(session, "2.0.0", "# 网络状态\n检查 WAN 地址。")
    results = HybridRetriever(session, embedder=BrokenEmbedder()).search(
        "WAN",
        tenant_id="tenant-1",
        product_id="router",
        model="X2",
        firmware_version="2.0.0",
    )
    assert results
    assert "WAN" in results[0].text
