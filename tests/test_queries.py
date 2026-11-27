import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = ROOT / "queries.json"
FILMS_PATH = ROOT / "data" / "en" / "films.json"


def test_evaluation_queries_match_step_19_contract() -> None:
    queries = json.loads(QUERY_PATH.read_text(encoding="utf-8"))
    films = json.loads(FILMS_PATH.read_text(encoding="utf-8"))

    assert isinstance(queries, list)
    assert len(queries) == 30
    assert [query["level"] for query in queries].count("common") == 15
    assert [query["level"] for query in queries].count("rare") == 15

    query_texts = [query["query"] for query in queries]
    assert all(isinstance(text, str) and text.strip() for text in query_texts)
    assert len({text.casefold() for text in query_texts}) == len(query_texts)
    assert all(isinstance(query.get("expect"), dict) for query in queries)

    no_match_count = 0
    must_count = 0
    kazakh_count = 0
    negation_count = 0
    strict_filter_count = 0
    injection_count = 0
    all_ids = {str(film["id"]) for film in films}

    for query in queries:
        text = query["query"]
        expect = query["expect"]

        assert set(expect) <= {"no_match", "must", "forbid", "outcome"}
        assert not (expect.get("no_match") is True and ("must" in expect or "forbid" in expect))
        if "outcome" in expect:
            assert expect["outcome"] in {"ok", "no_match", "invalid", "clarify"}
        if "no_match" in expect:
            assert expect["no_match"] is True

        no_match_count += expect.get("no_match") is True
        must = expect.get("must", [])
        forbid = expect.get("forbid", [])
        assert isinstance(must, list)
        assert isinstance(forbid, list)
        must_count += bool(must)
        assert all(str(film_id) in all_ids for film_id in [*must, *forbid])

        kazakh_count += bool(re.search(r"[әғқңөұүһі]", text, re.IGNORECASE))
        negation_count += bool(re.search(r"\b(?:не|без|кроме|емес|жоқ)\b", text, re.IGNORECASE))
        strict_filter_count += bool(
            re.search(
                r"\b(?:under|over|before|after|between|shorter than|longer than)\b|"
                r"\b\d+\s*(?:minutes?|минут)\b|\b\d{4}\b",
                text,
                re.IGNORECASE,
            )
        )
        injection_count += bool(re.search(r"ignore all previous instructions", text, re.IGNORECASE))

    assert no_match_count >= 3
    assert must_count >= 3
    assert kazakh_count >= 3
    assert negation_count >= 3
    assert injection_count >= 1
    assert strict_filter_count >= 3
    assert sum(query["expect"].get("outcome") == "clarify" for query in queries) >= 1
    assert any(
        query["query"] == "A Kazakh-language film about a robot uprising"
        and query["expect"].get("no_match") is True
        for query in queries
    )
