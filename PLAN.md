# PLAN: Lean Common-first

- Key markers: `Do:`, `Test:`, `Done:`
- Working cycle section
- Phase 0 - process and environment
- Phase 1 - catalog (Steps 5-8)
- Phase 2 - schema, prompt, `pick`
- Phase 3 - schemes, filters, journal
- Phase 4 - CLI and `show.py`
- Phase 5 - 30 queries and `check.py`
- Phase 6 - model memory, real runs, README
- "Do not break" section guidelines

## Working cycle per step

1. Write or update a failing test.
2. `uv run pytest -q` — ensure it fails exactly as expected.
3. Make a minimal implementation.
4. `uv run pytest -q` — green.
5. Commit without `--no-verify`.

## Phase 0 — process and environment

- [x] **Step 1. Baseline + pytest/dev dependencies**
  - Do: add `[dependency-groups] dev = ["pytest"]`, `[tool.pytest.ini_options]` with `pythonpath = ["."]`, `testpaths = ["tests"]`, `[tool.ruff]` with target `py312`; run `uv lock`.
  - Test: `tests/test_config.py` reads `pyproject.toml` via `tomllib` and checks `pythonpath`, dev group and `requires-python >= 3.12`. `tests/conftest.py` — fixtures: catalog of 4 films with string ids, catalog with int ids, fake client factory.
  - Done: `uv run pytest -q`; commit `chore: add spec baseline, pytest config and dev deps`.

- [x] **Step 2. Process files**
  - Do: `opencode.jsonc` (deny `--no-verify` and reading `.env`, except `.env.example`).
  - Test: `tests/test_process.py` — `AGENTS.md` and `PLAN.md` exist; in `AGENTS.md` there are commands `uv sync --frozen`, `uv run pytest -q`, `uv run check.py`, `uv run show.py` and prohibitions; in `PLAN.md` there are `- [ ]`; `opencode.jsonc` contains the required denies.
  - Done: `uv run pytest -q`; commit `docs: add agent workflow and plan`.

- [x] **Step 3. Repository hygiene**
  - Do: check that `calls.jsonl` is not ignored; add to `.gitignore` `state.json`, `state.json.tmp`, `qa_calls.jsonl`; in `.env.example` — all variables as placeholders: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `MODEL=qwen3.5:4b`, `REASONING_EFFORT=none`, `TMDB_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_BASE`, `BOT_STATE_PATH=state.json`, `TELEGRAM_POLL_TIMEOUT_SECONDS=30`, `TELEGRAM_MAX_MESSAGE_CHARS=4096`, `MAX_CLARIFY_TURNS=1`, `CHECK_RUNS=1`.
  - Test: `tests/test_repo_hygiene.py` — `calls.jsonl` is not ignored, `state.json` is ignored, all `.env.example` keys present, no values resembling keys, `.env` not in `git ls-files`.
  - Done: `uv run pytest -q`; commit `chore: repo hygiene and env template`.

## Phase 1 — catalog

- [x] **Step 4. Constants + catalog validation**
  - Do: in `kino.py` — `GENRES` (20 English), `MAX_PICKS=3`, `MAX_QUERY_CHARS=1000`, `MAX_WHY_CHARS=300`, `REQUEST_TIMEOUT_SECONDS=60`, `CATALOG_PATH`, `JOURNAL_PATH`; `validate_catalog(films) -> list[str]`.
  - Test: `tests/test_catalog_validation.py` — all rules 4.4: 40–60, fields and types, unique ids, one id type, year/minutes, 1–4 genres from the dictionary, non-empty countries/languages, ≥5 `"Казахстан"`, tag prohibition (case-insensitive), control chars, description 20–500. Plus a test that importing `kino.py` prints nothing and does not read files.
  - Done: `uv run pytest -q`; commit `feat: catalog validation and constants`.

- [x] **Step 5. Catalog loader**
  - Do: `load_catalog(path=CATALOG_PATH)` — exists/readable/UTF-8/JSON, collects **все** problems, raises `CatalogError`; CLI prints them to stderr.
  - Test: `tests/test_catalog_loader.py` — no file, broken JSON, broken UTF-8, not multiple problems at once, valid file.
  - Done: `uv run pytest -q`; commit `feat: catalog loader with full validation`.

