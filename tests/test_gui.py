"""GUI 离屏测试：主窗口、快速记录、编辑器、设置与主题。

注意：本测试在无真实显示器的环境下以 offscreen 平台运行，验证界面逻辑与
数据流；实际桌面渲染效果需在图形桌面人工确认。
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from PySide6.QtWidgets import QMessageBox

from chronolog.core.config import Config
from chronolog.core.storage import Storage
from chronolog.ui.editor import EntryEditorDialog
from chronolog.ui.main_window import MainWindow
from chronolog.ui.qtutil import dt_to_qdt
from chronolog.ui.quick_capture import QuickCaptureWindow
from chronolog.ui.theme import apply_theme


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    cfg = Config()
    cfg.settings.log_root_dir = str(tmp_path / "logs")
    storage = Storage(cfg.settings.log_root_dir)
    return cfg, storage


@pytest.fixture()
def no_dialogs(monkeypatch):
    """避免模态对话框阻塞离屏测试。"""
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))


def test_main_window_empty_state(qapp, env):
    cfg, storage = env
    mw = MainWindow(storage, cfg)
    assert mw.count_label.text() == "今天共记录 0 条"
    mw.close()


def test_main_window_shows_entries(qapp, env):
    cfg, storage = env
    storage.append_entry(date.today(), _entry("测试标题", "测试正文", date.today()))
    mw = MainWindow(storage, cfg)
    assert mw.count_label.text() == "今天共记录 1 条"
    mw.close()


def test_quick_capture_save_writes_entry(qapp, env, no_dialogs):
    cfg, storage = env
    qc = QuickCaptureWindow(storage, cfg)
    qc.config.settings.auto_close_after_save = False
    qc.title_edit.setText("测试记录")
    qc.body_edit.setPlainText("正文内容 **加粗**")
    qc.dt_edit.setDateTime(dt_to_qdt(datetime(2026, 11, 14, 9, 30, 0)))
    qc._save()
    doc = storage.load_day(date(2026, 11, 14))
    assert len(doc.entries) == 1
    assert doc.entries[0].title == "测试记录"
    assert doc.entries[0].body == "正文内容 **加粗**"
    qc.close()


def test_quick_capture_auto_title(qapp, env, no_dialogs):
    cfg, storage = env
    qc = QuickCaptureWindow(storage, cfg)
    qc.config.settings.auto_close_after_save = False
    qc.body_edit.setPlainText("使用 DINOv3 进行建筑特征提取。")
    qc.dt_edit.setDateTime(dt_to_qdt(datetime(2026, 11, 14, 10, 0, 0)))
    qc._save()
    doc = storage.load_day(date(2026, 11, 14))
    assert doc.entries[0].title == "使用 DINOv3 进行建筑特征提取。"
    qc.close()


def test_quick_capture_empty_rejected(qapp, env, no_dialogs):
    cfg, storage = env
    qc = QuickCaptureWindow(storage, cfg)
    qc._save()
    assert storage.load_day(date.today()).exists is False
    qc.close()


def test_quick_capture_save_failure_keeps_content(qapp, env, no_dialogs, monkeypatch):
    cfg, storage = env
    qc = QuickCaptureWindow(storage, cfg)
    qc.title_edit.setText("保留我")
    qc.body_edit.setPlainText("不要丢")

    def boom(*a, **k):
        raise RuntimeError("磁盘写入失败")

    monkeypatch.setattr(storage, "append_entry", boom)
    qc._save()
    assert qc.title_edit.text() == "保留我"
    assert qc.body_edit.toPlainText() == "不要丢"
    qc.close()


def test_quick_capture_double_save_no_duplicate(qapp, env, no_dialogs):
    cfg, storage = env
    qc = QuickCaptureWindow(storage, cfg)
    qc.config.settings.auto_close_after_save = False
    qc.title_edit.setText("只保存一次")
    qc.body_edit.setPlainText("内容")
    qc.dt_edit.setDateTime(dt_to_qdt(datetime(2026, 11, 14, 9, 30, 0)))
    qc._save()
    qc._save()  # 第二次保存：内容已被清空，应被拒绝，不产生重复
    doc = storage.load_day(date(2026, 11, 14))
    assert len(doc.entries) == 1
    qc.close()


def test_editor_empty_rejected(qapp, no_dialogs):
    ed = EntryEditorDialog("", "", datetime.now().astimezone())
    ed._on_save()
    assert ed.result_timestamp is None  # 未通过校验，未接受


def test_editor_auto_title(qapp, no_dialogs):
    ed = EntryEditorDialog("", "正文内容第一行", datetime.now().astimezone())
    ed._on_save()
    assert ed.result_title == "正文内容第一行"
    assert ed.result_timestamp is not None


def test_theme_apply(qapp):
    apply_theme(qapp, "light")
    apply_theme(qapp, "dark")
    assert qapp.styleSheet() != ""


def test_draft_roundtrip(qapp, env, no_dialogs):
    cfg, storage = env
    qc = QuickCaptureWindow(storage, cfg)
    qc.title_edit.setText("草稿标题")
    qc.body_edit.setPlainText("草稿正文")
    qc._save_draft()
    assert cfg.has_draft()
    # 模拟重启后的恢复
    qc2 = QuickCaptureWindow(storage, cfg)
    assert qc2.title_edit.text() == "草稿标题"
    assert qc2.body_edit.toPlainText() == "草稿正文"
    cfg.clear_draft()
    assert not cfg.has_draft()
    qc.close()
    qc2.close()


def _entry(title: str, body: str, d: date) -> object:
    from chronolog.core.models import LogEntry

    return LogEntry.new(datetime(d.year, d.month, d.day, 12, 0, 0), title=title, body=body)


def test_floating_button_position_persistence(qapp, env):
    from chronolog.ui.floating import FloatingButton

    cfg, storage = env
    fb = FloatingButton(cfg)
    assert fb.width() == 56 and fb.height() == 56
    # 默认位置应在屏幕内
    assert fb.x() >= 0 and fb.y() >= 0
    # 记录位置后，新实例应恢复
    cfg.settings.floating_pos_x = 300
    cfg.settings.floating_pos_y = 400
    fb2 = FloatingButton(cfg)
    assert (fb2.x(), fb2.y()) == (300, 400)


def test_floating_button_click_signal(qapp, env):
    from chronolog.ui.floating import FloatingButton

    cfg, storage = env
    fb = FloatingButton(cfg)
    received = []
    fb.quick_capture_requested.connect(lambda: received.append(1))
    fb.quick_capture_requested.emit()
    assert received == [1]


def test_config_floating_fields(qapp, env):
    cfg, storage = env
    assert cfg.settings.show_floating_window is True
    cfg.settings.show_floating_window = False
    cfg.save()
    cfg2 = Config()
    assert cfg2.settings.show_floating_window is False
