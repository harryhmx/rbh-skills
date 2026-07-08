"""
Convert binary documents to structured Markdown — preserves layout.

Companion to ``extract``: when you want *formatting* (not just raw words), use
convert.  When you want it *fast* and raw, use extract.

Supported this round:
    - DOCX → Markdown (headings, lists, bold/italic, tables)

DOCX path:
    1. Primary: ``python-docx`` walks the document in order and maps paragraph
       styles + run formatting to Markdown (precise style mapping).
    2. Fallback: when the DOCX XML is non-compliant and python-docx cannot load
       it, ``mammoth`` converts the file leniently as a safety net.

Inline image positions are marked with a textual ``(image)`` placeholder so the
Agent knows where pictures sat; the image files themselves are not extracted
(that is a heavier, separate operation).

PPTX is planned but not implemented yet.
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentType
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from scripts.common import logger


def iter_block_items(parent):
    """Yield each Paragraph and Table child of *parent* in document order."""
    if isinstance(parent, _Cell):
        parent_elm = parent._tc
    elif isinstance(parent, DocumentType):
        parent_elm = parent.element.body
    else:
        raise ValueError("Unsupported parent type for iter_block_items")
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def convert_to_md(input_path: str | Path, fmt: str | None = None) -> str:
    """Convert a document to structured Markdown.

    Parameters
    ----------
    input_path : str | Path
        Path to the source document.
    fmt : str | None
        Force a format (``docx``).  Inferred from the file extension when omitted.

    Returns
    -------
    str
        The converted Markdown text.
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    fmt = (fmt or path.suffix.lstrip(".")).lower()
    if fmt == "docx":
        return _convert_docx(path)
    if fmt == "pptx":
        raise NotImplementedError(
            "convert for .pptx is planned but not yet implemented "
            "(this round ships docx)."
        )
    raise ValueError(
        f"Unsupported format for convert: '.{fmt}' (supported: docx)"
    )


# ---------------------------------------------------------------------------
# DOCX → Markdown (python-docx primary, mammoth fallback)
# ---------------------------------------------------------------------------


def _convert_docx(path: Path) -> str:
    try:
        doc = Document(str(path))
    except Exception as exc:  # non-compliant / corrupted XML
        logger.warning(
            "python-docx could not load %s (%s) — falling back to mammoth",
            path.name, exc,
        )
        return _convert_docx_mammoth(path)

    lines: list[str] = []
    # Track numbered-list numbering across consecutive numbered paragraphs.
    list_counter = 0
    in_numbered_list = False

    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            body, list_type = _paragraph_to_md(block)
            if body is None:
                continue
            if list_type == "number":
                if not in_numbered_list:
                    list_counter = 0
                    in_numbered_list = True
                list_counter += 1
                lines.append(f"{list_counter}. {body}")
            else:
                in_numbered_list = False
                if list_type == "bullet":
                    lines.append(f"- {body}")
                else:
                    lines.append(body)
        elif isinstance(block, Table):
            in_numbered_list = False
            table_md = _table_to_md(block)
            if table_md:
                lines.append(table_md)

    logger.info("DOCX convert: %d blocks from %s", len(lines), path.name)
    return "\n\n".join(lines)


def _convert_docx_mammoth(path: Path) -> str:
    """Lenient fallback: mammoth's built-in DOCX → Markdown conversion."""
    import mammoth

    path = Path(path)
    with open(path, "rb") as fh:
        result = mammoth.convert_to_markdown(fh)
    logger.info("DOCX convert via mammoth fallback: %s", path.name)
    return result.value


def _heading_level(paragraph: Paragraph) -> int | None:
    """Return Markdown heading level (1–6) for the paragraph, or None.

    Checks the paragraph style name first ("Heading N", "Title"), then falls
    back to the outline level in the XML (which survives custom style names).
    """
    style_name = (paragraph.style.name if paragraph.style else "") or ""
    low = style_name.lower()
    if low.startswith("heading") or low.startswith("标题"):
        m = re.search(r"(\d+)", style_name)
        n = int(m.group(1)) if m else 1
        return max(1, min(n, 6))
    if low == "title" or low == "标题":
        return 1

    pPr = paragraph._element.find(qn("w:pPr"))
    if pPr is not None:
        outline = pPr.find(qn("w:outlineLvl"))
        if outline is not None:
            val = outline.get(qn("w:val"))
            if val is not None and val.lstrip("-").isdigit():
                n = int(val) + 1  # outlineLvl is 0-based
                if 1 <= n <= 6:
                    return n
    return None


def _list_kind(paragraph: Paragraph) -> str | None:
    """Return ``"bullet"`` / ``"number"`` for list-style paragraphs, else None."""
    name = (paragraph.style.name if paragraph.style else "") or ""
    low = name.lower()
    if "bullet" in low or "项目符号" in low:
        return "bullet"
    if "number" in low or "编号" in low:
        return "number"
    return None


def _count_images(paragraph: Paragraph) -> int:
    """Count inline images (drawings) carried by the paragraph's runs."""
    count = 0
    for run in paragraph.runs:
        if "pic:pic" in run._element.xml or "<w:drawing" in run._element.xml:
            count += 1
    return count


def _format_run(run) -> str:
    """Render a single run's text with bold/italic Markdown markers."""
    text = run.text or ""
    if not text:
        return ""
    bold = bool(run.bold)
    italic = bool(run.italic)
    if bold and italic:
        return f"***{text}***"
    if bold:
        return f"**{text}**"
    if italic:
        return f"*{text}*"
    return text


def _paragraph_to_md(paragraph: Paragraph) -> tuple[str | None, str | None]:
    """Convert a paragraph to a Markdown line.

    Returns ``(body, list_kind)`` where:
      - ``body`` is the rendered text WITHOUT any list prefix (the caller adds
        ``- `` or ``N. ``), or a fully-rendered heading/image line, or ``None``
        to mean "emit nothing".
      - ``list_kind`` is ``"bullet"`` / ``"number"`` / ``None``.
    """
    image_count = _count_images(paragraph)
    body = "".join(_format_run(run) for run in paragraph.runs).strip()
    if not body and image_count == 0:
        return None, None

    level = _heading_level(paragraph)
    if level is not None and body:
        # Headings drop inline formatting markers for clean titles.
        clean = re.sub(r"\*+", "", body)
        return f"{'#' * level} {clean}", None

    list_kind = _list_kind(paragraph)

    image_marker = " ".join(["(image)"] * image_count)
    if not body:
        return image_marker, None
    if image_count:
        body = f"{body} {image_marker}"

    return body, list_kind


def _table_to_md(table: Table) -> str:
    """Render a DOCX table as a GitHub-flavored Markdown table."""
    rows = []
    for row in table.rows:
        cells = [
            cell.text.strip().replace("|", "\\|").replace("\n", " ")
            for cell in row.cells
        ]
        rows.append("| " + " | ".join(cells) + " |")
    if not rows:
        return ""
    ncols = max(len(table.rows[0].cells), 1)
    separator = "| " + " | ".join(["---"] * ncols) + " |"
    return "\n".join([rows[0], separator, *rows[1:]])
