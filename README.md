# Common 100%; Rare points 1–2; Legendary points 1 and 4

Movie Buff recommends films from a fixed catalog for natural-language requests. The model proposes catalog IDs and short reasons; the program verifies each ID and prints film facts from the catalog.

This is the project’s claimed Lean scope. The completed three-pass local evaluation scored 83/90 (92.2%), and the five-run local report scored 143/150 (95.3%). These claims describe implemented coverage, not a promise that every model answer is correct.

## Purpose

The aim is to help someone find a film from a curated list when they describe a premise, mood, language, or a mix of constraints in ordinary language.

The program uses a two-stage model call. It extracts optional filters, applies those filters in code, then asks for a choice from the remaining catalog. Code checks the returned IDs before showing any film.

### Five questions from lecture 1

1. **What problem does the program solve?** It helps a person find a suitable film in a curated catalog from a natural-language request.
2. **What could solve it without machine learning?** A rules-based search could match explicit metadata such as genre, year, runtime, and language. It is easy to inspect, but it misses indirect descriptions of plot, mood, and combinations of ideas.
3. **What data does the program use?** A 40-film catalog in `data/en/films.json`, built from TMDb data and independently checked against linked sources. The catalog was not generated from model memory.
4. **What does the program output?** One to three catalog films with their catalog facts and a short reason, or a no-match message. It can also report an operational or validation outcome.
5. **What does an error cost?** A bad recommendation can waste the viewer’s time or spoil a choice. A fabricated film fact is also a trust failure, so the program validates IDs and prints facts from its own catalog.

## Quick start

Use Python 3.12, install the locked dependencies, and configure the local Ollama connection as described by `.env.example`. The default local model is `qwen3.5:4b` with reasoning effort set to `none`.

```bash
uv sync --frozen
uv run kino.py "a film like Interstellar, but not about space"
uv run check.py
uv run show.py
uv run pytest
```

The command form for a request is `uv run kino.py "..." `. Replace the dots with a natural-language request. `check.py` runs the 30 saved evaluation queries; `show.py` summarizes the model-call journal.

## How selection works

1. The model extracts optional filters from the request.
2. Python applies year, runtime, language, and genre filters to the catalog.
3. The model selects from the remaining film IDs. Python rejects unknown, repeated, or otherwise invalid IDs. Only after validation does it print a film, using facts from the catalog.

The model does not supply titles, years, runtimes, genres, countries, languages, or descriptions. An answer that names a foreign ID is rejected and never shown.

Prompt tags are Russian: the code sends the catalog inside `<каталог>` and the request inside `<запрос>`. The mentor autocheck `S18` requires these exact tags, so they match the PDF wording. An earlier version used English `<catalog>`/`<query>` and failed `S18`.

## Real evaluation

The local three-run benchmark ran all 30 queries three times on `qwen3.5:4b` and passed 83/90
(92.2%). Every query reached the `choice` stage (90 filter calls and 90 choice calls). It caught
no foreign IDs and reported no filter violations. The local model has no API price, so the
journal reports $0 for these calls.

A separate five-run local report is recorded in `real_run_output.txt` and `calls.jsonl`. It
passed **143/150 (95.3%)**, and 25 of 30 queries passed in all five runs (83.3%). The individual
runs passed 29/30, 30/30, 29/30, 28/30 and 27/30. Every request reached the `choice` stage
(150 filter calls and 150 choice calls). This is the L03 evidence: every query has at least five
`choice` rows in the local journal.

### Cloud R05 attempt

The cloud profile (`gpt-6-luna`) was tried for the two-model R05 comparison. The three-run
attempt made 98 calls before the API returned HTTP 429: 6 queries returned a real answer, 84
requests ended `error_429`, and the provider charged $0.003016 for the completed calls. Under
the owner’s 180-call cap, a clean 30-query ×3 run could not be completed, so R05 remains
unclaimed. The failed rows stay in `calls.jsonl`; they are not hidden or deleted. The measured
cloud report is 9/90 (10.0%) under the `check.py` rule, but only 6 of those were real answers;
the other three are `forbid`-only queries that pass with empty IDs even on an error.

| Benchmark | Model | Calls | Pass rate | Foreign IDs | Seconds | USD |
|---|---|---|---|---|---|---|
| Local ×3 | `qwen3.5:4b` | 180 | 83/90 (92.2%) | 0 | 894.0 | $0 |
| Local ×5 | `qwen3.5:4b` | 300 | 143/150 (95.3%) | 0 | 1425.8 | $0 |
| Cloud ×3 attempt (stopped) | `gpt-6-luna` | 98 | 9/90 (10.0%) | 0 | 32.5 | $0.003016 |

