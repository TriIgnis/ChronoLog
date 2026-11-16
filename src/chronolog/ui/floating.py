"""悬浮球：置顶、可拖动，一键呼出快速记录。

- 左键单击：快速记录。
- 左键拖动：移动位置（位置会记忆）。
- 右键：菜单（快速记录 / 打开主窗口 / 设置 / 退出）。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from chronolog.core.config import Config

_SIZE = 56
_MOVE_THRESHOLD = 6


class FloatingButton(QWidget):
    """常驻桌面的圆形悬浮按钮。"""

    quick_capture_requested = Signal()
    main_window_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(_SIZE, _SIZE)
        self.setToolTip("ChronoLog 悬浮球\n左键：快速记录    右键：菜单")

        self._drag_press: QPoint | None = None
        self._drag_window_pos: QPoint | None = None
        self._moved = False

        self._restore_position()

    # ------------------------------------------------------------ 位置
    def _restore_position(self) -> None:
        x = self._config.settings.floating_pos_x
        y = self._config.settings.floating_pos_y
        if x >= 0 and y >= 0:
            self.move(x, y)
        else:
            self._move_to_default()
        self._clamp_to_screen()

    def _move_to_default(self) -> None:
        app = QApplication.instance()
        if app is not None and app.primaryScreen() is not None:
            geo = app.primaryScreen().availableGeometry()
            self.move(
                geo.right() - _SIZE - 20,
                geo.top() + int(geo.height() * 0.42),
            )
        else:
            self.move(100, 100)

    def _clamp_to_screen(self) -> None:
        app = QApplication.instance()
        if app is None or app.primaryScreen() is None:
            return
        geo = app.primaryScreen().availableGeometry()
        x = max(geo.left(), min(self.x(), geo.right() - _SIZE))
        y = max(geo.top(), min(self.y(), geo.bottom() - _SIZE))
        self.move(x, y)

    def _save_position(self) -> None:
        self._config.settings.floating_pos_x = self.x()
        self._config.settings.floating_pos_y = self.y()
        try:
            self._config.save()
        except OSError:  # pragma: no cover - 配置不可写时静默忽略
            pass

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        circle = QRect(2, 2, _SIZE - 4, _SIZE - 4)
        painter.setBrush(QColor("#2f7da5"))
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawEllipse(circle)

        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPointSize(22)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, "记")

    # ------------------------------------------------------------ 交互
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_press = event.globalPosition().toPoint()
            self._drag_window_pos = self.pos()
            self._moved = False
            event.accept()
        elif event.button() == Qt.RightButton:
            self._show_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_press is None or not (event.buttons() & Qt.LeftButton):
            return
        delta = event.globalPosition().toPoint() - self._drag_press
        if not self._moved and delta.manhattanLength() > _MOVE_THRESHOLD:
            self._moved = True
        if self._moved and self._drag_window_pos is not None:
            self.move(self._drag_window_pos + delta)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            if self._moved:
                self._save_position()
            else:
                self.quick_capture_requested.emit()
            self._drag_press = None
            self._drag_window_pos = None
            self._moved = False
            event.accept()

    def _show_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        act_quick = menu.addAction("快速记录")
        act_main = menu.addAction("打开主窗口")
        act_settings = menu.addAction("设置")
        menu.addSeparator()
        act_quit = menu.addAction("退出")
        chosen = menu.exec(global_pos)
        if chosen == act_quick:
            self.quick_capture_requested.emit()
        elif chosen == act_main:
            self.main_window_requested.emit()
        elif chosen == act_settings:
            self.settings_requested.emit()
        elif chosen == act_quit:
            self.quit_requested.emit()
