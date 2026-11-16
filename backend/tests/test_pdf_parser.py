"""Tests for the multimodal PDF parser: page-aware text, tables, screenshots.

All fixtures are synthetic PDFs generated in-memory with reportlab.
No database, network, or LLM calls.
"""
from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from app.rag.pdf_parser import (
    PDFParseError,
    pages_to_segments,
    parse_pdf,
    render_page_images,
)


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
