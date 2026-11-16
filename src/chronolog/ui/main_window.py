"""主窗口：每日时间线浏览、搜索、日历导航、设置。"""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QIcon, QTextCharFormat, QColor
from PySide6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from chronolog.core.config import Config
from chronolog.core.models import LogEntry
from chronolog.core.search import SearchResult, search
from chronolog.core.storage import FileModifiedError, Storage
from chronolog.paths import APP_ICON
from chronolog.ui.editor import EntryEditorDialog
from chronolog.ui.settings import SettingsDialog
from chronolog.ui.theme import apply_theme
from chronolog.ui.timeline import TimelineWidget


class SearchWorker(QThread):
    """后台线程执行全文搜索，避免阻塞 GUI。"""

    results_ready = Signal(list)

    def __init__(self, root: str, keyword: str, parent=None) -> None:
        super().__init__(parent)
        self._root = root
        self._keyword = keyword

    def run(self) -> None:  # noqa: D102
        try:
            results = search(self._root, self._keyword, limit=300)
        except Exception:  # noqa: BLE001 - 搜索失败按无结果处理
            results = []
        self.results_ready.emit(results)


class SearchResultsDialog(QDialog):
    """搜索结果列表，双击跳转到对应日志。"""

    jump_requested = Signal(object)  # SearchResult

    def __init__(self, results: list[SearchResult], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("搜索结果")
        self.resize(560, 480)
        self.list_widget = QListWidget()
        for r in results:
            time_text = r.entry.timestamp.strftime("%H:%M:%S")
            item = QListWidgetItem(f"{r.date.isoformat()}  {time_text}  {r.entry.title or '(无标题)'}")
            item.setToolTip(r.snippet)
            item.setData(Qt.UserRole, r)
            self.list_widget.addItem(item)
        self.list_widget.itemActivated.connect(self._on_activate)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget, 1)
        layout.addWidget(close_btn, 0, Qt.AlignRight)

    def _on_activate(self, item: QListWidgetItem) -> None:
        result = item.data(Qt.UserRole)
        if result is not None:
            self.jump_requested.emit(result)
            self.accept()


