## 1. Audit all bare pass in exception handlers

- [ ] 1.1 Run `grep -rn "except.*:\s*$\|except.*:\n\s*pass" libs/geomemory/src libs/geoagent/src --include="*.py" | grep -v __pycache__` to enumerate all silent exception handlers
- [ ] 1.2 Categorize each: (a) expected-best-effort → `logger.info`, (b) unexpected-recoverable → `logger.warning`, (c) can scope to narrower types
- [ ] 1.3 Create a checklist of all locations to modify

## 2. Fix workspace.py exception handlers

- [ ] 2.1 `workspace.py:360-361` (vision embed pass): Replace with `logger.info("vision embed skipped for revision %s: %s", revision_id, exc)`
- [ ] 2.2 `workspace.py:806-808` (dense search fallback): Replace `except Exception:` with `except (ImportError, RuntimeError, ValueError) as exc:` + logging + fallback; add narrow `except Exception:` with warning as last resort
- [ ] 2.3 `workspace.py:858` (candidate search): Replace `except Exception:` with scoped catch + `logger.warning("candidate memory search failed: %s", exc)`
- [ ] 2.4 Verify each fix with a targeted unit test that triggers the exception path and asserts the log record

## 3. Fix index_service.py exception handlers

- [ ] 3.1 `index_service.py:90`: Replace bare pass with appropriate logging
- [ ] 3.2 `index_service.py:240`: Replace bare pass with appropriate logging
- [ ] 3.3 `index_service.py:273`: Replace bare pass with appropriate logging
- [ ] 3.4 `index_service.py:304`: Replace bare pass with appropriate logging
- [ ] 3.5 Categorize each as info (expected) or warning (unexpected)

## 4. Fix pipeline.py exception handler

- [ ] 4.1 `ingest/pipeline.py:273`: Replace bare pass in batch ingestion with `logger.warning("batch item failed: %s", exc)` including the item identifier
- [ ] 4.2 Ensure the batch continues processing remaining items after the logged warning

## 5. Fix geoagent playbooks.py

- [ ] 5.1 `playbooks.py:92-93`: Replace `except PlaybookError: continue` with `logger.warning("skipped invalid playbook %s: %s", path, exc)`

## 6. Verification

- [ ] 6.1 Run `grep -rn "except.*:\s*$" libs/geomemory/src libs/geoagent/src --include="*.py" | grep -v __pycache__ | grep -v "logger\|raise\|return\|pass # type:"` — expect zero bare-pass results in production code
- [ ] 6.2 Run `conda run -n geospatial pytest libs/geomemory/tests -q --tb=short` — all tests pass
- [ ] 6.3 Run `conda run -n geospatial pytest libs/geoagent/tests -q --tb=short` — all tests pass
- [ ] 6.4 Run `conda run -n geospatial ruff check libs/geomemory/src libs/geoagent/src` — no new violations
- [ ] 6.5 Check that existing tests which asserted silence on error paths are updated to expect log records
