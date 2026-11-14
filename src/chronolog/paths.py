"""包内资源路径。"""

from __future__ import annotations

from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = SRC_DIR / "resources"
ICONS_DIR = RESOURCES_DIR / "icons"
STYLES_DIR = RESOURCES_DIR / "styles"

APP_ICON = ICONS_DIR / "chronolog.svg"
