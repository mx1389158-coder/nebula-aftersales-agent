import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.core.database import get_db
from apps.api.app.core.security import require_admin
from apps.api.app.models import AuditLog, Document, Job
from apps.api.app.schemas import DocumentView, JobView, Principal, PublishDocumentRequest
from apps.api.app.services.documents import DocumentIngestor
from apps.api.app.services.jobs import enqueue_job

router = APIRouter()


@router.get("", response_model=list[DocumentView])
def list_documents(
    principal: Principal = Depends(require_admin), session: Session = Depends(get_db)
) -> list[Document]:
    return list(
        session.scalars(
            select(Document)
            .where(Document.tenant_id == principal.tenant_id)
            .order_by(Document.created_at.desc())
        )
    )


@router.post("", response_model=JobView, status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    product_id: str = Form(...),
    doc_version: str = Form(...),
    model: str | None = Form(default=None),
    firmware_version: str | None = Form(default=None),
    title: str | None = Form(default=None),
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> Job:
    content = await file.read(20 * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(status_code=422, detail="文档内容为空")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文档超过 20MB 限制")
    filename = file.filename or "upload.txt"
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".md", ".txt", ".html", ".htm"}:
        raise HTTPException(status_code=422, detail="仅支持 PDF、Markdown、TXT 和 HTML")
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(filename).name)
    job_dir = Path(settings.job_data_dir).resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    stored = job_dir / f"{uuid.uuid4()}-{safe_name}"
    stored.write_bytes(content)
    return enqueue_job(
        session,
        tenant_id=principal.tenant_id,
        kind="document_ingest",
        payload={
            "file_path": str(stored),
            "filename": filename,
            "product_id": product_id,
            "model": model,
            "firmware_version": firmware_version,
            "doc_version": doc_version,
            "title": title,
        },
    )


@router.post("/{document_id}/publish", response_model=DocumentView)
def publish_document(
    document_id: str,
    payload: PublishDocumentRequest,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> Document:
    document = session.scalar(
        select(Document).where(
            Document.id == document_id, Document.tenant_id == principal.tenant_id
        )
    )
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    if payload.active:
        try:
            DocumentIngestor(session).publish(document)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    else:
        document.status = "archived"
        session.commit()
        session.refresh(document)
    session.add(
        AuditLog(
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="document.publish" if payload.active else "document.archive",
            entity_type="document",
            entity_id=document.id,
        )
    )
    session.commit()
    return document


@router.post("/{document_id}/rollback/{doc_version}", response_model=DocumentView)
def rollback_document(
    document_id: str,
    doc_version: str,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> Document:
    current = session.scalar(
        select(Document).where(
            Document.id == document_id, Document.tenant_id == principal.tenant_id
        )
    )
    if not current:
        raise HTTPException(status_code=404, detail="文档不存在")
    target = session.scalar(
        select(Document).where(
            Document.tenant_id == principal.tenant_id,
            Document.product_id == current.product_id,
            Document.model == current.model,
            Document.firmware_version == current.firmware_version,
            Document.doc_version == doc_version,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="目标版本不存在")
    DocumentIngestor(session).publish(target)
    session.add(
        AuditLog(
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="document.rollback",
            entity_type="document",
            entity_id=target.id,
            detail={"from": current.doc_version, "to": target.doc_version},
        )
    )
    session.commit()
    return target
