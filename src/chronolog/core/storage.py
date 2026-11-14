"""日志存储层：每日 Markdown 文件的读写、追加、编辑与删除。

安全策略：

- 所有写操作先读取磁盘最新内容，绝不覆盖已有记录。
- 使用临时文件 + ``fsync`` + ``os.replace`` 原子替换。
- 使用 ``fcntl.flock`` 协调 ChronoLog 自身多进程并发。
- 编辑/删除前可传入 ``expected_hash`` 检测外部修改，冲突时抛出
  :class:`FileModifiedError`，绝不静默覆盖。

外部编辑器（不遵守锁）的修改靠内容哈希检测兜底。
"""

from __future__ import annotations

import hashlib
import os
import uuid as _uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from chronolog.core.models import LogEntry
from chronolog.core.parser import (
    append_entry_text,
    parse_date_from_filename,
    parse_day,
    remove_entry_text,
    render_day_header,
    replace_entry_text,
)

try:  # Ubuntu / POSIX 专有锁
    import fcntl

    _HAS_FCNTL = True
except ImportError:  # pragma: no cover - 非 Linux 环境
    _HAS_FCNTL = False


class FileModifiedError(RuntimeError):
    """文件在读取之后被外部修改，拒绝静默覆盖。"""


@dataclass
class DayDocument:
    """某一天的日志文档快照。"""

    date: date
    path: Path
    exists: bool
    raw: str
    sha256: str
    entries: list[LogEntry]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Storage:
    """管理日志根目录下的每日 Markdown 文件。"""

    def __init__(self, log_root: str | Path) -> None:
        self.log_root = Path(log_root).expanduser().resolve()

    def set_root(self, log_root: str | Path) -> None:
        """运行期切换日志根目录。"""
        self.log_root = Path(log_root).expanduser().resolve()

    # ---- 路径 ----
    def day_path(self, d: date) -> Path:
        return self.log_root / f"{d:%Y-%m}" / f"{d.isoformat()}.md"

    def _lock_path(self, path: Path) -> Path:
        return path.with_name(path.name + ".lock")

    @contextmanager
    def _file_lock(self, path: Path):
        if not _HAS_FCNTL:  # pragma: no cover
            yield
            return
        lock_path = self._lock_path(path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    # ---- 读 ----
    def load_day(self, d: date) -> DayDocument:
        path = self.day_path(d)
        if not path.exists():
            return DayDocument(date=d, path=path, exists=False, raw="", sha256="", entries=[])
        raw = path.read_text(encoding="utf-8")
        entries = parse_day(raw)
        return DayDocument(
            date=d, path=path, exists=True, raw=raw, sha256=_sha256(raw), entries=entries
        )

    # ---- 写 ----
    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.parent / f".{path.name}.tmp-{_uuid.uuid4().hex}"
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
            self._fsync_dir(path.parent)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    @staticmethod
    def _fsync_dir(directory: Path) -> None:
        try:
            fd = os.open(str(directory), os.O_RDONLY)
        except OSError:  # pragma: no cover
            return
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def append_entry(self, d: date, entry: LogEntry) -> None:
        """追加一条新记录：先读最新内容再追加，防止覆盖与重复。"""
        path = self.day_path(d)
        with self._file_lock(path):
            if path.exists():
                content = path.read_text(encoding="utf-8")
            else:
                content = ""
            if not content.strip():
                content = render_day_header(d) + "\n"
            new_content = append_entry_text(content, entry)
            self._atomic_write(path, new_content)

    def update_entry(
        self,
        d: date,
        uuid: str,
        new_entry: LogEntry,
        expected_hash: str | None = None,
    ) -> None:
        """按 UUID 替换单条记录；``expected_hash`` 用于外部修改检测。"""
        path = self.day_path(d)
        with self._file_lock(path):
            if not path.exists():
                raise FileNotFoundError(path)
            raw = path.read_text(encoding="utf-8")
            self._check_modified(raw, expected_hash)
            new_raw = replace_entry_text(raw, uuid, new_entry)
            self._atomic_write(path, new_raw)

    def delete_entry(self, d: date, uuid: str, expected_hash: str | None = None) -> None:
        """按 UUID 删除单条记录。"""
        path = self.day_path(d)
        with self._file_lock(path):
            if not path.exists():
                return
            raw = path.read_text(encoding="utf-8")
            self._check_modified(raw, expected_hash)
            new_raw = remove_entry_text(raw, uuid)
            self._atomic_write(path, new_raw)

    @staticmethod
    def _check_modified(raw: str, expected_hash: str | None) -> None:
        if expected_hash is not None and _sha256(raw) != expected_hash:
            raise FileModifiedError("日志文件已被外部修改，为避免覆盖请重新加载后再操作。")

    # ---- 枚举 ----
    def list_days(self) -> set[date]:
        """返回存在日志文件的所有日期（用于日历高亮）。"""
        if not self.log_root.exists():
            return set()
        days: set[date] = set()
        for path in self.log_root.rglob("*.md"):
            d = parse_date_from_filename(path.name)
            if d is not None:
                days.add(d)
        return days
