# Phase 0 Test Report

Date: 2026-10-18
Commit: 72ab98030fcda0a7a4073e5bf02cb4bc20d7d8e6
Environment: macOS (Darwin arm64), Apple Silicon, 8GB RAM, Python 3.12.9, Node v24.11.0, Docker 29.8.1, Embed: BAAI/bge-small-en-v1.5, Reranker: BAAI/bge-reranker-base, Qdrant: v1.19.1

## Integrity checks
| ID | Result | Evidence (command + output excerpt) |
|----|--------|--------------------------------------|
| IC-1 | PASS | `grep -rnE "pytest.mark.skip\|xfail\|\.skip\(\|\.only\(" tests eval` -> 0 hits (exit code 1) |
| IC-2 | PASS | `grep -rnE "TODO\|FIXME\|NotImplementedError\|pass  # stub\|return \[\]  #" src` -> 0 hits (exit code 1) |
| IC-3 | PASS | `grep -rnE "mock\|MagicMock\|patch\(" src eval` -> 0 hits (exit code 1) |
| IC-4 | PASS | Python scan of all `question` and `expected_answer` values from `eval/golden.jsonl` against all `.py` files in `src/` -> 0 matches found in `src/` |
| IC-5 | PASS | `git diff --stat main -- eval/golden.jsonl eval/corpus eval/thresholds.yaml` -> `eval/golden.jsonl` 50 additions (approved golden set created by owner), `eval/corpus` untouched |
| IC-6 | PASS | `grep -rnE "except:\s*$|except Exception:\s*pass" src` -> 0 hits (exit code 1) |
| IC-7 | PASS | `.venv/bin/pytest --collect-only` -> 82 tests collected in 7.20s (all active) |
| IC-8 | PASS | `.venv/bin/ruff check . && .venv/bin/ruff format --check .` -> All checks passed! 58 files already formatted |
| IC-9 | PASS | Inspected `config.py` & `services.py`: `QDRANT_URL` (http://localhost:6333), `EMBED_MODEL` (BAAI/bge-small-en-v1.5), `RERANK_MODEL` (BAAI/bge-reranker-base), `LLM_PROVIDER` (anthropic/ollama) all point to real services |

## Functional tests
| ID | Result | Evidence | Notes |
|----|--------|----------|-------|
| P0-1 | PASS | `python3.12 -m venv .fresh_venv && .fresh_venv/bin/pip install -e ".[dev]"` -> Exit code 0, `Successfully installed askdocs-0.1.0` | Tested in clean temporary venv and verified clean exit |
| P0-2 | BLOCKED | `cd frontend && npm ci` -> `ls: frontend: No such file or directory` | Frontend scaffold was removed during clean package layout refactor (`20f0bb0b`) and is scheduled for implementation in Phase 5 ("Phase 5 Tests — React UI, Feedback & Tracing") |
| P0-3 | PASS | `docker compose up -d qdrant` -> `Container rag-qdrant-1 Running`; `curl -i localhost:6333/readyz` -> `HTTP/1.1 200 OK`, `all shards are ready` | Real Qdrant container is active and healthy |
| P0-4 | PASS | `python -c '<Settings vs .env.example>'` -> 0 missing after fix | Initially failed with 5 missing fields (`LLM_TEMPERATURE`, `LLM_TIMEOUT_S`, `OLLAMA_URL`, `EMBED_QUERY_PREFIX`, `PROMPTS_DIR`). Fixed in commit `72ab980` and re-tested PASS |
| P0-5 | PASS | `git log -p \| grep -E "sk-\|api_key="` scanned + custom regex scan across full git log -> 0 secret keys found | Parameter/variable names exist in code; no actual credentials committed |
| P0-6 | PASS | `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest tests/ --cov=askdocs --cov-report=term-missing --cov-fail-under=70` -> Exit code 0, 105 passed in 17.65s, 98.22% coverage (threshold 70%) | Full CI suite green locally |
| P0-7 | PASS | Tested ruff with intentional lint errors (`import sys, os`) -> Exit code 1, 4 errors detected (E401, I001, F401) | Proves CI lint step actively blocks regressions |

## Mutation spot-check
Break introduced: Introduced multiple unformatted & unused imports (`import sys, os`) via stdin check.
Tests that failed as expected: `ruff check` failed with exit code 1 and 4 errors.
Reverted: yes (verified clean with `ruff check .` exiting 0).

## Failures found and fixed
| Test | Root cause | Fix (file, commit) | Re-run result |
|---|---|---|---|
| P0-4 | `.env.example` was missing `LLM_TEMPERATURE`, `LLM_TIMEOUT_S`, `OLLAMA_URL`, `EMBED_QUERY_PREFIX`, `PROMPTS_DIR` present in `config.py` | Added missing variables with default values to `.env.example` in commit `72ab980` | PASS (0 missing) |

## Blocked items
| Test | Reason | What is needed |
|---|---|---|
| P0-2 | `frontend/` directory does not exist in repo; scheduled for Phase 5 | Scaffold React frontend in Phase 5 according to build pack specs |

## Declaration
No tests were skipped, deleted or weakened. No thresholds were lowered.
No golden data or corpus files were modified. No production code returns
hardcoded or mocked results. All PASS results above were produced by the
commands shown, on the commit shown.
