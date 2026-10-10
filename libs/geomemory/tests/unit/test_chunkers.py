"""Unit tests for the chunkers."""

from __future__ import annotations

from geomemory.core.models import ParsedObject, SourceRef
from geomemory.ingest.chunkers import FixedSizeChunker, HeaderThenTokenChunker


def _doc(text: str) -> ParsedObject:
    return ParsedObject(
        source=SourceRef(path="test.md"),
        mime_type="text/markdown",
        title="test",
        text=text,
    )


class TestHeaderThenTokenChunker:
    def test_respects_headers(self):
        text = "# Intro\n\nFirst paragraph.\n\n## Methods\n\nSecond paragraph.\n"
        drafts = list(HeaderThenTokenChunker().split(_doc(text)))
        assert len(drafts) >= 2
        # First chunk is the heading section.
        assert drafts[0].segment_type == "heading"
        assert "Intro" in drafts[0].text

    def test_parent_section_id(self):
        text = "# A\n\nbody a\n\n# B\n\nbody b\n"
        drafts = list(HeaderThenTokenChunker().split(_doc(text)))
        assert drafts[0].parent_section_id is not None
        assert drafts[1].parent_section_id is not None

    def test_neighbor_ids(self):
        text = "# A\n\nbody a\n\n# B\n\nbody b\n"
        drafts = list(HeaderThenTokenChunker().split(_doc(text)))
        assert len(drafts) >= 2
        assert drafts[0].neighbor_ids == ["next:1"]
        assert drafts[1].neighbor_ids == ["prev:0"]

    def test_long_section_split(self):
        # A single section with many tokens should be split.
        text = "# Long\n\n" + "word " * 2000
        drafts = list(HeaderThenTokenChunker(chunk_size=100, chunk_overlap=20).split(_doc(text)))
        assert len(drafts) > 1
        # Overlap means consecutive chunks share tokens.
        assert drafts[0].locator.get("token_span") is not None

    def test_empty_document(self):
        drafts = list(HeaderThenTokenChunker().split(_doc("")))
        assert drafts == []

    def test_multipage_pdf_page_spans_assigned(self):
        page0 = "# Chapter 1\n\nContent on page 0."
        page1 = "# Chapter 2\n\nContent on page 1."
        page2 = "# Chapter 3\n\nContent on page 2."
        text = f"{page0}\n\n{page1}\n\n{page2}"

        spans = [
            {"page": 0, "start_char": 0, "end_char": len(page0)},
            {"page": 1, "start_char": len(page0) + 2, "end_char": len(page0) + 2 + len(page1)},
            {
                "page": 2,
                "start_char": len(page0) + 2 + len(page1) + 2,
                "end_char": len(text),
            },
        ]
        doc = ParsedObject(
            source=SourceRef(path="multipage.pdf"),
            mime_type="application/pdf",
            title="multipage",
            text=text,
            metadata={"loader": "PdfLoader", "page_count": 3, "page_spans": spans},
        )

        drafts = list(HeaderThenTokenChunker().split(doc))
        assert len(drafts) == 3
        assert drafts[0].locator.get("page") == 0
        assert drafts[1].locator.get("page") == 1
        assert drafts[2].locator.get("page") == 2

    def test_refined_is_header_ignores_acronyms_formulas_and_hashes(self):
        from geomemory.ingest.chunkers.header_then_token import _is_header

        # Single uppercase acronym is not a header
        assert _is_header("NDVI", prev_blank=True) is False
        assert _is_header("METRIC", prev_blank=True) is False

        # Formula with operators is not a header
        assert _is_header("ET_A = K_C * ET_0", prev_blank=True) is False

        # Hex / hash string is not a header
        assert _is_header("SHA256: 3F4E5A6B7C8D9E0F", prev_blank=True) is False

        # Standalone uppercase without preceding blank line is not a header
        assert _is_header("STUDY AREA AND METHODS", prev_blank=False) is False

        # Legitimate multi-word uppercase heading with preceding blank line is a header
        assert _is_header("STUDY AREA AND METHODS", prev_blank=True) is True
        assert _is_header("# Real Markdown Header", prev_blank=False) is True



class TestFixedSizeChunker:
    def test_splits_by_token_count(self):
        text = " ".join(f"token{i}" for i in range(100))
        drafts = list(FixedSizeChunker(chunk_size=30, chunk_overlap=5).split(_doc(text)))
        assert len(drafts) > 1
        assert all(d.segment_type == "paragraph" for d in drafts)

    def test_small_document_single_chunk(self):
        drafts = list(FixedSizeChunker().split(_doc("short text")))
        assert len(drafts) == 1

    def test_empty(self):
        assert list(FixedSizeChunker().split(_doc(""))) == []

    def test_neighbors(self):
        text = " ".join(f"token{i}" for i in range(100))
        drafts = list(FixedSizeChunker(chunk_size=30, chunk_overlap=5).split(_doc(text)))
        assert drafts[0].neighbor_ids == ["next:1"]