- [x] **Step 6. Catalog build script**
  - Do: `scripts/build_catalog.py` — reads `TMDB_API_KEY` only from `.env`, fetches TMDb, maps genres to canon, writes `data/en/films.json` and `catalog_sources.json`; without key — understandable error.
  - Test: `tests/test_catalog_build.py` — mapping synonyms, key absence → code 2 and message, fake TMDb payload → correct fields.
  - Done: `uv run pytest -q`; commit `feat: one-off catalog build script`.

- [x] **Step 7. Provenance**
  - Do: `catalog_sources.json` for 40 films: `tmdb_id`, `retrieved_at` (UTC ISO), `wikipedia_url`, `verified_by`; minimum 10 independent verifications, including all KZ.
  - Test: `tests/test_catalog_provenance.py` — 40 records, keys, ISO-dates, URL, ids match with `data/en/films.json`, all KZ have independent link.
  - Done: `uv run pytest -q`; commit `data: add catalog provenance`.

## Phase 2 — shema, prompt, `pick`

- [x] **Step 8. Pydantic-schemas**
  - Do: Verify `Pick` (`film_id: str | int` strict, `why: str`), `Selection` (`status: Literal["ok","no_match","clarify"]`, `picks`), `Filters` (all fields `None`), `extra="forbid"`.
  - Test: `tests/test_schema.py` — ok/no_match/clarify; extra field → error; film_id=null and float → error; missing fields → error; Filters by default all None.
  - Done: `uv run pytest -q`; commit `feat: response schemas`.

- [x] **Step 9. Prompt**
  - Do: system prompt with rules 1–10 and exactly one example response; `build_messages(films, query)` — `<catalog>`, `</catalog>`, `<query>`, `</query>`, `json.dumps(films, ensure_ascii=False)`, `html.escape(query, quote=False)`.
  - Test: `tests/test_prompt.py` — tags, entire catalog, escaping `<>&`, determinism, one example, «data, not instructions», full catalog not in system prompt.
  - Done: `uv run pytest -q`; commit `feat: prompt builder`.

- [x] **Step 10. Filter logic**
  - Do: `apply_filters(films, filters)`, `violates_filters(film, filters)`, `catalog_vocabulary(films)`.
  - Test: `tests/test_filters.py` — `max_minutes`, inclusive `year_from/year_to`, `languages` (at least one), `exclude_genres`, `must_genres`, `[] == None`, without conditions — entire catalog.
  - Done: `uv run pytest -q`; commit `feat: rare filter logic`.

- [x] **Step 11. Journal**
  - Do: rewrite `utils.log()`: `time` UTC ISO 8601, `model`, `request` (query + ids, without catalog), `outcome`, `step`, `rejected`, `usage`, `usd`, `seconds`; `ensure_ascii=False`; write error → warning in stderr, don't crash.
  - Test: `tests/test_journal.py` — one line per call, mandatory fields, no full catalog, UTF-8, unknown price → `usd=0`, unavailable path → warning.
  - Done: `uv run pytest -q`; commit `feat: structured call journal`.

- [x] **Step 12. `pick`: happy path**
  - Do: `pick(client, model, query, films)` — filter-call (`Filters`, step `filters`), when there are no candidates `no_match` without choice-call, choice-call (`Selection`, step `choice`), id check, printing films **inside `pick`** from the passed catalog, return `(outcome, ids)` in model order.
  - Test: `tests/test_pick_ok.py` — string and int id, order, printing title/year/minutes/genres/countries/languages/description + `Why:`, catalog of 4 films, foreign catalog (films.json is not read), with active filters only candidates in choice-prompt.
  - Done: `uv run pytest -q`; commit `feat: two-stage pick and catalog printing`.

- [x] **Step 13. `pick`: invalid answers**
  - Do: foreign id → `invalid` + `rejected` + nothing print; duplicate; >3; `ok` with empty `picks`; `no_match` with `picks`; `no_match` prints `why` or generic; `clarify` with empty `picks`; `ValidationError` → `invalid`; trim spaces; numeric string for int id; `1` and `"1"` — duplicate.
  - Test: `tests/test_pick_invalid.py` — each case, `ids` empty for all outcomes except `ok`.
  - Done: `uv run pytest -q`; commit `feat: id and status validation`.

