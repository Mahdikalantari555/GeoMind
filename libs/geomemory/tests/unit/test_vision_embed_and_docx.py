"""Unit tests for vision embedding ingestion, image retrieval backend, and docx loader."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from geomemory.core.models import (
    IndexManifest,
    IndexRecord,
    SearchRequest,
    SourceRef,
)
from geomemory.core.workspace import GeoMemory
from geomemory.index.image_backend import ImageRetrievalBackend
from geomemory.index.image_index import ImageIndex
from geomemory.ingest.loaders.pdf import DocxLoader, PdfLoader
from geomemory.ingest.vision_embed import (
    _determine_dimension,
    _load_image_index,
    _save_image_index,
    try_embed_vision,
)


def test_docx_loader(tmp_path: Path) -> None:
    loader = DocxLoader()
    assert loader.supports(SourceRef(path="doc.docx")) is True
    assert loader.supports(SourceRef(path="doc.pdf")) is False

    # Fallback when docx is missing
    with patch.dict(sys.modules, {"docx": None}):
        parsed = list(loader.load(SourceRef(content_bytes=b"raw docx bytes")))
        assert len(parsed) == 1
        assert parsed[0].metadata["fallback"] is True

    # With mocked docx
    mock_doc = MagicMock()
    p1 = MagicMock(text="First paragraph")
    p2 = MagicMock(text="Second paragraph")
    p_empty = MagicMock(text="")
    mock_doc.paragraphs = [p1, p_empty, p2]

    with patch.dict(sys.modules, {"docx": MagicMock(Document=MagicMock(return_value=mock_doc))}):
        parsed = list(loader.load(SourceRef(content_bytes=b"raw docx bytes")))
        assert len(parsed) == 1
        assert "First paragraph" in parsed[0].text
        assert "Second paragraph" in parsed[0].text


def test_determine_dimension() -> None:
    # 1. callable dimension
    idx1 = MagicMock(dimension=MagicMock(return_value=512))
    assert _determine_dimension(idx1) == 512

    # 2. callable vector
    idx2 = MagicMock(dimension=None, vector=MagicMock(return_value=np.zeros(256)))
    assert _determine_dimension(idx2) == 256

    # 3. vectors attribute
    idx3 = MagicMock(dimension=None, vector=None, vectors=np.zeros((10, 128)))
    assert _determine_dimension(idx3) == 128

    # 4. _embeddings dict
    idx4 = MagicMock(dimension=None, vector=None, vectors=None, _embeddings={"t1": np.zeros(64)})
    assert _determine_dimension(idx4) == 64

    # 5. default fallback 768
    idx5 = MagicMock(dimension=None, vector=None, vectors=None, _embeddings={})
    assert _determine_dimension(idx5) == 768


def test_try_embed_vision(temp_workspace: GeoMemory, tmp_path: Path) -> None:
    conn = temp_workspace.conn

    # 1. No vision_path -> noop
    try_embed_vision(conn=conn, revision_id="rev-1", vision_path=None, index_dir=tmp_path)

    # 2. OlmoEarthVisionEmbedder init error -> noop
    with patch("geomemory.ingest.vision_embed.OlmoEarthVisionEmbedder", side_effect=RuntimeError("Fail")):
        try_embed_vision(conn=conn, revision_id="rev-1", vision_path="fake.pth", index_dir=tmp_path)

    # 3. Scene row missing -> noop
    with patch("geomemory.ingest.vision_embed.OlmoEarthVisionEmbedder"):
        try_embed_vision(conn=conn, revision_id="rev-missing", vision_path="fake.pth", index_dir=tmp_path)

    # Insert raster_scene and raster_tile
    col = temp_workspace.create_collection("test_col")
    conn.execute("INSERT OR REPLACE INTO asset (id, collection_id, kind) VALUES ('ast-1', ?, 'raster')", (col.id,))
    conn.execute("INSERT OR REPLACE INTO asset_revision (id, asset_id, hash, mime_type, size_bytes, parser_version) VALUES ('rev-1', 'ast-1', 'a'*64, 'image/tiff', 100, 'v1')")
    conn.execute("INSERT INTO raster_scene (id, revision_id, crs, bbox) VALUES ('scn-1', 'rev-1', 'EPSG:4326', '[]')")
    preview_file = tmp_path / "tile.png"
    preview_file.write_bytes(b"png")
    conn.execute("INSERT INTO raster_tile (id, scene_id, window, transform, preview_path) VALUES ('til-1', 'scn-1', '{}', '[]', ?)", (str(preview_file),))
    conn.commit()

    # 4. Embedder runtime error -> noop
    mock_embedder = MagicMock(space_id="image.olmoearth-nano-v12.v1")
    mock_embedder.embed_images.side_effect = RuntimeError("Runtime err")
    with patch("geomemory.ingest.vision_embed.OlmoEarthVisionEmbedder", return_value=mock_embedder):
        try_embed_vision(conn=conn, revision_id="rev-1", vision_path="fake.pth", index_dir=tmp_path)

    # 5. Embedder shape mismatch -> noop
    mock_embedder.embed_images.side_effect = None
    mock_embedder.embed_images.return_value = np.zeros((0, 768))
    with patch("geomemory.ingest.vision_embed.OlmoEarthVisionEmbedder", return_value=mock_embedder):
        try_embed_vision(conn=conn, revision_id="rev-1", vision_path="fake.pth", index_dir=tmp_path)

    # 6. Success
    mock_embedder.embed_images.return_value = np.ones((1, 768), dtype=np.float32)
    with patch("geomemory.ingest.vision_embed.OlmoEarthVisionEmbedder", return_value=mock_embedder):
        try_embed_vision(conn=conn, revision_id="rev-1", vision_path="fake.pth", index_dir=tmp_path)

    loaded_idx = _load_image_index(tmp_path)
    assert loaded_idx.count() == 1


def test_image_retrieval_backend(tmp_path: Path) -> None:
    idx = ImageIndex()
    backend = ImageRetrievalBackend(idx, space_id="image.test.v1")

    # count == 0 -> search returns []
    req = SearchRequest(query="find trees", top_k=5)
    assert backend.search(req) == []

    # upsert
    vec1 = np.ones(128, dtype=np.float32)
    vec1 = vec1 / np.linalg.norm(vec1)
    rec = IndexRecord(id="til-1", text="", embedding=list(vec1))
    backend.upsert([rec])
    assert backend.count() == 1

    # zero query vector -> returns []
    req_zero = SearchRequest(query="find trees", query_embedding=list(np.zeros(128)), top_k=5)
    assert backend.search(req_zero) == []

    # dimension mismatch -> returns []
    req_wrong_dim = SearchRequest(query="find trees", query_embedding=list(np.ones(64)), top_k=5)
    assert backend.search(req_wrong_dim) == []

    # valid query vector -> returns hit
    req_valid = SearchRequest(query="find trees", query_embedding=list(vec1), top_k=5)
    hits = backend.search(req_valid)
    assert len(hits) == 1
    assert hits[0].id == "til-1"
    assert hits[0].metadata["modality"] == "image"

    # with vision_embedder text encoding
    mock_embedder = MagicMock()
    # 2D return
    mock_embedder.embed_texts.return_value = np.array([vec1])
    backend_with_emb = ImageRetrievalBackend(idx, vision_embedder=mock_embedder)
    hits_text = backend_with_emb.search(SearchRequest(query="query text", top_k=5))
    assert len(hits_text) == 1

    # 1D return
    mock_embedder.embed_texts.return_value = vec1
    assert len(backend_with_emb.search(SearchRequest(query="query text", top_k=5))) == 1

    # embed_texts raises
    mock_embedder.embed_texts.side_effect = RuntimeError("err")
    assert backend_with_emb.search(SearchRequest(query="query text", top_k=5)) == []

    # delete
    backend.delete(["til-1"])
    assert backend.count() == 0

    # rebuild noop
    backend.rebuild(IndexManifest(space_id="s", model_id="m", dimension=128, doc_count=0))


def test_pdf_loader() -> None:
    loader = PdfLoader()
    assert loader.supports(SourceRef(path="test.pdf")) is True
    assert loader.supports(SourceRef(path="test.txt")) is False

    mock_doc = MagicMock()
    page1 = MagicMock()
    page1.get_text.return_value = "Page 1 content"
    mock_doc.__iter__.return_value = [page1]

    # Success with fitz
    with patch("fitz.open", return_value=mock_doc):
        parsed = list(loader.load(SourceRef(content_bytes=b"%PDF-fake")))
        assert len(parsed) == 1
        assert "Page 1 content" in parsed[0].text
        assert parsed[0].metadata["page_count"] == 1

    # Exception during fitz.open -> fallback
    with patch("fitz.open", side_effect=RuntimeError("Corrupt PDF")):
        fallback = list(loader.load(SourceRef(content_bytes=b"corrupt text")))
        assert len(fallback) == 1
        assert fallback[0].metadata["fallback"] is True