The cloud row is the failed attempt: 84 of its 98 calls ended `error_429`, and only 6 queries
returned a real answer. It is shown for transparency, not as a completed R05 comparison. The
seconds and USD values are sums from the corresponding `calls.jsonl` rows.

`check.py` output for the local three-run benchmark:

```text
Outcome counts:
  clarify: 2
  no_connection: 1
  no_match: 12
  ok: 75
Foreign IDs caught: []
Filter violations: 0
Model calls by step:
  choice: 90
  filters: 90
Pass rate: 83/90 (92.2%)
Failures:
  query 23: 'A Kazakh-language film about a robot uprising' expected {'no_match': True}, got no_connection []
  query 30: 'Recommend me something good.' expected {'outcome': 'clarify'}, got ok ['kz-003', 'int-018', 'int-028']
  query 33: 'A mafia family epic' expected {'must': ['int-002']}, got no_match []
  query 41: 'A man who runs across America' expected {'must': ['int-012']}, got no_match []
  query 52: 'A film released before 1980 with a runtime over 200 minutes' expected {'must': ['int-016']}, got no_match []
  query 82: 'A film released before 1980 with a runtime over 200 minutes' expected {'must': ['int-016']}, got no_match []
  query 87: 'Ғарыш туралы фильм, бірақ соғыс емес' expected {'must': ['int-003']}, got ok ['kz-003']
```

Local five-run report (film output suppressed; the journal still records every call):

```text
Outcome counts:
  clarify: 5
  invalid: 1
  no_match: 19
  ok: 125
Foreign IDs caught: []
Filter violations: 0
Model calls by step:
  choice: 150
  filters: 150
Pass rate: 143/150 (95.3%)
Failures:
  query 22: 'A film released before 1980 with a runtime over 200 minutes' expected {'must': ['int-016']}, got no_match []
  query 82: 'A film released before 1980 with a runtime over 200 minutes' expected {'must': ['int-016']}, got no_match []
  query 112: 'A film released before 1980 with a runtime over 200 minutes' expected {'must': ['int-016']}, got no_match []
  query 116: 'Қазақстанда түсірілген фильм' expected {'must': ['kz-001', 'kz-002', 'kz-003', 'kz-004', 'kz-005']}, got invalid []
  query 123: 'A mafia family epic' expected {'must': ['int-002']}, got no_match []
  query 144: 'Фильм про космос, но не про войну' expected {'must': ['int-003']}, got ok ['int-027', 'int-035']
  query 147: 'Ғарыш туралы фильм, бірақ соғыс емес' expected {'must': ['int-003']}, got ok ['int-035', 'int-027']
```

`show.py` output for the full journal:

```text
Calls: 1347
Outcomes:
  clarify: 17
  error_429: 84
  invalid: 8
  no_connection: 4
  no_match: 88
  ok: 1146
Models:
  gpt-6-luna: 98
  qwen3.5:4b: 1249
Tokens: prompt=1927525, completion=75268, total=2002793
USD: 0.003016
```

The journal keeps 172 earlier local calls restored from the previous commit, the local three-run
benchmark, the completed five-run repeat, the cloud 429 attempt, an interrupted extra local report
attempt, and the clean five-run report. The `show.py` totals cover every row, including the failed
cloud calls and the restored earlier calls. The pass rates above come from the corresponding
reports, not from the journal totals.

## Telegram demonstration

