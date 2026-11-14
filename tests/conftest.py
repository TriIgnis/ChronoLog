"""pytest 全局配置：离屏渲染，隔离 XDG 目录。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XDG_CONFIG_HOME", os.path.join(os.environ.get("TMPDIR", "/tmp"), "chronolog-test-config"))
os.environ.setdefault("XDG_DATA_HOME", os.path.join(os.environ.get("TMPDIR", "/tmp"), "chronolog-test-data"))

import pytest  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
