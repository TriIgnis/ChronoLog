"""主题：浅色/深色，基于 Fusion + QSS + 深色调色板。"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from chronolog.paths import STYLES_DIR

_LIGHT = "light"
_DARK = "dark"


def _dark_palette() -> QPalette:
    p = QPalette()
    window = QColor("#171a21")
    base = QColor("#20242e")
    text = QColor("#d6dae2")
    accent = QColor("#2f7da5")
    p.setColor(QPalette.Window, window)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, QColor("#232833"))
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, QColor("#232833"))
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.ToolTipBase, base)
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.Highlight, accent)
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.PlaceholderText, QColor("#8a93a2"))
    p.setColor(QPalette.Link, QColor("#7fd1e8"))
    return p


def load_stylesheet(theme: str) -> str:
    name = _DARK if theme == _DARK else _LIGHT
    path = STYLES_DIR / f"{name}.qss"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def apply_theme(app: QApplication, theme: str) -> None:
    app.setStyle("Fusion")
    if theme == _DARK:
        app.setPalette(_dark_palette())
    else:
        app.setPalette(app.style().standardPalette())
    app.setStyleSheet(load_stylesheet(theme))
