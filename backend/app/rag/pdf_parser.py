"""
Page-aware PDF parsing for multimodal ingestion.

Extracts per-page text and tables (as Markdown) with pdfplumber (MIT) and
renders page screenshots with pypdfium2 (BSD-3-Clause). Both libraries are
permissively licensed and run fully offline: no external API calls.

The parsed segments carry page numbers and a kind ("text" or "table") so
every chunk stored in the vector index knows exactly which page it came
from, and the rendered page images let a user open the original page behind
any citation to check the evidence themselves.
"""
import logging
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Dict, List

import pdfplumber
import pypdfium2 as pdfium

try:  # pdfminer renamed the password error across releases
    from pdfminer.pdfdocument import PDFPasswordIncorrect as _PDFPasswordError
except ImportError:  # older pdfminer.six
    try:
        from pdfminer.pdfdocument import PDFPasswordError as _PDFPasswordError
    except ImportError:
        from pdfminer.pdfexceptions import PDFPasswordError as _PDFPasswordError


def _bbox_within(inner, outer) -> bool:
    """True when bbox inner=(x0, top, x1, bottom) is fully inside outer."""
    return (
        inner[0] >= outer[0]
        and inner[1] >= outer[1]
        and inner[2] <= outer[2]
        and inner[3] <= outer[3]
    )

logger = logging.getLogger(__name__)


class PDFParseError(Exception):
    """Raised when a PDF cannot be parsed (malformed, encrypted, ...)."""


@dataclass
class PDFPage:
    """Parsed content of a single page (1-based page numbers)."""

    page_number: int
    text: str
    tables: List[str] = field(default_factory=list)  # Markdown tables
    image_count: int = 0


@dataclass
class ParsedPDF:
    """Whole-document parse result."""

    page_count: int
    pages: List[PDFPage]


def _cell_to_text(cell) -> str:
    """Normalize a table cell for Markdown output."""
    if cell is None:
        return ""
    return str(cell).replace("\n", " ").replace("|", "\\|").strip()


def _table_to_markdown(rows: List[list]) -> str:
    """Render extracted table rows as a GitHub-flavored Markdown table."""
    cleaned = [[_cell_to_text(c) for c in row] for row in rows if row]
    cleaned = [row for row in cleaned if any(row)]
    if len(cleaned) < 2:
        return ""
    width = max(len(row) for row in cleaned)
    if width < 2:
        return ""
    cleaned = [row + [""] * (width - len(row)) for row in cleaned]
    header, body = cleaned[0], cleaned[1:]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def _extract_page(page) -> PDFPage:
    """Extract text (outside table regions), tables and image count."""
    tables_md: List[str] = []
    table_bboxes: List[tuple] = []
    try:
        for table in page.find_tables():
            markdown = _table_to_markdown(table.extract())
            if markdown:
                tables_md.append(markdown)
                table_bboxes.append(table.bbox)
    except Exception as e:
        logger.warning(f"Table detection failed on page {page.page_number}: {e}")

    def outside_tables(obj) -> bool:
        bbox = obj.get("bbox")
        if bbox is None:
            # chars/lines/rects expose x0/top/x1/bottom instead
            try:
                bbox = (obj["x0"], obj["top"], obj["x1"], obj["bottom"])
            except KeyError:
                return True
        return not any(_bbox_within(bbox, tb) for tb in table_bboxes)

    try:
        if table_bboxes:
            text = page.filter(outside_tables).extract_text() or ""
        else:
            text = page.extract_text() or ""
    except Exception as e:
        logger.warning(f"Text extraction failed on page {page.page_number}: {e}")
        text = ""

    return PDFPage(
        page_number=page.page_number,
        text=text.strip(),
        tables=tables_md,
        image_count=len(page.images),
    )


def parse_pdf(content: bytes) -> ParsedPDF:
    """
    Parse a PDF into page-aware text and table structures.

    Raises PDFParseError for malformed or password-protected input.
    """
    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            pages = [_extract_page(page) for page in pdf.pages]
    except _PDFPasswordError as e:
        raise PDFParseError("PDF is password-protected") from e
    except Exception as e:
        raise PDFParseError(f"Could not parse PDF: {e}") from e

    if not pages:
        raise PDFParseError("PDF has no pages")

    return ParsedPDF(page_count=len(pages), pages=pages)


def pages_to_segments(parsed: ParsedPDF) -> List[Dict]:
    """
    Convert parsed pages into ingestion segments.

    Each segment is a dict with content plus page_number and kind metadata,
    ready to be chunked and embedded with its provenance attached.
    """
    segments: List[Dict] = []
    for page in parsed.pages:
        if page.text:
            segments.append({
                "content": page.text,
                "page_number": page.page_number,
                "kind": "text",
            })
        for table_md in page.tables:
            segments.append({
                "content": f"Table from page {page.page_number}:\n{table_md}",
                "page_number": page.page_number,
                "kind": "table",
            })
    return segments


def render_page_images(
    content: bytes,
    document_id: str,
    output_dir: str,
    max_pages: int = 100,
    scale: float = 1.5,
) -> Dict[int, Path]:
    """
    Render page screenshots (PNG, ~108 DPI at default scale) to
    <output_dir>/<document_id>/page-<n>.png so citations can link to the
    original page. Returns a mapping of 1-based page number to file path.

    Raises PDFParseError if the document cannot be rendered.
    """
    out_dir = Path(output_dir) / document_id
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        pdf = pdfium.PdfDocument(content)
    except Exception as e:
        raise PDFParseError(f"Could not render PDF: {e}") from e

    written: Dict[int, Path] = {}
    try:
        page_total = min(len(pdf), max_pages)
        for index in range(page_total):
            page = pdf[index]
            try:
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
            finally:
                page.close()
            path = out_dir / f"page-{index + 1}.png"
            image.save(path, "PNG")
            written[index + 1] = path
    finally:
        pdf.close()

    logger.info(f"Rendered {len(written)} page images for document {document_id}")
    return written
