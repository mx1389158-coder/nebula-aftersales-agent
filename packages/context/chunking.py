from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    text: str
    section: str
    ordinal: int
    page: int | None = None


HEADING_PATTERN = re.compile(r"^(#{1,6}\s+.+|第[一二三四五六七八九十百0-9]+[章节部分].*)$")


def _split_oversized(text: str, size: int) -> list[str]:
    pieces: list[str] = []
    cursor = 0
    while cursor < len(text):
        end = min(cursor + size, len(text))
        if end < len(text):
            boundary = max(
                text.rfind("。", cursor, end),
                text.rfind("；", cursor, end),
                text.rfind("\n", cursor, end),
            )
            if boundary > cursor + size // 2:
                end = boundary + 1
        pieces.append(text[cursor:end].strip())
        cursor = end
    return [piece for piece in pieces if piece]


def recursive_chunks(
    text: str,
    *,
    target_size: int = 500,
    overlap: int = 80,
    page: int | None = None,
) -> list[TextChunk]:
    """Structure-aware Chinese chunker that avoids cutting numbered steps when possible."""
    if target_size < 100 or overlap < 0 or overlap >= target_size:
        raise ValueError("invalid chunk size or overlap")
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    section = "正文"
    blocks: list[tuple[str, str]] = []
    buffer: list[str] = []
    for line in lines:
        if HEADING_PATTERN.match(line):
            if buffer:
                blocks.append((section, "\n".join(buffer).strip()))
                buffer = []
            section = line.lstrip("# ").strip()
        elif line:
            buffer.append(line)
        elif buffer:
            blocks.append((section, "\n".join(buffer).strip()))
            buffer = []
    if buffer:
        blocks.append((section, "\n".join(buffer).strip()))
    output: list[TextChunk] = []
    carry = ""
    for block_section, block in blocks or [(section, text.strip())]:
        for piece in _split_oversized(block, target_size):
            combined = (carry + "\n" + piece).strip() if carry else piece
            output.append(TextChunk(combined, block_section, len(output), page))
            carry = combined[-overlap:] if overlap else ""
    return output
