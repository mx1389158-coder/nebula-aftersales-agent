from __future__ import annotations

from typing import Any

import httpx


class Mem0HTTPAdapter:
    """Thin adapter for the self-hosted Mem0 server while local governance stays canonical."""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 30.0) -> None:
        if not base_url:
            raise ValueError("MEM0_BASE_URL 未配置")
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key} if api_key else {}
        self.timeout = timeout

    def add(self, fact: str, *, tenant_id: str, user_id: str, memory_id: str) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/memories",
            headers=self.headers,
            json={
                "messages": [{"role": "user", "content": fact}],
                "user_id": f"{tenant_id}:{user_id}",
                "metadata": {"tenant_id": tenant_id, "local_memory_id": memory_id},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return dict(response.json())

    def search(
        self, query: str, *, tenant_id: str, user_id: str, limit: int = 4
    ) -> list[dict[str, Any]]:
        response = httpx.post(
            f"{self.base_url}/search",
            headers=self.headers,
            json={
                "query": query,
                "filters": {"user_id": f"{tenant_id}:{user_id}"},
                "top_k": limit,
                "show_expired": False,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return list(payload.get("results", payload if isinstance(payload, list) else []))

    def update(self, external_id: str, fact: str, *, memory_id: str) -> dict[str, Any]:
        response = httpx.put(
            f"{self.base_url}/memories/{external_id}",
            headers=self.headers,
            json={"text": fact, "metadata": {"local_memory_id": memory_id}},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return dict(response.json())

    def delete(self, external_id: str) -> None:
        response = httpx.delete(
            f"{self.base_url}/memories/{external_id}",
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
