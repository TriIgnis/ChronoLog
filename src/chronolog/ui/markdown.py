"""Markdown 渲染与语法高亮。

- :func:`markdown_to_html` 使用 markdown-it-py 渲染标准 Markdown。
- :class:`MarkdownHighlighter` 基于 QSyntaxHighlighter 提供源码高亮。
"""

from __future__ import annotations

import re

from markdown_it import MarkdownIt
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

_MD = MarkdownIt("commonmark").enable("table").enable("strikethrough")


def markdown_to_html(text: str) -> str:
    """将 Markdown 源码渲染为 HTML 片段（不含 html/body 包装）。"""
    return _MD.render(text or "")


_LIGHT_CSS = """
body { font-family: 'Noto Sans', 'Noto Sans CJK SC', 'WenQuanYi Micro Hei', sans-serif;
       font-size: 14px; color: #1f2430; }
h1, h2, h3, h4 { color: #12324a; }
a { color: #2f7da5; }
code { font-family: 'DejaVu Sans Mono', 'Noto Sans Mono CJK SC', monospace;
       background: #eceff3; padding: 1px 4px; border-radius: 3px; color: #b0433a; }
pre { background: #eceff3; padding: 10px; border-radius: 6px; overflow-x: auto; }
pre code { background: transparent; padding: 0; color: #1f2430; }
blockquote { border-left: 3px solid #c8ccd4; margin: 8px 0; padding: 2px 12px; color: #55606e; }
table { border-collapse: collapse; }
th, td { border: 1px solid #c8ccd4; padding: 4px 10px; }
th { background: #eceff3; }
hr { border: none; border-top: 1px solid #c8ccd4; }
"""

_DARK_CSS = """
body { font-family: 'Noto Sans', 'Noto Sans CJK SC', 'WenQuanYi Micro Hei', sans-serif;
       font-size: 14px; color: #d6dae2; }
h1, h2, h3, h4 { color: #eaf3fa; }
a { color: #7fd1e8; }
code { font-family: 'DejaVu Sans Mono', 'Noto Sans Mono CJK SC', monospace;
       background: #2a3040; padding: 1px 4px; border-radius: 3px; color: #e58a80; }
pre { background: #2a3040; padding: 10px; border-radius: 6px; overflow-x: auto; }
pre code { background: transparent; padding: 0; color: #d6dae2; }
blockquote { border-left: 3px solid #363c4a; margin: 8px 0; padding: 2px 12px; color: #8a93a2; }
table { border-collapse: collapse; }
th, td { border: 1px solid #363c4a; padding: 4px 10px; }
th { background: #2a3040; }
hr { border: none; border-top: 1px solid #363c4a; }
"""


def render_html_document(body: str, dark: bool = False) -> str:
    """渲染完整 HTML 文档，供 QTextBrowser 预览使用。"""
    css = _DARK_CSS if dark else _LIGHT_CSS
    html = markdown_to_html(body)
    return f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{html}</body></html>"


# --------------------------------------------------------------------------- #
# 语法高亮
# --------------------------------------------------------------------------- #

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_RULER_RE = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
_QUOTE_RE = re.compile(r"^\s{0,3}>\s?")
_LIST_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
_FENCE_RE = re.compile(r"^\s*```")
_BOLD_RE = re.compile(r"(\*\*|__)(.+?)\1")
_ITALIC_RE = re.compile(r"(\*|_)([^*_]+?)\1")
_CODE_RE = re.compile(r"`([^`]+)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")


class MarkdownHighlighter(QSyntaxHighlighter):
    """Markdown 源码语法高亮。"""

    def __init__(self, document) -> None:
        super().__init__(document)
        self._in_fence = False
        self._heading = QTextCharFormat()
        self._heading.setForeground(QColor("#2f7da5"))
        self._heading.setFontWeight(QFont.Bold)
        self._ruler = QTextCharFormat()
        self._ruler.setForeground(QColor("#9aa3af"))
        self._quote = QTextCharFormat()
        self._quote.setForeground(QColor("#6a9955"))
        self._quote.setFontItalic(True)
        self._list = QTextCharFormat()
        self._list.setForeground(QColor("#d19a66"))
        self._bold = QTextCharFormat()
        self._bold.setFontWeight(QFont.Bold)
        self._italic = QTextCharFormat()
        self._italic.setFontItalic(True)
        self._code = QTextCharFormat()
        self._code.setForeground(QColor("#c7254e"))
        self._code.setFontFamilies(["DejaVu Sans Mono", "Noto Sans Mono CJK SC"])
        self._fence = QTextCharFormat()
        self._fence.setForeground(QColor("#c7254e"))
        self._fence.setFontFamilies(["DejaVu Sans Mono", "Noto Sans Mono CJK SC"])
        self._link = QTextCharFormat()
        self._link.setForeground(QColor("#2f7da5"))
        self._comment = QTextCharFormat()
        self._comment.setForeground(QColor("#9aa3af"))

    def _apply(self, text: str, pattern, fmt: QTextCharFormat, group: int = 0) -> None:
        for m in pattern.finditer(text):
            self.setFormat(m.start(group), len(m.group(group)), fmt)

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt 命名)
        if _FENCE_RE.match(text):
            self.setFormat(0, len(text), self._fence)
            self._in_fence = not self._in_fence
            return
        if self._in_fence:
            self.setFormat(0, len(text), self._fence)
            return

        if _COMMENT_RE.match(text):
            self.setFormat(0, len(text), self._comment)
            return

        hm = _HEADING_RE.match(text)
        if hm:
            self.setFormat(0, len(text), self._heading)
            return

        if _RULER_RE.match(text):
            self.setFormat(0, len(text), self._ruler)
            return

        if _QUOTE_RE.match(text):
            self.setFormat(0, len(text), self._quote)

        lm = _LIST_RE.match(text)
        if lm:
            self.setFormat(lm.start(1), len(lm.group(1)), self._list)

        # 行内元素（按顺序应用，后者优先合并）
        self._apply(text, _CODE_RE, self._code)
        self._apply(text, _LINK_RE, self._link)
        self._apply(text, _BOLD_RE, self._bold, group=2)
        self._apply(text, _ITALIC_RE, self._italic, group=2)
