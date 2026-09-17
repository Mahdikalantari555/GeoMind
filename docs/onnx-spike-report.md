# ONNX Spike Report: OLMoEarth Nano v1.2 Export

**Date**: 2025-07-18
**Status**: Complete — inconclusive, recommendation: stay with torch
**Change**: `olmoearth-production-and-onnx-spike` Track B

## Goal

Determine whether exporting the OLMoEarth v1.2 Nano PyTorch checkpoint to ONNX
produces acceptable quality, latency, and model size vs. the native torch path.

## Acceptance Criteria (from spec)

| Metric | Threshold |
|---|---|
| Mean cosine distance (torch vs ONNX) | ≤ 0.02 |
| ONNX model file size | Documented vs. torch .pth |
| Per-image embedding latency (mean over 50 runs) | Documented ms |

## Scripts

- `scripts/export_olmoearth_onnx.py` — exports `.pth` → `.onnx`
- `scripts/benchmark_olmoearth_onnx.py` — compares quality + latency

Both scripts exit with code 1 and a clear message when `torch`, `onnx`, or
`onnxruntime` are unavailable so CI can skip the spike gracefully.

## Results

### Environment

- torch 2.14.0 (CPU), onnx 1.22.0, onnxruntime 1.29.0, onnxscript 0.7.2
- `olmoearth_pretrain_minimal` 0.0.9 (lightweight package, no training deps)
- Weights: `models/olmoearth-nano-v12/weights.pth` (17 MB, from HF `allenai/OlmoEarth-v1_2-Nano`)

### Torch path (native)

- Model loads via `olmoearth_pretrain_minimal.load_model_from_id(ModelID.OLMOEARTH_V1_2_NANO, load_weights=True)`
- `OlmoEarthVisionEmbedder.embed_images()` produces L2-normalized (N, 128) vectors
- Verified end-to-end with random 128×128×3 inputs

### ONNX export — FAILED

`scripts/export_olmoearth_onnx.py` was updated to:
- Use `olmoearth_pretrain_minimal` (lightweight) instead of the full `olmoearth_pretrain` package (which would pull in a 900 MB+ CUDA torch)
- Wrap the encoder in a `torch.nn.Module` subclass that bakes in `MaskedOlmoEarthSample` construction and `patch_size=8`, so `torch.onnx.export` sees a pure function of the input tensor
- Try both `dynamo=True` (default) and `dynamo=False` (legacy tracer)

**Failure**: Both paths fail at the `Sort` operator inside the encoder's
attention mask sorting (`flexi_vit.py`). The legacy tracer reports:

```
Unsupported: ONNX export of operator Sort, Out parameter is not supported.
```

The dynamo path fails earlier with `missing a required argument: 'patch_size'`
and later with a `scaled_dot_product_attention` guard check.

This is the known ONNX op-support risk anticipated in the design doc —
OLMoEarth's encoder uses custom attention patterns (mask sorting, SDPA) that
ONNX export cannot trace.

### Recommendation

**Stay with torch.** The ONNX spike is inconclusive because export itself fails;
there is no quality/latency/size delta to compare. Track A (production wiring)
proceeds with the existing torch path, which is already verified end-to-end.

### File sizes

- torch `.pth`: 17 MB
- ONNX: not produced (export failed)

## Risks / Notes

- OLMoEarth's encoder may use ops not yet supported by ONNX export (custom attention patterns). If export fails, Track A proceeds with torch-only and Change 3 designs for one vision space.
- This spike tests FP16 only; INT8 quantization is deferred.
- `apps/dashboard/` does not exist in this repo — the web UI lives at
  `apps/web/` (React Vite). A dedicated image-search page is tracked as Task A3
  in the production spec.