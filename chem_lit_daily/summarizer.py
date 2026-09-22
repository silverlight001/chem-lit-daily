from __future__ import annotations

import os
import re
from typing import Any

import requests


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def clean_abstract(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def fallback_summary(title: str, abstract: str | None, keywords: list[str]) -> str:
    abstract = clean_abstract(abstract)
    if not abstract:
        return "未获取到摘要，建议打开原文确认研究对象、实验方法和主要结论。"

    sentences = re.split(r"(?<=[.!?。！？])\s+", abstract)
    selected = []
    for sentence in sentences:
        low = sentence.lower()
        if any(keyword.lower() in low for keyword in keywords):
            selected.append(sentence)
        if len(selected) >= 2:
            break
    if not selected:
        selected = sentences[:2]

    summary = " ".join(selected).strip()
    if len(summary) > 420:
        summary = summary[:417].rsplit(" ", 1)[0] + "..."

    matched = [keyword for keyword in keywords if keyword.lower() in (title + " " + abstract).lower()]
    prefix = f"命中关键词：{', '.join(matched[:5])}。" if matched else "与当前主题可能相关。"
    return f"{prefix}{summary}"


def _extract_response_text(payload: dict[str, Any]) -> str:
    if payload.get("output_text"):
        return str(payload["output_text"]).strip()
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def ai_summary(title: str, journal: str, abstract: str | None, keywords: list[str]) -> str | None:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    abstract = clean_abstract(abstract)
    if not abstract:
        return None

    model = os.environ.get("OPENAI_SUMMARY_MODEL", "gpt-5-mini").strip()
    prompt = f"""
请用中文为一篇化学/材料/光物理方向论文写一个简短但有信息量的总结。

要求：
1. 只基于题目和摘要，不要编造摘要里没有的信息。
2. 用 3 个短句或 3 个项目符号回答。
3. 必须讲清楚：这篇文章做了什么；核心结果/方法是什么；创新点或值得关注之处在哪里。
4. 如果创新点不明确，请写“摘要中未明确体现创新点”，并说明可能的价值。

关注关键词：{", ".join(keywords) or "无"}
期刊/来源：{journal or "未知"}
题目：{title}
摘要：{abstract[:6000]}
""".strip()

    try:
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": prompt,
                "store": False,
            },
            timeout=45,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    text = _extract_response_text(response.json())
    return text or None


def summarize(title: str, abstract: str | None, keywords: list[str], journal: str = "") -> str:
    return ai_summary(title, journal, abstract, keywords) or fallback_summary(title, abstract, keywords)
