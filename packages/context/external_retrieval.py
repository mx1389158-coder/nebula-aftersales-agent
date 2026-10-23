from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import httpx

from apps.api.app.core.config import settings


class ExternalRetrieverUnavailable(RuntimeError):
    """Raised when an explicitly selected experimental backend is unavailable."""


def _headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key} if api_key else {}


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    if isinstance(value, Mapping):
        for key in ("content", "text", "rendered", "excerpt", "summary"):
            if key in value:
                return _text(value[key])
    return ""


def _id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:24]}"


def query_lightrag(query: str, *, top_k: int) -> list[dict[str, Any]]:
    if not settings.lightrag_base_url:
        raise ExternalRetrieverUnavailable(
            "R4 需要配置 LIGHTRAG_BASE_URL；不会静默退化为本地混合检索"
        )
    response = httpx.post(
        f"{settings.lightrag_base_url.rstrip('/')}/query",
        headers=_headers(settings.lightrag_api_key),
        json={
            "query": query,
            "mode": "mix",
            "only_need_context": True,
            "include_references": True,
            "top_k": top_k,
        },
        timeout=settings.external_retrieval_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    references = payload.get("references") or []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(references[:top_k]):
        source = str(item.get("file_path") or item.get("reference_id") or f"reference-{index}")
        content = _text(item)
        if content:
            rows.append(
                {
                    "id": _id("lightrag", source),
                    "title": source,
                    "section": "LightRAG",
                    "version": "external",
                    "text": content,
                    "score": max(0.0, 1.0 - index / max(top_k, 1)),
                }
            )
    return rows


def query_openviking(query: str, *, top_k: int) -> list[dict[str, Any]]:
    if not settings.openviking_base_url:
        raise ExternalRetrieverUnavailable(
            "R5 需要配置 OPENVIKING_BASE_URL；不会静默退化为本地混合检索"
        )
    response = httpx.post(
        f"{settings.openviking_base_url.rstrip('/')}/api/v1/search/find",
        headers=_headers(settings.openviking_api_key),
        json={
            "query": query,
            "target_uri": settings.openviking_root_uri,
            "limit": top_k,
        },
        timeout=settings.external_retrieval_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json().get("result") or {}
    entries = payload.get("entries") or payload.get("resources") or []
    rendered = _text(payload.get("rendered"))
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(entries[:top_k]):
        uri = str(item.get("uri") or item.get("path") or f"entry-{index}")
        content = _text(item) or rendered
        if content:
            rows.append(
                {
                    "id": _id("openviking", uri),
                    "title": uri,
                    "section": "OpenViking",
                    "version": "external",
                    "text": content,
                    "score": float(item.get("score", max(0.0, 1.0 - index / max(top_k, 1)))),
                }
            )
    if not rows and rendered:
        rows.append(
            {
                "id": _id("openviking", rendered),
                "title": settings.openviking_root_uri,
                "section": "OpenViking",
                "version": "external",
                "text": rendered,
                "score": 1.0,
            }
        )
    return rows