[Watch the recorded Telegram bot demonstration](https://drive.google.com/file/d/1APMZaH40BTPDoRI77rL37VLj7bRwz_qO/view?usp=drivesdk). During a manual check, the bot received the broad request “Посоветуй что нибудь” and replied “Недостаточно конкретики для подбора фильма.”

## Catalog and provenance

The English catalog contains 40 films. It was built from English-language TMDb data, with Wikipedia references recorded for independent verification. The catalog was not generated from model memory. `catalog_sources.json` records the catalog `id`, `tmdb_id`, retrieval timestamp, `wikipedia_url`, and `verified_by` for each film. The recorded retrieval timestamp is **2026-11-24T11:32:41Z**.

The English file uses TMDb’s English-language (`en-US`) fields; the catalog builder maps its genre labels to the project’s canonical English list. `data/ru/films.json` is a Russian-language mirror of the same facts: IDs, years, runtimes, and the genre, country, and language sets match the English catalog, with Russian labels. The exact country token `Казахстан` is kept unchanged. `tests/test_catalog_translation.py` fails if the two files drift apart.

The English runtimes for Ayka (100 min), Mongol (125 min), The Old Man (102 min), and Baikonur (94 min) were manually checked against [Wikipedia](https://en.wikipedia.org/wiki/Ayka), [Wikipedia](https://en.wikipedia.org/wiki/Mongol_(film)), [Wikipedia](https://en.wikipedia.org/wiki/The_Old_Man_(2012_film)), and [French Wikipedia](https://fr.wikipedia.org/wiki/Baikonur). The Russian mirror was then synced to those values.

**Attribution:** This product uses the TMDB API but is not endorsed or certified by TMDB. See [TMDB](https://www.themoviedb.org/) and [TMDB’s API FAQ](https://developer.themoviedb.org/docs/faq).

## Model memory experiment

The experiment asks for years and runtimes from model memory without supplying a catalog. It compares the response in code with ten reference facts defined in `scripts/memory_experiment.py`. The prompt was:

```text
Answer from your existing knowledge. For each listed film, provide its original release year and theatrical runtime in minutes. Do not use a supplied catalog; none is provided. If unsure, give your best estimate. Return exactly one entry for each title, preserving the title, and follow the response schema.

Give the year and runtime for each of these films:
- The Godfather
- The Shawshank Redemption
- Pulp Fiction
- Forrest Gump
- Titanic
- Inception
- Spirited Away
- Parasite
- The Matrix
- The Dark Knight
```

The report compared all ten films and found four runtime discrepancies. The six other films matched their reference values. These are the model’s answers and the experiment’s reference values:

| Film | Reference year / runtime | Model year / runtime | Result |
| --- | --- | --- | --- |
| The Godfather | 1972 / 175 min | 1972 / 172 min | Runtime differs |
| The Shawshank Redemption | 1994 / 142 min | 1994 / 142 min | Match |
| Pulp Fiction | 1994 / 154 min | 1994 / 153 min | Runtime differs |
| Forrest Gump | 1994 / 142 min | 1994 / 142 min | Match |
| Titanic | 1997 / 195 min | 1997 / 196 min | Runtime differs |
| Inception | 2010 / 148 min | 2010 / 148 min | Match |
| Spirited Away | 2001 / 125 min | 2001 / 135 min | Runtime differs |
| Parasite | 2019 / 132 min | 2019 / 132 min | Match |
| The Matrix | 1999 / 136 min | 1999 / 136 min | Match |
| The Dark Knight | 2008 / 152 min | 2008 / 152 min | Match |

All ten titles are in `data/en/films.json`, and the reference values match its year and runtime fields. The experiment writes to its separate `memory_calls.jsonl` journal.

The real report:

```text
Outcome: ok
Films compared: 10
Discrepancies: 4
  The Godfather — minutes: expected 175, got 172
  Pulp Fiction — minutes: expected 154, got 153
  Titanic — minutes: expected 195, got 196
  Spirited Away — minutes: expected 125, got 135
```

Run it with `PYTHONPATH=. uv run python scripts/memory_experiment.py`.

## Assignment questions

1. **Why check IDs when titles are clearer, and how many memory discrepancies occurred?** Titles can have aliases or translations; the catalog ID is the stable key. Code resolves each returned ID against the candidate catalog. The memory experiment found four discrepancies. See `kino.py:594–614` and `scripts/memory_experiment.py:85–125`.
2. **What if the model returns an ID outside the catalog?** The ID is recorded as rejected, the result becomes invalid, and no film is printed. See `kino.py:600–601` and `kino.py:551–564`.
3. **How is a valid response different from a correct recommendation?** A response can parse and contain valid IDs but still miss the expected film. `check.py` compares returned outcomes and IDs with each query’s expectation and counts failures. See `check.py:47–65` and `check.py:118–138`.
4. **What can a non-ML solution do, and what does it miss here?** Exact rules can filter by year, runtime, language, and genre. They do not infer that “a poor family infiltrating a rich household” describes a film unless the query matches stored metadata or text rules. The current code applies explicit filters in `kino.py:272–304`.
5. **What did one query cost, and what most affects the price?** The local `qwen3.5:4b` path costs **$0** in model usage; the final journal reports $0 for all 1,249 local calls. The cloud R05 attempt cost **$0.003016** for 98 calls before HTTP 429, with 6 real answers. A paid model’s price depends on input and output token counts; a recommendation can use one filter call and a second choice call. See `utils.py:17–21`, `utils.py:51–61`, and `kino.py:472–516`.

## Scope and limits

The project claims Common checks `S01`–`S21`, Rare points 1–2, and Legendary points 1 and 4. `L03` is now backed by the local five-run journal. `R05` remains unclaimed because the cloud attempt hit HTTP 429 under the owner’s 180-call cap. `V00`–`V05`, Epic, and free-text question answering remain outside the claim. The local model is useful for a no-paid-model path, but even the 95.3% five-run report contains semantic mismatches. A valid ID and a well-formed response do not prove that the recommendation is correct.

## Project documents

- [Behavior and acceptance contract](SPEC.md)
- [Agent workflow and constraints](AGENTS.md)
- [Work plan](PLAN.md)
- [Implementation decisions](docs/decisions.md)
