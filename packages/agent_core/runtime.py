from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.core.observability import redact, telemetry
from apps.api.app.models import AgentCheckpoint, HumanHandoff, Skill, SkillVersion, User
from packages.agent_core.providers import LLMProvider, get_provider
from packages.context.memory import GovernedMemoryStore
from packages.context.retrieval import HybridRetriever, RetrievedChunk
from packages.tools.product import ProductTools
from packages.tools.tickets import TicketTools

HIGH_RISK_TERMS = ("冒烟", "起火", "漏电", "触电", "爆炸", "高压", "烧焦", "拆机")
TICKET_TERMS = ("创建工单", "提交工单", "售后工单", "报修", "联系售后", "转人工")
STATUS_TERMS = ("工单状态", "查询工单", "工单进度")
MEMORY_TERMS = ("请记住", "帮我记住", "以后记得", "我的偏好")
MEMORY_QUERY_TERMS = (
    "你记得",
    "还记得",
    "回忆我确认",
    "我的偏好是什么",
    "我常用的设备",
)
PROMPT_INJECTION_TERMS = (
    "忽略之前",
    "忽略以上",
    "系统提示词",
    "system prompt",
    "读取其他用户",
    "跨用户",
    "管理员密钥",
)


class AgentState(TypedDict, total=False):
    request_id: str
    tenant_id: str
    user_id: str
    thread_id: str
    message: str
    device_id: str | None
    product_id: str | None
    model: str | None
    firmware_version: str | None
    confirmed: bool
    contact: str | None
    idempotency_key: str | None
    decision: str
    evidence: list[RetrievedChunk]
    memories: list[str]
    skills: list[dict[str, Any]]
    answer: str
    trace: list[dict[str, Any]]
    tool_result: dict[str, Any]
    pending_action: dict[str, Any]
    handoff_id: str
    intent: str
    defer_answer: bool
    retrieval_variant: str
    memory_variant: str
    skill_variant: str
    evaluation_mode: bool


