"""Qt 与 Python 数据类型转换等小工具。"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QKeySequence, QShortcut


def qdt_to_dt(qdt: QDateTime) -> datetime:
    """QDateTime -> 带时区的 datetime（按本地时区解释）。"""
    dt = qdt.toPython()
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def dt_to_qdt(dt: datetime) -> QDateTime:
    """datetime -> QDateTime。"""
    if dt.tzinfo is not None:
        # 转成本地时区后再交给 QDateTime，避免时区歧义。
        dt = dt.astimezone()
    return QDateTime(dt)


def bind_shortcut(widget, key_sequence: str, slot) -> QShortcut:
    """在 widget 上绑定快捷键，默认仅在 widget 可见时生效。"""
    sc = QShortcut(QKeySequence(key_sequence), widget)
    sc.setContext(Qt.WindowShortcut)
    sc.activated.connect(slot)
    return sc