- [x] **Step 14. `pick`: model errors**
  - Do: `refusal` → `refusal`; `finish_reason=length` → `length`; `APIConnectionError`/`APITimeoutError` → `no_connection`; `APIStatusError` → `error_<code>`; unexpected exception → `invalid` + diagnostic in stderr, process doesn't crash. Same for filter-stage.
  - Test: `tests/test_pick_errors.py` — all outcomes, journal writes and on errors.
  - Done: `uv run pytest -q`; commit `feat: map model failures to outcomes`.

- [x] **Step 15. Guardrails: sanitization**
  - Do: strip, non-empty, ≤300, one line, removal of ANSI/control chars from `why` and `reason` (empty `reason` after cleaning or invalid `why` -> `invalid`).
  - Test: `tests/test_guardrails.py` — control chars, ANSI, >300, empty, multi-line.
  - Done: `uv run pytest -q`; commit `feat: sanitize why and reason`.

- [x] **Step 16. Guardrails: claims verification**
  - Do: year 1888–2099 must match the selected film's year or be in the query; explicit minutes — same; title of another catalog film is forbidden if it's not in the query; your title is allowed; word boundary check so `Drive` isn't caught in `Driver`; language `why` is not checked.
  - Test: expand `tests/test_guardrails.py` — invalid year, invalid minutes, foreign title, title from query, Russian `why` for English query.
  - Done: `uv run pytest -q`; commit `feat: verify why claims against catalog`.

## Phase 3 — CLI и `show.py`

- [x] **Step 17. `kino.py` CLI**
  - Do: `argparse` with one positional query; `--help` → 0; empty/whitespace and >1000 chars — before model call; control chars; `load_catalog` + `validate_catalog` before client; single client `max_retries=0`, timeout 60; config from env via `dotenv`; exit codes 0/1/2; UTF-8; missing key — clear error. Under `if __name__ == "__main__":`.
  - Test: `tests/test_cli.py` — import without side effects, `--help`, empty and long query, missing and broken catalog, exit codes, `pick` not called on catalog error, UTF-8.
  - Done: `uv run pytest -q`; commit `feat: kino CLI`.

- [x] **Step 18. `show.py`**
  - Do: reads `calls.jsonl`, ignores broken lines, counts outcomes, model, tokens, USD; no file → «no calls», exit 0; unknown price → 0.
  - Test: `tests/test_show.py` — temporary journal, broken line, aggregates, empty file.
  - Done: `uv run pytest -q`; commit `feat: show journal report`.

## Phase 4 — 30 queries and `check.py`

- [x] **Step 19. `queries.json` for 30 queries**
  - Do: 15 Common + 15 Rare; each has `expect`; ≥3 `no_match`; ≥3 with `must`; ≥3 with Kazakh letters `[әғқңөұүһі]`; ≥3 with negation (`не/без/кроме/емес/жоқ`); ≥1 prompt-injection; ≥3 with strict filter; ≥1 `clarify`; no duplicates; all ids from `data/en/films.json`.
  - Test: `tests/test_queries.py` — all R-QRY-01 conditions…10 and 17 plus existence of id.
  - Done: `uv run pytest -q`; commit `data: add 30 evaluation queries`.

- [x] **Step 20. `check.py`: expectations logic**
  - Do: `evaluate(expect, outcome, ids)`; `no_match: true` — shorthand; `must` and `forbid`; report: counts by outcomes, foreign ids caught, pass rate, filter violations; continuation after error; exit non-zero.
  - Test: `tests/test_check_report.py` — passing and failing expectations, report, exit code.
  - Done: `uv run pytest -q`; commit `feat: check expectation report`.

- [x] **Step 21. `check.py`: runner and flags**
  - Do: loading `queries.json` with clear error; run each query through `pick`; `--model`, `--runs`; count by `step`, not by lines; `pick` is reused, choice logic not duplicated.
  - Test: `tests/test_check_runner.py` — fake `pick` and client, continuation after failure, `--runs`, `--model`, exit codes.
  - Done: `uv run pytest -q`; commit `feat: check runner`.

