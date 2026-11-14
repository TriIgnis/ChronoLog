"""应用入口：单实例、主题、主窗口与快速记录窗口调度。

启动方式：

- ``chronolog`` 或 ``python -m chronolog`` —— 打开主窗口。
- ``chronolog --quick`` 或 ``python -m chronolog --quick`` —— 打开快速记录窗口。
"""

from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from chronolog import __version__
from chronolog.core.config import Config, data_dir
from chronolog.core.storage import Storage
from chronolog.paths import APP_ICON
from chronolog.ui.main_window import MainWindow
from chronolog.ui.quick_capture import QuickCaptureWindow
from chronolog.ui.theme import apply_theme

SOCKET_KEY = "chronolog-single-instance"


def _setup_logging() -> None:
    log_path = data_dir() / "chronolog.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(log_path),
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    except OSError:  # pragma: no cover - 日志目录不可写时静默降级
        logging.basicConfig(level=logging.INFO)


class SingleInstance(QObject):
    """基于 QLocalServer 的单实例协调。"""

    message_received = Signal(str)

    def __init__(self, key: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._is_secondary = False
        self._server: QLocalServer | None = None
        socket = QLocalSocket(self)
        socket.connectToServer(key)
        if socket.waitForConnected(300):
            self._is_secondary = True
            self._socket = socket
        else:
            QLocalServer.removeServer(key)
            self._server = QLocalServer(self)
            self._server.newConnection.connect(self._on_new_connection)
            if not self._server.listen(key):
                # 极端情况下监听失败，退化为多实例。
                self._server = None

    def is_secondary(self) -> bool:
        return self._is_secondary

    def send_message(self, message: str) -> None:
        if getattr(self, "_socket", None) is None:
            return
        self._socket.write(message.encode("utf-8"))
        self._socket.flush()
        self._socket.waitForBytesWritten(500)

    def _on_new_connection(self) -> None:
        conn = self._server.nextPendingConnection()
        conn.readyRead.connect(lambda c=conn: self._read_message(c))

    def _read_message(self, conn: QLocalSocket) -> None:
        data = bytes(conn.readAll()).decode("utf-8", errors="ignore").strip()
        if data:
            self.message_received.emit(data)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="chronolog", description="ChronoLog —— Ubuntu Markdown 时间线日志软件"
    )
    parser.add_argument("--quick", action="store_true", help="打开快速记录窗口")
    parser.add_argument("--version", action="version", version=f"chronolog {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _setup_logging()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ChronoLog")
    app.setOrganizationName("ChronoLog")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(True)
    app.setWindowIcon(QIcon(str(APP_ICON)))

    config = Config()
    apply_theme(app, config.settings.theme)

    single = SingleInstance(SOCKET_KEY)
    if single.is_secondary():
        single.send_message("quick" if args.quick else "show")
        return 0

    storage = Storage(config.settings.log_root_dir)
    window = MainWindow(storage, config)
    quick = QuickCaptureWindow(storage, config)

    def handle_message(message: str) -> None:
        if message == "quick":
            quick.center_on_screen()
            quick.show()
            quick.raise_()
            quick.activateWindow()
            quick.focus_body()
        else:
            window.show()
            window.raise_()
            window.activateWindow()

    single.message_received.connect(handle_message)

    # 快速记录保存后刷新主窗口
    quick.saved.connect(lambda _entry: window.refresh_after_quick_save())
    # 主窗口的「快速记录」按钮
    window.quick_capture_requested.connect(
        lambda: handle_message("quick")
    )

    def on_quick_closed() -> None:
        if not window.isVisible():
            app.quit()

    quick.closed.connect(on_quick_closed)

    if args.quick:
        quick.center_on_screen()
        quick.show()
        quick.focus_body()
    else:
        window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
