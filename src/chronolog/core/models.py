"""数据模型与纯函数工具。

:class:`LogEntry` 是 ChronoLog 的核心数据模型：一条日志记录包含 UUID、
带时区的时间戳、标题与 Markdown 正文。
"""

from __future__ import annotations

import re
import uuid as _uuid
from dataclasses import dataclass
from datetime import date, datetime

# 周几的中文名称，用于日志标题。
WEEKDAY_CN = [
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
    "星期日",
]


@dataclass
class LogEntry:
    """一条时间线条目。"""

    uuid: str
    timestamp: datetime  # 带时区（tz-aware）
    title: str = ""
    body: str = ""

    @classmethod
    def new(
        cls,
        timestamp: datetime,
        title: str = "",
        body: str = "",
        uuid: str | None = None,
    ) -> "LogEntry":
        """创建一条新条目；未指定 UUID 时自动生成。"""
        return cls(
            uuid=uuid or str(_uuid.uuid4()),
            timestamp=timestamp,
            title=title.strip(),
            body=body,
        )


def weekday_cn(d: date) -> str:
    """返回某日期的中文星期，例如 ``星期六``。"""
    return WEEKDAY_CN[d.weekday()]


_MD_STRIP_RE = re.compile(r"^[#>\s*_`~\-+\d.]+")


def auto_title(body: str, max_len: int = 32) -> str:
    """正文有内容但标题为空时，从正文第一行生成简短标题。"""
    text = (body or "").strip()
    if not text:
        return ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # 跳过代码围栏等结构标记
        stripped = _MD_STRIP_RE.sub("", line).strip()
        if not stripped:
            stripped = line
        if len(stripped) > max_len:
            stripped = stripped[:max_len].rstrip() + "…"
        return stripped
    return ""
