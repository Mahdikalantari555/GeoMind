"""HeaderThenToken chunker — structural-first chunking with overlap."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from geomemory.core.models import ParsedObject, SegmentDraft

_HEADER_RE = {"# ", "## ", "### ", "#### ", "##### ", "###### "}


class HeaderThenTokenChunker:
    """Split a document by header structure, then by token count.

    Headers (Markdown ``#`` lines and standalone ALL-CAPS lines) become chunk
    boundaries. Individual sections are further split when they exceed the
    configured token budget, with configurable overlap. Chunks preserve a
    ``parent_section_id`` (the nearest preceding header) and neighbor ids.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, document: ParsedObject) -> Iterable[SegmentDraft]:
        sections = _split_sections(document)
        page_spans: list[dict[str, Any]] = document.metadata.get("page_spans", [])
        fallback_locator: dict[str, Any] = dict(
            document.metadata.get("locators", [{}])[0]
            if document.metadata.get("locators")
            else {}
        )

        drafts: list[SegmentDraft] = []
        for section in sections:
            section_id = str(section["id"])
            lines = section["lines"]
            if not lines:
                continue
            joined = "\n".join(lines)
            token_count = _approx_tokens(joined)
            start_char = int(section.get("start_char", 0))

            if page_spans:
                page_num = _find_page(start_char, page_spans)
                locator = {"page": page_num}
            else:
                locator = dict(fallback_locator)

            if token_count <= self.chunk_size:
                drafts.append(
                    SegmentDraft(
                        text=joined,
                        segment_type="heading" if section["is_header"] else "paragraph",
                        locator={**locator, "section": section["title"]},
                        parent_section_id=section_id,
                    )
                )
            else:
                drafts.extend(
                    _split_long_section(
                        joined,
                        locator=locator,
                        section_id=section_id,
                        section_title=str(section["title"]),
                        chunk_size=self.chunk_size,
                        overlap=self.chunk_overlap,
                        section_start_char=start_char,
                        page_spans=page_spans,
                    )
                )
        # Assign neighbor ids (relative indices; real ids assigned at persist time).
        for i, draft in enumerate(drafts):
            draft.neighbor_ids = []
            if i > 0:
                draft.neighbor_ids.append(f"prev:{i - 1}")
            if i + 1 < len(drafts):
                draft.neighbor_ids.append(f"next:{i + 1}")
        return drafts


def _find_page(char_offset: int, page_spans: list[dict[str, Any]]) -> int:
    """Find the page index covering the given character offset."""
    for span in page_spans:
        if int(span["start_char"]) <= char_offset < int(span["end_char"]):
            return int(span["page"])
    if page_spans:
        if char_offset >= int(page_spans[-1]["end_char"]):
            return int(page_spans[-1]["page"])
        return int(page_spans[0]["page"])
    return 0


def _split_sections(document: ParsedObject) -> list[dict[str, Any]]:
    """Split parsed text into header-delimited sections."""
    sections: list[dict[str, Any]] = []
    current: list[str] = []
    current_title = "document"
    current_is_header = False
    current_start = 0

    cur_offset = 0
    lines = document.text.splitlines(keepends=True)

    def flush(end_offset: int) -> None:
        nonlocal current, current_start
        if current:
            sections.append(
                {
                    "id": f"sec_{len(sections)}",
                    "title": current_title,
                    "is_header": current_is_header,
                    "lines": [line.rstrip("\r\n") for line in current],
                    "start_char": current_start,
                    "end_char": end_offset,
                }
            )
            current = []

    prev_blank = True
    for line in lines:
        stripped = line.strip()
        line_start = cur_offset
        cur_offset += len(line)
        if not stripped:
            prev_blank = True
            current.append(line)
            continue

        is_header = _is_header(stripped, prev_blank=prev_blank)
        if is_header:
            flush(line_start)
            current_title = stripped.lstrip("# ").strip()
            current_is_header = True
            current_start = line_start
            current.append(stripped)
        else:
            current.append(line)
        prev_blank = False

    flush(cur_offset)
    if not sections and document.text.strip():
        sections.append(
            {
                "id": "sec_0",
                "title": "document",
                "is_header": False,
                "lines": [line.rstrip("\r\n") for line in document.text.splitlines()],
                "start_char": 0,
                "end_char": len(document.text),
            }
        )
    return sections


def _is_header(line: str, prev_blank: bool = True) -> bool:
    if any(line.startswith(h) for h in _HEADER_RE):
        return True
    if not prev_blank:
        return False
    # Standalone uppercase heading: require at least 2 words, length between 4 and 120 chars
    if not (line and line.isupper() and 4 < len(line) < 120):
        return False
    # Reject math / formula symbols
    if any(ch in line for ch in ("=", "+", "*", "^", "<", ">", "{", "}", "~")):
        return False
    # Reject hash / digest prefixes
    if any(line.startswith(prefix) for prefix in ("SHA", "MD5", "CRC", "HASH")):
        return False
    words = line.split()
    if len(words) < 2:
        return False
    # Reject hex / hashes
    if all(ch in "0123456789ABCDEF-_: " for ch in line):
        return False
    # Reject long tokens with mixed digits/letters (hashes/IDs)
    return not any(any(ch.isdigit() for ch in w) and len(w) > 6 for w in words)


def _split_long_section(
    text: str,
    *,
    locator: dict[str, Any],
    section_id: str,
    section_title: str,
    chunk_size: int,
    overlap: int,
    section_start_char: int = 0,
    page_spans: list[dict[str, Any]] | None = None,
) -> list[SegmentDraft]:
    """Split an oversized section on token boundaries with overlap."""
    tokens = text.split()
    drafts: list[SegmentDraft] = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_text = " ".join(tokens[start:end])
        token_offset = len(" ".join(tokens[:start])) if start > 0 else 0
        chunk_char = section_start_char + token_offset

        chunk_loc = dict(locator)
        if page_spans:
            chunk_loc["page"] = _find_page(chunk_char, page_spans)

        drafts.append(
            SegmentDraft(
                text=chunk_text,
                segment_type="paragraph",
                locator={**chunk_loc, "section": section_title, "token_span": [start, end]},
                parent_section_id=section_id,
            )
        )
        if end >= len(tokens):
            break
        start += step
    return drafts


def _approx_tokens(text: str) -> int:
    """Approximate token count from characters (roughly 4 chars/token)."""
    return max(1, len(text) // 4)
