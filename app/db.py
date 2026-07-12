from pathlib import Path
import sqlite3

from app.config import DEFAULT_DB_PATH


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            analyzed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS paragraphs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            paragraph_number INTEGER NOT NULL,
            text TEXT NOT NULL,
            UNIQUE(article_id, paragraph_number)
        );

        CREATE TABLE IF NOT EXISTS terms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('word', 'phrase')),
            canonical_text TEXT NOT NULL,
            meaning TEXT,
            status TEXT NOT NULL DEFAULT 'unknown'
                CHECK(status IN ('unknown', 'confusing', 'familiar')),
            user_edited INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(type, canonical_text)
        );

        CREATE TABLE IF NOT EXISTS term_occurrences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            paragraph_id INTEGER NOT NULL REFERENCES paragraphs(id) ON DELETE CASCADE,
            term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
            original_text TEXT NOT NULL,
            char_start INTEGER NOT NULL DEFAULT 0,
            char_end INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS article_term_stats (
            article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
            frequency INTEGER NOT NULL,
            first_paragraph_number INTEGER NOT NULL,
            sort_weight INTEGER NOT NULL,
            PRIMARY KEY(article_id, term_id)
        );

        CREATE INDEX IF NOT EXISTS idx_term_occurrences_term
            ON term_occurrences(term_id);
        CREATE INDEX IF NOT EXISTS idx_article_term_stats_article
            ON article_term_stats(article_id, sort_weight);

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tag_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            word TEXT NOT NULL,
            UNIQUE(tag_id, word)
        );

        CREATE TABLE IF NOT EXISTS term_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            UNIQUE(term_id, tag_id)
        );
        """
    )
    conn.commit()
