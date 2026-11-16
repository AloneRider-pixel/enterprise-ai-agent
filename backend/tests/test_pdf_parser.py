"""Tests for the multimodal PDF parser: page-aware text, tables, screenshots.

All fixtures are synthetic PDFs generated in-memory with reportlab.
No database, network, or LLM calls. OCR tests skip without a tesseract
binary; captioning is disabled by default and covered by an opt-in test
(set RUN_CAPTION_TESTS=1) since it downloads a local model.
"""
import os
import shutil
from io import BytesIO

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from app.rag import pdf_parser
from app.rag.pdf_parser import (
    PDFParseError,
    pages_to_segments,
    parse_pdf,
    render_page_images,
)


@pytest.fixture(autouse=True)
def no_caption_model(monkeypatch):
    """Keep unit tests offline: stub the captioner unless opted in."""
    if not os.environ.get("RUN_CAPTION_TESTS"):
        monkeypatch.setattr(pdf_parser, "_load_captioner", lambda: None)


def _build_fixture_pdf() -> bytes:
    """Two-page PDF: prose on page 1, a bordered table + prose on page 2."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    story = [
        Paragraph("Support Handbook", styles["Title"]),
        Spacer(1, 12),
        Paragraph(
            "Refund policy: customers can request a refund within 30 days "
            "of purchase by contacting the support team.",
            styles["BodyText"],
        ),
        PageBreak(),
        Paragraph("Plans and pricing", styles["Heading2"]),
        Spacer(1, 6),
    ]
    table = Table(
        [
            ["Plan", "Monthly price", "Support channel"],
            ["Basic", "$10", "Email"],
            ["Pro", "$25", "Priority 24/7"],
        ]
    )
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    story.append(table)
    story.append(Spacer(1, 6))
    story.append(Paragraph("All prices are in USD.", styles["BodyText"]))

    doc.build(story)
    return buffer.getvalue()


def _text_image(text: str, path: str) -> str:
    """Render text into a PNG (a synthetic 'screenshot')."""
    image = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 80), text, fill="black")
    image.save(path)
    return path


def _build_screenshot_pdf(tmp_path) -> bytes:
    """One page whose main content is an embedded screenshot with text."""
    shot = _text_image("System status: all services operational", str(tmp_path / "shot.png"))
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawImage(shot, 60, 500, width=600, height=200)
    c.showPage()
    c.save()
    return buffer.getvalue()


def _build_scanned_pdf(tmp_path) -> bytes:
    """A page that is only a scanned image (no embedded text layer)."""
    scan = _text_image("Scanned invoice total due 42 dollars", str(tmp_path / "scan.png"))
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawImage(scan, 60, 400, width=600, height=200)
    c.showPage()
    c.save()
    return buffer.getvalue()


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract binary not installed")
class TestImageContentReading:
    def test_embedded_screenshot_text_is_read(self, tmp_path):
        pdf = _build_screenshot_pdf(tmp_path)
        segments = pages_to_segments(parse_pdf(pdf))
        image_segments = [s for s in segments if s["kind"] == "image"]
        assert image_segments, "expected an image segment for the screenshot page"
        assert image_segments[0]["page_number"] == 1
        assert "operational" in image_segments[0]["content"]

    def test_scanned_page_is_ocr_read(self, tmp_path):
        pdf = _build_scanned_pdf(tmp_path)
        segments = pages_to_segments(parse_pdf(pdf))
        image_segments = [s for s in segments if s["kind"] == "image"]
        assert image_segments, "expected an OCR segment for the scanned page"
        assert "invoice" in image_segments[0]["content"]

    def test_tiny_images_are_skipped(self, tmp_path):
        tiny = Image.new("RGB", (16, 16), "white")
        tiny_path = str(tmp_path / "tiny.png")
        tiny.save(tiny_path)
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.drawImage(tiny_path, 60, 500, width=16, height=16)
        c.drawString(60, 400, "Ordinary text page with enough prose content to index here without any fallback.")
        c.showPage()
        c.save()
        segments = pages_to_segments(parse_pdf(buffer.getvalue()))
        assert all(s["kind"] != "image" for s in segments)


@pytest.mark.skipif(
    not os.environ.get("RUN_CAPTION_TESTS"),
    reason="downloads the local captioning model; run with RUN_CAPTION_TESTS=1",
)
class TestImageCaptioning:
    def test_local_captioner_describes_diagram(self, tmp_path):
        image = Image.new("RGB", (500, 300), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle([50, 50, 450, 250], outline="blue", width=3)
        draw.ellipse([200, 100, 300, 200], fill="green")
        caption = pdf_parser._caption_image(image)
        assert isinstance(caption, str) and caption.strip()


@pytest.fixture(scope="module")
def fixture_pdf() -> bytes:
    return _build_fixture_pdf()


class TestParsePdf:
    def test_page_count(self, fixture_pdf):
        parsed = parse_pdf(fixture_pdf)
        assert parsed.page_count == 2
        assert [p.page_number for p in parsed.pages] == [1, 2]

    def test_page_one_text(self, fixture_pdf):
        parsed = parse_pdf(fixture_pdf)
        assert "refund within 30 days" in parsed.pages[0].text
        assert parsed.pages[0].tables == []

    def test_page_two_table_as_markdown(self, fixture_pdf):
        parsed = parse_pdf(fixture_pdf)
        tables = parsed.pages[1].tables
        assert len(tables) == 1
        markdown = tables[0]
        # Header row, separator and cell values survive as Markdown
        assert "| Plan | Monthly price | Support channel |" in markdown
        assert "| --- | --- | --- |" in markdown
        assert "| Basic | $10 | Email |" in markdown
        assert "| Pro | $25 | Priority 24/7 |" in markdown

    def test_table_text_not_duplicated_in_page_text(self, fixture_pdf):
        parsed = parse_pdf(fixture_pdf)
        page_two = parsed.pages[1]
        assert "All prices are in USD." in page_two.text
        # Table cell text lives in the table segment, not duplicated in prose
        assert "Basic" not in page_two.text

    def test_malformed_pdf_raises_parse_error(self):
        with pytest.raises(PDFParseError):
            parse_pdf(b"this is not a PDF at all")

    def test_password_protected_pdf_raises_parse_error(self, fixture_pdf):
        writer = PdfWriter()
        writer.append_pages_from_reader(PdfReader(BytesIO(fixture_pdf)))
        writer.encrypt("synthetic-fixture-only")
        buffer = BytesIO()
        writer.write(buffer)
        with pytest.raises(PDFParseError):
            parse_pdf(buffer.getvalue())


class TestPagesToSegments:
    def test_segments_carry_page_and_kind(self, fixture_pdf):
        segments = pages_to_segments(parse_pdf(fixture_pdf))
        assert len(segments) == 3
        text_segments = [s for s in segments if s["kind"] == "text"]
        table_segments = [s for s in segments if s["kind"] == "table"]
        assert {s["page_number"] for s in text_segments} == {1, 2}
        assert [s["page_number"] for s in table_segments] == [2]
        assert "| Basic | $10 | Email |" in table_segments[0]["content"]
        assert "Table from page 2" in table_segments[0]["content"]


class TestRenderPageImages:
    def test_renders_png_per_page(self, fixture_pdf, tmp_path):
        written = render_page_images(fixture_pdf, "doc-1", str(tmp_path))
        assert sorted(written.keys()) == [1, 2]
        for page_number, path in written.items():
            data = path.read_bytes()
            assert data[:8] == b"\x89PNG\r\n\x1a\n"
            assert len(data) > 1000  # real raster content, not an empty file
            assert path.name == f"page-{page_number}.png"

    def test_max_pages_cap(self, fixture_pdf, tmp_path):
        written = render_page_images(fixture_pdf, "doc-2", str(tmp_path), max_pages=1)
        assert sorted(written.keys()) == [1]

    def test_malformed_pdf_raises_parse_error(self, tmp_path):
        with pytest.raises(PDFParseError):
            render_page_images(b"not a pdf", "doc-3", str(tmp_path))
