import uuid

from fastapi.testclient import TestClient

from apps.api.app.main import app
from apps.worker.app.main import process_once


def test_demo_api_flow() -> None:
    ticket_key = f"api-smoke-{uuid.uuid4()}"
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200

        token_response = client.post("/api/v1/auth/demo-token")
        assert token_response.status_code == 200
        headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "demo@example.com", "password": "demo-change-me"},
        )
        assert login_response.status_code == 200

        chat = client.post(
            "/api/v1/chat",
            headers=headers,
            json={
                "message": "X2 固件 2.1.0 红灯常亮是什么意思？",
                "product_id": "router",
                "model": "X2",
                "firmware_version": "2.1.0",
            },
        )
        assert chat.status_code == 200
        assert chat.json()["decision"] == "ANSWER"
        assert chat.json()["citations"]

        memory = client.post(
            "/api/v1/memories",
            headers=headers,
            json={"kind": "preference", "fact": "我希望使用中文分步骤说明", "consent": True},
        )
        assert memory.status_code == 201

        confirmation = client.post(
            "/api/v1/tickets",
            headers=headers,
            json={
                "summary": "X2 无法取得 WAN 地址",
                "contact": "13800000000",
                "idempotency_key": ticket_key,
                "confirmed": False,
            },
        )
        assert confirmation.status_code == 409

        created = client.post(
            "/api/v1/tickets",
            headers=headers,
            json={
                "summary": "X2 无法取得 WAN 地址",
                "contact": "13800000000",
                "idempotency_key": ticket_key,
                "confirmed": True,
            },
        )
        assert created.status_code == 201
        assert created.json()["status"] == "success"

        eval_response = client.post(
            "/api/v1/evals/run",
            headers=headers,
            json={"dataset_version": "aftersales-smoke-v1", "retrieval_variant": "hybrid"},
        )
        assert eval_response.status_code == 202
        run_id = eval_response.json()["run_id"]
        assert process_once() is True

        runs = client.get("/api/v1/evals", headers=headers)
        assert runs.status_code == 200
        completed = next(item for item in runs.json() if item["id"] == run_id)
        assert completed["status"] == "completed"
        assert completed["metrics"]["total"] == 50
