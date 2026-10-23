import httpx
import pytest

from packages.agent_core.providers import OllamaProvider
from packages.context.retrieval import RetrievedChunk


def test_ollama_prompt_requires_explicit_troubleshooting_language() -> None:
    evidence = [
        RetrievedChunk(
            chunk_id="chunk-1",
            document_id="document-1",
            title="X2 服务手册",
            section="网络",
            version="2.1.0",
            text="检查 WAN 地址。",
            score=1.0,
        )
    ]

    prompt = OllamaProvider()._prompt("无法联网怎么办？", evidence, [])

    assert "根据当前版本资料，排查步骤如下：" in prompt
    assert "不得编造政策、版本、原因和操作" in prompt


def test_ollama_failure_retries_then_uses_evidence_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fail(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "post", fail)
    evidence = [
        RetrievedChunk(
            chunk_id="chunk-1",
            document_id="document-1",
            title="X2 服务手册",
            section="网络",
            version="2.1.0",
            text="检查 WAN 地址。",
            score=1.0,
        )
    ]
    answer = OllamaProvider().answer("无法联网怎么办？", evidence, [])
    assert calls == 2
    assert "WAN" in answer
