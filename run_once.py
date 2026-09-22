from __future__ import annotations

from datetime import date, timedelta

from chem_lit_daily.database import (
    create_collection,
    get_setting,
    init_db,
    list_papers,
    set_setting,
    upsert_paper,
)
from chem_lit_daily.fetchers import fetch_openalex


def main() -> None:
    init_db()
    create_collection("待读")
    create_collection("重点跟进")

    keywords = get_setting("keywords", ["photocatalysis", "CO2 reduction"])
    journals = get_setting(
        "journals",
        ["Journal of the American Chemical Society", "Angewandte Chemie"],
    )
    days_back = int(get_setting("days_back", 30))
    max_results = int(get_setting("max_results", 20))

    set_setting("keywords", keywords)
    set_setting("journals", journals)
    set_setting("days_back", days_back)
    set_setting("max_results", max_results)

    papers = fetch_openalex(
        keywords=keywords,
        journals=journals,
        from_date=date.today() - timedelta(days=days_back - 1),
        max_results=max_results,
    )
    for paper in papers:
        upsert_paper(paper)

    print(f"saved {len(papers)} papers")
    for row in list_papers(limit=5):
        title = row["title"][:90].encode("utf-8", errors="ignore").decode("utf-8")
        print(f"{row['impact_score']:>5.1f} | {row['publication_date']} | {title}")


if __name__ == "__main__":
    main()