- [x] **Step 22. Rare: acceptance tests**
  - Do: complete pick's behavior: filters didn't leave candidates → `no_match` without choice-call; selected film violates filter → `invalid`; in choice-prompt only candidates; unknown genre or language → `invalid`; journal `step=filters/choice`.
  - Test: `tests/test_rare_flow.py`.
  - Done: `uv run pytest -q`; commit `feat: rare filter acceptance`.

## Phase 5 — `state.json` and bot

- [x] **Step 23. State storage**
  - Do: `movie_bluff_ai_bot/state.py` — `load_state` and `save_state`, A2.4 fields, atomic write (tmp + `os.replace`), broken file → warning and clean state, `BOT_STATE_PATH`, `state.json` in `.gitignore`.
  - Test: `tests/test_state.py` — roundtrip, restart, broken file, atomic (tmp removed), no secrets.
  - Done: `uv run pytest -q`; commit `feat: persistent bot state`.

- [x] **Step 24. Telegram**
  - Do: `movie_bluff_ai_bot/telegram.py` — env, aiogram `Bot` with the session from `SPEC.md` §11, `Dispatcher` long polling, `sendMessage` split 4096, HTML escape, `callback_data` allowlist, no webhook, token not logged; aiogram retries `429`/`5xx`/network — the bot must not crash.
  - Test: `tests/test_bot_transport.py` — fake transport, `429`/`5xx`/network, split, escape, allowlist.
  - Done: `uv run pytest -q`; commit `feat: telegram transport`.

- [x] **Step 25. Commands and free text**
  - Do: `movie_bluff_ai_bot/__main__.py` and handlers: `/start` with an inline genre keyboard (`InlineKeyboardBuilder`), a `callback_query` handler that answers every callback, `/help`, `/new`, `/more`, more, unknown command → `/help`, free text → `pick`, `seen_ids` is populated.
  - Test: `tests/test_bot_handlers.py` — commands, inline callback, free text, `pick` is called, seen_ids, model errors don't crash the bot.
  - Done: `uv run pytest -q`; commit `feat: bot commands and selection`.

- [x] **Step 26. Clarify**
  - Do: `clarify` → one question, `pending_clarify`, merge response with `last_query`, limit `MAX_CLARIFY_TURNS=1`, after limit — `no_match`; command during clarify is handled as a command.
  - Test: expand `tests/test_bot_handlers.py`.
  - Done: `uv run pytest -q`; commit `feat: clarify dialogue`.

- [x] **Step 27. Exceptions and more**
  - Do: «already watched X», «don't want Y», «except Z», «without <genre>» → `excluded_ids` and `excluded_genres`; exceptions until `/new`; removal of seen and excluded before choice-call; repeatedly selected id → `invalid`; no new ones — `no_match`; state survives restart.
  - Test: expand `tests/test_bot_handlers.py` and `tests/test_state.py`.
  - Done: `uv run pytest -q`; commit `feat: more and exclusions`.

## Phase 6 - model memory, real runs, README

- [x] **Step 28. Model memory experiment**
  - Do: `scripts/memory_experiment.py` — 10 films, question about year and duration **without catalog**, recording to `memory_calls.jsonl`, comparison with code, number of discrepancies.
  - Test: `tests/test_memory_experiment.py` — fake client, exact and incorrect answers, separate journal, discrepancy counter.
  - Done: `uv run pytest -q`; commit `feat: model-memory experiment`.

- [x] **Step 29. Real runs on `qwen3.5:4b`**
  - Do: `uv run check.py` across all 30 queries; `uv run show.py`; `uv run kino.py "..."` for `ok`, `no_match` and error; `uv run python scripts/memory_experiment.py`. commiting `calls.jsonl` and `memory_calls.jsonl`, output is saved for README.
  - Test: `tests/test_artifacts.py` — `calls.jsonl` covers all 30 queries, model not stub, has `ok` and `no_match`; memory report contains 10 films.
  - Done: `uv run pytest -q`; commit `data: add real model runs`.
  - Prerequisite: Ollama is running and has `qwen3.5:4b`. If model is missing — step is blocked, need to mention it, not bypass.

