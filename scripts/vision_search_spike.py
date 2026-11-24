#!/usr/bin/env python3
"""Offline tiles-to-embedding bridge spike (change: ship-and-measure-agent).

Proves the plumbing for "find imagery similar to this tile" without a vision
checkpoint, network or gateway: a deterministic downsample embedder implements
the `VisionEmbedder` seam, bundles real Landsat band windows into an `ImageIndex`,
and measures self / near-duplicate / cross-band retrieval.

This validates TRANSPORT ONLY. It is not a semantic-quality result and the
Studio view deliberately does not ship from this spike (see the decision record).

Usage:
    python scripts/vision_search_spike.py --out docs/spikes
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from geomemory.embeddings.normalization import l2_normalize
from geomemory.index.image_index import ImageIndex
from geomemory.index.manifest import create_manifest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BANDS = ROOT / "libs" / "geomemory" / "geomemorytest" / "data" / "landsat_20161220_165_039"
SIZE = (16, 16)
DIM = SIZE[0] * SIZE[1] * 3
MODEL = "spike-downsample-l2-v0"


class DownsampleEmbedder:
    """Deterministic stand-in for OlmoEarth — implements VisionEmbedder's seam."""

    space_id = ImageIndex.space_id
    model_id = MODEL

    def embed_images(self, images: list[Any]) -> np.ndarray:
        vectors = [self._one(image) for image in images]
        return np.stack(vectors)

    def embed_texts(self, texts: list[str]) -> None:
        return None  # OlmoEarth also returns None for text

    @staticmethod
    def _one(image: Any) -> np.ndarray:
        if isinstance(image, np.ndarray):
            arr = np.asarray(image, dtype=np.float32)
        else:
            arr = np.asarray(Image.open(image).convert("RGB"), dtype=np.float32)
        if arr.ndim == 2:
            arr = np.stack([arr] * 3, axis=-1)
        lo, hi = np.percentile(arr, (2, 98))
        scaled = np.clip((arr - lo) / max(hi - lo, 1e-6), 0, 1)
        resized = np.asarray(
            Image.fromarray((scaled * 255).astype(np.uint8)).resize(SIZE),
            dtype=np.float32,
        ) / 255.0
        return l2_normalize(resized.reshape(1, -1))[0]


def _band_preview(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        data = src.read(1, window=rasterio.windows.Window(0, 0, 256, 256))
    return data


def run_spike(out_dir: Path) -> dict[str, Any]:
    tifs = sorted(BANDS.glob("*.tif"))
    if not tifs:
        raise FileNotFoundError(f"no Landsat band GeoTIFFs under {BANDS}")

    embedder = DownsampleEmbedder()
    index = ImageIndex()
    previews: dict[str, np.ndarray] = {}
    for tif in tifs:
        name = tif.stem
        preview = _band_preview(tif)
        previews[name] = preview
        index.upsert(name, embedder.embed_images([preview])[0])

    # near-duplicate: a slightly noisy copy of the red band
    rng = np.random.default_rng(42)
    red = previews["red"]
    noisy = red + rng.normal(0, red.std() * 0.02, size=red.shape).astype(red.dtype)
    index.upsert("red_noisy", embedder.embed_images([noisy])[0])

    with tempfile.TemporaryDirectory(prefix="geomind-vision-spike-") as tmp:
        index_dir = Path(tmp) / "image"
        index.save(
            index_dir,
            create_manifest(
                space_id=ImageIndex.space_id, model_id=MODEL, dimension=DIM,
                doc_count=index.count(),
            ),
        )
        reloaded = ImageIndex.load(index_dir)
        self_hits = reloaded.search(embedder.embed_images([previews["red"]])[0], top_k=1)
        duplicate_hits = reloaded.search(embedder.embed_images([noisy])[0], top_k=3)
        repeat = reloaded.search(embedder.embed_images([previews["red"]])[0], top_k=1)

    target_ids = set(index._embeddings)
    report: dict[str, Any] = {
        "granularity": "tile",
        "images_indexed": index.count(),
        "embedding_space": ImageIndex.space_id,
        "embedder": MODEL,
        "checks": {
            "self_retrieval_top1": self_hits[0]["target_id"] == "red",
            "self_score": round(float(self_hits[0]["score"]), 6),
            "near_duplicate_top2": [h["target_id"] for h in duplicate_hits[:2]],
            "deterministic": repeat == self_hits,
            "all_targets_known": all(h["target_id"] in target_ids for h in duplicate_hits),
            "text_query_unsupported": embedder.embed_texts(["red"]) is None,
        },
        "verdict": "plumbing_only",
        "blockers_for_studio_view": [
            "POST /images/search route does not exist in the gateway OpenAPI",
            "no OLMoEarth checkpoint / [vision] extra offline; ONNX path is text-only",
            "sample/ has no imagery; tile previews are NULL in existing workspaces",
            "no semantic-quality measurement (near-duplicate vs random ranking under a real model)",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "vision-search.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "spikes")
    args = parser.parse_args()
    print(json.dumps(run_spike(args.out), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
