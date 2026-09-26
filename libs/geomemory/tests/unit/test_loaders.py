"""Unit tests for the ingest loaders."""

from __future__ import annotations

import pytest

from geomemory.core.models import SourceRef, WorkspaceSettings
from geomemory.ingest.loaders import (
    CodeLoader,
    NotebookLoader,
    PdfLoader,
    TextLoader,
    get_loader,
    select_pdf_loader,
)
from geomemory.ingest.loaders.base import java_available


class TestTextLoader:
    def test_supports_markdown(self, sample_markdown):
        loader = TextLoader()
        assert loader.supports(SourceRef(path=str(sample_markdown)))

    def test_load(self, sample_markdown):
        loader = TextLoader()
        objs = list(loader.load(SourceRef(path=str(sample_markdown))))
        assert len(objs) == 1
        assert "NDVI" in objs[0].text
        assert objs[0].mime_type == "text/markdown"


class TestCodeLoader:
    def test_supports_python(self, sample_python):
        loader = CodeLoader()
        assert loader.supports(SourceRef(path=str(sample_python)))

    def test_load_python_ast(self, sample_python):
        loader = CodeLoader()
        objs = list(loader.load(SourceRef(path=str(sample_python))))
        assert len(objs) == 1
        units = objs[0].metadata["code_units"]
        names = {u["name"] for u in units}
        assert "compute_ndvi" in names
        assert "VegetationIndex" in names
        # Function has a signature and docstring.
        fn = next(u for u in units if u["name"] == "compute_ndvi")
        assert fn["signature"].startswith("compute_ndvi(")
        assert "NDVI" in fn["docstring"]
        assert fn["start_line"] >= 1

    def test_load_python_syntax_error(self, tmp_path):
        bad_py = tmp_path / "bad.py"
        bad_py.write_text("def broken(x:\n   return")
        loader = CodeLoader()
        objs = list(loader.load(SourceRef(path=str(bad_py))))
        assert len(objs) == 1
        assert objs[0].metadata["code_units"] == []

    def test_load_javascript_and_gee(self, tmp_path):
        js_file = tmp_path / "script.js"
        js_file.write_text(
            "// comment\n"
            "var processTile = function(image, geometry) {\n  return image.clip(geometry);\n};\n"
            "const calcNdvi = (b8, b4) => {\n  return (b8 - b4) / (b8 + b4);\n};\n"
        )
        loader = CodeLoader()
        assert loader.supports(SourceRef(path=str(js_file)))
        objs = list(loader.load(SourceRef(path=str(js_file))))
        assert len(objs) == 1
        assert objs[0].metadata["language"] == "javascript"
        units = objs[0].metadata["code_units"]
        names = {u["name"] for u in units}
        assert "processTile" in names
        assert "calcNdvi" in names


class TestNotebookLoader:
    def test_load(self, sample_notebook):
        loader = NotebookLoader()
        objs = list(loader.load(SourceRef(path=str(sample_notebook))))
        assert len(objs) == 1
        assert objs[0].metadata["cell_count"] == 2
        assert "print('hello')" in objs[0].text


class TestPdfLoader:
    def test_supports(self, tmp_path):
        p = tmp_path / "doc.pdf"
        p.write_bytes(b"%PDF-1.4")
        assert PdfLoader().supports(SourceRef(path=str(p)))

    def test_fallback_without_pymupdf(self, tmp_path):
        # Without pymupdf installed, loader falls back to raw text.
        p = tmp_path / "doc.pdf"
        p.write_bytes(b"plain pdf text")
        objs = list(PdfLoader().load(SourceRef(path=str(p))))
        assert len(objs) == 1
        assert objs[0].metadata.get("fallback") is True

    def test_corrupt_pdf_with_pymupdf_fallback(self, tmp_path):
        from unittest.mock import MagicMock, patch

        p = tmp_path / "corrupt.pdf"
        p.write_bytes(b"not a valid pdf header")

        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = Exception("FileDataError: cannot open broken stream")
        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            objs = list(PdfLoader().load(SourceRef(path=str(p))))
            assert len(objs) == 1
            assert objs[0].metadata.get("fallback") is True
            assert "FileDataError" in objs[0].metadata.get("fallback_reason", "")

    def test_valid_pdf_with_pymupdf(self, tmp_path):
        from unittest.mock import MagicMock, patch

        p = tmp_path / "valid.pdf"
        p.write_bytes(b"%PDF-1.4 dummy content")

        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "Page 1: Vegetation index overview."
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = "Page 2: Irrigation table."

        mock_doc = MagicMock()
        mock_doc.__iter__.return_value = [mock_page1, mock_page2]
        mock_doc.__len__.return_value = 2

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            objs = list(PdfLoader().load(SourceRef(path=str(p))))
            assert len(objs) == 1
            assert objs[0].metadata["page_count"] == 2
            assert "Vegetation index" in objs[0].text
            assert "Irrigation table" in objs[0].text
            assert len(objs[0].metadata["locators"]) == 2
            mock_doc.close.assert_called_once()