class AgentRuntime:
    def __init__(self, session: Session, provider: LLMProvider | None = None) -> None:
        self.session = session
        self.provider = provider or get_provider()
        self.retriever = HybridRetriever(session)
        self.memory = GovernedMemoryStore(session)
        self.product_tools = ProductTools(session)
        self.ticket_tools = TicketTools(session)
        self.graph = self._build_graph()

    def _record(self, state: AgentState, node: str, detail: dict[str, Any]) -> list[dict[str, Any]]:
        return [*state.get("trace", []), {"node": node, "detail": detail}]

    def _checkpoint(self, state: AgentState) -> AgentCheckpoint:
        checkpoint = self.session.scalar(
            select(AgentCheckpoint).where(
                AgentCheckpoint.tenant_id == state["tenant_id"],
                AgentCheckpoint.user_id == state["user_id"],
                AgentCheckpoint.thread_id == state["thread_id"],
            )
        )
        if not checkpoint:
            checkpoint = AgentCheckpoint(
                tenant_id=state["tenant_id"],
                user_id=state["user_id"],
                thread_id=state["thread_id"],
            )
            self.session.add(checkpoint)
            self.session.flush()
        return checkpoint

    def _active_skills(self, state: AgentState) -> list[dict[str, Any]]:
        skill_variant = state.get("skill_variant", "reviewed")
        if skill_variant == "none":
            return []
        rows = self.session.execute(
            select(Skill, SkillVersion)
            .join(
                SkillVersion,
                (SkillVersion.skill_id == Skill.id)
                & (SkillVersion.version == Skill.active_version),
            )
            .where(Skill.tenant_id == state["tenant_id"], Skill.status == "active")
        ).all()
        applicable: list[dict[str, Any]] = []
        for skill, version in rows:
            scope = skill.scope or {}
            if skill_variant in {"manual", "extracted"} and scope.get("origin") != skill_variant:
                continue
            if scope.get("product_id") not in {None, state.get("product_id")}:
                continue
            bucket = int(hashlib.sha256(state["user_id"].encode()).hexdigest()[:8], 16) % 100
            if bucket >= skill.rollout_percent:
                continue
            applicable.append(
                {"name": skill.name, "version": version.version, "steps": version.steps}
            )
        return applicable

    def _load_context(self, state: AgentState) -> dict[str, Any]:
        message = state["message"]
        model = state.get("model")
        firmware = state.get("firmware_version")
        product_id = state.get("product_id")
        if state.get("device_id"):
            profile = self.product_tools.get_product_profile(
                tenant_id=state["tenant_id"],
                user_id=state["user_id"],
                device_id=str(state["device_id"]),
            )
            if profile.status == "success":
                product_id = str(profile.data["product_id"])
                model = str(profile.data["model"])
                firmware = str(profile.data["firmware_version"])
        if not model:
            match = re.search(r"\b([A-Z][A-Z0-9-]{1,12}\d)\b", message, re.IGNORECASE)
            model = match.group(1).upper() if match else None
        if not firmware:
            match = re.search(
                r"(?:固件|版本|firmware)\s*[vV]?([0-9]+(?:\.[0-9]+){1,3})",
                message,
                re.IGNORECASE,
            )
            firmware = match.group(1) if match else None
        memory_variant = state.get("memory_variant", "M3")
        if memory_variant == "M0":
            memory_rows = []
        elif memory_variant == "M1":
            memory_rows = self.memory.recent(tenant_id=state["tenant_id"], user_id=state["user_id"])
        else:
            memory_rows = self.memory.search(
                message,
                tenant_id=state["tenant_id"],
                user_id=state["user_id"],
                governed=memory_variant == "M3",
            )
        memories = [item.fact for item in memory_rows]
        provisional: AgentState = {**state, "product_id": product_id, "model": model}
        skills = self._active_skills(provisional)
        pending = (
            {} if state.get("evaluation_mode") else (self._checkpoint(state).pending_action or {})
        )
        lowered = message.lower()
        if state.get("confirmed") and pending:
            intent = str(pending.get("type", "normal"))
        elif any(term in lowered for term in PROMPT_INJECTION_TERMS):
            intent = "security_refuse"
        elif any(term in lowered for term in HIGH_RISK_TERMS):
            intent = "handoff"
        elif any(term in lowered for term in STATUS_TERMS):
            intent = "ticket_status"
        elif any(term in lowered for term in TICKET_TERMS):
            intent = "create_ticket"
        elif any(term in lowered for term in MEMORY_QUERY_TERMS):
            intent = "memory_answer"
        elif any(term in lowered for term in MEMORY_TERMS):
            intent = "save_memory"
        else:
            user = self.session.get(User, state["user_id"])
            auto_fact = message.startswith(("我使用", "我的设备", "我偏好", "以后请"))
            intent = "save_memory" if user and user.auto_memory_enabled and auto_fact else "normal"
        return {
            "product_id": product_id,
            "model": model,
            "firmware_version": firmware,
            "memories": memories,
            "skills": skills,
            "pending_action": pending,
            "intent": intent,
            "trace": self._record(
                state,
                "load_context",
                {"memory_count": len(memories), "skill_count": len(skills), "intent": intent},
            ),
        }

    def _route_intent(self, state: AgentState) -> str:
        intent = state.get("intent", "normal")
        if intent == "normal":
            return self._route_context(state)
        return intent

    def _route_context(self, state: AgentState) -> str:
        if (
            not state.get("product_id")
            or not state.get("model")
            or not state.get("firmware_version")
        ):
            return "ask"
        return "retrieve"

    def _ask_context(self, state: AgentState) -> dict[str, Any]:
        missing = [
            label
            for field, label in (
                ("product_id", "产品类型"),
                ("model", "设备型号"),
                ("firmware_version", "固件版本"),
            )
            if not state.get(field)
        ]
        return {
            "decision": "ASK",
            "answer": f"为了避免引用错误版本的排查步骤，请补充：{'、'.join(missing)}。",
            "trace": self._record(state, "ask_context", {"missing": missing}),
        }

    def _retrieve(self, state: AgentState) -> dict[str, Any]:
        if state.get("retrieval_variant") == "no_retrieval":
            return {
                "evidence": [],
                "trace": self._record(state, "retrieve", {"variant": "no_retrieval"}),
            }
        with telemetry.observe(
            "rag.retrieve",
            input={"query": state["message"], "product_id": state.get("product_id")},
            metadata={"model": state.get("model"), "firmware": state.get("firmware_version")},
        ) as observation:
            evidence = self.retriever.search(
                state["message"],
                tenant_id=state["tenant_id"],
                product_id=str(state["product_id"]),
                model=state.get("model"),
                firmware_version=state.get("firmware_version"),
                top_k=settings.retrieval_top_k,
                variant=state.get("retrieval_variant", "hybrid"),
            )
            if observation:
                observation.update(
                    output={"chunk_ids": [item.chunk_id for item in evidence]},
                    metadata={"result_count": len(evidence)},
                )
        coverage = sum(item.score for item in evidence[:3]) / max(min(len(evidence), 3), 1)
        return {
            "evidence": evidence,
            "trace": self._record(
                state,
                "retrieve",
                {"evidence_count": len(evidence), "coverage": round(coverage, 4)},
            ),
        }

    def _route_evidence(self, state: AgentState) -> str:
        if state.get("retrieval_variant") == "no_retrieval":
            return "answer"
        evidence = state.get("evidence", [])
        if not evidence:
            return "refuse"
        coverage = sum(item.score for item in evidence[:3]) / min(len(evidence), 3)
        return "answer" if coverage >= settings.evidence_threshold else "refuse"

    def _refuse(self, state: AgentState) -> dict[str, Any]:
        return {
            "decision": "REFUSE",
            "answer": "当前已发布知识中没有与你的产品版本匹配且覆盖度足够的证据。为了安全起见我不会猜测，请上传对应手册或转人工处理。",
            "trace": self._record(state, "refuse", {"reason": "insufficient_evidence"}),
        }

    def _security_refuse(self, state: AgentState) -> dict[str, Any]:
        return {
            "decision": "REFUSE",
            "answer": "该请求试图绕过权限或读取受保护信息，我不能执行。请提出与本人设备售后相关的问题。",
            "trace": self._record(state, "security_refuse", {"reason": "prompt_injection"}),
        }

    def _memory_answer(self, state: AgentState) -> dict[str, Any]:
        memories = state.get("memories", [])
        if not memories:
            return {
                "decision": "ASK",
                "answer": "我没有找到经你确认且仍有效的相关记忆，请重新提供。",
                "trace": self._record(state, "memory_answer", {"memory_count": 0}),
            }
        return {
            "decision": "ANSWER",
            "answer": "根据你已确认的记忆：" + "；".join(memories[:3]),
            "trace": self._record(state, "memory_answer", {"memory_count": len(memories)}),
        }

    def _answer(self, state: AgentState) -> dict[str, Any]:
        evidence = state.get("evidence", [])
        skill_steps = [
            str(step) for skill in state.get("skills", []) for step in skill.get("steps", [])
        ]
        context = [*state.get("memories", []), *skill_steps[:3]]
        with telemetry.observe(
            "llm.answer",
            as_type="generation",
            input={"question": state["message"], "evidence": [item.chunk_id for item in evidence]},
            model=settings.ollama_model if settings.llm_provider == "ollama" else "template-v1",
            metadata={"prompt_version": "answer-v2"},
        ) as observation:
            answer = (
                ""
                if state.get("defer_answer")
                else self.provider.answer(state["message"], evidence, context)
            )
            if observation:
                observation.update(output=redact(answer))
        return {
            "decision": "ANSWER",
            "answer": answer,
            "trace": self._record(state, "answer", {"provider": type(self.provider).__name__}),
        }

    def _create_ticket(self, state: AgentState) -> dict[str, Any]:
        if state.get("evaluation_mode"):
            if not state.get("contact"):
                return {"decision": "ASK", "answer": "创建工单前，请提供联系方式。"}
            return {
                "decision": "TOOL",
                "answer": "即将创建售后工单，请确认后再提交。",
                "pending_action": {"type": "create_ticket", "summary": state["message"]},
                "tool_result": {"status": "need_confirm"},
            }
        checkpoint = self._checkpoint(state)
        pending = checkpoint.pending_action or {}
        contact = state.get("contact") or pending.get("contact")
        summary = str(pending.get("summary") or state["message"])
        if not contact:
            return {
                "decision": "ASK",
                "answer": "创建工单前，请提供可联系的手机号或邮箱。",
                "trace": self._record(state, "ticket", {"reason": "missing_contact"}),
            }
        key = state.get("idempotency_key") or pending.get("idempotency_key")
        if not key:
            raw = f"{state['tenant_id']}:{state['user_id']}:{state['thread_id']}:{summary}"
            key = hashlib.sha256(raw.encode()).hexdigest()[:32]
        result = self.ticket_tools.create_ticket(
            tenant_id=state["tenant_id"],
            user_id=state["user_id"],
            summary=summary,
            contact=str(contact),
            idempotency_key=str(key),
            confirmed=bool(state.get("confirmed")),
            device_id=state.get("device_id"),
        )
        if result.status == "need_confirm":
            action = {
                "type": "create_ticket",
                "summary": summary,
                "contact": contact,
                "idempotency_key": key,
                "device_id": state.get("device_id"),
            }
            checkpoint.pending_action = action
            checkpoint.state = {"last_request_id": state["request_id"]}
            self.session.commit()
            return {
                "decision": "TOOL",
                "answer": f"即将创建售后工单：{summary}；联系方式：{contact}。请确认后再提交。",
                "pending_action": action,
                "tool_result": result.model_dump(),
                "trace": self._record(state, "ticket_interrupt", {"confirmation": "required"}),
            }
        checkpoint.pending_action = {}
        checkpoint.state = {"last_request_id": state["request_id"]}
        self.session.commit()
        return {
            "decision": "TOOL",
            "answer": f"工单已创建，编号：{result.data.get('ticket_id')}。",
            "pending_action": {},
            "tool_result": result.model_dump(),
            "trace": self._record(state, "ticket_created", result.data),
        }

    def _ticket_status(self, state: AgentState) -> dict[str, Any]:
        match = re.search(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            state["message"],
            re.IGNORECASE,
        )
        if not match:
            return {"decision": "ASK", "answer": "请提供要查询的工单编号。"}
        result = self.ticket_tools.get_ticket_status(
            tenant_id=state["tenant_id"], user_id=state["user_id"], ticket_id=match.group(0)
        )
        return {
            "decision": "TOOL",
            "answer": result.message_for_model,
            "tool_result": result.model_dump(),
            "trace": self._record(state, "ticket_status", {"status": result.status}),
        }

    def _save_memory(self, state: AgentState) -> dict[str, Any]:
        if state.get("evaluation_mode"):
            return {"decision": "TOOL", "answer": "请确认是否将该信息保存为长期记忆。"}
        checkpoint = self._checkpoint(state)
        pending = checkpoint.pending_action or {}
        fact = str(pending.get("fact") or state["message"])
        if not state.get("confirmed"):
            action = {"type": "save_memory", "fact": fact}
            checkpoint.pending_action = action
            self.session.commit()
            return {
                "decision": "TOOL",
                "answer": f"即将保存长期记忆：{fact}。请确认；你之后可在记忆中心编辑或删除。",
                "pending_action": action,
                "tool_result": {"status": "need_confirm"},
                "trace": self._record(state, "memory_interrupt", {"confirmation": "required"}),
            }
        try:
            memory = self.memory.add(
                tenant_id=state["tenant_id"],
                user_id=state["user_id"],
                fact=fact,
                kind="preference" if "偏好" in fact else "fact",
                consent=True,
            )
        except ValueError as exc:
            return {
                "decision": "REFUSE",
                "answer": str(exc),
                "tool_result": {"status": "failed", "error": str(exc)},
            }
        checkpoint.pending_action = {}
        self.session.commit()
        return {
            "decision": "TOOL",
            "answer": "已保存。你可以在记忆中心随时编辑、停用或删除。",
            "pending_action": {},
            "tool_result": {"status": "success", "memory_id": memory.id},
            "trace": self._record(state, "memory_saved", {"memory_id": memory.id}),
        }

    def _handoff(self, state: AgentState) -> dict[str, Any]:
        if state.get("evaluation_mode"):
            return {
                "decision": "ESCALATE",
                "answer": "检测到潜在安全风险。请立即断电、远离设备，不要自行拆机；已为你转接人工支持。",
                "handoff_id": "evaluation-handoff",
                "trace": self._record(state, "human_handoff", {"evaluation_mode": True}),
            }
        handoff = HumanHandoff(
            tenant_id=state["tenant_id"],
            user_id=state["user_id"],
            thread_id=state["thread_id"],
            reason="检测到人身或设备安全风险",
            context={"message": state["message"], "device_id": state.get("device_id")},
        )
        self.session.add(handoff)
        self.session.commit()
        return {
            "decision": "ESCALATE",
            "answer": "检测到潜在安全风险。请立即断电、远离设备，不要自行拆机；已为你转接人工支持。",
            "handoff_id": handoff.id,
            "trace": self._record(state, "human_handoff", {"handoff_id": handoff.id}),
        }

    def _build_graph(self) -> Any:
        builder = StateGraph(AgentState)
        nodes = {
            "load_context": self._load_context,
            "ask_context": self._ask_context,
            "retrieve": self._retrieve,
            "refuse": self._refuse,
            "answer": self._answer,
            "create_ticket": self._create_ticket,
            "ticket_status": self._ticket_status,
            "handoff": self._handoff,
            "save_memory": self._save_memory,
            "memory_answer": self._memory_answer,
            "security_refuse": self._security_refuse,
        }
        for name, node in nodes.items():
            builder.add_node(name, node)
        builder.add_edge(START, "load_context")
        builder.add_conditional_edges(
            "load_context",
            self._route_intent,
            {
                "ask": "ask_context",
                "retrieve": "retrieve",
                "create_ticket": "create_ticket",
                "ticket_status": "ticket_status",
                "handoff": "handoff",
                "save_memory": "save_memory",
                "memory_answer": "memory_answer",
                "security_refuse": "security_refuse",
            },
        )
        builder.add_edge("ask_context", END)
        builder.add_conditional_edges(
            "retrieve", self._route_evidence, {"refuse": "refuse", "answer": "answer"}
        )
        for terminal in (
            "refuse",
            "answer",
            "create_ticket",
            "ticket_status",
            "handoff",
            "save_memory",
            "memory_answer",
            "security_refuse",
        ):
            builder.add_edge(terminal, END)
        return builder.compile()

    def invoke(self, payload: dict[str, Any]) -> AgentState:
        initial: AgentState = {
            "request_id": payload.get("request_id") or str(uuid.uuid4()),
            "thread_id": payload.get("thread_id") or str(uuid.uuid4()),
            "tenant_id": payload["tenant_id"],
            "user_id": payload["user_id"],
            "message": payload["message"],
            "device_id": payload.get("device_id"),
            "product_id": payload.get("product_id"),
            "model": payload.get("model"),
            "firmware_version": payload.get("firmware_version"),
            "confirmed": bool(payload.get("confirmed")),
            "contact": payload.get("contact"),
            "idempotency_key": payload.get("idempotency_key"),
            "defer_answer": bool(payload.get("_defer_answer")),
            "retrieval_variant": str(payload.get("retrieval_variant", "hybrid")),
            "memory_variant": str(payload.get("memory_variant", "M3")),
            "skill_variant": str(payload.get("skill_variant", "reviewed")),
            "evaluation_mode": bool(payload.get("evaluation_mode")),
            "trace": [],
        }
        with telemetry.observe(
            "aftersales.agent",
            input={"message": initial["message"]},
            metadata={
                "request_id": initial["request_id"],
                "tenant_id": initial["tenant_id"],
                "user_id": initial["user_id"],
                "session_id": initial["thread_id"],
            },
        ) as observation:
            result = self.graph.invoke(initial)
            if observation:
                observation.update(
                    output=redact(
                        {"decision": result.get("decision"), "answer": result.get("answer")}
                    )
                )
            return result
