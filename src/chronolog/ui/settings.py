"""设置对话框。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from chronolog.core.config import Config


class SettingsDialog(QDialog):
    theme_changed = Signal(str)

    def __init__(self, config: Config, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(520, 320)
        self._config = config
        s = config.settings

        self.root_edit = QLineEdit(s.log_root_dir)
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._browse)

        root_row = QHBoxLayout()
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(browse_btn)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("浅色", "light")
        self.theme_combo.addItem("深色", "dark")
        self.theme_combo.setCurrentIndex(0 if s.theme == "light" else 1)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 40)
        self.font_spin.setValue(s.editor_font_size)

        self.auto_close = QCheckBox("保存后自动关闭快速记录窗口")
        self.auto_close.setChecked(s.auto_close_after_save)

        self.startup_combo = QComboBox()
        self.startup_combo.addItem("主窗口", "main")
        self.startup_combo.addItem("快速记录", "quick")
        self.startup_combo.addItem("上次使用", "last")
        idx = {"main": 0, "quick": 1, "last": 2}.get(s.startup_behavior, 0)
        self.startup_combo.setCurrentIndex(idx)

        form = QFormLayout()
        form.addRow("日志根目录", root_row)
        form.addRow("主题", self.theme_combo)
        form.addRow("编辑器字号", self.font_spin)
        form.addRow("", self.auto_close)
        form.addRow("启动行为", self.startup_combo)

        cancel_btn = QPushButton("取消")
        save_btn = QPushButton("保存")
        save_btn.setObjectName("primary")
        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self._save)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addStretch(1)
        layout.addLayout(btns)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择日志根目录", self.root_edit.text())
        if d:
            self.root_edit.setText(d)

    def _save(self) -> None:
        s = self._config.settings
        old_theme = s.theme
        s.log_root_dir = self.root_edit.text().strip()
        s.theme = self.theme_combo.currentData()
        s.editor_font_size = self.font_spin.value()
        s.auto_close_after_save = self.auto_close.isChecked()
        s.startup_behavior = self.startup_combo.currentData()
        try:
            self._config.save()
        except OSError as exc:  # pragma: no cover - 磁盘错误
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "保存失败", f"配置保存失败：{exc}")
            return
        if s.theme != old_theme:
            self.theme_changed.emit(s.theme)
        self.accept()
