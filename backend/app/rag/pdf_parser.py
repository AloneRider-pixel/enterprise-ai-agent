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
import shutil
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber
import pypdfium2 as pdfium

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - pypdf is a hard dependency
    PdfReader = None

try:
    from app.config import settings
except Exception:  # allow standalone parser use in tests without app settings
    settings = None

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

# Minimum side length for an embedded image to be worth reading (skips icons)
_MIN_IMAGE_SIDE = 120
# Pages whose extracted prose is thinner than this are treated as image-led
_THIN_TEXT_CHARS = 60


class PDFParseError(Exception):
    """Raised when a PDF cannot be parsed (malformed, encrypted, ...)."""


@dataclass
class PDFPage:
    """Parsed content of a single page (1-based page numbers)."""

    page_number: int
    text: str
    tables: List[str] = field(default_factory=list)  # Markdown tables
    image_count: int = 0
    image_descriptions: List[str] = field(default_factory=list)  # OCR/captions


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


# ─── Image content reading: OCR + local captioning ───

_captioner = None
_captioner_failed = False


def _ocr_available() -> bool:
    """OCR needs the tesseract binary and pytesseract; both optional."""
    if not _setting("enable_pdf_ocr", True):
        return False
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def _ocr_image(image) -> str:
    """Extract visible text from an image via tesseract. Returns '' on failure."""
    if not _ocr_available():
        return ""
    try:
        import pytesseract

        text = pytesseract.image_to_string(image)
        return " ".join(text.split())
    except Exception as e:
        logger.warning(f"OCR failed: {e}")
        return ""


def _load_captioner():
    """
    Lazy-load a local image captioning model (vit-gpt2). Runs fully offline
    after a one-time model download; no API calls or keys. Returns a
    (model, processor, tokenizer) tuple, or None when unavailable.
    """
    global _captioner, _captioner_failed
    if _captioner is not None or _captioner_failed:
        return _captioner
    if not _setting("enable_pdf_image_captions", True):
        _captioner_failed = True
        return None
    try:
        import torch  # noqa: F401
        from transformers import (
            AutoImageProcessor,
            AutoTokenizer,
            VisionEncoderDecoderModel,
        )

        name = "nlpconnect/vit-gpt2-image-captioning"
        _captioner = (
            VisionEncoderDecoderModel.from_pretrained(name),
            AutoImageProcessor.from_pretrained(name),
            AutoTokenizer.from_pretrained(name),
        )
        logger.info("Local image captioning model loaded")
    except Exception as e:
        logger.warning(f"Image captioning unavailable ({e}); OCR still applies")
        _captioner_failed = True
        _captioner = None
    return _captioner


def _caption_image(image) -> str:
    """Caption a diagram/screenshot with the local model. '' if unavailable."""
    loaded = _load_captioner()
    if loaded is None:
        return ""
    model, processor, tokenizer = loaded
    try:
        import torch

        pixel_values = processor(
            images=image.convert("RGB"), return_tensors="pt"
        ).pixel_values
        with torch.no_grad():
            output = model.generate(pixel_values, max_new_tokens=30)
        return tokenizer.decode(output[0], skip_special_tokens=True).strip()
    except Exception as e:
        logger.warning(f"Captioning failed: {e}")
        return ""


def _setting(name: str, default):
    if settings is None:
        return default
    return getattr(settings, name, default)


def _embedded_page_images(content: bytes) -> Dict[int, List]:
    """Extract embedded raster images per page via pypdf (PIL images)."""
    if PdfReader is None:
        return {}
    images_by_page: Dict[int, List] = {}
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            return {}
        for index, page in enumerate(reader.pages, 1):
            page_images = []
            try:
                for image_file in page.images:
                    image = image_file.image
                    if image.width >= _MIN_IMAGE_SIDE and image.height >= _MIN_IMAGE_SIDE:
                        page_images.append(image.convert("RGB"))
            except Exception as e:
                logger.warning(f"Image extraction failed on page {index}: {e}")
            if page_images:
                images_by_page[index] = page_images
    except Exception as e:
        logger.warning(f"Embedded image scan failed: {e}")
    return images_by_page


def _describe_image(image, page_number: int, ordinal: int) -> Optional[str]:
    """Build a text description of one image: caption plus visible text."""
    caption = _caption_image(image)
    ocr_text = _ocr_image(image)
    if not caption and not ocr_text:
        return None
    parts = [f"Image {ordinal} on page {page_number}."]
    if caption:
        parts.append(f"Picture shows: {caption}.")
    if ocr_text:
        parts.append(f"Text visible in image: {ocr_text}")
    return " ".join(parts)


def parse_pdf(content: bytes) -> ParsedPDF:
    """
    Parse a PDF into page-aware text, tables and image descriptions.

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

    _attach_image_descriptions(content, pages)
    return ParsedPDF(page_count=len(pages), pages=pages)


def _attach_image_descriptions(content: bytes, pages: List[PDFPage]) -> None:
    """Read embedded images (OCR + caption) onto their pages, and OCR
    image-led pages whose extracted prose is thin (scans, screenshots)."""
    images_by_page = _embedded_page_images(content)

    for page in pages:
        embedded = images_by_page.get(page.page_number, [])
        for ordinal, image in enumerate(embedded, 1):
            description = _describe_image(image, page.page_number, ordinal)
            if description:
                page.image_descriptions.append(description)

        prose_chars = len(page.text) + sum(len(t) for t in page.tables)
        if prose_chars < _THIN_TEXT_CHARS and not page.image_descriptions:
            # Scanned or screenshot page: OCR the rendered page itself.
            page_image = _render_single_page(content, page.page_number)
            if page_image is not None:
                ocr_text = _ocr_image(page_image)
                if ocr_text:
                    page.image_descriptions.append(
                        f"Page {page.page_number} is a scanned/image page. "
                        f"Text read from it: {ocr_text}"
                    )


def _render_single_page(content: bytes, page_number: int):
    """Render one page to a PIL image for OCR of scanned pages."""
    try:
        pdf = pdfium.PdfDocument(content)
        try:
            page = pdf[page_number - 1]
            try:
                return page.render(scale=2.0).to_pil()
            finally:
                page.close()
        finally:
            pdf.close()
    except Exception as e:
        logger.warning(f"Could not render page {page_number} for OCR: {e}")
        return None


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
        for description in page.image_descriptions:
            segments.append({
                "content": description,
                "page_number": page.page_number,
                "kind": "image",
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