class MainWindow(QMainWindow):
    """ChronoLog 主窗口。"""

    quick_capture_requested = Signal()
    floating_preference_changed = Signal(bool)

    def __init__(self, storage: Storage, config: Config) -> None:
        super().__init__()
        self.storage = storage
        self.config = config
        self.current_date = date.today()
        self._current_doc = storage.load_day(self.current_date)
        self._search_generation = 0
        self._search_worker: SearchWorker | None = None

        self.setWindowTitle("ChronoLog")
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.resize(1080, 720)

        self._build_ui()
        self._connect_signals()
        self._refresh_calendar_marks()
        self._reload()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        # 顶部工具栏
        title = QLabel("ChronoLog")
        title.setObjectName("bigDate")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索标题或正文…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(280)
        quick_btn = QPushButton("快速记录")
        quick_btn.setObjectName("primary")
        settings_btn = QPushButton("设置")

        toolbar = QHBoxLayout()
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        toolbar.addWidget(self.search_edit)
        toolbar.addWidget(quick_btn)
        toolbar.addWidget(settings_btn)
        root.addLayout(toolbar)

        # 分栏
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：日历 + 今天
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        today_btn = QPushButton("今天")
        left_layout.addWidget(self.calendar, 1)
        left_layout.addWidget(today_btn)

        # 右侧：日期 + 条数 + 时间线 + 新增
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.date_label = QLabel()
        self.date_label.setObjectName("bigDate")
        self.count_label = QLabel()
        self.count_label.setObjectName("muted")
        self.timeline = TimelineWidget()
        add_btn = QPushButton("+ 新增记录")
        add_btn.setObjectName("primary")

        head = QHBoxLayout()
        head.addWidget(self.date_label)
        head.addStretch(1)
        head.addWidget(self.count_label)

        right_layout.addLayout(head)
        right_layout.addWidget(self.timeline, 1)
        right_layout.addWidget(add_btn, 0, Qt.AlignRight)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 760])
        root.addWidget(splitter, 1)

        self.setCentralWidget(central)

        # 保存控件引用
        self._quick_btn = quick_btn
        self._settings_btn = settings_btn
        self._today_btn = today_btn
        self._add_btn = add_btn

    def _connect_signals(self) -> None:
        self.calendar.clicked.connect(self._on_date_selected)
        self._today_btn.clicked.connect(lambda: self._set_date(date.today()))
        self._add_btn.clicked.connect(self._on_add)
        self._quick_btn.clicked.connect(self.quick_capture_requested.emit)
        self._settings_btn.clicked.connect(self._on_settings)
        self.timeline.edit_requested.connect(self._on_edit)
        self.timeline.delete_requested.connect(self._on_delete)

        self.search_edit.textChanged.connect(self._on_search_text)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(350)
        self._search_timer.timeout.connect(self._run_search)

    # ------------------------------------------------------------ 日期导航
    def _on_date_selected(self, qdate) -> None:
        self._set_date(date(qdate.year(), qdate.month(), qdate.day()))

    def _set_date(self, d: date) -> None:
        self.current_date = d
        from PySide6.QtCore import QDate

        if self.calendar.selectedDate() != QDate(d.year, d.month, d.day):
            self.calendar.setSelectedDate(QDate(d.year, d.month, d.day))
        self._reload()

    def _reload(self) -> None:
        self._current_doc = self.storage.load_day(self.current_date)
        d = self.current_date
        from chronolog.core.parser import weekday_cn

        self.date_label.setText(f"{d:%Y年%m月%d日} {weekday_cn(d)}")
        count = len(self._current_doc.entries)
        self.count_label.setText(f"今天共记录 {count} 条" if d == date.today() else f"共记录 {count} 条")
        if count:
            self.timeline.render(self._current_doc.entries)
        else:
            self.timeline.show_empty("这一天还没有记录，点击「+ 新增记录」开始吧。")

    def _refresh_calendar_marks(self) -> None:
        """给有日志的日期加高亮标记。"""
        try:
            days = self.storage.list_days()
        except Exception:  # noqa: BLE001
            days = set()
        fmt = QTextCharFormat()
        fmt.setFontWeight(700)
        fmt.setForeground(QColor("#2f7da5"))
        for d in days:
            from PySide6.QtCore import QDate

            self.calendar.setDateTextFormat(QDate(d.year, d.month, d.day), fmt)

    # ------------------------------------------------------------ 新增/编辑/删除
    def _on_add(self) -> None:
        dlg = self._make_editor("", "", datetime.now().astimezone(), "新增记录")
        if dlg.exec() == QDialog.Accepted:
            entry = LogEntry.new(dlg.result_timestamp, title=dlg.result_title, body=dlg.result_body)
            try:
                self.storage.append_entry(dlg.result_timestamp.date(), entry)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "保存失败", str(exc))
            self._reload()
            self._refresh_calendar_marks()

    def _make_editor(self, title: str, body: str, ts: datetime, window_title: str) -> EntryEditorDialog:
        dlg = EntryEditorDialog(
            title=title,
            body=body,
            timestamp=ts,
            dark=self.config.settings.theme == "dark",
            font_size=self.config.settings.editor_font_size,
            parent=self,
        )
        dlg.setWindowTitle(window_title)
        return dlg

    def _on_edit(self, entry: LogEntry) -> None:
        dlg = self._make_editor(entry.title, entry.body, entry.timestamp, "编辑记录")
        if dlg.exec() != QDialog.Accepted:
            return
        new_entry = LogEntry.new(
            dlg.result_timestamp, title=dlg.result_title, body=dlg.result_body, uuid=entry.uuid
        )
        try:
            self.storage.update_entry(
                self.current_date, entry.uuid, new_entry, expected_hash=self._current_doc.sha256
            )
        except FileModifiedError as exc:
            self._conflict(str(exc))
        self._reload()

    def _on_delete(self, entry: LogEntry) -> None:
        ret = QMessageBox.question(
            self,
            "删除确认",
            f"确定删除「{entry.title or '(无标题)'}」吗？\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        try:
            self.storage.delete_entry(
                self.current_date, entry.uuid, expected_hash=self._current_doc.sha256
            )
        except FileModifiedError as exc:
            self._conflict(str(exc))
        self._reload()
        self._refresh_calendar_marks()

    def _conflict(self, message: str) -> None:
        QMessageBox.warning(
            self,
            "检测到外部修改",
            f"{message}\n\n已取消本次操作并重新加载，未覆盖外部修改。",
        )
        self._reload()

    # ------------------------------------------------------------ 搜索
    def _on_search_text(self, text: str) -> None:
        self._search_timer.start()

    def _run_search(self) -> None:
        keyword = self.search_edit.text().strip()
        if not keyword:
            return
        self._search_generation += 1
        gen = self._search_generation
        if self._search_worker is not None and self._search_worker.isRunning():
            self._search_worker.requestInterruption()
        worker = SearchWorker(str(self.storage.log_root), keyword, self)
        worker.results_ready.connect(lambda results, g=gen: self._on_search_results(g, results))
        worker.finished.connect(worker.deleteLater)
        self._search_worker = worker
        worker.start()

    def _on_search_results(self, generation: int, results: list[SearchResult]) -> None:
        if generation != self._search_generation:
            return
        if not results:
            self.statusBar().showMessage("未找到匹配的日志", 3000)
            return
        dlg = SearchResultsDialog(results, self)
        dlg.jump_requested.connect(self._jump_to_result)
        dlg.exec()

    def _jump_to_result(self, result: SearchResult) -> None:
        self._set_date(result.date)
        self._refresh_calendar_marks()
        self.timeline.scroll_to(result.entry.uuid)

    # ------------------------------------------------------------ 设置
    def open_settings(self) -> None:
        self._on_settings()

    def _on_settings(self) -> None:
        dlg = SettingsDialog(self.config, self)
        dlg.theme_changed.connect(lambda theme: apply_theme(QApplication.instance(), theme))
        if dlg.exec() == QDialog.Accepted:
            self.storage.set_root(self.config.settings.log_root_dir)
            self._reload()
            self._refresh_calendar_marks()
            self.floating_preference_changed.emit(self.config.settings.show_floating_window)

    def refresh_after_quick_save(self) -> None:
        """快速记录保存后刷新当前视图。"""
        self._reload()
        self._refresh_calendar_marks()
