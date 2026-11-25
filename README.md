# Common 100%; Rare points 1–2; Legendary points 1 and 4

Movie Buff recommends films from a fixed catalog for natural-language requests. The model proposes catalog IDs and short reasons; the program verifies each ID and prints film facts from the catalog.

This is the project’s claimed Lean scope. Three real local evaluation runs scored 23/30, 21/30, and 22/30; the detailed report below is the third run. These claims describe implemented coverage, not a promise that every model answer is correct.

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

## Real evaluation

This is the third local run on `qwen3.5:4b`, not a statistical estimate. It covered all 30 queries and passed 22 (73.3%). Five requests expected a particular film but returned no match; one returned `invalid`; one returned `ok` with the wrong expected IDs; and the broad request expected `clarify` but returned `ok`. The run caught no foreign IDs and reported no filter violations. The first two runs passed 23/30 (76.7%) and 21/30 (70.0%).

`check.py` output:

```text
Outcome counts:
  invalid: 1
  no_match: 8
  ok: 21
Foreign IDs caught: []
Filter violations: 0
Model calls by step:
  choice: 25
  filters: 30
Pass rate: 22/30 (73.3%)
Failures:
  query 1: 'A film about dreams within dreams' expected {'must': ['int-006']}, got no_match []
  query 2: 'A story about a wrongfully imprisoned banker' expected {'must': ['int-001']}, got no_match []
  query 8: 'A hacker discovers the world is a simulation' expected {'must': ['int-009']}, got invalid []
  query 9: 'A musical romance in Los Angeles' expected {'must': ['int-010']}, got no_match []
  query 15: 'A samurai village defends itself from bandits' expected {'must': ['int-016']}, got no_match []
  query 16: 'A Kazakh film about a migrant mother in Moscow' expected {'must': ['kz-002']}, got no_match []
  query 27: 'Ғарыш туралы фильм, бірақ соғыс емес' expected {'must': ['int-003']}, got ok ['kz-003', 'int-027']
  query 30: 'Recommend me something good.' expected {'outcome': 'clarify'}, got ok ['int-018', 'kz-004', 'int-029']
```

`show.py` output for the journal after the third run:

```text
Calls: 172
Outcomes:
  invalid: 3
  no_connection: 3
  no_match: 13
  ok: 153
Models:
  qwen3.5:4b: 172
Tokens: prompt=183524, completion=9804, total=193328
USD: 0.000000
```

The 172 calls include 166 calls across the three 30-query runs and six single-query samples. Two early calls timed out before the configured reasoning effort was forwarded; the third `no_connection` was the intentional error-path sample. The successful `ok` and `no_match` samples are also in `real_run_output.txt`.

## Catalog and provenance

The English catalog contains 40 films. It was built from English-language TMDb data, with Wikipedia references recorded for independent verification. The catalog was not generated from model memory. `catalog_sources.json` records the catalog `id`, `tmdb_id`, retrieval timestamp, `wikipedia_url`, and `verified_by` for each film. The recorded retrieval timestamp is **2026-11-24T11:32:41Z**.

The English file uses TMDb’s English-language (`en-US`) fields; the catalog builder maps its genre labels to the project’s canonical English list. The Russian file is retained as a Russian-language provenance/reference source. The two files share IDs and years. The current English runtimes for the four records below were manually checked against these sources; they differ from their corresponding Russian records:

