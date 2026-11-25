"""Tests for OpenAlex / Wikidata tools (module research_mcp) with a mocked HTTP layer."""
from __future__ import annotations

import json
import urllib.parse

import pytest

import research_mcp as r


@pytest.fixture
def calls(monkeypatch):
    """Подменяет _http_json: запоминает адрес и параметры, отдаёт заданный ответ."""
    log: list[dict] = []
    reply: dict = {"payload": {}}

    def fake(url, params, accept="application/json", timeout=30):
        log.append({"url": url, "params": dict(params), "accept": accept})
        return reply["payload"]

    monkeypatch.setattr(r, "_http_json", fake)
    return log, reply


WORK = {
    "id": "https://openalex.org/W2052953969",
    "doi": "https://doi.org/10.1021/ed061p494",
    "display_name": "The development of the Arrhenius equation",
    "publication_year": 1984,
    "authorships": [{"author": {"display_name": f"Author {i}", "id": f"https://openalex.org/A{i}"},
                     "institutions": [{"display_name": "Univ"}]} for i in range(7)],
    "primary_location": {"source": {"display_name": "Journal of Chemical Education"}},
    "type": "article",
    "cited_by_count": 500,
    "open_access": {"oa_status": "closed", "oa_url": None},
    "abstract_inverted_index": {"Arrhenius": [0], "equation": [1], "history": [3], "the": [2]},
    "biblio": {"volume": "61", "issue": "6", "first_page": "494", "last_page": "494"},
    "locations": [],
}


def test_abstract_restores_word_order():
    assert r._abstract({"b": [1], "a": [0], "c": [2, 4], "d": [3]}) == "a b c d c"
    assert r._abstract(None) == ""


def test_work_ref_forms():
    assert r._work_ref("https://openalex.org/W123") == "W123"
    assert r._work_ref("10.1021/ed061p494") == "https://doi.org/10.1021/ed061p494"
    assert r._work_ref("doi: 10.1021/x") == "https://doi.org/10.1021/x"
    assert r._work_ref("W42") == "W42"


def test_search_builds_filters_and_caps_limit(calls):
    log, reply = calls
    reply["payload"] = {"meta": {"count": 1}, "results": [WORK]}
    out = json.loads(r.openalex_search("Arrhenius", year_from=1980, year_to=1990, work_type="review",
                                       open_access="open", sort="cited_by_count", limit=100))
    p = log[0]["params"]
    assert p["per_page"] == r.MAX_LIMIT
    assert p["filter"] == ("from_publication_date:1980-01-01,to_publication_date:1990-12-31,"
                           "type:review,open_access.is_oa:true")
    assert p["sort"] == "cited_by_count:desc"
    rec = out["results"][0]
    assert rec["openalex_id"] == "W2052953969" and rec["doi"] == "10.1021/ed061p494"
    assert rec["authors"][-1] == "и др." and len(rec["authors"]) == 6
    assert out["found"] == 1 and out["provenance"]["source"] == "OpenAlex"


def test_api_key_not_in_provenance(calls, monkeypatch):
    log, reply = calls
    monkeypatch.setattr(r, "API_KEY", "SECRET123")
    reply["payload"] = {"meta": {"count": 0}, "results": []}
    raw = r.openalex_search("Arrhenius")
    assert log[0]["params"]["api_key"] == "SECRET123"
    assert "SECRET123" not in raw


def test_work_record_fields(calls):
    log, reply = calls
    reply["payload"] = WORK
    out = json.loads(r.openalex_work("10.1021/ed061p494"))
    assert urllib.parse.unquote(log[0]["url"]).endswith("/works/https://doi.org/10.1021/ed061p494")
    w = out["work"]
    assert w["abstract"] == "Arrhenius equation the history"
    assert w["pages"] == "494" and w["volume"] == "61"
    assert w["authors"][0] == {"name": "Author 0", "openalex_id": "A0", "institutions": ["Univ"]}


@pytest.mark.parametrize("relation,key", [("references", "cited_by"), ("cited_by", "cites"),
                                          ("related", "related_to")])
def test_links_relation_filter(calls, relation, key):
    log, reply = calls
    reply["payload"] = {"meta": {"count": 0}, "results": []}
    out = json.loads(r.openalex_links("https://openalex.org/W1", relation=relation))
    assert log[0]["params"]["filter"] == f"{key}:W1"
    assert out["relation"] == relation


@pytest.mark.parametrize("q", ["INSERT DATA { wd:Q1 wdt:P31 wd:Q5 }",
                               "DELETE WHERE { ?s ?p ?o }",
                               "DESCRIBE wd:Q1"])
def test_sparql_rejects_non_select(calls, q):
    log, _ = calls
    out = json.loads(r.wikidata_sparql(q))
    assert "error" in out and not log


def test_sparql_select_rows(calls):
    log, reply = calls
    reply["payload"] = {"results": {"bindings": [{"item": {"value": "Q507505"}}] * 3}}
    out = json.loads(r.wikidata_sparql("SELECT ?item WHERE { ?item wdt:P138 wd:Q80956 }", limit=2))
    assert out["found"] == 3 and len(out["results"]) == 2
    assert log[0]["accept"] == "application/sparql-results+json"


def test_http_error_is_reported_as_json(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("нет сети")
    monkeypatch.setattr(r, "_http_json", boom)
    out = json.loads(r.openalex_search("x"))
    assert out["error"].startswith("openalex_search: RuntimeError")


def test_tools_registered_in_main_server(m):
    import asyncio
    names = {t.name for t in asyncio.run(m.mcp.list_tools())}
    assert set(m.RESEARCH_TOOLS) <= names
