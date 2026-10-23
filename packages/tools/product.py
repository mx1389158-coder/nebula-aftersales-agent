from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.models import Device
from packages.context.retrieval import HybridRetriever
from packages.tools.contracts import ToolEvidence, ToolResult


class ProductTools:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_product_profile(self, *, tenant_id: str, user_id: str, device_id: str) -> ToolResult:
        device = self.session.scalar(
            select(Device).where(
                Device.id == device_id,
                Device.tenant_id == tenant_id,
                Device.user_id == user_id,
            )
        )
        if not device:
            return ToolResult(status="not_found", message_for_model="设备不存在或不属于当前用户。")
        return ToolResult(
            status="success",
            data={
                "device_id": device.id,
                "product_id": device.product_id,
                "model": device.model,
                "firmware_version": device.firmware_version,
            },
            message_for_model="已读取用户设备的必要字段。",
            evidence=[ToolEvidence(type="db_record", id=device.id)],
        )

    def search_manual(
        self,
        *,
        tenant_id: str,
        query: str,
        product_id: str,
        model: str,
        firmware_version: str,
    ) -> ToolResult:
        evidence = HybridRetriever(self.session).search(
            query,
            tenant_id=tenant_id,
            product_id=product_id,
            model=model,
            firmware_version=firmware_version,
        )
        if not evidence:
            return ToolResult(
                status="not_found", message_for_model="没有匹配当前产品版本的已发布手册。"
            )
        return ToolResult(
            status="success",
            data={
                "items": [
                    {
                        "chunk_id": item.chunk_id,
                        "title": item.title,
                        "version": item.version,
                        "section": item.section,
                        "text": item.text,
                        "score": item.score,
                    }
                    for item in evidence
                ]
            },
            message_for_model="已返回版本过滤后的证据，不包含自由生成内容。",
            evidence=[ToolEvidence(type="document_chunk", id=item.chunk_id) for item in evidence],
        )