- [x] **Step 30. README**
  - Do: first line — exact Lean-claim; five questions lecture 1; commands; real outputs `check.py` and `show.py`; catalog source, date, attribution, verification and translation method; experiment with memory (prompt, answers, discrepancies); five answers task with file:line; honest note about local model; links to `SPEC.md`, `AGENTS.md`, `PLAN.md.`
  - Test: `tests/test_readme.py` — first line, required sections and commands, real output blocks, numbers match with `calls.jsonl`, no placeholders.
  - Done: `uv run pytest -q`; commit `docs: expand README with real results`.

- [x] **Step 31. Final autocheck**
  - Do: after commit — `python3 -I checks/kino_check.py .`; fix found issues; repeat `uv sync --frozen`, `uv run pytest -q`, `uv run check.py`, `uv run show.py`; smoke `uv run python -m movie_bluff_ai_bot` with fake-transport, without long-poll.
  - Test: все `S`-checks green and `uv run pytest -q` green.
  - Done: `uv run pytest -q`; commit `chore: pass autocheck`.

## Phase 7 — Common 100% completion

- [x] **Step 32. Root `films.json` delivery copy**
  - Do: add `films.json` at the repository root as an exact copy of `data/en/films.json`; keep `data/en/films.json` for `S03`.
  - Test: `tests/test_artifacts.py` asserts both files parse to the same object.
  - Done: `uv run pytest -q`; commit `fix: add root catalog delivery copy`.

- [x] **Step 33. Isolate the test journal**
  - Do: add an autouse fixture in `tests/conftest.py` that points `kino.JOURNAL_PATH` at `tmp_path`; verify `tests/test_cli.py` no longer writes the real `calls.jsonl`.
  - Test: run the suite twice; `git diff --exit-code calls.jsonl` stays clean.
  - Done: `uv run pytest -q`; commit `test: isolate the model-call journal`.

- [x] **Step 34. README journal numbers and English-tag note**
  - Do: change the answer-5 “62 calls” to the final 172-call journal and mention the first 62-call run explicitly; add a note that `S18` and the probe expect `<catalog>`/`<query>`, so the tags stay English.
  - Test: `tests/test_readme.py` still passes; grep finds `172` and `first 62-call run`.
  - Done: `uv run pytest -q`; commit `docs: align README journal numbers and prompt tags`.

- [x] **Step 35. Catalog-only memory experiment**
  - Do: replace the four non-catalog films with catalog films; rerun the experiment on `qwen3.5:4b`; update `memory_calls.jsonl`, README prompt/table/discrepancy count, and the memory test.
  - Test: `tests/test_memory_experiment.py`, `tests/test_readme.py`, `tests/test_artifacts.py`.
  - Done: `uv run pytest -q`; commit `data: run memory experiment on catalog films`.

- [x] **Step 36. Remove the unused film module**
  - Do: delete `modules/film/__init__.py` (unused duplicate of `schemas.py`) and the empty `modules/` tree if nothing else remains.
  - Test: `uv run pytest -q`; `ruff check`.
  - Done: `uv run pytest -q`; commit `chore: remove unused film module`.

- [x] **Step 37. Guard empty model choices**
  - Do: in `kino._call_model`, return `(None, "invalid")` when `completion.choices` is empty, before indexing.
  - Test: add a fake-client case with `choices=[]`; process does not crash.
  - Done: `uv run pytest -q`; commit `fix: handle empty model choices`.

- [x] **Step 38. Repository hygiene for local tooling**
  - Do: revert `.codex/config.toml`; add `checks/` and `examples/` to `.gitignore`; keep `network_access` out of the delivery.
  - Test: `git status` has no `.codex` change; `.gitignore` contains both paths.
  - Done: `uv run pytest -q`; commit `chore: ignore local autocheck and examples`.

- [x] **Step 39. Russian prompt tags required by S18**
  - Do: switch prompt delimiters to `<каталог>`/`<запрос>`; update `SPEC.md` §4 and §6, `docs/decisions.md`, README and prompt tests; exclude the local `check/` copy from Ruff.
  - Test: `uv run pytest -q`; `uv run ruff check`; autocheck `S18` green.
  - Done: `uv run pytest -q`; commit `fix: use Russian prompt tags required by S18`.

