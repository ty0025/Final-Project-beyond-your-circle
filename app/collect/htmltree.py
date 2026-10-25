"""A tiny HTML tree for deterministic field extraction (stdlib only, no new dependency).

Good enough for the server-rendered pages of the connected sources: it tolerates unclosed
tags, skips script/style text, and keeps block boundaries as line breaks.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Callable, Iterator

VOID_TAGS = frozenset("area base br col embed hr img input link meta source track wbr".split())
SKIP_TEXT_TAGS = frozenset("script style noscript svg template head".split())
BLOCK_TAGS = frozenset(
    "address article aside blockquote dd div dl dt figcaption footer form h1 h2 h3 h4 h5 h6 header "
    "hr li main nav ol p pre section table tbody td th thead tr ul".split()
)

_SPACES = re.compile(r"[ \t\r\f\v ]+")


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: dict[str, str], parent: "Node | None" = None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list["Node | str"] = []
        self.parent = parent

    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    def iter(self) -> Iterator["Node"]:
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.iter()

    def find_all(
        self, tag: str | None = None, cls: str | None = None, pred: Callable[["Node"], bool] | None = None
    ) -> list["Node"]:
        return [
            node
            for node in self.iter()
            if (tag is None or node.tag == tag)
            and (cls is None or cls in node.classes())
            and (pred is None or pred(node))
        ]

    def find(
        self, tag: str | None = None, cls: str | None = None, pred: Callable[["Node"], bool] | None = None
    ) -> "Node | None":
        found = self.find_all(tag, cls, pred)
        return found[0] if found else None

    def text(self) -> str:
        """Visible text with one line per block element; runs of spaces collapsed."""
        parts: list[str] = []

        def walk(node: Node) -> None:
            for child in node.children:
                if isinstance(child, str):
                    parts.append(child)
                elif child.tag == "br":
                    parts.append("\n")
                elif child.tag not in SKIP_TEXT_TAGS:
                    block = child.tag in BLOCK_TAGS
                    if block:
                        parts.append("\n")
                    walk(child)
                    if block:
                        parts.append("\n")

        walk(self)
        lines = (_SPACES.sub(" ", line).strip() for line in "".join(parts).split("\n"))
        return "\n".join(line for line in lines if line)


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {})
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: (v or "") for k, v in attrs}, self._stack[-1])
        self._stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._stack[-1].children.append(Node(tag, {k: (v or "") for k, v in attrs}, self._stack[-1]))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)


def parse_html(text: str) -> Node:
    builder = _TreeBuilder()
    builder.feed(text)
    builder.close()
    return builder.root


def meta_content(root: Node, key: str) -> str | None:
    """Content of <meta property=key> or <meta name=key>."""
    for node in root.find_all("meta"):
        if node.attrs.get("property") == key or node.attrs.get("name") == key:
            value = (node.attrs.get("content") or "").strip()
            return value or None
    return None


def sentences(text: str) -> list[str]:
    """Split text into sentences/lines (keeps the original wording)."""
    out: list[str] = []
    for line in text.split("\n"):
        for piece in re.split(r"(?<=[.!?])\s+(?=[A-Z*(])", line):
            piece = piece.strip()
            if piece:
                out.append(piece)
    return out
