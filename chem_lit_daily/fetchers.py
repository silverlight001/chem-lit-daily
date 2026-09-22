from __future__ import annotations

from datetime import date, datetime
from html import unescape
import re
import time

import requests

from .scoring import journal_matches, keyword_hits, score_paper
from .summarizer import summarize


OPENALEX_URL = "https://api.openalex.org/works"


def _abstract_from_inverted_index(index: dict | None) -> str:
    if not index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, offsets in index.items():
        for offset in offsets:
            positions.append((offset, word))
    return " ".join(word for _, word in sorted(positions))


def _authors(work: dict) -> str:
    names = []
    for item in work.get("authorships", [])[:8]:
        author = item.get("author") or {}
        if author.get("display_name"):
            names.append(author["display_name"])
    if len(work.get("authorships", [])) > 8:
        names.append("et al.")
    return ", ".join(names)


def _clean_html(value: str | None) -> str:
    return re.sub(r"<[^>]+>", "", unescape(value or "")).strip()


def _source_display(work: dict) -> str:
    locations = work.get("locations") or []
    for location in locations:
        source = location.get("source") or {}
        if source.get("type") == "journal" and source.get("display_name"):
            return source["display_name"]
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    return source.get("display_name") or ""


def _paper_id(work: dict) -> str:
    doi = work.get("doi")
    if doi:
        return doi.replace("https://doi.org/", "").lower()
    return work.get("id", "").rsplit("/", 1)[-1]


def _is_relevant(paper: dict, keywords: list[str], journals: list[str]) -> bool:
    combined = " ".join([paper.get("title", ""), paper.get("abstract", ""), paper.get("keywords", "")])
    if keyword_hits(combined, keywords):
        return True
    return any(journal_matches(paper.get("journal"), watched) for watched in journals)


def _request_openalex(params: dict) -> list[dict]:
    last_error: requests.RequestException | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                OPENALEX_URL,
                params=params,
                timeout=25,
                headers={"User-Agent": "chem-lit-daily/0.1 (mailto:local@example.com)"},
            )
            response.raise_for_status()
            return response.json().get("results", [])
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    if last_error:
        raise last_error
    return []


def fetch_openalex(
    *,
    keywords: list[str],
    journals: list[str],
    from_date: date,
    to_date: date | None = None,
    max_results: int = 50,
    keyword_boosts: dict[str, float] | None = None,
) -> list[dict]:
    to_date = to_date or date.today()
    queries: list[str] = [keyword for keyword in keywords if keyword.strip()]
    queries.extend(journal for journal in journals if journal.strip())
    if not queries:
        return []

    seen: set[str] = set()
    papers: list[dict] = []
    per_query = max(8, min(25, max_results // max(1, len(queries)) + 5))

    for query in queries:
        params = {
            "search": query,
            "filter": f"from_publication_date:{from_date.isoformat()},to_publication_date:{to_date.isoformat()},type:article",
            "sort": "publication_date:desc,cited_by_count:desc",
            "per-page": per_query,
            "select": "id,doi,title,display_name,publication_date,authorships,primary_location,locations,abstract_inverted_index,cited_by_count,concepts,open_access",
        }
        for work in _request_openalex(params):
            paper_id = _paper_id(work)
            if not paper_id or paper_id in seen:
                continue
            seen.add(paper_id)

            location = work.get("primary_location") or {}
            doi = (work.get("doi") or "").replace("https://doi.org/", "")
            url = work.get("doi") or work.get("id") or location.get("landing_page_url") or ""
            abstract = _abstract_from_inverted_index(work.get("abstract_inverted_index"))
            concepts = [
                concept.get("display_name", "")
                for concept in work.get("concepts", [])[:6]
                if concept.get("display_name")
            ]
            paper = {
                "id": paper_id,
                "doi": doi,
                "title": _clean_html(work.get("title") or work.get("display_name") or "Untitled"),
                "journal": _source_display(work),
                "publication_date": work.get("publication_date") or "",
                "authors": _authors(work),
                "abstract": abstract,
                "url": url,
                "cited_by_count": work.get("cited_by_count") or 0,
                "keywords": ", ".join(concepts),
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            }
            if not _is_relevant(paper, keywords, journals):
                continue
            paper["impact_score"] = score_paper(
                paper,
                keywords=keywords,
                watched_journals=journals,
                keyword_boosts=keyword_boosts,
            )
            paper["summary"] = summarize(paper["title"], abstract, keywords, paper["journal"])
            papers.append(paper)

    return sorted(papers, key=lambda item: item["impact_score"], reverse=True)[:max_results]
