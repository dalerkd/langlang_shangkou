from __future__ import annotations

import sqlite3

from app.services.analyzer import lemmatize_word

TAG_COLOR_PALETTE = [
    "#e8f5e9",
    "#e3f2fd",
    "#fff9c4",
    "#fce4ec",
    "#f3e5f5",
    "#e0f7fa",
    "#fff3e0",
    "#e8eaf6",
    "#fbe9e7",
    "#e0f2f1",
]


def _next_color(conn: sqlite3.Connection) -> str:
    count = conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    return TAG_COLOR_PALETTE[count % len(TAG_COLOR_PALETTE)]


def normalize_tag_word(word: str) -> str:
    w = word.strip().lower().strip("'")
    if not w:
        return ""
    return lemmatize_word(w)


def create_tag(conn: sqlite3.Connection, name: str) -> int:
    color = _next_color(conn)
    cursor = conn.execute(
        "INSERT INTO tags (name, color) VALUES (?, ?)",
        (name.strip(), color),
    )
    return cursor.lastrowid


def update_tag_words(conn: sqlite3.Connection, tag_id: int, words_text: str) -> None:
    raw_words = [normalize_tag_word(line) for line in words_text.splitlines()]
    seen: set[str] = set()
    words: list[str] = []
    for w in raw_words:
        if w and w not in seen:
            seen.add(w)
            words.append(w)

    conn.execute("DELETE FROM tag_words WHERE tag_id = ?", (tag_id,))
    for w in words:
        conn.execute(
            "INSERT INTO tag_words (tag_id, word) VALUES (?, ?)",
            (tag_id, w),
        )

    conn.execute("DELETE FROM term_tags WHERE tag_id = ?", (tag_id,))
    if words:
        placeholders = ",".join("?" * len(words))
        rows = conn.execute(
            f"""
            SELECT id, canonical_text
            FROM terms
            WHERE type = 'word' AND canonical_text IN ({placeholders})
            """,
            tuple(words),
        ).fetchall()
        for row in rows:
            conn.execute(
                "INSERT OR IGNORE INTO term_tags (term_id, tag_id) VALUES (?, ?)",
                (row["id"], tag_id),
            )


def apply_tags_for_term(
    conn: sqlite3.Connection,
    term_id: int,
    canonical_text: str,
) -> None:
    if not canonical_text:
        return
    rows = conn.execute(
        "SELECT DISTINCT tag_id FROM tag_words WHERE word = ?",
        (canonical_text,),
    ).fetchall()
    for row in rows:
        conn.execute(
            "INSERT OR IGNORE INTO term_tags (term_id, tag_id) VALUES (?, ?)",
            (term_id, row["tag_id"]),
        )


def get_all_tags(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, name, color FROM tags ORDER BY name"
    ).fetchall()


def get_term_tags(
    conn: sqlite3.Connection,
    term_ids: list[int],
) -> dict[int, list[sqlite3.Row]]:
    if not term_ids:
        return {}
    placeholders = ",".join("?" * len(term_ids))
    rows = conn.execute(
        f"""
        SELECT tt.term_id, t.id AS tag_id, t.name, t.color
        FROM term_tags tt
        JOIN tags t ON t.id = tt.tag_id
        WHERE tt.term_id IN ({placeholders})
        ORDER BY t.name
        """,
        tuple(term_ids),
    ).fetchall()
    result: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        result.setdefault(row["term_id"], []).append(row)
    return result
