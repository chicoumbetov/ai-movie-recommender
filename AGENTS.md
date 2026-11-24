# Movie Buff

An AI movie recommendation system that understands complex and unconventional queries.

- Behavior contract "how to do": `SPEC.md` (normative; do not duplicate it here)
- Work order "what to do": `PLAN.md`
- Choices and reasons: `docs/decisions.md`

## Stack

Python 3.12, uv, OpenAI SDK, Pydantic, pytest. Local default: `qwen3.5:4b` via Ollama with
`reasoning_effort="none"`. Keys only in `.env`; `.env` is not in git. If unsure about an API,
read the docs inside the installed package instead of relying on memory.

## Language and style

- `SPEC.md`, `PLAN.md`, `AGENTS.md`, `README.md`: English.
- Code-generated CLI and bot messages: English.
- `why` and `reason`: the language of the query.
- Code is identified by spec; without spec nothing is built.

## Start of a phase

Read this file, `SPEC.md`, and the current `PLAN.md` step. Build only what the step asks, then
stop. If context is lost, inspect the files and `git log`; the last commit is the last passed
phase. State what you worked out before building on it.

## Acceptance ownership

- The agent checks before saying a phase is done: `uv run pytest -q`, types, lint, build, CLI
  smoke tests, `check.py`.
- The owner runs the final `python3 -I checks/kino_check.py .` on the last commit and `--live`
  on the owner's machine. The owner also checks the Telegram bot manually, verifies three films
  against their sources, and checks README numbers against `calls.jsonl`.
- `checks/` is a local copy of the mentor's autocheck, not part of the delivery. Do not expose
  or call `kino_probe.py`; it is an internal probe.
- Do not adjust code to the autocheck's random values and do not weaken tests to pass.

## Working cycle

1. Write or update a failing test for one `SPEC.md` criterion.
2. `uv run pytest -q` — confirm it fails as expected.
3. Make the minimal implementation.
4. `uv run pytest -q` — green. Do not delete or weaken tests for a green run.
5. Commit without `--no-verify`, with the step number, and mark the step in `PLAN.md` in the
   same commit.

If `SPEC.md`, `PLAN.md`, the task and the autocheck disagree, stop, show the discrepancy and
propose one option. Do not choose a side silently.

## Contract with the autocheck

The full contract is in `SPEC.md` §2, §6–§8. The non-negotiables:

- `kino.py` does nothing on import; execution only under `if __name__ == "__main__":`.
- `pick(client, model, query, films)` returns `(outcome, ids)`. Any outcome except `ok` has
  empty `ids`.
- `pick` prints the shown films itself, using only facts from the passed `films`; it never reads
  `data/en/films.json` and validates only received IDs.
- The model call is `client.chat.completions.parse(..., response_format=Selection)`.
- `Selection` has `status`, `reason`, `picks`; `Pick` has `film_id`, `why`; extra fields are
  forbidden.
- `calls.jsonl` has one line per model call with `model`, `request`, `outcome`, `step`; on
  `invalid` also `rejected`; `request` contains the query and IDs, not the whole catalog.
- Rare uses `Filters` with all fields defaulting to `None`; journal `"step": "filters"` and
  `"step": "choice"`.
- Legendary adds `clarify`; Common uses only `ok` and `no_match`.

## Code structure

- ID verification is done by code, not by prompt words.
- Film facts come from the catalog; the model writes only `reason`, `why` and the `clarify`
  question.
- A foreign ID is `invalid`, goes to `rejected`, and is never shown.
- Errors never crash the program: no connection, API error, refusal, truncation,
  `pydantic.ValidationError`.
- One client, created in one place.
- Selection logic lives only in `pick`; the CLI, `check.py` and the bot reuse it.

## Conventions

Strict types everywhere. If a type is genuinely awkward, say so rather than casting.
Comment decisions, not syntax. Prefer one obvious way over a configurable one.
README is written from facts.

## Things not to do

Breaking one of these is worse than not finishing.

- Do not collect the catalog from model memory, and do not let the model write title, year,
  minutes, genres, countries, languages or description.
- Do not show a film outside the catalog. Foreign ID → `invalid`, nothing printed.
- Do not weaken verification or tests to get green. A check that cannot run must fail loudly.
- Do not install a package without asking: name it, say why, wait. `pytest` and `ruff` are the
  agreed dev tools.
- Do not build ahead of the current phase. Rare, Legendary and Epic only when the plan says so.
- Do not put keys, tokens or secrets in the repository, chat, issues, README, logs or
  screenshots. `.env.example` has placeholders only.
- Do not read `data/en/films.json` inside `pick`; do not print anything on import.
- Do not return more than 3 films, duplicates, `ok` with empty `picks`, or `no_match` with
  non-empty `picks`.
- Do not “lose” a film that violated a Rare filter: it is `invalid`, not a partial answer.
- Do not translate the token `"Казахстан"`; do not change `id`, `year` or `minutes` when
  translating the catalog.
- Do not enable OpenAI client retries: `max_retries=0`.
- Do not use a webhook for Telegram, send unescaped HTML/Markdown, or write `state.json`
  without an atomic write.
- Do not commit `.env`, `state.json`, keys or tokens.
- Do not invent numbers or estimate cost “at a glance”. Use `calls.jsonl` and real runs.
- Do not use `stub`, `fake`, `mock` or `test` in the real-run model name.
- Do not run the final autocheck before commit; it checks `HEAD`.
- Do not delete decision or passed-action history for “cleanliness”.

## How to talk to me

Briefly. If a sentence does not convey needed information, strike it.

- **Question with a ready answer:** one question plus “I would choose B, because …”. Never choose a direction silently, never do both.
- **Need something only from me** (a key, a value in `.env`): say what and where, then stop.
- **After a phase:** a few lines on what it does and what the check should show.
- **If something did not work:** say so. Quietly bypassing an error costs an hour later.
