"""
Extract plain text from binary documents — the simplest possible text dump.

No formatting is preserved at all.  Use this when you just need the raw words
out of a file the Agent cannot read directly.  For structured output (headings,
lists, tables) use ``convert`` instead.

Supported this round:
    - DOCX → plain text (one paragraph per line)
    - PDF  → plain text (pages joined by a blank line)

Both formats support partial extraction via a 1-indexed inclusive range:
    - DOCX: paragraph range  (``--range 3-8`` → paragraphs 3 through 8)
    - PDF:  page range        (``--range 2-5``  → pages 2 through 5)

Range syntax: ``N`` (single), ``N-M`` (inclusive), ``N-`` (to end), ``-M`` (first M).
PPTX / XLSX are planned but not implemented yet.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.common import logger

# Matches "N", "N-M", "N-", "-M" (1-indexed).
_RANGE_RE = re.compile(r"^(?:(?P<start>\d+)?-(?P<end>\d+)?)|(?P<single>\d+)$")


def parse_range(spec: str | None) -> tuple[int | None, int | None]:
    """Parse a 1-indexed inclusive range spec.

    Returns ``(start, end)`` where ``None`` means unbounded on that side.
    ``(None, None)`` means "whole document" (no range given).

    Raises ``ValueError`` on a malformed spec.
    """
    if spec is None or spec.strip() == "":
        return None, None
    spec = spec.strip()
    m = _RANGE_RE.match(spec)
    if not m:
        raise ValueError(
            f"Invalid --range '{spec}' — expected N, N-M, N-, or -M (1-indexed)"
        )
    if m.group("single"):
        n = int(m.group("single"))
        return n, n
    start = int(m.group("start")) if m.group("start") else None
    end = int(m.group("end")) if m.group("end") else None
    if start is None and end is None:
        raise ValueError(f"Invalid --range '{spec}' — expected N, N-M, N-, or -M")
    return start, end


def _apply_range(items: list, start: int | None, end: int | None) -> list:
    """Apply a 1-indexed inclusive range to a list, clamped to its bounds."""
    total = len(items)
    s = (start - 1) if start else 0
    e = end if end is not None else total
    s = max(0, min(s, total))
    e = max(s, min(e, total))
    return items[s:e]


def extract_text(
    input_path: str | Path,
    fmt: str | None = None,
    range_spec: str | None = None,
) -> str:
    """Extract plain text from a document.

    Parameters
    ----------
    input_path : str | Path
        Path to the source document.
    fmt : str | None
        Force a format (``docx`` / ``pdf``).  Inferred from the file extension
        when omitted.
    range_spec : str | None
        Optional 1-indexed inclusive range (e.g. ``"3-8"``).  Semantics depend
        on the format: paragraphs for DOCX, pages for PDF.

    Returns
    -------
    str
        The extracted plain text.
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    fmt = (fmt or path.suffix.lstrip(".")).lower()
    start, end = parse_range(range_spec)

    if fmt == "docx":
        return _extract_docx(path, start, end)
    if fmt == "pdf":
        return _extract_pdf(path, start, end)
    if fmt in ("pptx", "xlsx"):
        raise NotImplementedError(
            f"extract for .{fmt} is planned but not yet implemented "
            f"(this round ships docx and pdf)."
        )
    raise ValueError(
        f"Unsupported format for extract: '.{fmt}' (supported: docx, pdf)"
    )


def _extract_docx(path: Path, start: int | None, end: int | None) -> str:
    """Dump DOCX body paragraph text — one paragraph per line, no formatting.

    Table cell text is intentionally excluded (use ``convert`` for tables).
    """
    from docx import Document

    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs]
    selected = _apply_range(paragraphs, start, end)
    logger.info(
        "DOCX extract: %d of %d paragraphs from %s",
        len(selected), len(paragraphs), path.name,
    )
    return "\n".join(selected)


def _extract_pdf(path: Path, start: int | None, end: int | None) -> str:
    """Dump PDF page text — non-empty pages joined by a blank line, no formatting."""
    import pypdf

    reader = pypdf.PdfReader(str(path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    selected = _apply_range(pages, start, end)
    non_empty = [p for p in selected if p]
    logger.info(
        "PDF extract: %d of %d pages from %s",
        len(non_empty), len(pages), path.name,
    )
    return "\n\n".join(non_empty)
