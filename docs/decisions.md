# Decisions and rationale

Normative requirements live in `SPEC.md`; work order lives in `PLAN.md`. This file records
choices and reasons. It does not restate the contract.

## Scope

- Lean path: Common 100%, checks `S01`–`S21`, Rare 1–2, Legendary 1 and 4: Telegram bot and the local `$0` model. This line is the source of truth for the claimed levels.
- Not claimed: `R05` (two-model comparison), `L03` (five runs), `V00`–`V05` (`--live` with the mentor), video. README must state this explicitly.
- Epic (1000+ catalog, `candidates()`, `pick_big()`, embeddings/TF-IDF) is out of scope.
- Free-text Q&A is an unclaimed bonus; it is not built and is not part of Common.
- README is written only after real runs; numbers come from `calls.jsonl` and `memory_calls.jsonl`, never from estimates.

## Catalog

- Canonical English source: `data/en/films.json`.
- `data/ru/films.json` is the Russian source for provenance.
- 40–60 films; minimum 5 with the exact token `"Казахстан"`.
- 20 English canonical genres; synonyms are mapped before writing.
- IDs are unique and of one type; recommended format is string `f-001`.
- When translating, `id`, `year` and `minutes` are not changed.
- The catalog is not generated from model memory; source is TMDb plus independent verification.
- Runtime does not call TMDb or IMDb.

## Model and client

- Default: local `qwen3.5:4b` via Ollama, `reasoning_effort="none"`.
- Cloud fallback: `gpt-6-luna`, opt-in only through `.env`.
- The model is not hardcoded: `pick` receives it as an argument.
- One OpenAI client per process, `max_retries=0`, timeout 60 seconds.
- Tests never create a real client; only a fake.
- Environment variables are listed only in `.env.example`; no other document repeats the list.

## Schemas and `pick`

- `Selection`: `status: Literal["ok", "no_match", "clarify"]`, `reason`, `picks`.
- `Pick`: `film_id: str | int`, `why`.
- `Filters`: all fields default to `None`.
- Extra fields are forbidden (`extra="forbid"`).
- `film_id` accepts strings and integers; float, `null` and precision loss are not allowed.
- Code verifies IDs against the catalog allowlist; a dynamic `Literal` is only a hint, never the
  only check.
- `pick(client, model, query, films) -> (outcome, ids)`.
- `pick` prints films itself, only after successful validation.
- `pick` does not read `data/en/films.json` or any other file.
- `pick` validates only received IDs, not the entire catalog.
- `pick` works with a small catalog (minimum 4 films) and does not require 40–60.
- ID order is preserved as returned by the model.
- `pick` always makes a `Filters` call, even with empty conditions, so `R02` is stable. Cost is one extra call per request.
- Two-stage flow: `Filters` → code filters the catalog → `Selection` by candidates → re-check
  the selected films.
- If no candidates remain, return `no_match` without a choice call.
- If a selected film violates a filter, return `invalid`; no partial answer.
- Only candidates go to the choice prompt, never the full catalog.

## Prompt and protection

- Tags are defined only in `SPEC.md` §6: English `<catalog>`, `</catalog>`, `<query>`,
  `</query>`. The probe expects these exact tags.
- Catalog is serialized with `json.dumps(..., ensure_ascii=False)`.
- The query is escaped with `html.escape(query, quote=False)`.
- The system prompt contains exactly one full response example.
- The full runtime catalog appears only inside `<catalog>`.
- Catalog strings do not contain prompt tags or ASCII control characters.
- The model has no tools and cannot retrieve a film outside the catalog.

## Guardrails for `why` and `reason`

- `why`: strip, non-empty, ≤300 characters, one line.
- Control characters and ANSI are removed; an impermissible value is `invalid`.
- A year 1888–2099 in `why` must match the selected film or appear in the query.
- Explicit minutes in `why` must match `minutes` or appear in the query.
- Another catalog film's title is forbidden if it is not in the query; its own title is allowed.
- Word-boundary check so `Drive` is not caught in `Driver`.
- Numeric checks on `reason` are a quality warning, not a hard failure: `reason` is explanatory,
  not a film field.
- Catalog titles should be unique so the “other title in `why`” check is unambiguous.

## Journal

One model call writes one JSON line to `calls.jsonl`.

- Required: `time` (UTC ISO 8601), `model`, `request`, `outcome`, `step`.
- `step`: `filters` for the filter call, `choice` for the choice call.
- `rejected` is required on `invalid` when foreign IDs exist.
- Optional: `usage`, `usd`, `seconds`.
- `request` contains the query and candidate/catalog IDs, but not the full catalog.
- UTF-8, one JSON object per line, `ensure_ascii=False`.
- The committed `calls.jsonl` is valid JSONL; `show.py` may skip broken lines.
- A journal write error prints a warning to stderr and does not crash.
- `calls.jsonl` is not in `.gitignore` and is committed after a real run.
- `memory_calls.jsonl` is a separate journal for the memory experiment.
- The journal contains no keys, full prompt or full catalog.

