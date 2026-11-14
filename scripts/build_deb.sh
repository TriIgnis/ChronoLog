#!/usr/bin/env bash
# ChronoLog .deb 打包脚本（best-effort）
#
# 生成一个包含 ChronoLog 源码、launcher、.desktop 与图标的 Debian 包。
# 注意：.deb 声明依赖 python3；运行时还需 PySide6、markdown-it-py 等 Python
# 依赖（可通过 pip 安装，或使用 venv 方式）。此 .deb 便于桌面集成，但依赖
# Python 环境中的第三方库。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION="0.1.0"
ARCH="all"

BUILD_DIR="$(mktemp -d)"
STAGE="$BUILD_DIR/chronolog_${VERSION}_${ARCH}"
DEBIAN="$STAGE/DEBIAN"

mkdir -p "$DEBIAN"

# 1. 将源码包复制到固定位置（纯 Python，避免依赖具体 Python 环境的 site-packages）
cd "$PROJECT_DIR"
mkdir -p "$STAGE/usr/lib/chronolog"
cp -r src/chronolog "$STAGE/usr/lib/chronolog/chronolog"
find "$STAGE/usr/lib/chronolog" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# 2. control 文件
cat > "$DEBIAN/control" <<EOF
Package: chronolog
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: ChronoLog Developers <chronolog@example.com>
Depends: python3
Description: Markdown 时间线日志软件
 ChronoLog 是面向 Ubuntu 科研与学习的本地优先 Markdown 每日日志工具。
 提供快速记录、自动时间戳、每日归档、时间线浏览与全文搜索。
EOF

# 3. launcher
mkdir -p "$STAGE/usr/bin"
cat > "$STAGE/usr/bin/chronolog" <<'EOF'
#!/bin/sh
PYTHONPATH=/usr/lib/chronolog exec python3 -m chronolog "$@"
EOF
chmod 755 "$STAGE/usr/bin/chronolog"

# 4. 桌面文件与图标
mkdir -p "$STAGE/usr/share/applications" "$STAGE/usr/share/icons/hicolor/scalable/apps"
cp "$PROJECT_DIR/packaging/chronolog.desktop" "$STAGE/usr/share/applications/chronolog.desktop"
cp "$PROJECT_DIR/src/chronolog/resources/icons/chronolog.svg" \
   "$STAGE/usr/share/icons/hicolor/scalable/apps/chronolog.svg"

# 5. 构建
command -v dpkg-deb >/dev/null 2>&1 || { echo "错误：未找到 dpkg-deb"; exit 1; }
dpkg-deb --build --root-owner-group "$STAGE" "$PROJECT_DIR/dist/chronolog_${VERSION}_${ARCH}.deb"

echo ""
echo "==> 已生成：dist/chronolog_${VERSION}_${ARCH}.deb"
echo "    安装： sudo dpkg -i dist/chronolog_${VERSION}_${ARCH}.deb"
echo "    注意：仍需 pip 安装 PySide6、markdown-it-py（见 README）。"
