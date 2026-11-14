"""Markdown 日志文件的解析与渲染。

文件格式（UTF-8、本地时区）：

.. code-block:: markdown

    # 2026-11-14 星期六

    <!-- chronolog:entry id=UUID timestamp=2026-11-14T09:30:15+08:00 -->

    ## 09:30:15 | 开始阅读论文

    正文……

    <!-- chronolog:end id=UUID -->

    ---

元数据使用 HTML 注释保存，普通 Markdown 编辑器仍然可读。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

from chronolog.core.models import LogEntry, weekday_cn

ENTRY_RE = re.compile(
    r"^<!--\s*chronolog:entry\s+id=(?P<id>\S+)\s+timestamp=(?P<ts>\S+)\s*-->\s*$"
)
END_RE = re.compile(r"^<!--\s*chronolog:end\s+id=(?P<id>\S+)\s*-->\s*$")
HEADING_RE = re.compile(r"^##\s+(.*)$")
SEPARATOR_RE = re.compile(r"^\s*-{3,}\s*$")

DATE_FILENAME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.md$")


class EntryNotFoundError(KeyError):
    """按 UUID 找不到目标条目。"""


def _parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        # 容忍缺少时区的历史文件，按本地时区解释。
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt


def _title_from_heading(raw: str) -> str:
    """从 ``## 09:30:15 | 标题`` 提取标题。"""
    if " | " in raw:
        return raw.split(" | ", 1)[1].strip()
    return raw.strip()


@dataclass
class _EntrySpan:
    entry: LogEntry
    marker_idx: int  # entry 注释行号（0 基）
    end_idx: int  # end 注释行号（0 基）
    sep_idx: int | None  # 紧随其后的分隔线 ``---`` 行号，可能为 None


def _scan_entries(lines: list[str]) -> list[_EntrySpan]:
    """扫描行列表，返回带行号信息的条目。"""
    spans: list[_EntrySpan] = []
    n = len(lines)
    i = 0
    while i < n:
        m = ENTRY_RE.match(lines[i].strip())
        if not m:
            i += 1
            continue
        uuid = m.group("id")
        ts = _parse_ts(m.group("ts"))
        j = i + 1
        end_idx: int | None = None
        while j < n:
            em = END_RE.match(lines[j].strip())
            if em and em.group("id") == uuid:
                end_idx = j
                break
            j += 1
        if end_idx is None:
            # 未闭合的条目：容错地视为到文件末尾（含最后一行）。
            end_idx = n
        title, body = _parse_entry_body(lines[i + 1 : end_idx])
        # 查找紧随 end 之后的分隔线。
        sep_idx: int | None = None
        k = end_idx + 1
        while k < n and not lines[k].strip():
            k += 1
        if k < n and SEPARATOR_RE.match(lines[k].strip()):
            sep_idx = k
        spans.append(
            _EntrySpan(
                LogEntry(uuid=uuid, timestamp=ts, title=title, body=body),
                i,
                end_idx,
                sep_idx,
            )
        )
        i = end_idx + 1
    return spans


def _parse_entry_body(lines: list[str]) -> tuple[str, str]:
    """从 entry 注释与 end 注释之间的行中提取标题与正文。"""
    title = ""
    idx: int | None = None
    for k, line in enumerate(lines):
        hm = HEADING_RE.match(line.strip())
        if hm:
            title = _title_from_heading(hm.group(1).strip())
            idx = k
            break
    if idx is None:
        body_lines = lines
    else:
        body_lines = lines[idx + 1 :]
    body = "\n".join(body_lines).strip("\n")
    return title, body


def parse_day(content: str) -> list[LogEntry]:
    """解析某一天的 Markdown 文件内容，返回按出现顺序排列的条目。"""
    if not content:
        return []
    return [s.entry for s in _scan_entries(content.splitlines())]


def render_day_header(d: date) -> str:
    """生成每日文件头，例如 ``# 2026-11-14 星期六``。"""
    return f"# {d.isoformat()} {weekday_cn(d)}\n"


def render_entry_block(entry: LogEntry) -> str:
    """渲染单条条目（不含尾部 ``---`` 分隔线）。"""
    ts = entry.timestamp.isoformat()
    time_text = entry.timestamp.strftime("%H:%M:%S")
    lines = [
        f"<!-- chronolog:entry id={entry.uuid} timestamp={ts} -->",
        "",
        f"## {time_text} | {entry.title}",
        "",
    ]
    body = (entry.body or "").strip("\n")
    if body:
        lines.append(body)
        lines.append("")
    lines.append(f"<!-- chronolog:end id={entry.uuid} -->")
    return "\n".join(lines)


def render_day(d: date, entries: list[LogEntry]) -> str:
    """渲染整份每日文件（用于新建与测试）。"""
    lines = [render_day_header(d).rstrip("\n"), ""]
    for e in entries:
        lines.append(render_entry_block(e))
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines) + "\n"


def append_entry_text(content: str, entry: LogEntry) -> str:
    """向已有文件内容追加一条条目，保持原有内容不变。"""
    content = (content or "").rstrip("\n")
    if content:
        content += "\n\n"
    return content + render_entry_block(entry) + "\n\n---\n"


def replace_entry_text(content: str, uuid: str, new_entry: LogEntry) -> str:
    """仅替换指定 UUID 对应的条目块，其他内容原样保留。"""
    lines = content.splitlines()
    spans = _scan_entries(lines)
    for s in spans:
        if s.entry.uuid == uuid:
            new_lines = render_entry_block(new_entry).splitlines()
            lines[s.marker_idx : s.end_idx + 1] = new_lines
            return "\n".join(lines) + "\n"
    raise EntryNotFoundError(uuid)


def remove_entry_text(content: str, uuid: str) -> str:
    """仅删除指定 UUID 对应的条目块（含其尾部分隔线），其他内容原样保留。"""
    lines = content.splitlines()
    spans = _scan_entries(lines)
    for s in spans:
        if s.entry.uuid == uuid:
            end = s.sep_idx if s.sep_idx is not None else s.end_idx
            del lines[s.marker_idx : end + 1]
            _collapse_blanks(lines, s.marker_idx)
            return "\n".join(lines).rstrip("\n") + "\n"
    raise EntryNotFoundError(uuid)


def _collapse_blanks(lines: list[str], idx: int) -> None:
    """删除 idx 处可能出现的连续空行，保持排版整洁。"""
    idx = max(0, min(idx, len(lines) - 1))
    if lines[idx].strip() == "":
        prev = idx - 1
        if prev >= 0 and lines[prev].strip() == "":
            del lines[idx]
            return
    if idx + 1 < len(lines) and lines[idx].strip() == "" and lines[idx + 1].strip() == "":
        del lines[idx + 1]


def parse_date_from_filename(name: str) -> date | None:
    """从 ``2026-11-14.md`` 解析日期；无法解析返回 None。"""
    m = DATE_FILENAME_RE.match(name)
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
