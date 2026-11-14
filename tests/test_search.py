"""search 模块单元测试：标题/正文/中文搜索。"""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

from chronolog.core.models import LogEntry
from chronolog.core.search import search
from chronolog.core.storage import Storage

import pytest

TZ = timezone(timedelta(hours=8))


@pytest.fixture()
def storage(tmp_path):
    return Storage(tmp_path / "ChronoLog")


def _entry(title: str, body: str, day: int, hour: int) -> LogEntry:
    return LogEntry.new(datetime(2026, 11, day, hour, 0, 0, tzinfo=TZ), title=title, body=body)


def _seed(storage: Storage) -> None:
    storage.append_entry(date(2026, 11, 14), _entry("阅读论文", "无人机视觉导航综述。", 14, 9))
    storage.append_entry(date(2026, 11, 14), _entry("运行实验", "开始新的 DINOv3 实验，验证跨视角建筑特征。", 14, 14))
    storage.append_entry(date(2026, 11, 15), _entry("修改代码", "修复特征提取的边界问题。", 15, 19))


def test_search_title(storage):
    _seed(storage)
    results = search(storage.log_root, "阅读")
    assert len(results) == 1
    assert results[0].entry.title == "阅读论文"


def test_search_body(storage):
    _seed(storage)
    results = search(storage.log_root, "DINOv3")
    assert len(results) == 1
    assert results[0].entry.title == "运行实验"


def test_search_chinese_keyword(storage):
    _seed(storage)
    results = search(storage.log_root, "跨视角")
    assert len(results) == 1
    assert results[0].entry.title == "运行实验"


def test_search_no_result(storage):
    _seed(storage)
    assert search(storage.log_root, "不存在关键词xyz") == []


def test_search_case_insensitive(storage):
    _seed(storage)
    assert len(search(storage.log_root, "dinov3")) == 1


def test_search_empty_keyword(storage):
    _seed(storage)
    assert search(storage.log_root, "   ") == []