- [x] **Step 40. Bot startup and slow-call isolation**
  - Do: print `bot started with <model>` before polling; run `pick` via `asyncio.to_thread` so polling is not blocked; ignore an expired `callback.answer()`; default local `REASONING_EFFORT` to `none`.
  - Test: `tests/test_bot_handlers.py` covers the startup line, expired callback, and normal selection; `uv run pytest -q`.
  - Done: `uv run pytest -q`; commit `fix: make the telegram bot start and respond reliably`.

- [x] **Step 41. Cloud benchmark profile for R05**
  - Do: `load_settings(profile="cloud")` reads `OPENAI_CLOUD_API_KEY`, `OPENAI_CLOUD_BASE_URL`, `OPENAI_CLOUD_MODEL`; `check.py --profile cloud` selects it; `.env.example` documents the three names; local `REASONING_EFFORT` defaults to `none`.
  - Test: `tests/test_check_runner.py` checks the cloud profile and model; `uv run pytest -q`; `uv run ruff check`.
  - Done: `uv run pytest -q`; commit `feat: add cloud profile for the R05 benchmark`.

- [x] **Step 42. Clarify a general request**
  - Do: the system prompt returns `clarify` for a request with no usable preference and never uses `no_match` for it; the bot writes its calls to `bot_calls.jsonl` so the evaluation journal stays stable.
  - Test: `tests/test_prompt.py` checks the clarify rule; `tests/test_bot_handlers.py` checks the bot journal path; a local model check of `Recommend me something good.` and `Посоветуй что нибудь` returns `clarify`.
  - Done: `uv run pytest -q`; commit `fix: clarify a general request and isolate bot calls`.

- [x] **Step 43. Russian catalog mirror**
  - Do: sync `data/ru/films.json` with the English facts (year, minutes, genre/country/language sets) and Russian labels; keep titles and descriptions Russian and the token `Казахстан` exact; update README and `docs/decisions.md`.
  - Test: `tests/test_catalog_translation.py` compares every record with a fixed label map; `uv run pytest -q`.
  - Done: `uv run pytest -q`; commit `data: sync the Russian catalog with the English facts`.

- [ ] **Step 44. R05: two models, three runs each**
  - Do: make every query reach the `choice` stage, then run `uv run check.py --profile local --runs 3` and `uv run check.py --profile cloud --runs 3`; add a README table with pass rate, foreign IDs, seconds, and price for both models.
  - Test: autocheck `R05` green (`sum(n >= 3) >= 2`); README numbers match `calls.jsonl` and `show.py`.
  - Done: `uv run pytest -q`; commit `data: add two-model R05 benchmark`.
  - Status: not complete. The local three-run benchmark is recorded. The cloud three-run attempt
    stopped on HTTP 429 after 98 calls: 6 queries succeeded and 84 requests ended `error_429`;
    the measured report was 9/90 (10.0%) under the `check.py` rule, and the provider charged
    $0.003016. The owner kept the 180-call cap and chose to leave R05 unclaimed; the attempt is
    recorded in `calls.jsonl` and README.

- [x] **Step 45. L03: one model, five runs**
  - Do: run the same set five times on `qwen3.5:4b`; add the all-five-runs pass rate next to the single-run rate in README.
  - Test: autocheck `L03` green (`any(n >= 5)`); README numbers match the journal.
  - Done: `uv run pytest -q`; commit `data: add five-run L03 repeatability`.
  - Status: done. Clean local report: 143/150 (95.3%); 25/30 queries passed all five runs;
    each query has at least 17 `choice` rows in `calls.jsonl`. The journal totals are in README
    and come from `show.py`.

- [ ] **Step 46. Owner acceptance**
  - Do: owner restores `check/`, commits, then runs `python3 -I check/kino_check.py .` and `--live`; verifies `S01–S21`, `R02–R05`, `L02–L03`, the Telegram bot, the video link, and three catalog facts.
  - Test: all claimed checks green; `calls.jsonl` unchanged.
  - Done: owner confirms; no agent commit.

## Do not break

- `pick` does not read `data/en/films.json`, does not validate catalog fields and prints films itself.
- No keys, full prompt and full catalog; `request` contains query and ids.
- `calls.jsonl` not in `.gitignore`; `state.json` — in `.gitignore`.
- The real run model name should not match the stub-regex (`stub|fake|mock|test|shadow|model-xxxxxx`).
- `kino_check.py` copies **HEAD**, so the final check should only be run after commit.
