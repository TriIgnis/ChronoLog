"""全文搜索：扫描日志目录下的 Markdown 文件，匹配标题与正文。

第一版采用简单文件扫描，假设数据量为数百至数千个文件。GUI 层应在后台线程
中调用本模块，避免阻塞界面。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from chronolog.core.models import LogEntry
from chronolog.core.parser import parse_date_from_filename, parse_day


@dataclass
class SearchResult:
    date: date
    entry: LogEntry
    path: Path
    snippet: str


_SNIPPET_LEN = 120


def _make_snippet(entry: LogEntry, keyword: str) -> str:
    kw = keyword.lower()
    for line in entry.body.splitlines():
        if kw in line.lower():
            text = line.strip()
            if len(text) > _SNIPPET_LEN:
                text = text[:_SNIPPET_LEN] + "…"
            return text
    # 命中标题时给出正文开头作为摘要。
    text = entry.body.strip().replace("\n", " ")
    if len(text) > _SNIPPET_LEN:
        text = text[:_SNIPPET_LEN] + "…"
    return text


def search(root: str | Path, keyword: str, limit: int | None = None) -> list[SearchResult]:
    """在日志根目录下全文搜索关键词，返回按时间倒序的结果。"""
    kw = keyword.strip().lower()
    if not kw:
        return []
    root_path = Path(root)
    if not root_path.exists():
        return []
    results: list[SearchResult] = []
    for path in root_path.rglob("*.md"):
        d = parse_date_from_filename(path.name)
        if d is None:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for entry in parse_day(content):
            if kw in entry.title.lower() or kw in entry.body.lower():
                results.append(
                    SearchResult(
                        date=d,
                        entry=entry,
                        path=path,
                        snippet=_make_snippet(entry, kw),
                    )
                )
    results.sort(key=lambda r: (r.date, r.entry.timestamp), reverse=True)
    if limit is not None:
        results = results[:limit]
    return results
