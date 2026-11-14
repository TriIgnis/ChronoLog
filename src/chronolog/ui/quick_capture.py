"""快速记录窗口：ChronoLog 最重要的轻量录入入口。"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chronolog.core.config import Config
from chronolog.core.models import LogEntry, auto_title
from chronolog.core.parser import weekday_cn
from chronolog.core.storage import Storage
from chronolog.paths import APP_ICON
from chronolog.ui.markdown import MarkdownHighlighter
from chronolog.ui.qtutil import bind_shortcut, dt_to_qdt, qdt_to_dt


class QuickCaptureWindow(QWidget):
    """自动时间戳 + 标题/正文 + 快捷键保存的快速记录窗口。"""

    saved = Signal(object)  # LogEntry
    closed = Signal()

    def __init__(self, storage: Storage, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.storage = storage
        self.config = config
        self._frozen = False
        self._resetting = False
        self._record_dt = datetime.now().astimezone()

        self.setWindowTitle("ChronoLog 快速记录")
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.resize(600, 500)

        # 日期与时间显示
        self.date_label = QLabel()
        self.date_label.setObjectName("bigDate")
        self.time_label = QLabel()
        self.time_label.setObjectName("bigTime")

        self.dt_edit = QDateTimeEdit()
        self.dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.dt_edit.setCalendarPopup(True)

        # 标题与正文
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("标题（可留空，将从正文自动生成）")
        self.body_edit = QPlainTextEdit()
        self.body_edit.setPlaceholderText("输入 Markdown 内容…（Ctrl+Enter 保存，Ctrl+B/I 加粗/斜体）")
        self.highlighter = MarkdownHighlighter(self.body_edit.document())

        self.cancel_btn = QPushButton("取消")
        self.save_btn = QPushButton("保存  Ctrl+Enter")
        self.save_btn.setObjectName("primary")

        # 布局
        head = QHBoxLayout()
        head.addWidget(QLabel("📅"))
        head.addWidget(self.date_label)
        head.addStretch(1)
        head.addWidget(QLabel("🕘"))
        head.addWidget(self.time_label)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("记录时间"))
        time_row.addWidget(self.dt_edit)
        time_row.addStretch(1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.save_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(head)
        layout.addLayout(time_row)
        layout.addWidget(QLabel("标题"))
        layout.addWidget(self.title_edit)
        layout.addWidget(QLabel("内容"))
        layout.addWidget(self.body_edit, 1)
        layout.addLayout(btns)

        # 时钟
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

        # 信号与快捷键
        self.title_edit.textChanged.connect(self._on_first_input)
        self.body_edit.textChanged.connect(self._on_first_input)
        self.dt_edit.editingFinished.connect(self._on_time_edited)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self._cancel)

        bind_shortcut(self, "Ctrl+Return", self._save)
        bind_shortcut(self, "Ctrl+Enter", self._save)
        bind_shortcut(self, "Ctrl+S", self._save)
        bind_shortcut(self, "Esc", self._cancel)
        bind_shortcut(self, "Ctrl+B", lambda: self._wrap("**"))
        bind_shortcut(self, "Ctrl+I", lambda: self._wrap("*"))

        self._update_time_display()
        self._load_draft()
        self.body_edit.setFocus()

    # -- 时间 --
    def _tick(self) -> None:
        if self._frozen:
            return
        self._record_dt = datetime.now().astimezone()
        self._update_time_display()

    def _update_time_display(self) -> None:
        self.date_label.setText(f"{self._record_dt:%Y-%m-%d} {weekday_cn(self._record_dt.date())}")
        self.time_label.setText(self._record_dt.strftime("%H:%M:%S"))
        self.dt_edit.setDateTime(dt_to_qdt(self._record_dt))

    def _freeze(self) -> None:
        if self._frozen:
            return
        self._frozen = True
        self._timer.stop()
        self._record_dt = qdt_to_dt(self.dt_edit.dateTime())
        self._update_time_display()

    def _on_first_input(self) -> None:
        if self._resetting:
            return
        self._freeze()

    def _on_time_edited(self) -> None:
        self._freeze()
        self._record_dt = qdt_to_dt(self.dt_edit.dateTime())
        self._update_time_display()

    # -- 加粗 / 斜体 --
    def _wrap(self, marker: str) -> None:
        cursor = self.body_edit.textCursor()
        sel = cursor.selectedText()
        if sel:
            cursor.insertText(marker + sel + marker)
        else:
            cursor.insertText(marker + marker)
            cursor.movePosition(cursor.MoveOperation.Left, cursor.MoveMode.MoveAnchor, len(marker))
        self.body_edit.setTextCursor(cursor)
        self.body_edit.setFocus()

    # -- 保存 --
    def _save(self) -> None:
        self._freeze()
        title = self.title_edit.text().strip()
        body = self.body_edit.toPlainText()
        if not title and not body.strip():
            QMessageBox.warning(self, "无法保存", "标题和正文不能同时为空。")
            return
        if not title:
            title = auto_title(body)
        record_dt = qdt_to_dt(self.dt_edit.dateTime())
        entry = LogEntry.new(record_dt, title=title, body=body)
        try:
            self.storage.append_entry(record_dt.date(), entry)
        except Exception as exc:  # noqa: BLE001 - 保存失败必须保留内容
            QMessageBox.critical(self, "保存失败", f"保存失败：{exc}\n\n输入内容已保留，可重试或复制。")
            return
        self.config.clear_draft()
        self.saved.emit(entry)
        if self.config.settings.auto_close_after_save:
            self._reset()
            self.hide()
            self.closed.emit()
        else:
            self._reset()

    # -- 重置 --
    def _reset(self) -> None:
        self._resetting = True
        try:
            self.title_edit.clear()
            self.body_edit.clear()
        finally:
            self._resetting = False
        self._frozen = False
        self._record_dt = datetime.now().astimezone()
        self._update_time_display()
        self._timer.start()
        self.body_edit.setFocus()

    # -- 取消 / 关闭 --
    def _cancel(self) -> None:
        self._save_draft()
        self.hide()
        self.closed.emit()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_draft()
        self.closed.emit()
        super().closeEvent(event)

    # -- 草稿 --
    def _load_draft(self) -> None:
        draft = self.config.load_draft()
        if not draft:
            return
        self._resetting = True
        try:
            self.title_edit.setText(draft.get("title", ""))
            self.body_edit.setPlainText(draft.get("body", ""))
        finally:
            self._resetting = False
        ts = draft.get("timestamp")
        if ts:
            try:
                self._record_dt = datetime.fromisoformat(ts)
                self._freeze()
            except ValueError:
                pass
        # 草稿恢复后固定时间，避免覆盖用户原定时间
        self._freeze()
        self.body_edit.setFocus()

    def _save_draft(self) -> None:
        title = self.title_edit.text().strip()
        body = self.body_edit.toPlainText()
        if title or body.strip():
            self.config.save_draft(title, body, self._record_dt.isoformat())

    def focus_body(self) -> None:
        self.body_edit.setFocus()

    def center_on_screen(self) -> None:
        screen = self.screen() if self.screen() else None
        if screen is None:
            return
        geo = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(geo.center())
        self.move(frame.topLeft())