class TestShapefileLoader:
    def test_supports(self):
        from geomemory.ingest.loaders.shapefile import ShapefileLoader

        loader = ShapefileLoader()
        assert loader.supports(SourceRef(path="/path/to/data.shp"))
        assert not loader.supports(SourceRef(path="/path/to/data.geojson"))
        assert not loader.supports(SourceRef(content_bytes=b"dummy"))

    def test_load_valid_shapefile_mocked(self, tmp_path):
        from unittest.mock import MagicMock

        from geomemory.ingest.loaders.shapefile import ShapefileLoader

        mock_layer = MagicMock()
        mock_layer.name = "fields"
        mock_layer.feature_count = 5
        mock_layer.geom_type = "Polygon"
        mock_layer.crs = "EPSG:4326"
        mock_layer.bbox = [-120.0, 35.0, -119.0, 36.0]
        mock_layer.properties = ["crop", "area_ha"]
        mock_layer.sample = [{"crop": "corn", "area_ha": 10.5}]
        mock_layer.model_dump.return_value = {"name": "fields", "count": 5}

        mock_reader = MagicMock()
        mock_reader.read_layer.return_value = mock_layer

        shp_file = tmp_path / "parcels.shp"
        shp_file.write_bytes(b"dummy shp bytes")

        loader = ShapefileLoader(reader=mock_reader)
        objs = list(loader.load(SourceRef(path=str(shp_file))))
        assert len(objs) == 1
        assert objs[0].title == "parcels.shp"
        assert objs[0].mime_type == "application/x-shp"
        assert "Vector layer with 5 feature(s)" in objs[0].text
        assert objs[0].metadata["vector"]["layer"]["count"] == 5

    def test_load_missing_path_raises(self):
        from geomemory.ingest.loaders.shapefile import ShapefileLoader

        loader = ShapefileLoader()
        with pytest.raises(ValueError, match="requires a local file path"):
            list(loader.load(SourceRef(content_bytes=b"dummy")))

    def test_load_corrupt_file_raises(self, tmp_path):
        from unittest.mock import MagicMock

        from geomemory.ingest.loaders.shapefile import ShapefileLoader

        mock_reader = MagicMock()
        mock_reader.read_layer.side_effect = RuntimeError("Corrupted DBF or SHP header")

        shp_file = tmp_path / "corrupt.shp"
        shp_file.write_bytes(b"bad")

        loader = ShapefileLoader(reader=mock_reader)
        with pytest.raises(RuntimeError, match="Corrupted DBF"):
            list(loader.load(SourceRef(path=str(shp_file))))


class TestGetLoader:
    def test_resolves_markdown(self, sample_markdown):
        loader = get_loader(SourceRef(path=str(sample_markdown)))
        assert isinstance(loader, TextLoader)

    def test_resolves_python(self, sample_python):
        loader = get_loader(SourceRef(path=str(sample_python)))
        assert isinstance(loader, CodeLoader)

    def test_resolves_notebook(self, sample_notebook):
        loader = get_loader(SourceRef(path=str(sample_notebook)))
        assert isinstance(loader, NotebookLoader)

    def test_unknown_returns_none(self, tmp_path):
        p = tmp_path / "file.xyz"
        p.write_text("x")
        assert get_loader(SourceRef(path=str(p))) is None


class TestJavaAvailable:
    def test_detects_java(self):
        import shutil
        result = java_available()
        assert result == (shutil.which("java") is not None)


class TestSelectPdfLoader:
    def test_pymupdf_preference_returns_pymupdf(self):
        loader = select_pdf_loader(WorkspaceSettings(name="x", pdf_parser="pymupdf"))
        assert isinstance(loader, PdfLoader)

    def test_auto_picks_pymupdf_when_no_java(self, monkeypatch):
        monkeypatch.setattr(
            "geomemory.ingest.loaders.java_available", lambda: False
        )
        loader = select_pdf_loader()
        assert isinstance(loader, PdfLoader)

