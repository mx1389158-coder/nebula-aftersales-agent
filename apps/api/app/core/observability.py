from __future__ import annotations

import importlib
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from apps.api.app.core.config import settings

SENSITIVE = re.compile(r"\b1\d{10}\b|\b\d{17}[0-9Xx]\b|(?:密码|验证码)[:：]?\s*\S+")


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return SENSITIVE.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class Telemetry:
    def __init__(self) -> None:
        self.client: Any = None
        if not settings.langfuse_enabled:
            return
        try:
            module = importlib.import_module("langfuse")
            self.client = module.Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_host,
            )
        except Exception:
            self.client = None

    @contextmanager
    def observe(
        self,
        name: str,
        *,
        as_type: str = "span",
        input: Any = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[Any]:
        if not self.client:
            yield None
            return
        kwargs: dict[str, Any] = {
            "as_type": as_type,
            "name": name,
            "input": redact(input),
            "metadata": redact(metadata or {}),
        }
        if model:
            kwargs["model"] = model
        with self.client.start_as_current_observation(**kwargs) as observation:
            yield observation


telemetry = Telemetry()