| Film | English catalog | Russian catalog | Manual verification |
| --- | ---: | ---: | --- |
| Ayka | 100 min | 120 min | [Wikipedia](https://en.wikipedia.org/wiki/Ayka) |
| Mongol: The Rise of Genghis Khan | 125 min | 121 min | [Wikipedia](https://en.wikipedia.org/wiki/Mongol_(film)) |
| The Old Man (2012) | 102 min | 106 min | [Wikipedia](https://en.wikipedia.org/wiki/The_Old_Man_(2012_film)) |
| Baikonur | 94 min | 107 min | [French Wikipedia](https://fr.wikipedia.org/wiki/Baikonur) |

These English values are the manually verified values in `data/en/films.json`; the catalog files were left unchanged. The differences are documented as provenance discrepancies between the paired language catalogs.

**Attribution:** This product uses the TMDB API but is not endorsed or certified by TMDB. See [TMDB](https://www.themoviedb.org/) and [TMDB’s API FAQ](https://developer.themoviedb.org/docs/faq).

## Model memory experiment

The experiment asks for years and runtimes from model memory without supplying a catalog. It compares the response in code with ten reference facts defined in `scripts/memory_experiment.py`. The prompt was:

```text
Answer from your existing knowledge. For each listed film, provide its original release year and theatrical runtime in minutes. Do not use a supplied catalog; none is provided. If unsure, give your best estimate. Return exactly one entry for each title, preserving the title, and follow the response schema.

Give the year and runtime for each of these films:
- The Godfather
- Casablanca
- Jaws
- Alien
- Titanic
- Inception
- Spirited Away
- Parasite
- The Matrix
- The Wizard of Oz
```

The report compared all ten films and found five runtime discrepancies. The five other films matched their reference values. These are the model’s answers and the experiment’s reference values:

| Film | Reference year / runtime | Model year / runtime | Result |
| --- | --- | --- | --- |
| The Godfather | 1972 / 175 min | 1972 / 178 min | Runtime differs |
| Casablanca | 1942 / 102 min | 1942 / 105 min | Runtime differs |
| Jaws | 1975 / 124 min | 1975 / 116 min | Runtime differs |
| Alien | 1979 / 117 min | 1979 / 111 min | Runtime differs |
| Titanic | 1997 / 195 min | 1997 / 196 min | Runtime differs |
| Inception | 2010 / 148 min | 2010 / 148 min | Match |
| Spirited Away | 2001 / 125 min | 2001 / 125 min | Match |
| Parasite | 2019 / 132 min | 2019 / 132 min | Match |
| The Matrix | 1999 / 136 min | 1999 / 136 min | Match |
| The Wizard of Oz | 1939 / 102 min | 1939 / 102 min | Match |

The reference facts are experiment fixtures, not all current catalog entries: Casablanca, Jaws, Alien, and The Wizard of Oz are not in `data/en/films.json`. For the six titles that are in that catalog, the reference values match its year and runtime fields. The experiment writes to its separate `memory_calls.jsonl` journal.

The real report:

```text
Outcome: ok
Films compared: 10
Discrepancies: 5
  The Godfather — minutes: expected 175, got 178
  Casablanca — minutes: expected 102, got 105
  Jaws — minutes: expected 124, got 116
  Alien — minutes: expected 117, got 111
  Titanic — minutes: expected 195, got 196
```

Run it with `PYTHONPATH=. uv run python scripts/memory_experiment.py`.

## Assignment questions

1. **Why check IDs when titles are clearer, and how many memory discrepancies occurred?** Titles can have aliases or translations; the catalog ID is the stable key. Code resolves each returned ID against the candidate catalog. The memory experiment found five discrepancies. See `kino.py:575–583` and `scripts/memory_experiment.py:85–125`.
2. **What if the model returns an ID outside the catalog?** The ID is recorded as rejected, the result becomes invalid, and no film is printed. See `kino.py:581–583` and `kino.py:532–545`.
3. **How is a valid response different from a correct recommendation?** A response can parse and contain valid IDs but still miss the expected film. `check.py` compares returned outcomes and IDs with each query’s expectation and counts failures. See `check.py:47–65` and `check.py:118–138`.
4. **What can a non-ML solution do, and what does it miss here?** Exact rules can filter by year, runtime, language, and genre. They do not infer that “a poor family infiltrating a rich household” describes a film unless the query matches stored metadata or text rules. The current code applies explicit filters in `kino.py:267–299`.
5. **What did one query cost, and what most affects the price?** In this local run, the model-call journal reports **$0.000000** for 62 calls, so the local Qwen path costs $0 per query in model usage. A paid model’s price depends on input and output token counts; a recommendation can use one filter call and a second choice call. See `utils.py:17–21`, `utils.py:51–61`, and `kino.py:471–507`.

## Scope and limits

The project claims Common checks `S01`–`S21`, Rare points 1–2, and Legendary points 1 and 4. It does not claim `R05`, `L03`, `V00`–`V05`, Epic, video, or free-text question answering. The local model is useful for a no-paid-model path, but the 23/30 result shows that semantic matching still misses some expected recommendations. A valid ID and a well-formed response do not prove that the recommendation is correct.

## Project documents

- [Behavior and acceptance contract](SPEC.md)
- [Agent workflow and constraints](AGENTS.md)
- [Work plan](PLAN.md)
- [Implementation decisions](docs/decisions.md)