## CLI, `check.py`, `show.py`

- CLI accepts exactly one positional query.
- Empty/whitespace and queries longer than 1000 characters are rejected before the model call.
- Exit codes: `0` for `ok`/`no_match`, `1` for `invalid`, `2` for operational errors.
- `kino.py` prints nothing on import, does not read files and does not create a client.
- `check.py` reuses `pick` and does not duplicate selection logic.
- `check.py` makes one run by default; `--model` and `--runs` are for the full bonus path.
- `check.py` counts requests by `step`, not by all journal lines.
- `show.py` ignores broken lines and prints outcomes, models, tokens and USD.
- `queries.json`: 30 queries, each with `expect`, no duplicate text.

## Telegram bot

- Entry: `uv run python -m movie_bluff_ai_bot`.
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_API_BASE` and transport settings come from `.env` (see `.env.example`).
- `state.json` (or the path from `.env.example`) stores per-chat state, is written atomically and is gitignored.
- State fields: `seen_ids`, `excluded_ids`, `excluded_genres`, `last_query`, `last_filters`, `pending_clarify`, `clarify_turns`, `updated_at`.
- “More” returns only new films; a re-shown ID is `invalid`.
- Exclusions live until `/new`.
- `clarify`: one question, empty `picks`, limit `MAX_CLARIFY_TURNS=1`, then `no_match`.
- A command during `pending_clarify` is handled as a command.
- Text is escaped; messages over 4096 characters are split.
- `callback_data` is checked against an allowlist.
- `429`, `5xx` and network errors back off without crashing.
- Per-chat lock; one response per update.
- The bot does not log the token, full prompt or full catalog.

## Process

- `SPEC.md`, `AGENTS.md`, `PLAN.md`, `.pre-commit-config.yaml` and `.github/workflows/` are part
  of the delivery.
- CI runs `pytest`; pre-commit runs `ruff check`, `ruff format --check` and `pytest`.
- Each PLAN step: failing test → minimal implementation → green pytest.
- One step, one commit; `--no-verify` is forbidden.
- `SPEC.md` and the test appear no later than the code.
- A reviewer sub-agent only advises and does not edit files.

## Decision log (moved from SPEC)

- **D-01**: `countries` uses the exact token `"Казахстан"`; the autocheck counts this string.
- **D-03**: `film_id` is `str | int`; the autocheck can generate all-integer catalogs.
- **D-05**: the client uses `max_retries=0`; one `pick` call produces at most one model request
  and one journal row.
- **D-06**: code messages are English; `why` and `reason` follow the query language.
- **D-07**: TMDb is the primary catalog source; year and runtime are cross-checked.
- **D-08**: `why` guardrails fail closed; a rejected reason is safer than an unverifiable claim.
- **D-09**: numeric checks on `reason` are a quality warning, not a hard failure.
- **D-10**: catalog titles should be unique for the “other title” check.
- **D-11**: a dynamic `Literal` for `film_id` is optional and never the only check.
- **D-12**: the memory experiment logs to `memory_calls.jsonl`, keeping `calls.jsonl` clean.
- **D-14**: `show.py` reports outcomes, models, tokens and USD; these are the README numbers.
- **D-16**: free-text Q&A is a bonus with its own entry point; it is not claimed.
- **D-17**: the catalog is not generated from model memory; this is why the project exists.
- **D-18**: the real-run model name must not match the autocheck stub pattern (`stub`, `fake`,
  `mock`, `test`, `заглушк`, `model-xxxxxx`).
- **D-19**: `pytest` and `ruff` are the only dev tools; any other package needs explicit
  approval.

## Optimisations

1. Pre-filter before the choice call; send only filtered candidates, capped at 30.
2. `reasoning_effort="none"` for local `qwen3.5:4b`; otherwise one call can take minutes.
3. One client, `max_retries=0`: one `pick` call makes at most one request per stage.
4. Journal `step` (`filters`/`choice`); `show.py` counts requests, not raw rows.
5. Short `request` payload (query + IDs), never the full catalog.
6. Cache the catalog in memory; do not re-read `data/en/films.json` per message.
7. Single `queries.json` with optional level tags.
8. Code allowlist is authoritative; `Literal` is optional schema help only.
9. Atomic `state.json` writes (tmp then replace); corrupt state starts clean.
10. Fake client in tests and CI: no network, no API key, deterministic.
11. Local model for free runs; cloud only when required.
12. README numbers come from `calls.jsonl` with model and run count; no estimates.
