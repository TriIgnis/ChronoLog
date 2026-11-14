"""配置管理与草稿保护。

配置与草稿遵循 Linux XDG 规范：

- 配置：``$XDG_CONFIG_HOME/chronolog/config.json``
- 草稿：``$XDG_DATA_HOME/chronolog/drafts/``

不混入正式日志目录。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _xdg_dir(env_var: str, fallback: Path) -> Path:
    value = os.environ.get(env_var)
    if value and os.path.isabs(value):
        return Path(value)
    return fallback


def config_dir() -> Path:
    return _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config") / "chronolog"


def data_dir() -> Path:
    return _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share") / "chronolog"


def default_log_root() -> Path:
    return Path.home() / "Documents" / "ChronoLog"


@dataclass
class Settings:
    log_root_dir: str = field(default_factory=lambda: str(default_log_root()))
    theme: str = "light"  # "light" | "dark"
    editor_font_size: int = 12
    auto_close_after_save: bool = True
    startup_behavior: str = "main"  # "main" | "quick" | "last"


class Config:
    """持久化配置 + 快速记录草稿。"""

    def __init__(self, settings_path: Path | None = None) -> None:
        self._path = settings_path or (config_dir() / "config.json")
        self._draft_path = data_dir() / "drafts" / "quick.json"
        self.settings = self._load()

    # ---- 配置 ----
    def _load(self) -> Settings:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return Settings()
        base = Settings()
        for key in asdict(base):
            if key in data:
                setattr(base, key, data[key])
        return base

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(asdict(self.settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)

    # ---- 草稿 ----
    def save_draft(self, title: str, body: str, timestamp_iso: str | None = None) -> None:
        draft = {
            "title": title,
            "body": body,
            "timestamp": timestamp_iso,
        }
        self._draft_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._draft_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._draft_path)

    def load_draft(self) -> dict | None:
        try:
            data = json.loads(self._draft_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            return None
        return None

    def clear_draft(self) -> None:
        try:
            self._draft_path.unlink()
        except OSError:
            pass

    def has_draft(self) -> bool:
        return self._draft_path.exists()
