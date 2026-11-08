from __future__ import annotations

import httpx
import pytest

from packages.tools.java_business import JavaBusinessClient


def test_create_ticket_forwards_user_identity_and_idempotency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        captured.update({"method": method, "url": url, **kwargs})
        return httpx.Response(
            201,
            json={"id": "ticket-1", "status": "CREATED", "deduplicated": False},
        )

    monkeypatch.setattr(httpx, "request", fake_request)
    result = JavaBusinessClient("http://business:8080").create_ticket(
        access_token="signed-user-token",
        summary="X2 无法联网",
        contact="13800000000",
        idempotency_key="stable-request-key",
        request_id="request-1",
    )

    assert result.status == "success"
    assert result.data["status"] == "CREATED"
    assert result.data["ticket_id"] == "ticket-1"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer signed-user-token"
    assert headers["Idempotency-Key"] == "stable-request-key"
    assert headers["X-Request-ID"] == "request-1"


def test_write_timeout_is_not_blindly_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(*args: object, **kwargs: object) -> httpx.Response:
        del args, kwargs
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(httpx, "request", timeout)
    result = JavaBusinessClient("http://business:8080").create_ticket(
        access_token="token",
        summary="X2 无法联网",
        contact="13800000000",
        idempotency_key="stable-request-key",
    )

    assert result.status == "failed"
    assert result.error_code == "BUSINESS_TIMEOUT"
    assert result.retryable is False


def test_get_timeout_can_be_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(*args: object, **kwargs: object) -> httpx.Response:
        del args, kwargs
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(httpx, "request", timeout)
    result = JavaBusinessClient("http://business:8080").get_ticket_status(
        access_token="token", ticket_id="ticket-1"
    )

    assert result.error_code == "BUSINESS_TIMEOUT"
    assert result.retryable is True


def test_write_timeout_reconciles_by_idempotency_key(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        del kwargs
        calls.append(f"{method} {url}")
        if method == "POST":
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(200, json={"id": "ticket-2", "status": "CREATED"})

    monkeypatch.setattr(httpx, "request", fake_request)
    result = JavaBusinessClient("http://business:8080").create_ticket(
        access_token="token",
        summary="X2 无法联网",
        contact="13800000000",
        idempotency_key="stable-request-key",
        agent_context={"thread_id": "thread-1", "request_id": "request-1"},
    )

    assert result.status == "success"
    assert result.data["ticket_id"] == "ticket-2"
    assert result.data["reconciled"] is True
    assert calls == [
        "POST http://business:8080/api/business/v1/tickets",
        "GET http://business:8080/api/business/v1/tickets/idempotency/stable-request-key",
    ]


@pytest.mark.parametrize(
    ("status_code", "expected_status", "error_code"),
    [
        (404, "not_found", "DEVICE_NOT_OWNED"),
        (500, "failed", "BUSINESS_HTTP_500"),
    ],
)
def test_create_ticket_preserves_java_failure_status(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected_status: str,
    error_code: str,
) -> None:
    def fake_request(*args: object, **kwargs: object) -> httpx.Response:
        del args, kwargs
        body = (
            {"error_code": "DEVICE_NOT_OWNED", "message": "设备不存在"}
            if status_code == 404
            else {"message": "内部错误"}
        )
        return httpx.Response(status_code, json=body)

    monkeypatch.setattr(httpx, "request", fake_request)
    result = JavaBusinessClient("http://business:8080").create_ticket(
        access_token="token",
        summary="X2 无法联网",
        contact="13800000000",
        idempotency_key="stable-request-key",
    )

    assert result.status == expected_status
    assert result.error_code == error_code
    assert "ticket_id" not in result.data
