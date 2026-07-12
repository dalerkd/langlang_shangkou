from __future__ import annotations

import sqlite3
from collections.abc import Callable
import logging

from app.services.analyzer import AnalysisResult, TermAnalysis, analyze_text
from app.services.tags import apply_tags_for_term
from app.services.ollama_client import get_explainer

logger = logging.getLogger(__name__)

PENDING_MEANING = "待生成"


def analyze_article(
    conn: sqlite3.Connection,
    article_id: int,
    explainer: object | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> None:
    _progress(progress_callback, 5, "读取文章")
    article = conn.execute(
        "SELECT id, content FROM articles WHERE id = ?",
        (article_id,),
    ).fetchone()
    if article is None:
        raise ValueError(f"Article {article_id} does not exist")

    _progress(progress_callback, 12, "拆分段落并统计词频")
    result = analyze_text(article["content"])
    conn.execute("DELETE FROM paragraphs WHERE article_id = ?", (article_id,))
    conn.execute("DELETE FROM article_term_stats WHERE article_id = ?", (article_id,))
    conn.execute("DELETE FROM term_occurrences WHERE article_id = ?", (article_id,))

    _progress(progress_callback, 25, "写入段落和词表")
    paragraph_ids = _store_paragraphs(conn, article_id, result.paragraphs)
    all_terms = result.words + result.phrases
    term_ids = _ensure_terms(conn, all_terms)
    for term in result.words:
        apply_tags_for_term(conn, term_ids[(term.type, term.canonical)], term.canonical)
    _store_stats_and_occurrences(conn, article_id, all_terms, term_ids, paragraph_ids)
    _progress(progress_callback, 45, f"准备生成 {len(all_terms)} 个解释")
    _fill_meanings(conn, all_terms, term_ids, explainer or get_explainer(), progress_callback)
    conn.execute(
        "UPDATE articles SET status = 'analyzed', analyzed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (article_id,),
    )
    conn.commit()
    _progress(progress_callback, 100, "分析完成")
    logger.info(f"Article {article_id} analysis completed ({len(all_terms)} terms)")


def _store_paragraphs(
    conn: sqlite3.Connection,
    article_id: int,
    paragraphs: list[str],
) -> dict[int, int]:
    paragraph_ids: dict[int, int] = {}
    for paragraph_number, text in enumerate(paragraphs, start=1):
        cursor = conn.execute(
            """
            INSERT INTO paragraphs (article_id, paragraph_number, text)
            VALUES (?, ?, ?)
            """,
            (article_id, paragraph_number, text),
        )
        paragraph_ids[paragraph_number] = int(cursor.lastrowid)
    return paragraph_ids


def _ensure_terms(
    conn: sqlite3.Connection,
    terms: list[TermAnalysis],
) -> dict[tuple[str, str], int]:
    term_ids: dict[tuple[str, str], int] = {}
    for term in terms:
        conn.execute(
            """
            INSERT INTO terms (type, canonical_text, status)
            VALUES (?, ?, 'unknown')
            ON CONFLICT(type, canonical_text) DO NOTHING
            """,
            (term.type, term.canonical),
        )
        row = conn.execute(
            "SELECT id FROM terms WHERE type = ? AND canonical_text = ?",
            (term.type, term.canonical),
        ).fetchone()
        term_ids[(term.type, term.canonical)] = int(row["id"])
    return term_ids


def _store_stats_and_occurrences(
    conn: sqlite3.Connection,
    article_id: int,
    terms: list[TermAnalysis],
    term_ids: dict[tuple[str, str], int],
    paragraph_ids: dict[int, int],
) -> None:
    for sort_weight, term in enumerate(terms, start=1):
        term_id = term_ids[(term.type, term.canonical)]
        conn.execute(
            """
            INSERT INTO article_term_stats
                (article_id, term_id, frequency, first_paragraph_number, sort_weight)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                article_id,
                term_id,
                term.frequency,
                min(term.paragraph_numbers),
                sort_weight,
            ),
        )
        for occurrence in term.occurrences:
            conn.execute(
                """
                INSERT INTO term_occurrences
                    (article_id, paragraph_id, term_id, original_text, char_start, char_end)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    paragraph_ids[occurrence.paragraph_number],
                    term_id,
                    occurrence.original_text,
                    occurrence.char_start,
                    occurrence.char_end,
                ),
            )


def _fill_meanings(
    conn: sqlite3.Connection,
    terms: list[TermAnalysis],
    term_ids: dict[tuple[str, str], int],
    explainer: object,
    progress_callback: Callable[[int, str], None] | None = None,
) -> None:
    rows = []
    for term in terms:
        term_id = term_ids[(term.type, term.canonical)]
        existing = conn.execute(
            "SELECT meaning, user_edited FROM terms WHERE id = ?",
            (term_id,),
        ).fetchone()
        if existing["meaning"] and existing["user_edited"]:
            continue
        if existing["meaning"] and existing["meaning"] != PENDING_MEANING:
            continue
        rows.append({"type": term.type, "canonical_text": term.canonical})

    if not rows:
        _progress(progress_callback, 90, "解释已存在")
        return

    logger.info(f"Requesting explanations for {len(rows)} terms")
    explanations = explainer.explain_terms(rows)
    _progress(progress_callback, 85, "保存中文解释")
    success = 0
    failed = 0
    for row in rows:
        result = explanations.get(row["canonical_text"])
        meaning = result.meaning if result and result.meaning else PENDING_MEANING
        if meaning == PENDING_MEANING:
            failed += 1
            logger.warning(f"Pending meaning for '{row['canonical_text']}': {result.error if result else 'no result'}")
        else:
            success += 1
        conn.execute(
            """
            UPDATE terms
            SET meaning = ?, updated_at = CURRENT_TIMESTAMP
            WHERE type = ? AND canonical_text = ? AND user_edited = 0
            """,
            (meaning, row["type"], row["canonical_text"]),
        )
    logger.info(f"Explanations saved: {success} success, {failed} pending")


def _progress(
    progress_callback: Callable[[int, str], None] | None,
    percent: int,
    message: str,
) -> None:
    if progress_callback is not None:
        progress_callback(percent, message)
