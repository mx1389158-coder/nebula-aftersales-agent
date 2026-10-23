from __future__ import annotations

import json
import re
from typing import Any

ALLOWED_TOOLS = {"get_product_profile", "search_manual", "get_ticket_status", "create_ticket"}
FORBIDDEN = re.compile(r"(?:忽略.+指令|system prompt|api[_ -]?key|password|执行任意|shell)", re.I)


def validate_skill(
    steps: list[dict[str, Any]], tests: list[dict[str, Any]], constraints: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    max_steps = int(constraints.get("max_steps", 12))
    if not steps or len(steps) > max_steps:
        errors.append(f"步骤数必须在 1 到 {max_steps} 之间")
    for index, step in enumerate(steps, start=1):
        tool = step.get("tool")
        if tool and tool not in ALLOWED_TOOLS:
            errors.append(f"第 {index} 步使用了未授权工具：{tool}")
        if FORBIDDEN.search(json.dumps(step, ensure_ascii=False)):
            errors.append(f"第 {index} 步包含不安全内容")
    if not tests:
        errors.append("至少需要一个回归测试")
    passed = 0
    for index, test in enumerate(tests, start=1):
        if not test.get("input") or not test.get("expected_decision"):
            errors.append(f"第 {index} 个测试缺少 input 或 expected_decision")
        else:
            passed += 1
    return {
        "passed": not errors,
        "static_checks": {"errors": errors, "allowed_tools": sorted(ALLOWED_TOOLS)},
        "regression": {"total": len(tests), "schema_passed": passed},
    }
