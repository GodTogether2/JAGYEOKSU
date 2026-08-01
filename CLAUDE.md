# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

CareSignal API is an open-source FastAPI service that compares synthetic/simulated water-usage data against a household's own historical pattern, to help welfare caseworkers prioritize phone check-ins or manual review. **It does not predict or diagnose lonely death, death probability, survival status, illness, or emergencies** — this constraint is enforced in code (see Safety constraints below), not just documentation. Do not weaken it.

Do not input real personal data. `request_id`/`household_id` must be anonymous identifiers; the schemas reject names, addresses, phone numbers, and national ID numbers via `extra="forbid"`.

## Competition constraint

CareSignal is submitted to the 2026 오픈소스 개발자대회 (osscontest.kr). 운영규정 제9조 requires every AI model embedded in the submission to be open-weight and independently operable (runnable on a local/self-hosted server) — hosted-API-only models like OpenAI's GPT are not allowed for the submission's core functionality. This is why the anomaly-judgment LLM is `LocalLLMConnector` (Ollama + Qwen3, Apache 2.0) rather than an OpenAI connector. Don't reintroduce a hosted-commercial-API-only model as the core connector without checking this constraint first. Submission deadline: 2026-08-27 18:00 KST.

## Commands

Setup (Windows PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Run the server:

```bash
python scripts/generate_sample_data.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Quality gates (run all before considering work done):

```bash
pytest
ruff check .
ruff format --check .
mypy app
```

Single-module tests (each owner works independently against these):

```bash
pytest tests/unit/test_water_usage_getter.py
pytest tests/unit/test_local_llm_connector.py
pytest tests/unit/test_anomaly_analysis_service.py
```

Single test: `pytest tests/unit/test_anomaly_analysis_service.py::test_name -v`

Integration tests never call a real Ollama server — everything goes through `tests.conftest.FakeLLMConnector` or an injected `request_callable`. Never introduce a test that requires a running Ollama server.

Sample requests live in `samples/*.json` (e.g. `normal_request.json`, `meter_offline_request.json`, `missing_data_request.json`) and can be POSTed directly:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/anomalies/analyze" \
  -H "Content-Type: application/json" \
  --data-binary "@samples/no_usage_request.json"
```

Docker: `cp .env.example .env && docker compose up --build` (runs as non-root, CORS disabled unless `CORS_ORIGINS` is set in development).

## Architecture

Fixed request flow through three independently-owned classes, wired only by dependency injection in [app/api/dependencies.py](app/api/dependencies.py):

```
FastAPI Router → WaterUsageGetter → AnomalyAnalysisService → LocalLLMConnector → AnomalyAnalysisService → AnomalyAnalysisResponse
```

The router ([app/api/routes/anomalies.py](app/api/routes/anomalies.py)) only connects dependencies — it does not compute anything itself.

- **`WaterUsageGetter`** ([app/modules/getter/water_usage_getter.py](app/modules/getter/water_usage_getter.py)) — validates anonymized IDs, timezone-aware/non-future/non-duplicate timestamps, and measurement count (24–5000), then sorts into an immutable `NormalizedWaterUsage`. Does not compute features, build prompts, or call AI. Field-level contract is fully specified in [app/modules/getter/INPUT_SPEC.md](app/modules/getter/INPUT_SPEC.md).
- **`AnomalyAnalysisService`** ([app/modules/detector/anomaly_analysis_service.py](app/modules/detector/anomaly_analysis_service.py)) — computes all objective features in pure Python ([app/utils/feature_utils.py](app/utils/feature_utils.py)), applies safety gates, and assembles the final response. `meter_status == "OFFLINE"` or `missing_ratio >= settings.missing_ratio_threshold` short-circuits to a deterministic local response (`model_provider="local"`) **without calling the LLM**. Otherwise it loads the system prompt from `app/prompts/anomaly_system_prompt.txt`, builds a payload containing only the last 72 hours of measurements plus computed features, and calls the connector. Depends only on `NormalizedWaterUsage` and the `AnalysisConnector` protocol — never instantiate `LocalLLMConnector` directly here, inject `tests.conftest.FakeLLMConnector` instead.
- **`LocalLLMConnector`** ([app/modules/ai/local_llm_connector.py](app/modules/ai/local_llm_connector.py)) — the only class that talks to Ollama (a locally-installed server hosting Qwen3 8B, an open-weight model — required by the competition's 제9조, see above). Uses `ollama.AsyncClient.chat(..., format=AnomalyLLMResult.model_json_schema())` for schema-constrained decoding, never free-text `json.loads`. Public contract is `analyze(system_prompt, user_payload) -> AnomalyLLMResult`, implementing the `AnalysisConnector` Protocol. Does not compute features or write business prompts. Only connection failures (Ollama server not running) are retried, up to `LLM_MAX_RETRIES` times via `tenacity`. A `request_callable` injection point exists for tests to avoid needing a real Ollama server.

### Shared models: `app/common/models/` is canonical, `app/schemas/` is a compat shim

`app/common/models/anomaly.py` and `app/common/models/water_usage.py` are the single source of truth for cross-module Pydantic v2 contracts (`NormalizedWaterUsage`, `WaterUsageAnalysisRequest`, `AnomalyLLMResult`, `AnomalyAnalysisResponse`, etc.). `app/schemas/anomaly.py` and `app/schemas/water_usage.py` only re-export from `app/common/models/` for backward-compatible imports — put new fields/validators in `app/common/models/`, not in `app/schemas/`.

Any change to these shared contracts requires updating both the model and every consuming module's tests in the same PR (Getter, Service, and Connector all import from here).

### Safety gates enforced in code, not just prompting

- `AnomalyLLMResult` field validators reject forbidden diagnostic/death-related terms (see `FORBIDDEN_TERMS` in [app/common/models/anomaly.py](app/common/models/anomaly.py)) and Markdown syntax in `summary`/`limitations`/evidence messages — this runs on every LLM response, not just at prompt-authoring time.
- OFFLINE meter status and missing-ratio-over-threshold cases never reach the LLM at all (see `AnomalyAnalysisService.analyze`).
- `expected_absence=True` downgrades an LLM `CHECK_REQUIRED` verdict to `OBSERVE`/`RECHECK_LATER` and caps `anomaly_score` at 49, in `AnomalyAnalysisService.analyze`.
- Baselines under 30 days and expected-absence context are always appended to `limitations` in the final response (deduplicated, capped at 5).
- Logging ([app/core/logging.py](app/core/logging.py)) only ever writes masked household IDs (`mask_household_id`) and structured metadata as one-line JSON — never raw time series, full prompts/responses, or API keys.

### Per-module owner and contract (see README.md for full Korean-language detail)

| Owner | Module | Responsible for | Does not do |
|---|---|---|---|
| 홍성표 | `WaterUsageGetter` | input validation, sorting, `NormalizedWaterUsage` | feature calc, prompts, AI calls |
| 문범석 | `LocalLLMConnector` | Ollama client, structured outputs, timeout/retry/error translation | feature calc, business prompt authoring |
| 최지욱 | `AnomalyAnalysisService` | feature calc, payload/prompt loading, safety gates, final response assembly | SDK init, HTTP routing |

When changing one module's internals, don't reach into another owner's module directly — go through the shared models and the `AnalysisConnector` protocol boundary.

### Configuration

All settings are read once via `app.core.config.get_settings()` (`lru_cache`d `Settings` from `pydantic-settings`, backed by `.env`). Never read `os.environ` directly elsewhere — inject `Settings` through FastAPI `Depends`. `settings.llm_configured` exposes only whether an LLM model name is set.
