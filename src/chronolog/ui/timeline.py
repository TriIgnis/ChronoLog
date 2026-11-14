"""时间线组件：按时间排序展示某一天的日志条目卡片。"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from chronolog.core.models import LogEntry
from chronolog.ui.markdown import markdown_to_html


class TimelineWidget(QScrollArea):
    """以卡片形式展示一天内的日志条目。"""

    edit_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self.setWidget(self._container)
        self._cards: dict[str, QWidget] = {}

    def _clear(self) -> None:
        self._cards.clear()
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def show_empty(self, message: str) -> None:
        self._clear()
        label = QLabel(message)
        label.setObjectName("muted")
        label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(label)
        self._layout.addStretch(1)

    def render(self, entries: list[LogEntry]) -> None:
        self._clear()
        ordered = sorted(entries, key=lambda e: e.timestamp)
        for entry in ordered:
            card = self._make_card(entry)
            self._cards[entry.uuid] = card
            self._layout.addWidget(card)
        self._layout.addStretch(1)

    def scroll_to(self, uuid: str) -> None:
        card = self._cards.get(uuid)
        if card is not None:
            self.ensureWidgetVisible(card)

    def _make_card(self, entry: LogEntry) -> QFrame:
        card = QFrame()
        card.setObjectName("card")

        time_label = QLabel(entry.timestamp.strftime("%H:%M:%S"))
        time_label.setObjectName("timeBadge")

        title_label = QLabel(entry.title or "(无标题)")
        title_label.setObjectName("titleLabel")
        title_label.setWordWrap(True)

        edit_btn = QPushButton("编辑")
        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("danger")
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(entry))
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(entry))

        header = QHBoxLayout()
        header.addWidget(time_label)
        header.addWidget(title_label, 1)
        header.addWidget(edit_btn)
        header.addWidget(delete_btn)

        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(6)
        v.addLayout(header)

        if entry.body.strip():
            body_label = QLabel()
            body_label.setTextFormat(Qt.RichText)
            body_label.setWordWrap(True)
            body_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            body_label.setOpenExternalLinks(True)
            body_label.setText(markdown_to_html(entry.body))
            v.addWidget(body_label)

        return card
