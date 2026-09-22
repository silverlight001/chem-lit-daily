from __future__ import annotations

from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st

from chem_lit_daily.database import (
    add_to_collection,
    create_collection,
    get_setting,
    hide_paper,
    init_db,
    list_collections,
    list_papers,
    papers_in_collection,
    set_setting,
    update_rating,
    upsert_paper,
)
from chem_lit_daily.fetchers import fetch_openalex
from chem_lit_daily.scoring import journal_matches, keyword_hits, learned_keyword_boost
from chem_lit_daily.summarizer import clean_abstract


st.set_page_config(
    page_title="Chem Lit Daily",
    page_icon="CL",
    layout="wide",
    initial_sidebar_state="expanded",
)


CSS = """
<style>
    :root {
        --ink: #17202a;
        --muted: #5e6b78;
        --line: #dfe6ee;
        --blue: #2764cf;
        --teal: #0c8b7b;
    }
    .stApp {
        background:
            radial-gradient(circle at 12% 8%, rgba(39,100,207,.10), transparent 28%),
            linear-gradient(180deg, #f7fafc 0%, #eef4f8 100%);
        color: var(--ink);
    }
    [data-testid="stSidebar"] {
        background: #f8fbfd;
        border-right: 1px solid var(--line);
    }
    .main-title {
        font-size: 2.3rem;
        line-height: 1.08;
        font-weight: 760;
        letter-spacing: 0;
        margin: .25rem 0 .35rem;
    }
    .subtle {
        color: var(--muted);
        font-size: .98rem;
    }
    .metric-row {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .8rem;
        margin: 1rem 0 1.2rem;
    }
    .metric {
        background: rgba(255,255,255,.82);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: .82rem .95rem;
        min-height: 76px;
    }
    .metric b {
        display: block;
        font-size: 1.35rem;
        color: var(--ink);
    }
    .paper {
        background: rgba(255,255,255,.94);
        border: 1px solid var(--line);
        border-left: 5px solid var(--blue);
        border-radius: 8px;
        padding: 1rem 1.1rem;
        margin-bottom: .85rem;
        box-shadow: 0 8px 22px rgba(24,44,67,.05);
    }
    .paper h3 {
        font-size: 1.08rem;
        line-height: 1.35;
        margin: 0 0 .35rem;
    }
    .paper h3 a {
        color: var(--ink);
        text-decoration: none;
    }
    .paper h3 a:hover {
        color: var(--blue);
        text-decoration: underline;
    }
    .paper-meta {
        color: var(--muted);
        font-size: .88rem;
        margin-bottom: .58rem;
    }
    .score {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 54px;
        height: 30px;
        border-radius: 999px;
        background: #e9f0ff;
        color: #174899;
        font-weight: 740;
        margin-right: .5rem;
    }
    .section-label {
        color: #30485f;
        font-size: .82rem;
        font-weight: 760;
        margin: .7rem 0 .2rem;
    }
    .abstract-box {
        color: #2d3a45;
        line-height: 1.58;
        font-size: .94rem;
    }
    .summary-box {
        background: #f3f8f7;
        border: 1px solid #cfe3df;
        border-radius: 8px;
        color: #163d38;
        line-height: 1.58;
        padding: .72rem .82rem;
        margin-top: .25rem;
    }
    .tag {
        display: inline-block;
        border: 1px solid #cfd9e6;
        color: #385066;
        border-radius: 999px;
        padding: .12rem .5rem;
        font-size: .78rem;
        margin: .18rem .2rem .05rem 0;
        background: #f8fbfe;
    }
    @media (max-width: 850px) {
        .metric-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .main-title { font-size: 1.75rem; }
    }
</style>
"""


def split_lines(value: str) -> list[str]:
    return [item.strip() for item in value.replace(";", "\n").replace(",", "\n").splitlines() if item.strip()]


def paper_url(paper) -> str:
    if paper["url"]:
        return paper["url"]
    if paper["doi"]:
        return f"https://doi.org/{paper['doi']}"
    return "#"


def matches_current_profile(paper, keywords: list[str], journals: list[str]) -> bool:
    combined = " ".join([paper["title"] or "", paper["abstract"] or "", paper["keywords"] or ""])
    if keyword_hits(combined, keywords):
        return True
    return any(journal_matches(paper["journal"], journal) for journal in journals)


