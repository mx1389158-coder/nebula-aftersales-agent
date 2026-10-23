from packages.context.chunking import recursive_chunks


def test_chunker_preserves_heading_and_overlap() -> None:
    text = "# 无法联网\n" + "检查网线。" * 80 + "\n\n# 安全警告\n恢复出厂设置需要确认。"
    chunks = recursive_chunks(text, target_size=120, overlap=20)
    assert len(chunks) > 2
    assert chunks[0].section == "无法联网"
    assert chunks[-1].section == "安全警告"
    assert "确认" in chunks[-1].text
