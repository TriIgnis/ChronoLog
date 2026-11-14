"""parser 模块单元测试：解析、渲染、行级替换与删除。"""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

import pytest

from chronolog.core.models import LogEntry, auto_title
from chronolog.core.parser import (
    EntryNotFoundError,
    append_entry_text,
    parse_date_from_filename,
    parse_day,
    remove_entry_text,
    render_day,
    render_entry_block,
    replace_entry_text,
)

TZ = timezone(timedelta(hours=8))


def make_entry(title: str, body: str = "", hour: int = 9, minute: int = 30, second: int = 0) -> LogEntry:
    return LogEntry.new(
        datetime(2026, 11, 14, hour, minute, second, tzinfo=TZ), title=title, body=body
    )


def test_round_trip_single_entry():
    d = date(2026, 11, 14)
    entry = make_entry("开始阅读论文", "阅读无人机视觉导航综述。")
    text = render_day(d, [entry])
    parsed = parse_day(text)
    assert len(parsed) == 1
    assert parsed[0].uuid == entry.uuid
    assert parsed[0].title == "开始阅读论文"
    assert parsed[0].body == "阅读无人机视觉导航综述。"
    assert parsed[0].timestamp.isoformat() == entry.timestamp.isoformat()


def test_round_trip_multiple_entries_and_order():
    d = date(2026, 11, 14)
    entries = [
        make_entry("一", "第一条", hour=9),
        make_entry("二", "第二条", hour=14),
        make_entry("三", "第三条", hour=16),
    ]
    text = render_day(d, entries)
    parsed = parse_day(text)
    assert [e.title for e in parsed] == ["一", "二", "三"]
    assert [e.uuid for e in parsed] == [e.uuid for e in entries]


def test_body_with_code_block_headings_and_ruler():
    d = date(2026, 11, 14)
    body = (
        "实验配置如下：\n\n"
        "```python\n"
        "x = 1\n"
        "print(x)\n"
        "```\n\n"
        "### 结果\n"
        "---\n"
        "某分隔线内容。"
    )
    entry = make_entry("运行实验", body)
    text = render_day(d, [entry])
    parsed = parse_day(text)
    assert len(parsed) == 1
    assert parsed[0].body == body


def test_special_characters_and_chinese():
    d = date(2026, 11, 14)
    body = "中文：验证跨视角建筑特征一致性。Unicode：λ θ π，emoji ✅，表格：| a | b |"
    entry = make_entry("记录想法", body)
    text = render_day(d, [entry])
    parsed = parse_day(text)
    assert parsed[0].body == body


def test_replace_only_target_entry():
    d = date(2026, 11, 14)
    a = make_entry("一", "内容一", hour=9)
    b = make_entry("二", "内容二", hour=14)
    c = make_entry("三", "内容三", hour=16)
    text = render_day(d, [a, b, c])

    new_b = LogEntry.new(b.timestamp, title="二改", body="内容二已修改")
    new_text = replace_entry_text(text, b.uuid, new_b)

    parsed = parse_day(new_text)
    assert [e.title for e in parsed] == ["一", "二改", "三"]
    assert [e.body for e in parsed] == ["内容一", "内容二已修改", "内容三"]
    # 未修改条目原文必须逐字保留
    assert "内容一" in new_text
    assert "内容三" in new_text
    # 未修改条目的 UUID 保持不变
    assert parsed[0].uuid == a.uuid
    assert parsed[2].uuid == c.uuid


def test_replace_unknown_uuid_raises():
    d = date(2026, 11, 14)
    entry = make_entry("一")
    text = render_day(d, [entry])
    with pytest.raises(EntryNotFoundError):
        replace_entry_text(text, "no-such-uuid", entry)


def test_remove_only_target_entry():
    d = date(2026, 11, 14)
    a = make_entry("一", "内容一", hour=9)
    b = make_entry("二", "内容二", hour=14)
    c = make_entry("三", "内容三", hour=16)
    text = render_day(d, [a, b, c])
    new_text = remove_entry_text(text, b.uuid)
    parsed = parse_day(new_text)
    assert [e.title for e in parsed] == ["一", "三"]
    assert [e.body for e in parsed] == ["内容一", "内容三"]


def test_remove_unknown_uuid_raises():
    d = date(2026, 11, 14)
    entry = make_entry("一")
    text = render_day(d, [entry])
    with pytest.raises(EntryNotFoundError):
        remove_entry_text(text, "no-such-uuid")


def test_append_preserves_existing_content():
    d = date(2026, 11, 14)
    a = make_entry("一", "内容一", hour=9)
    text = render_day(d, [a])
    b = make_entry("二", "内容二", hour=14)
    new_text = append_entry_text(text, b)
    parsed = parse_day(new_text)
    assert [e.title for e in parsed] == ["一", "二"]
    assert "内容一" in new_text


def test_parse_date_from_filename():
    assert parse_date_from_filename("2026-11-14.md") == date(2026, 11, 14)
    assert parse_date_from_filename("notes.md") is None
    assert parse_date_from_filename("2026-11-14.txt") is None


def test_auto_title_from_body():
    assert auto_title("") == ""
    assert auto_title("使用 DINOv3 进行建筑特征提取。") == "使用 DINOv3 进行建筑特征提取。"
    assert auto_title("## 实验目的\n验证跨视角特征相似性。") == "实验目的"
    long_body = "长" * 100
    assert len(auto_title(long_body)) <= 33


def test_unclosed_entry_tolerated():
    text = "<!-- chronolog:entry id=x timestamp=2026-11-14T09:30:15+08:00 -->\n\n## 09:30:15 | 标题\n\n正文\n"
    parsed = parse_day(text)
    assert len(parsed) == 1
    assert parsed[0].title == "标题"
    assert parsed[0].body == "正文"
