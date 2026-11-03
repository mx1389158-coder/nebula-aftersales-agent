from __future__ import annotations

import uuid
from typing import Any

import httpx

from apps.api.app.core.config import settings
from packages.tools.contracts import ToolEvidence, ToolResult


class JavaBusinessClient:
    """Authenticated client for Java-owned business facts.

    GET requests may be retried by callers. Writes are sent once and rely on
    Java's database-backed Idempotency-Key contract for safe reconciliation.
    """

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.business_service_url).rstrip("/")
        self.timeout = timeout or settings.business_service_timeout_seconds

    def create_ticket(
        self,
        *,
        access_token: str,
        summary: str,
        contact: str,
        idempotency_key: str,
        device_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> ToolResult:
        payload: dict[str, Any] = {"summary": summary, "contact": contact}
        if device_id:
            payload["device_id"] = device_id
        result = self._request(
            "POST",
            "/api/business/v1/tickets",
            access_token=access_token,
            json=payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
            trace_id=trace_id,
        )
        if result.status == "success" and result.data.get("id"):
            result.data.setdefault("ticket_id", str(result.data["id"]))
        return result

    def get_ticket_status(
        self,
        *,
        access_token: str,
        ticket_id: str,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> ToolResult:
        return self._request(
            "GET",
            f"/api/business/v1/tickets/{ticket_id}",
            access_token=access_token,
            request_id=request_id,
            trace_id=trace_id,
        )

    def list_tickets(self, *, access_token: str, request_id: str | None = None) -> ToolResult:
        return self._request(
            "GET",
            "/api/business/v1/tickets",
            access_token=access_token,
            request_id=request_id,
        )

    def get_device_profile(
        self,
        *,
        access_token: str,
        device_id: str,
        request_id: str | None = None,
    ) -> ToolResult:
        return self._request(
            "GET",
            f"/api/business/v1/devices/{device_id}",
            access_token=access_token,
            request_id=request_id,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        access_token: str,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> ToolResult:
        if not self.base_url:
            return ToolResult(
                status="failed",
                error_code="BUSINESS_SERVICE_NOT_CONFIGURED",
                message_for_model="业务服务尚未配置。",
                retryable=False,
            )
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Request-ID": request_id or str(uuid.uuid4()),
            "X-Trace-ID": trace_id or request_id or str(uuid.uuid4()),
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                json=json,
                headers=headers,
                timeout=self.timeout,
            )
        except httpx.TimeoutException:
            return ToolResult(
                status="failed",
                error_code="BUSINESS_TIMEOUT",
                message_for_model="业务服务响应超时；写操作结果未知，请按幂等键核对后再重试。",
                retryable=method == "GET",
            )
        except httpx.HTTPError:
            return ToolResult(
                status="failed",
                error_code="BUSINESS_UNAVAILABLE",
                message_for_model="业务服务暂时不可用。",
                retryable=method == "GET",
            )

        body = self._json(response)
        if response.is_success:
            resource_id = str(body.get("id") or body.get("ticket_id") or "business-response")
            return ToolResult(
                status="success",
                data=body,
                message_for_model="Java 业务服务操作成功。",
                evidence=[ToolEvidence(type="business_api", id=resource_id)],
            )
        error_code = str(body.get("error_code") or f"BUSINESS_HTTP_{response.status_code}")
        message = str(body.get("message") or body.get("detail") or "业务服务拒绝了请求。")
        status = "not_found" if response.status_code == 404 else "failed"
        return ToolResult(
            status=status,
            data=body,
            error_code=error_code,
            message_for_model=message,
            retryable=response.status_code >= 500 and method == "GET",
        )

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            value = response.json()
            return value if isinstance(value, dict) else {"value": value}
        except ValueError:
            return {"message": response.text[:500]}
