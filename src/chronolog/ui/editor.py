"""Markdown 编辑器：源码编辑 + 预览，以及条目编辑对话框。"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from chronolog.core.models import auto_title
from chronolog.ui.markdown import MarkdownHighlighter, render_html_document
from chronolog.ui.qtutil import bind_shortcut, dt_to_qdt, qdt_to_dt


class MarkdownEditorPane(QWidget):
    """源码编辑 + 预览的可切换面板。"""

    def __init__(self, dark: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dark = dark
        self.edit = QPlainTextEdit()
        self.edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.edit.setTabStopDistance(4 * self.edit.fontMetrics().horizontalAdvance(" "))
        self.highlighter = MarkdownHighlighter(self.edit.document())

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.edit)  # 0
        self.stack.addWidget(self.preview)  # 1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

    # -- 文本 --
    def text(self) -> str:
        return self.edit.toPlainText()

    def set_text(self, text: str) -> None:
        self.edit.setPlainText(text or "")

    # -- 模式切换 --
    def show_edit(self) -> None:
        self.stack.setCurrentIndex(0)
        self.edit.setFocus()

    def show_preview(self) -> None:
        self.preview.setHtml(render_html_document(self.edit.toPlainText(), self._dark))
        self.stack.setCurrentIndex(1)

    def toggle_preview(self) -> None:
        if self.is_preview():
            self.show_edit()
        else:
            self.show_preview()

    def is_preview(self) -> bool:
        return self.stack.currentIndex() == 1

    # -- 字号 --
    def set_font_size(self, px: int) -> None:
        f = QFont()
        f.setPointSize(px)
        self.edit.setFont(f)
        self.preview.setFont(f)

    # -- 快捷插入 --
    def wrap_selection(self, prefix: str, suffix: str | None = None) -> None:
        """把当前选中文本用前后缀包裹（加粗/斜体等）。"""
        suffix = prefix if suffix is None else suffix
        cursor = self.edit.textCursor()
        sel = cursor.selectedText()
        if sel:
            cursor.insertText(prefix + sel + suffix)
        else:
            cursor.insertText(prefix + suffix)
            cursor.movePosition(cursor.MoveOperation.Left, cursor.MoveMode.MoveAnchor, len(suffix))
        self.edit.setTextCursor(cursor)
        self.edit.setFocus()


class EntryEditorDialog(QDialog):
    """编辑/新增一条日志记录的对话框。"""

    def __init__(
        self,
        title: str = "",
        body: str = "",
        timestamp: datetime | None = None,
        dark: bool = False,
        font_size: int = 12,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑记录")
        self.resize(680, 560)
        self.result_title = ""
        self.result_body = ""
        self.result_timestamp: datetime | None = None

        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("标题（可留空，将从正文自动生成）")

        self.dt_edit = QDateTimeEdit()
        self.dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.dt_edit.setCalendarPopup(True)
        self.dt_edit.setDateTime(dt_to_qdt(timestamp or datetime.now().astimezone()))

        self.pane = MarkdownEditorPane(dark=dark)
        self.pane.set_text(body)
        self.pane.set_font_size(font_size)

        # 工具行
        self.preview_btn = QPushButton("预览")
        self.preview_btn.setCheckable(True)
        self.preview_btn.toggled.connect(self._toggle_preview)
        self.font_minus = QPushButton("A-")
        self.font_plus = QPushButton("A+")
        self.font_minus.clicked.connect(lambda: self._change_font(-1))
        self.font_plus.clicked.connect(lambda: self._change_font(+1))
        self._font_size = font_size

        self.cancel_btn = QPushButton("取消")
        self.save_btn = QPushButton("保存")
        self.save_btn.setObjectName("primary")

        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("标题"))
        title_row.addWidget(self.title_edit, 1)
        title_row.addWidget(QLabel("时间"))
        title_row.addWidget(self.dt_edit)

        tools = QHBoxLayout()
        tools.addWidget(self.preview_btn)
        tools.addWidget(self.font_minus)
        tools.addWidget(self.font_plus)
        tools.addStretch(1)
        tools.addWidget(self.cancel_btn)
        tools.addWidget(self.save_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(title_row)
        layout.addWidget(QLabel("内容"))
        layout.addWidget(self.pane, 1)
        layout.addLayout(tools)

        self.save_btn.clicked.connect(self._on_save)
        self.cancel_btn.clicked.connect(self.reject)

        # 快捷键
        bind_shortcut(self, "Ctrl+Return", self._on_save)
        bind_shortcut(self, "Ctrl+Enter", self._on_save)
        bind_shortcut(self, "Ctrl+S", self._on_save)
        bind_shortcut(self, "Esc", self.reject)
        bind_shortcut(self, "Ctrl+B", lambda: self.pane.wrap_selection("**"))
        bind_shortcut(self, "Ctrl+I", lambda: self.pane.wrap_selection("*"))

        self.title_edit.setFocus()

    def _toggle_preview(self, checked: bool) -> None:
        if checked:
            self.pane.show_preview()
            self.preview_btn.setText("编辑")
        else:
            self.pane.show_edit()
            self.preview_btn.setText("预览")

    def _change_font(self, delta: int) -> None:
        self._font_size = max(8, min(40, self._font_size + delta))
        self.pane.set_font_size(self._font_size)

    def _on_save(self) -> None:
        title = self.title_edit.text().strip()
        body = self.pane.text()
        if not title and not body.strip():
            QMessageBox.warning(self, "无法保存", "标题和正文不能同时为空。")
            return
        if not title:
            title = auto_title(body)
        self.result_title = title
        self.result_body = body
        self.result_timestamp = qdt_to_dt(self.dt_edit.dateTime())
        self.accept()
