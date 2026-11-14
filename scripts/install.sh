#!/usr/bin/env bash
# ChronoLog 用户级安装脚本（Ubuntu）
#
# 将 ChronoLog 安装到当前用户：
#   1. 用 pip 安装 Python 包（默认安装到当前环境）。
#   2. 安装 .desktop 启动器与 SVG 图标到 ~/.local。
#
# 用法：
#   ./scripts/install.sh          # 普通安装
#   ./scripts/install.sh --dev    # 可编辑安装（开发模式）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

DEV=0
if [[ "${1:-}" == "--dev" ]]; then
    DEV=1
fi

PYTHON="${PYTHON:-python3}"
echo "==> 使用 Python: $PYTHON ($($PYTHON --version 2>&1))"

# 1. 安装 Python 包
cd "$PROJECT_DIR"
if [[ "$DEV" == "1" ]]; then
    echo "==> 可编辑安装 (pip install -e .)"
    "$PYTHON" -m pip install -e .
else
    echo "==> 安装 (pip install .)"
    "$PYTHON" -m pip install .
fi

# 2. 桌面集成
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$APPS_DIR" "$ICON_DIR" "$BIN_DIR"

# 确保 chronolog 命令在 PATH 中（若 pip 未安装到 ~/.local/bin）
CHRONOLOG_BIN="$(command -v chronolog || true)"
if [[ -z "$CHRONOLOG_BIN" ]]; then
    cat > "$BIN_DIR/chronolog" <<'EOF'
#!/usr/bin/env bash
exec python3 -m chronolog "$@"
EOF
    chmod +x "$BIN_DIR/chronolog"
    echo "==> 已创建 $BIN_DIR/chronolog 包装脚本（请确认 ~/.local/bin 在 PATH 中）"
fi

cp "$PROJECT_DIR/packaging/chronolog.desktop" "$APPS_DIR/chronolog.desktop"
cp "$PROJECT_DIR/src/chronolog/resources/icons/chronolog.svg" "$ICON_DIR/chronolog.svg"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_DIR" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f "$(dirname "$ICON_DIR")" || true

echo ""
echo "==> ChronoLog 安装完成。"
echo "    运行： chronolog          打开主窗口"
echo "    运行： chronolog --quick  快速记录"
echo "    若命令不可用，请确认 $BIN_DIR 在 PATH 中，或使用：$PYTHON -m chronolog"
