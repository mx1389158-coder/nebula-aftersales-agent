from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Protocol

import httpx

from apps.api.app.core.config import settings
from packages.context.retrieval import RetrievedChunk


class LLMProvider(Protocol):
    def answer(self, question: str, evidence: list[RetrievedChunk], memories: list[str]) -> str: ...

    def stream(
        self, question: str, evidence: list[RetrievedChunk], memories: list[str]
    ) -> Iterator[str]: ...


class EvidenceTemplateProvider:
    def answer(self, question: str, evidence: list[RetrievedChunk], memories: list[str]) -> str:
        if not evidence:
            return "当前知识库中没有足够证据回答。请补充产品型号、固件版本或更具体的故障现象。"
        steps = []
        for item in evidence[:3]:
            excerpt = item.text.strip().replace("\n", " ")[:220]
            steps.append(f"- {excerpt}（{item.title} / {item.section} / {item.version}）")
        memory_note = f"\n\n已参考你的设备信息：{'；'.join(memories[:2])}" if memories else ""
        return (
            "根据当前版本的售后资料，建议按以下证据逐项排查：\n\n" + "\n".join(steps) + memory_note
        )

    def stream(
        self, question: str, evidence: list[RetrievedChunk], memories: list[str]
    ) -> Iterator[str]:
        answer = self.answer(question, evidence, memories)
        for offset in range(0, len(answer), 18):
            yield answer[offset : offset + 18]


class OllamaProvider:
    def _prompt(self, question: str, evidence: list[RetrievedChunk], memories: list[str]) -> str:
        context = "\n\n".join(
            f"[{index}] {item.title}/{item.section}/{item.version}\n{item.text}"
            for index, item in enumerate(evidence, start=1)
        )
        return (
            "你是星云智家售后服务助手。只能依据给定证据回答；证据不足时明确追问。"
            "不得编造政策、版本、原因和操作。回答使用中文分步骤，并用 [1] 形式引用。"
            "回答首句必须用‘根据当前版本资料，排查步骤如下：’开头。\n\n"
            f"用户记忆：{json.dumps(memories, ensure_ascii=False)}\n问题：{question}\n证据：\n{context}"
        )

    def answer(self, question: str, evidence: list[RetrievedChunk], memories: list[str]) -> str:
        for attempt in range(2):
            try:
                response = httpx.post(
                    f"{settings.ollama_base_url.rstrip('/')}/api/generate",
                    json={
                        "model": settings.ollama_model,
                        "prompt": self._prompt(question, evidence, memories),
                        "stream": False,
                        "options": {"temperature": 0, "num_predict": 256},
                    },
                    timeout=90,
                )
                response.raise_for_status()
                return str(response.json()["response"])
            except httpx.HTTPError:
                if attempt == 0:
                    continue
        return EvidenceTemplateProvider().answer(question, evidence, memories)

    def stream(
        self, question: str, evidence: list[RetrievedChunk], memories: list[str]
    ) -> Iterator[str]:
        try:
            with httpx.stream(
                "POST",
                f"{settings.ollama_base_url.rstrip('/')}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": self._prompt(question, evidence, memories),
                    "stream": True,
                    "options": {"temperature": 0, "num_predict": 256},
                },
                timeout=90,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        token = json.loads(line).get("response")
                        if token:
                            yield str(token)
        except httpx.HTTPError:
            yield from EvidenceTemplateProvider().stream(question, evidence, memories)


def get_provider() -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider()
    return EvidenceTemplateProvider()