class TestOpenDataLoaderPdfFallback:
    def test_supports(self):
        from geomemory.ingest.loaders.opendataloader_pdf import OpenDataLoaderPdf

        loader = OpenDataLoaderPdf()
        assert loader.supports(SourceRef(path="file.pdf"))
        assert not loader.supports(SourceRef(path="file.txt"))
        assert not loader.supports(SourceRef(content_bytes=b"dummy"))

    def test_unavailable_when_java_missing(self, monkeypatch):
        from geomemory.ingest.loaders import opendataloader_pdf as odl_mod
        from geomemory.ingest.loaders.opendataloader_pdf import OpenDataLoaderPdf
        monkeypatch.setattr(odl_mod, "java_available", lambda: False)
        loader = OpenDataLoaderPdf()
        with pytest.raises(RuntimeError, match="Java|opendataloader"):
            list(loader.load(SourceRef(path="tests/data/flood_report.pdf")))

    def test_error_when_no_json_output(self, monkeypatch, tmp_path):
        import sys
        from unittest.mock import MagicMock

        from geomemory.ingest.loaders import opendataloader_pdf as odl_mod
        from geomemory.ingest.loaders.opendataloader_pdf import OpenDataLoaderPdf

        monkeypatch.setattr(odl_mod, "java_available", lambda: True)
        mock_odl = MagicMock()
        mock_odl.convert = MagicMock()  # doesn't write any json files

        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 dummy")

        monkeypatch.setitem(sys.modules, "opendataloader_pdf", mock_odl)
        loader = OpenDataLoaderPdf()
        with pytest.raises(RuntimeError, match="OpenDataLoader produced no JSON output"):
            list(loader.load(SourceRef(path=str(pdf_path))))

    def test_error_when_convert_fails(self, monkeypatch, tmp_path):
        import sys
        from unittest.mock import MagicMock

        from geomemory.ingest.loaders import opendataloader_pdf as odl_mod
        from geomemory.ingest.loaders.opendataloader_pdf import OpenDataLoaderPdf

        monkeypatch.setattr(odl_mod, "java_available", lambda: True)
        mock_odl = MagicMock()
        mock_odl.convert.side_effect = Exception("Java JVM crash")

        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 dummy")

        monkeypatch.setitem(sys.modules, "opendataloader_pdf", mock_odl)
        loader = OpenDataLoaderPdf()
        with pytest.raises(RuntimeError, match="OpenDataLoader failed to parse PDF"):
            list(loader.load(SourceRef(path=str(pdf_path))))

    def test_success_with_mocked_json(self, monkeypatch, tmp_path):
        import json
        import sys
        from pathlib import Path
        from unittest.mock import MagicMock

        from geomemory.ingest.loaders import opendataloader_pdf as odl_mod
        from geomemory.ingest.loaders.opendataloader_pdf import OpenDataLoaderPdf

        monkeypatch.setattr(odl_mod, "java_available", lambda: True)

        def _fake_convert(input_path, format, output_dir, quiet=True):
            p = Path(output_dir) / "output.json"
            p.write_text(
                json.dumps(
                    {
                        "title": "Satellite Report",
                        "number of pages": 1,
                        "kids": [
                            {"type": "heading", "heading level": 1, "content": "Executive Summary", "page number": 1, "bounding box": [0, 0, 100, 20]},
                            {"type": "paragraph", "content": "NDVI observed at 0.72", "page number": 1, "bounding box": [0, 20, 100, 50]},
                        ],
                    }
                )
            )

        mock_odl = MagicMock()
        mock_odl.convert.side_effect = _fake_convert

        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 dummy")

        monkeypatch.setitem(sys.modules, "opendataloader_pdf", mock_odl)
        loader = OpenDataLoaderPdf()
        objs = list(loader.load(SourceRef(path=str(pdf_path))))
        assert len(objs) == 1
        assert objs[0].title == "Satellite Report"
        assert "Executive Summary" in objs[0].text
        assert "NDVI observed at 0.72" in objs[0].text
        assert objs[0].metadata["page_count"] == 1
        assert len(objs[0].metadata["locators"]) == 2
