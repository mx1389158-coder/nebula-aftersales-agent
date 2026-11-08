from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_service_credential_is_blank_by_default_and_required_in_production() -> None:
    base_compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    prod_compose = (PROJECT_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    assert "BUSINESS_SERVICE_CREDENTIAL: ${BUSINESS_SERVICE_CREDENTIAL:-}" in base_compose
    assert "local-ai-service-credential-change-me" not in base_compose
    assert (
        "BUSINESS_SERVICE_CREDENTIAL: "
        "${BUSINESS_SERVICE_CREDENTIAL:?BUSINESS_SERVICE_CREDENTIAL is required}"
    ) in prod_compose
    assert "BUSINESS_SERVICE_CREDENTIAL=\n" in env_example
    assert "BUSINESS_SERVICE_TOKEN" not in env_example