def filter_current_profile(papers, keywords: list[str], journals: list[str]):
    return [paper for paper in papers if matches_current_profile(paper, keywords, journals)]


def render_text_block(text: str) -> str:
    escaped = escape(text or "")
    return escaped.replace("\n", "<br>")


def paper_card(paper, collections) -> None:
    abstract = clean_abstract(paper["abstract"])
    if len(abstract) > 1800:
        abstract = abstract[:1797].rsplit(" ", 1)[0] + "..."

    st.markdown(
        f"""
        <div class="paper">
            <h3><a href="{escape(paper_url(paper))}" target="_blank" rel="noopener noreferrer">{escape(paper["title"])}</a></h3>
            <div class="paper-meta">
                <span class="score">{paper["impact_score"]:.1f}</span>
                {escape(paper["journal"] or "Unknown journal")} · {escape(paper["publication_date"] or "No date")} ·
                Citations {paper["cited_by_count"] or 0}
            </div>
            <div class="paper-meta">{escape(paper["authors"] or "Authors unavailable")}</div>
            <div class="section-label">AI 总结</div>
            <div class="summary-box">{render_text_block(paper["summary"] or "暂无总结。重新运行扫描后会自动补全。")}</div>
            <div class="section-label">摘要</div>
            <div class="abstract-box">{render_text_block(abstract or "OpenAlex 未返回摘要。点击标题可打开原文查看。")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if paper["keywords"]:
        st.markdown(
            " ".join(f'<span class="tag">{escape(tag.strip())}</span>' for tag in paper["keywords"].split(",")[:6]),
            unsafe_allow_html=True,
        )

    c1, c2, c3, c4 = st.columns([1.2, 1.7, 1.2, 1])
    with c1:
        rating = st.slider(
            "兴趣评分",
            1,
            5,
            int(paper["user_rating"] or 3),
            key=f"rating_{paper['id']}",
            help="你的评分会在下次抓取时影响关键词偏好。",
        )
    with c2:
        note = st.text_input("笔记", value=paper["user_note"] or "", key=f"note_{paper['id']}")
    with c3:
        collection_names = {row["name"]: row["id"] for row in collections}
        if collection_names:
            selected = st.selectbox("收藏夹", list(collection_names), key=f"collection_{paper['id']}")
            if st.button("收藏", key=f"fav_{paper['id']}", use_container_width=True):
                add_to_collection(collection_names[selected], paper["id"])
                st.toast("已加入收藏夹")
    with c4:
        if st.button("保存评分", key=f"save_{paper['id']}", use_container_width=True):
            update_rating(paper["id"], rating, note)
            st.toast("评分已保存")
        if st.button("隐藏", key=f"hide_{paper['id']}", use_container_width=True):
            hide_paper(paper["id"])
            st.rerun()


def render_dashboard() -> None:
    papers = list_papers(limit=500)
    rated = [paper for paper in papers if paper["user_rating"] is not None]
    favorites = sum(1 for row in list_collections() for _ in papers_in_collection(row["id"]))
    avg_score = sum(float(paper["impact_score"]) for paper in papers) / len(papers) if papers else 0
    st.markdown(
        f"""
        <div class="metric-row">
            <div class="metric"><span class="subtle">文献总数</span><b>{len(papers)}</b></div>
            <div class="metric"><span class="subtle">已评分</span><b>{len(rated)}</b></div>
            <div class="metric"><span class="subtle">收藏记录</span><b>{favorites}</b></div>
            <div class="metric"><span class="subtle">平均影响分</span><b>{avg_score:.1f}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    init_db()
    st.markdown(CSS, unsafe_allow_html=True)

    default_keywords = "\n".join(get_setting("keywords", ["photocatalysis", "electrocatalysis", "CO2 reduction"]))
    default_journals = "\n".join(get_setting("journals", ["Journal of the American Chemical Society", "Angewandte Chemie", "Nature Chemistry"]))

    with st.sidebar:
        st.header("追踪设置")
        keywords_text = st.text_area("关键词", default_keywords, height=130)
        journals_text = st.text_area("期刊名", default_journals, height=130)
        days_back = st.number_input("抓取最近几天", min_value=1, max_value=30, value=int(get_setting("days_back", 1)))
        max_results = st.slider("最多返回文献", 10, 100, int(get_setting("max_results", 40)), step=5)
        min_score = st.slider("最低影响分", 0, 100, 45, step=5)

        if st.button("保存设置", use_container_width=True):
            set_setting("keywords", split_lines(keywords_text))
            set_setting("journals", split_lines(journals_text))
            set_setting("days_back", days_back)
            set_setting("max_results", max_results)
            st.toast("设置已保存")

        st.divider()
        new_collection = st.text_input("新建收藏夹", placeholder="例如：CPL / 综述 / 必读")
        if st.button("创建收藏夹", use_container_width=True):
            create_collection(new_collection)
            st.rerun()

    st.markdown('<div class="main-title">Chem Lit Daily</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtle">每天把关键词和目标期刊里的新化学文献收进来，按影响潜力排序，留下你的兴趣反馈。</div>',
        unsafe_allow_html=True,
    )
    render_dashboard()

    tabs = st.tabs(["今日筛选", "历史文献", "收藏夹", "数据表"])

    with tabs[0]:
        keywords = split_lines(keywords_text)
        journals = split_lines(journals_text)
        st.caption("来源：OpenAlex。标题可直接打开原文；AI 总结优先使用 OPENAI_API_KEY，没有配置时使用本地摘要规则。")
        if st.button("运行今日文献扫描", type="primary"):
            set_setting("keywords", keywords)
            set_setting("journals", journals)
            set_setting("days_back", days_back)
            set_setting("max_results", max_results)
            from_date = date.today() - timedelta(days=int(days_back) - 1)
            with st.spinner("正在抓取、评分并总结新文献..."):
                rated_history = [dict(paper) for paper in list_papers(only_rated=True, limit=500)]
                keyword_boosts = learned_keyword_boost(rated_history, keywords)
                papers = fetch_openalex(
                    keywords=keywords,
                    journals=journals,
                    from_date=from_date,
                    max_results=max_results,
                    keyword_boosts=keyword_boosts,
                )
                for paper in papers:
                    upsert_paper(paper)
            st.success(f"完成：新增或更新 {len(papers)} 篇文献")
            st.rerun()

        papers = filter_current_profile(
            list_papers(min_score=min_score, only_unread=True, limit=200),
            keywords,
            journals,
        )[:80]
        collections = list_collections()
        if not collections:
            create_collection("待读")
            create_collection("重点跟进")
            collections = list_collections()
        for paper in papers:
            paper_card(paper, collections)
        if not papers:
            st.info("当前关键词/期刊下还没有未评分文献。请点击“运行今日文献扫描”。历史库里的旧主题文献不会再混到这里。")

    with tabs[1]:
        search = st.text_input("搜索历史", placeholder="标题、期刊、摘要或关键词")
        only_rated = st.checkbox("只看已评分")
        papers = list_papers(search=search, min_score=min_score, only_rated=only_rated, limit=200)
        collections = list_collections()
        for paper in papers:
            paper_card(paper, collections)

    with tabs[2]:
        collections = list_collections()
        if not collections:
            st.info("还没有收藏夹。可以在左侧创建。")
        for collection in collections:
            with st.expander(collection["name"], expanded=False):
                papers = papers_in_collection(collection["id"])
                if not papers:
                    st.caption("这个收藏夹还没有文献。")
                for paper in papers:
                    st.markdown(
                        f'**[{escape(paper["title"])}]({paper_url(paper)})**',
                        unsafe_allow_html=False,
                    )
                    st.caption(f"{paper['journal']} · {paper['publication_date']} · score {paper['impact_score']:.1f}")

    with tabs[3]:
        papers = list_papers(limit=500)
        if papers:
            df = pd.DataFrame([dict(paper) for paper in papers])
            st.dataframe(
                df[["title", "journal", "publication_date", "impact_score", "user_rating", "doi", "url"]],
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "导出 CSV",
                df.to_csv(index=False).encode("utf-8-sig"),
                "chem_lit_daily.csv",
                "text/csv",
                use_container_width=False,
            )
        else:
            st.info("暂无数据。")


if __name__ == "__main__":
    main()
