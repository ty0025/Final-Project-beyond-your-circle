"""Make an HTML file self-contained by embedding its local images as base64 data URIs.

Usage (from the repo root):
    python scripts/inline_images.py report.html                 # -> report.inline.html
    python scripts/inline_images.py slides.html slides_final.html

Every <img src="..."> that points to a local .png/.jpg/.jpeg/.gif/.svg/.webp file (relative to
the HTML file, or absolute) is replaced by a data: URI. http(s)://, protocol-relative and data:
sources are left alone. Missing or unsupported files produce a warning and are left unchanged.
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}

# The src attribute inside an <img ...> tag: double-quoted, single-quoted or unquoted.
IMG_SRC_RE = re.compile(
    r"""(?P<prefix><img\b[^>]*?\ssrc\s*=\s*)(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<uq>[^\s"'>]+))""",
    re.IGNORECASE | re.DOTALL,
)
REMOTE_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.IGNORECASE)  # any scheme, or protocol-relative
WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:[\\/]")


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def resolve_local(src: str, base_dir: Path) -> Path | None:
    """Local file path for an <img src>, or None if it is remote / data / some other scheme."""
    src = src.strip()
    if not src:
        return None
    if WINDOWS_DRIVE_RE.match(src):  # C:\... or C:/... looks like a URL scheme but is a local path
        return Path(src)
    if REMOTE_RE.match(src):  # http:, https:, data:, //host/...
        return None
    path = Path(unquote(urlsplit(src).path))  # drop ?query / #fragment, decode %20
    return path if path.is_absolute() else base_dir / path


def inline_images(html: str, base_dir: Path) -> tuple[str, int, int]:
    """Return (new_html, embedded_count, embedded_bytes)."""
    embedded = 0
    total_bytes = 0

    def replace(match: re.Match) -> str:
        nonlocal embedded, total_bytes
        src = next(g for g in (match.group("dq"), match.group("sq"), match.group("uq")) if g is not None)
        path = resolve_local(src, base_dir)
        if path is None:
            return match.group(0)
        mime = MIME_TYPES.get(path.suffix.lower())
        if mime is None:
            warn(f"unsupported image type, left as is: {src}")
            return match.group(0)
        if not path.is_file():
            warn(f"image not found, left as is: {src} (looked for {path})")
            return match.group(0)
        data = path.read_bytes()
        embedded += 1
        total_bytes += len(data)
        uri = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
        return f'{match.group("prefix")}"{uri}"'

    return IMG_SRC_RE.sub(replace, html), embedded, total_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed local <img> files in an HTML file as base64 data URIs.")
    parser.add_argument("input", help="HTML file to read")
    parser.add_argument("output", nargs="?", help="where to write the result (default: <input>.inline.html)")
    args = parser.parse_args(argv)

    src_path = Path(args.input)
    if not src_path.is_file():
        print(f"error: {src_path} not found", file=sys.stderr)
        return 2
    out_path = Path(args.output) if args.output else src_path.with_name(f"{src_path.stem}.inline{src_path.suffix}")

    html = src_path.read_text(encoding="utf-8")
    result, count, size = inline_images(html, src_path.resolve().parent)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result, encoding="utf-8")
    print(f"Embedded {count} image(s) ({size / 1024:,.1f} KB) -> {out_path}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
