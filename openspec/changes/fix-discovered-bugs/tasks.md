# Tasks: fix-discovered-bugs

## 1. Test import fix

- [ ] 1.1 Change error imports in `libs/data_engine/tests/test_planetary_computer_fetcher.py` to `data_engine.io.errors`; verify `conda run -n geospatial pytest libs/data_engine/tests/test_planetary_computer_fetcher.py -q` collects and passes
- [ ] 1.2 Run `conda run -n geospatial ruff check libs/data_engine/tests/test_planetary_computer_fetcher.py && conda run -n geospatial mypy --strict libs/data_engine/src/data_engine/io/errors.py` → exit 0

## 2. Sample script tests

- [ ] 2.1 Create `scripts/tests/test_compute_sample_indices.py` mocking both fetchers covering Landsat + Sentinel paths; verify `conda run -n geospatial pytest scripts/tests/test_compute_sample_indices.py -q` → green
- [ ] 2.2 Verify `python scripts/compute_sample_indices.py --help` lists `--input`, `--dates`, `--sentinel`, `--resolution`

## 3. Full gate

- [ ] 3.1 Run `conda run -n geospatial pytest libs/data_engine/tests -q && conda run -n geospatial pytest server/tests -q && pnpm --prefix apps/web build` → clean
- [ ] 3.2 Validate change: `openspec validate --change fix-discovered-bugs --strict` → no errors

## Dependencies

1→2 (independent files, either order works), 1+2→3 (gate last).
