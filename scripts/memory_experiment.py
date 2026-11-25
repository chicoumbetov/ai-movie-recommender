"""Compare model recall of film years and runtimes without sending a catalog."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr

import kino
from utils import log

MEMORY_JOURNAL_PATH = Path("memory_calls.jsonl")


@dataclass(frozen=True)
class FilmFact:
    title: str
    year: int
    minutes: int


FILMS: tuple[FilmFact, ...] = (
    FilmFact("The Godfather", 1972, 175),
    FilmFact("The Shawshank Redemption", 1994, 142),
    FilmFact("Pulp Fiction", 1994, 154),
    FilmFact("Forrest Gump", 1994, 142),
    FilmFact("Titanic", 1997, 195),
    FilmFact("Inception", 2010, 148),
    FilmFact("Spirited Away", 2001, 125),
    FilmFact("Parasite", 2019, 132),
    FilmFact("The Matrix", 1999, 136),
    FilmFact("The Dark Knight", 2008, 152),
)


class RecalledFilm(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: StrictStr
    year: StrictInt
    minutes: StrictInt


class MemoryRecall(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    films: list[RecalledFilm]


@dataclass(frozen=True)
class MemoryReport:
    outcome: str
    compared_films: int
    discrepancies: list[dict[str, str | int]]

    @property
    def discrepancy_count(self) -> int:
        return len(self.discrepancies)


def build_messages() -> list[dict[str, str]]:
    """Ask for facts using titles alone; the reference facts stay in local code."""
    titles = "\n".join(f"- {film.title}" for film in FILMS)
    return [
        {
            "role": "system",
            "content": (
                "Answer from your existing knowledge. For each listed film, provide its original "
                "release year and theatrical runtime in minutes. Do not use a supplied catalog; "
                "none is provided. If unsure, give your best estimate. Return exactly one entry "
                "for each title, preserving the title, and follow the response schema."
            ),
        },
        {
            "role": "user",
            "content": "Give the year and runtime for each of these films:\n" + titles,
        },
    ]


def _compare(answer: MemoryRecall) -> list[dict[str, str | int]]:
    expected = {film.title: film for film in FILMS}
    actual: dict[str, RecalledFilm] = {}
    discrepancies: list[dict[str, str | int]] = []
    for recalled in answer.films:
        if recalled.title not in expected or recalled.title in actual:
            discrepancies.append(
                {
                    "title": recalled.title,
                    "field": "title",
                    "expected": "one of the ten titles, once",
                    "actual": recalled.title,
                }
            )
        else:
            actual[recalled.title] = recalled

    for fact in FILMS:
        recalled = actual.get(fact.title)
        if recalled is None:
            for field, value in (("year", fact.year), ("minutes", fact.minutes)):
                discrepancies.append(
                    {
                        "title": fact.title,
                        "field": field,
                        "expected": value,
                        "actual": "missing",
                    }
                )
            continue
        for field, value in (("year", fact.year), ("minutes", fact.minutes)):
            received = getattr(recalled, field)
            if received != value:
                discrepancies.append(
                    {
                        "title": fact.title,
                        "field": field,
                        "expected": value,
                        "actual": received,
                    }
                )
    return discrepancies


def run_experiment(
    client: Any,
    model: str,
    *,
    journal_path: str | Path = MEMORY_JOURNAL_PATH,
) -> MemoryReport:
    """Make one catalog-free call, compare the facts, and write its separate journal row."""
    messages = build_messages()
    started = time.time()
    completion, outcome = kino._call_model(client, model, messages, MemoryRecall)
    parsed = (
        completion.choices[0].message.parsed if outcome == "ok" and completion is not None else None
    )
    if parsed is None:
        outcome = "invalid" if outcome == "ok" else outcome
        discrepancies: list[dict[str, str | int]] = []
    else:
        discrepancies = _compare(parsed)

    log(
        model=model,
        request={"query": messages[1]["content"], "titles": [film.title for film in FILMS]},
        outcome=outcome,
        step="memory",
        started=started,
        completion=completion,
        path=journal_path,
    )
    return MemoryReport(outcome, len(FILMS) if parsed is not None else 0, discrepancies)


def format_report(report: MemoryReport) -> str:
    lines = [f"Outcome: {report.outcome}", f"Films compared: {report.compared_films}"]
    lines.append(f"Discrepancies: {report.discrepancy_count}")
    lines.extend(
        f"  {item['title']} — {item['field']}: expected {item['expected']}, got {item['actual']}"
        for item in report.discrepancies
    )
    return "\n".join(lines)


def main() -> int:
    settings = kino.load_settings()
    if not settings.get("api_key") or not settings.get("model"):
        print("error: OPENAI_API_KEY and MODEL must be configured", file=sys.stderr)
        return 2
    report = run_experiment(kino.make_client(settings), settings["model"])
    print(format_report(report))
    return 0 if report.outcome == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
