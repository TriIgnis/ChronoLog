"""storage 模块单元测试：文件创建、追加、编辑、删除、跨日期、外部修改检测、并发。"""

from __future__ import annotations

import multiprocessing
from datetime import date, datetime, timezone, timedelta

import pytest

from chronolog.core.models import LogEntry
from chronolog.core.storage import FileModifiedError, Storage

TZ = timezone(timedelta(hours=8))


def make_entry(title: str, body: str = "", day: int = 14, hour: int = 9) -> LogEntry:
    return LogEntry.new(
        datetime(2026, 11, day, hour, 30, 0, tzinfo=TZ), title=title, body=body
    )


@pytest.fixture()
def storage(tmp_path):
    return Storage(tmp_path / "ChronoLog")


def test_first_append_creates_file_and_dirs(storage):
    d = date(2026, 11, 14)
    storage.append_entry(d, make_entry("首次记录", "内容"))
    doc = storage.load_day(d)
    assert doc.exists
    assert doc.path.exists()
    assert len(doc.entries) == 1
    assert doc.entries[0].title == "首次记录"
    assert "2026-11" in str(doc.path)


def test_append_three_entries_no_duplication(storage):
    d = date(2026, 11, 14)
    for i in range(3):
        storage.append_entry(d, make_entry(f"记录{i}", f"内容{i}", hour=9 + i))
    doc = storage.load_day(d)
    assert len(doc.entries) == 3
    titles = [e.title for e in doc.entries]
    assert titles == ["记录0", "记录1", "记录2"]


def test_reload_after_restart_keeps_history(storage, tmp_path):
    d = date(2026, 11, 14)
    storage.append_entry(d, make_entry("一", hour=9))
    storage.append_entry(d, make_entry("二", hour=14))
    # 模拟重启：新建 Storage 实例重新读取
    storage2 = Storage(tmp_path / "ChronoLog")
    doc = storage2.load_day(d)
    assert len(doc.entries) == 2


def test_update_second_does_not_affect_others(storage):
    d = date(2026, 11, 14)
    storage.append_entry(d, make_entry("一", "内容一", hour=9))
    storage.append_entry(d, make_entry("二", "内容二", hour=14))
    storage.append_entry(d, make_entry("三", "内容三", hour=16))

    doc = storage.load_day(d)
    target = doc.entries[1]
    new_entry = LogEntry.new(target.timestamp, title="二改", body="内容二已修改")
    storage.update_entry(d, target.uuid, new_entry, expected_hash=doc.sha256)

    doc2 = storage.load_day(d)
    assert [e.title for e in doc2.entries] == ["一", "二改", "三"]
    assert [e.body for e in doc2.entries] == ["内容一", "内容二已修改", "内容三"]
    assert doc2.entries[0].uuid == doc.entries[0].uuid
    assert doc2.entries[2].uuid == doc.entries[2].uuid


def test_delete_does_not_affect_others(storage):
    d = date(2026, 11, 14)
    storage.append_entry(d, make_entry("一", "内容一", hour=9))
    storage.append_entry(d, make_entry("二", "内容二", hour=14))
    storage.append_entry(d, make_entry("三", "内容三", hour=16))
    doc = storage.load_day(d)
    storage.delete_entry(d, doc.entries[1].uuid, expected_hash=doc.sha256)
    doc2 = storage.load_day(d)
    assert [e.title for e in doc2.entries] == ["一", "三"]


def test_cross_date_writes_correct_file(storage):
    d1 = date(2026, 11, 14)
    d2 = date(2026, 12, 1)
    storage.append_entry(d1, make_entry("十一月", day=14))
    storage.append_entry(d2, make_entry("十二月", day=1))
    assert storage.load_day(d1).entries[0].title == "十一月"
    assert storage.load_day(d2).entries[0].title == "十二月"
    assert storage.day_path(d1) != storage.day_path(d2)


def test_external_modification_detected(storage):
    d = date(2026, 11, 14)
    storage.append_entry(d, make_entry("一", "内容一"))
    doc = storage.load_day(d)
    # 模拟外部程序修改
    doc.path.write_text(doc.path.read_text(encoding="utf-8") + "\n外部修改\n", encoding="utf-8")
    target = doc.entries[0]
    new_entry = LogEntry.new(target.timestamp, title="改", body="改")
    with pytest.raises(FileModifiedError):
        storage.update_entry(d, target.uuid, new_entry, expected_hash=doc.sha256)


def test_update_without_hash_still_works(storage):
    d = date(2026, 11, 14)
    storage.append_entry(d, make_entry("一", "内容一"))
    doc = storage.load_day(d)
    target = doc.entries[0]
    new_entry = LogEntry.new(target.timestamp, title="改", body="改")
    storage.update_entry(d, target.uuid, new_entry)  # 无哈希：直接按 UUID 定位
    assert storage.load_day(d).entries[0].title == "改"


def test_list_days(storage):
    storage.append_entry(date(2026, 11, 14), make_entry("a", day=14))
    storage.append_entry(date(2026, 11, 15), make_entry("b", day=15))
    days = storage.list_days()
    assert date(2026, 11, 14) in days
    assert date(2026, 11, 15) in days


def _worker_append(log_root: str, idx: int) -> None:
    st = Storage(log_root)
    st.append_entry(
        date(2026, 11, 14),
        LogEntry.new(datetime(2026, 11, 14, 10, idx, 0, tzinfo=TZ), title=f"进程{idx}", body=f"body{idx}"),
    )


def test_multiprocess_append_no_loss(storage, tmp_path):
    """多进程并发追加不应覆盖已有数据。"""
    log_root = str(tmp_path / "ChronoLog")
    procs = [multiprocessing.Process(target=_worker_append, args=(log_root, i)) for i in range(6)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
        assert p.exitcode == 0
    doc = Storage(log_root).load_day(date(2026, 11, 14))
    titles = sorted(e.title for e in doc.entries)
    assert titles == [f"进程{i}" for i in range(6)]
