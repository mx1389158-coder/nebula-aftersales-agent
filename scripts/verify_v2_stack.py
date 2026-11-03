"""Black-box verification for the Java/Python/Nginx V2 stack."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

WEB_URL = os.getenv("VERIFY_WEB_URL", "http://127.0.0.1:15173").rstrip("/")
AI_URL = os.getenv("VERIFY_AI_URL", "http://127.0.0.1:18000").rstrip("/")
BUSINESS_URL = os.getenv("VERIFY_BUSINESS_URL", "http://127.0.0.1:18080").rstrip("/")


def request(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    token: str | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    outgoing = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        outgoing["Content-Type"] = "application/json; charset=utf-8"
    if token:
        outgoing["Authorization"] = f"Bearer {token}"
    call = urllib.request.Request(url, data=payload, headers=outgoing, method=method)
    try:
        with urllib.request.urlopen(call, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"{method} {url} returned {exc.code}: {detail[:500]}") from exc


def main() -> None:
    business_health = request("GET", f"{BUSINESS_URL}/api/business/v1/health")
    ai_health = request("GET", f"{AI_URL}/api/ai/v1/health")
    assert business_health["status"] == "ok"
    assert ai_health["status"] == "ok"

    login = request(
        "POST",
        f"{WEB_URL}/api/business/v1/auth/login",
        body={"username": "demo@example.com", "password": "demo-change-me"},
    )
    token = login["access_token"]
    devices = request("GET", f"{WEB_URL}/api/business/v1/devices", token=token)
    assert devices, "demo user must own at least one seeded device"
    device_id = str(devices[0]["id"])

    first = request(
        "POST",
        f"{WEB_URL}/api/ai/v1/chat",
        token=token,
        body={
            "message": "请为 X2 无法联网创建工单",
            "device_id": device_id,
            "contact": "demo@example.com",
        },
    )
    assert first["decision"] == "TOOL"
    assert first["tool_result"]["status"] == "need_confirm"
    assert first["pending_action"]["type"] == "create_ticket"

    resumed = request(
        "POST",
        f"{WEB_URL}/api/ai/v1/chat/{first['thread_id']}/resume",
        token=token,
        body={"confirmed": True},
    )
    assert resumed["tool_result"]["status"] == "success"
    ticket_id = str(resumed["tool_result"]["data"]["ticket_id"])
    assert ticket_id in resumed["answer"]

    tickets = request("GET", f"{WEB_URL}/api/business/v1/tickets", token=token)
    assert any(str(ticket["id"]) == ticket_id for ticket in tickets)

    pending = first["pending_action"]
    duplicate = request(
        "POST",
        f"{BUSINESS_URL}/api/business/v1/tickets",
        token=token,
        headers={"Idempotency-Key": pending["idempotency_key"]},
        body={
            "device_id": device_id,
            "summary": pending["summary"],
            "contact": pending["contact"],
        },
    )
    assert str(duplicate["id"]) == ticket_id
    assert duplicate["deduplicated"] is True

    print("V2_STACK_OK")
    print("health=business,ai; routing=nginx; auth=jwt; agent=confirm/resume")
    print("ownership=device; ticket=java-authoritative; idempotency=deduplicated")


if __name__ == "__main__":
    main()
