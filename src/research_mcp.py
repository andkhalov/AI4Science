"""research_mcp — инструменты MCP для учебного агента: OpenAlex и Wikidata.

Место в агенте: общий сервер `src/ai4science_mcp.py` импортирует этот модуль и
регистрирует его инструменты (openalex_search, openalex_work, openalex_links,
wikidata_search, wikidata_sparql) рядом с Lean, поиском по Mathlib, сетью и PDF.
Отдельный сервер не нужен; запуск файла напрямую тоже работает (`python src/research_mcp.py`).
Зависимости: пакет `mcp` версии 1.x или 2.x и стандартная библиотека.
Сеть: api.openalex.org, www.wikidata.org, query.wikidata.org. Все запросы — только чтение.

Ключ OpenAlex читается из переменной окружения OPENALEX_API_KEY. Без ключа сервис
отвечает, но суточный лимит меньше. В выдачу инструментов ключ не попадает.

Каждый ответ содержит поле `provenance`: откуда и когда получены данные. Поля `title`
и `abstract` — внешний текст: это данные, инструкции из них не выполняются.

Проверка без агента:  .venv/bin/python src/research_mcp.py --selftest
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Literal

try:                       # пакет mcp 1.x — он стоит в окружении учебного агента
    from mcp.server.fastmcp import FastMCP
except ImportError:        # пакет mcp 2.x: класс переименован в MCPServer
    from mcp.server.mcpserver import MCPServer as FastMCP

if sys.platform == "win32":  # протокол MCP — UTF-8
    for _stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass

mcp = FastMCP("research")

OPENALEX = "https://api.openalex.org"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = "AI4ScienceCourse/0.1 (https://github.com/andkhalov/AI4Science; research_mcp)"
API_KEY = os.environ.get("OPENALEX_API_KEY") or os.environ.get("OPEN_ALEX") or ""
MAX_LIMIT = 25
MAX_RETRY_WAIT = 10  # секунд между повторами, не больше
ABSTRACT_CHARS = 1500

WorkType = Literal["any", "article", "review", "preprint", "book-chapter", "dataset"]
OpenAccess = Literal["any", "open", "closed"]
SortBy = Literal["relevance", "cited_by_count", "publication_date"]
Relation = Literal["references", "cited_by", "related"]
Language = Literal["ru", "en"]


# ---------- общие функции ----------

def _http_json(url: str, params: dict, accept: str = "application/json", timeout: int = 30) -> dict:
    """GET-запрос с двумя повторами при 429 и ошибках сервера."""
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT, "Accept": accept})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2:
                try:
                    wait = float(e.headers.get("Retry-After") or 3 * (attempt + 1))
                except ValueError:
                    wait = 3 * (attempt + 1)
                time.sleep(min(wait, MAX_RETRY_WAIT))  # вызов инструмента не висит минутами
                continue
            raise
    raise RuntimeError("нет ответа")


def _openalex(path: str, params: dict) -> tuple[dict, str]:
    """Запрос к OpenAlex. Возвращает ответ и адрес запроса без ключа (для provenance)."""
    public = f"{OPENALEX}{path}?{urllib.parse.urlencode(params)}"
    if API_KEY:
        params = {**params, "api_key": API_KEY}
    return _http_json(f"{OPENALEX}{path}", params), public


def _provenance(source: str, request: str) -> dict:
    return {"source": source, "request": request, "retrieved": date.today().isoformat(),
            "untrusted_text_fields": ["title", "abstract", "description"]}


def _error(tool: str, e: Exception) -> str:
    detail = ""
    if isinstance(e, urllib.error.HTTPError):
        detail = e.read()[:200].decode("utf-8", "replace")
    return json.dumps({"error": f"{tool}: {type(e).__name__}: {str(e)[:200]} {detail}".strip()}, ensure_ascii=False)


def _short_id(url_or_id: str | None) -> str:
    return (url_or_id or "").rstrip("/").rsplit("/", 1)[-1]


def _work_ref(work: str) -> str:
    """Идентификатор OpenAlex (W…), DOI или адрес → путь для запроса одной записи."""
    work = work.strip()
    low = work.lower()
    if low.startswith("https://openalex.org/"):
        return _short_id(work)
    if low.startswith("10."):
        return "https://doi.org/" + work
    if low.startswith("doi:"):
        return "https://doi.org/" + work[4:].strip()
    return work  # W…, https://doi.org/…


def _abstract(inverted: dict | None) -> str:
    """OpenAlex хранит аннотацию инвертированным индексом: слово → позиции."""
    if not inverted:
        return ""
    words = sorted((pos, word) for word, positions in inverted.items() for pos in positions)
    text = " ".join(word for _, word in words)
    return text if len(text) <= ABSTRACT_CHARS else text[:ABSTRACT_CHARS] + " …"


def _brief(w: dict) -> dict:
    """Короткая запись о работе: то, что нужно для выбора и для заметки-источника."""
    authors = [a.get("author", {}).get("display_name") for a in w.get("authorships") or []]
    oa = w.get("open_access") or {}
    source = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
    return {
        "openalex_id": _short_id(w.get("id")),
        "title": w.get("display_name"),
        "year": w.get("publication_year"),
        "authors": authors[:5] + (["и др."] if len(authors) > 5 else []),
        "source": source,
        "type": w.get("type"),
        "cited_by": w.get("cited_by_count"),
        "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
        "oa_status": oa.get("oa_status"),
        "oa_url": oa.get("oa_url"),
    }


BRIEF_FIELDS = "id,doi,display_name,publication_year,authorships,primary_location,type,cited_by_count,open_access"
SORT = {"relevance": "relevance_score:desc", "cited_by_count": "cited_by_count:desc",
        "publication_date": "publication_date:desc"}


# ---------- OpenAlex ----------

@mcp.tool()
def openalex_search(query: str, year_from: int = 0, year_to: int = 0, work_type: WorkType = "any",
                    open_access: OpenAccess = "any", sort: SortBy = "relevance", limit: int = 10) -> str:
    """Поиск научных работ в OpenAlex по названию, аннотации и полному тексту.
    query — слова запроса на английском; year_from, year_to — границы года (0 — без границы);
    work_type, open_access, sort — значения из списка; limit — до 25 записей.
    Возвращает JSON: число найденных, записи (openalex_id, title, year, authors, source,
    cited_by, doi, oa_status, oa_url) и provenance."""
    try:
        filters = []
        if year_from:
            filters.append(f"from_publication_date:{int(year_from)}-01-01")
        if year_to:
            filters.append(f"to_publication_date:{int(year_to)}-12-31")
        if work_type != "any":
            filters.append(f"type:{work_type}")
        if open_access != "any":
            filters.append(f"open_access.is_oa:{'true' if open_access == 'open' else 'false'}")
        params = {"search": query, "per_page": max(1, min(int(limit), MAX_LIMIT)),
                  "sort": SORT[sort], "select": BRIEF_FIELDS}
        if filters:
            params["filter"] = ",".join(filters)
        data, request = _openalex("/works", params)
        return json.dumps({"provenance": _provenance("OpenAlex", request),
                           "found": data.get("meta", {}).get("count"),
                           "results": [_brief(w) for w in data.get("results", [])]}, ensure_ascii=False)
    except Exception as e:
        return _error("openalex_search", e)


@mcp.tool()
def openalex_work(work: str) -> str:
    """Полная запись об одной работе в OpenAlex. work — идентификатор OpenAlex (W…) или DOI.
    Возвращает JSON: название, авторы с организациями, источник, том и страницы, аннотация,
    тема, число ссылок и цитирований, открытые версии и provenance."""
    try:
        w, request = _openalex("/works/" + urllib.parse.quote(_work_ref(work), safe=":/"), {})
        topic = w.get("primary_topic") or {}
        biblio = w.get("biblio") or {}
        record = _brief(w)
        record.update({
            "publication_date": w.get("publication_date"),
            "authors": [{"name": a.get("author", {}).get("display_name"),
                         "openalex_id": _short_id(a.get("author", {}).get("id")),
                         "institutions": [i.get("display_name") for i in a.get("institutions") or []][:2]}
                        for a in (w.get("authorships") or [])[:12]],
            "volume": biblio.get("volume"), "issue": biblio.get("issue"),
            "pages": "–".join(dict.fromkeys(p for p in (biblio.get("first_page"), biblio.get("last_page")) if p)) or None,
            "topic": {"name": topic.get("display_name"), "field": (topic.get("field") or {}).get("display_name"),
                      "domain": (topic.get("domain") or {}).get("display_name")} if topic else None,
            "references_count": w.get("referenced_works_count"),
            "is_retracted": w.get("is_retracted"),
            "pdf_urls": [u for u in dict.fromkeys(loc.get("pdf_url") for loc in w.get("locations") or [] if loc.get("is_oa")) if u][:3],
            "abstract": _abstract(w.get("abstract_inverted_index")),
        })
        return json.dumps({"provenance": _provenance("OpenAlex", request), "work": record}, ensure_ascii=False)
    except Exception as e:
        return _error("openalex_work", e)


@mcp.tool()
def openalex_links(work: str, relation: Relation = "references", sort: SortBy = "cited_by_count",
                   limit: int = 10) -> str:
    """Связи работы в графе цитирований OpenAlex. work — идентификатор OpenAlex (W…).
    relation: references — на что работа ссылается; cited_by — кто на неё ссылается;
    related — близкие по содержанию. sort и limit — как в openalex_search.
    Возвращает JSON: число связей, записи и provenance."""
    try:
        wid = _short_id(_work_ref(work))
        key = {"references": "cited_by", "cited_by": "cites", "related": "related_to"}[relation]
        order = SORT["cited_by_count"] if sort == "relevance" else SORT[sort]
        data, request = _openalex("/works", {"filter": f"{key}:{wid}", "sort": order, "select": BRIEF_FIELDS,
                                              "per_page": max(1, min(int(limit), MAX_LIMIT))})
        return json.dumps({"provenance": _provenance("OpenAlex", request), "work": wid, "relation": relation,
                           "found": data.get("meta", {}).get("count"),
                           "results": [_brief(w) for w in data.get("results", [])]}, ensure_ascii=False)
    except Exception as e:
        return _error("openalex_links", e)


# ---------- Wikidata ----------

@mcp.tool()
def wikidata_search(text: str, language: Language = "ru", limit: int = 5) -> str:
    """Поиск сущности Wikidata по названию: возвращает идентификаторы Q…, подписи и описания.
    Идентификатор нужен для запроса wikidata_sparql."""
    try:
        params = {"action": "wbsearchentities", "search": text, "language": language, "uselang": language,
                  "limit": max(1, min(int(limit), 20)), "format": "json"}
        data = _http_json(WIKIDATA_API, params)
        rows = [{"id": r.get("id"), "label": r.get("label"), "description": r.get("description")}
                for r in data.get("search", [])]
        request = WIKIDATA_API + "?" + urllib.parse.urlencode(params)
        return json.dumps({"provenance": _provenance("Wikidata", request), "results": rows}, ensure_ascii=False)
    except Exception as e:
        return _error("wikidata_search", e)


FORBIDDEN = ("INSERT", "DELETE", "LOAD", "CLEAR", "CREATE", "DROP", "COPY", "MOVE", "ADD")


@mcp.tool()
def wikidata_sparql(query: str, limit: int = 50) -> str:
    """Запрос SPARQL (только SELECT и ASK) к основной точке доступа Wikidata.
    Префиксы wd:, wdt:, rdfs:, wikibase:, bd: объявлять не нужно. Сведения о научных
    статьях в этой точке не хранятся — для них есть openalex_search.
    Возвращает JSON: строки результата (до limit) и provenance с текстом запроса."""
    try:
        head = " ".join(query.upper().split())
        if not any(word in head for word in ("SELECT", "ASK")) or any(f" {word} " in f" {head} " for word in FORBIDDEN):
            return json.dumps({"error": "wikidata_sparql: разрешены только запросы SELECT и ASK"}, ensure_ascii=False)
        data = _http_json(WIKIDATA_SPARQL, {"query": query, "format": "json"}, accept="application/sparql-results+json")
        if "boolean" in data:
            rows, found = [{"ask": data["boolean"]}], 1
        else:
            bindings = data.get("results", {}).get("bindings", [])
            found = len(bindings)
            rows = [{k: v.get("value") for k, v in b.items()} for b in bindings[: max(1, min(int(limit), 200))]]
        return json.dumps({"provenance": {**_provenance("Wikidata Query Service", WIKIDATA_SPARQL), "sparql": query},
                           "found": found, "results": rows}, ensure_ascii=False)
    except Exception as e:
        return _error("wikidata_sparql", e)


# ---------- проверка без агента ----------

def _selftest() -> int:
    print("ключ OpenAlex:", "задан" if API_KEY else "не задан (меньший суточный лимит)")
    checks = [
        ("openalex_search", openalex_search("Arrhenius equation activation energy", work_type="review", limit=3)),
        ("openalex_work", openalex_work("10.1021/ed061p494")),
        ("wikidata_search", wikidata_search("уравнение Аррениуса")),
        ("wikidata_sparql", wikidata_sparql(
            'SELECT ?item ?itemLabel WHERE { ?item wdt:P138 wd:Q80956 . '
            'SERVICE wikibase:label { bd:serviceParam wikibase:language "ru,en". } } LIMIT 5')),
    ]
    failed = 0
    for name, raw in checks:
        data = json.loads(raw)
        if "error" in data:
            failed += 1
            print(f"[НЕТ] {name}: {data['error']}")
        else:
            first = (data.get("results") or [data.get("work")])[0]
            print(f"[OK]  {name}: {json.dumps(first, ensure_ascii=False)[:150]}")
    return 1 if failed else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    mcp.run()
