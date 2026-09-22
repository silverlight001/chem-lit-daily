from __future__ import annotations

import re
from collections import Counter


HIGH_IMPACT_JOURNALS = {
    "nature": 13,
    "science": 13,
    "cell": 12,
    "nature chemistry": 14,
    "nature catalysis": 13,
    "nature materials": 13,
    "nature nanotechnology": 12,
    "journal of the american chemical society": 13,
    "angewandte chemie": 12,
    "chemical society reviews": 13,
    "chem": 11,
    "acs catalysis": 10,
    "energy & environmental science": 12,
    "advanced materials": 11,
    "nano letters": 10,
    "environmental science & technology": 9,
}


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def text_contains_phrase(text: str, phrase: str) -> bool:
    normalized = normalize_text(text)
    normalized_phrase = normalize_text(phrase)
    if not normalized_phrase:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(normalized_phrase)}(?![a-z0-9])", normalized) is not None


def keyword_hits(text: str, keywords: list[str]) -> int:
    return sum(1 for keyword in keywords if text_contains_phrase(text, keyword))


def journal_matches(journal: str | None, watched: str) -> bool:
    normalized = normalize_text(journal)
    target = normalize_text(watched)
    if not normalized or not target:
        return False
    if target in {"science", "nature", "cell", "chem"}:
        return normalized == target
    return normalized == target or normalized.startswith(f"{target}:")


def learned_keyword_boost(papers: list[dict], keywords: list[str]) -> dict[str, float]:
    positive: Counter[str] = Counter()
    negative: Counter[str] = Counter()
    for paper in papers:
        rating = paper.get("user_rating")
        if rating is None:
            continue
        combined = normalize_text(" ".join([paper.get("title", ""), paper.get("abstract", "")]))
        for keyword in keywords:
            if normalize_text(keyword) in combined:
                if rating >= 4:
                    positive[keyword] += rating - 3
                elif rating <= 2:
                    negative[keyword] += 3 - rating
    return {
        keyword: max(-8, min(12, positive[keyword] * 2 - negative[keyword] * 2))
        for keyword in keywords
    }


def journal_bonus(journal: str | None, watched_journals: list[str]) -> float:
    normalized = normalize_text(journal)
    bonus = 0.0
    for watched in watched_journals:
        if journal_matches(journal, watched):
            bonus += 18
    for name, value in HIGH_IMPACT_JOURNALS.items():
        if journal_matches(journal, name):
            bonus += value
            break
    return bonus


def score_paper(
    paper: dict,
    *,
    keywords: list[str],
    watched_journals: list[str],
    keyword_boosts: dict[str, float] | None = None,
) -> float:
    keyword_boosts = keyword_boosts or {}
    combined = " ".join([paper.get("title", ""), paper.get("abstract", ""), paper.get("journal", "")])
    hits = keyword_hits(combined, keywords)
    boost = sum(keyword_boosts.get(keyword, 0) for keyword in keywords if text_contains_phrase(combined, keyword))
    citations = min(float(paper.get("cited_by_count") or 0), 80.0)
    score = 28 + hits * 9 + journal_bonus(paper.get("journal"), watched_journals) + citations * 0.35 + boost
    if paper.get("abstract"):
        score += 4
    return round(max(0, min(100, score)), 1)
