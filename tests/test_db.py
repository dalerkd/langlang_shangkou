import sqlite3

from app.db import create_schema, get_connection
from app.services.analysis_store import analyze_article
from app.services.ollama_client import ExplanationResult


class FailingExplainer:
    def explain_terms(self, terms):
        return {
            term["canonical_text"]: ExplanationResult(
                meaning=None,
                error="ollama unavailable",
            )
            for term in terms
        }


class SuccessfulExplainer:
    def __init__(self):
        self.terms = []

    def explain_terms(self, terms):
        self.terms = list(terms)
        return {
            term["canonical_text"]: ExplanationResult(
                meaning=f"{term['canonical_text']} 的解释",
                error=None,
            )
            for term in self.terms
        }


def test_analyze_article_persists_terms_occurrences_and_keeps_user_status(tmp_path):
    db_path = tmp_path / "learn.db"
    conn = get_connection(db_path)
    create_schema(conn)

    conn.execute(
        "INSERT INTO articles (title, content, status) VALUES (?, ?, ?)",
        ("One", "Running helps learners look up words. Learners look up examples.", "new"),
    )
    article_id = conn.execute("SELECT id FROM articles").fetchone()["id"]

    analyze_article(conn, article_id, FailingExplainer())
    conn.execute(
        "UPDATE terms SET status = ?, meaning = ?, user_edited = 1 WHERE canonical_text = ?",
        ("familiar", "用户修订含义", "learner"),
    )
    conn.execute(
        "INSERT INTO articles (title, content, status) VALUES (?, ?, ?)",
        ("Two", "Learners look up phrases again.", "new"),
    )
    second_article_id = conn.execute(
        "SELECT id FROM articles WHERE title = ?",
        ("Two",),
    ).fetchone()["id"]

    analyze_article(conn, second_article_id, FailingExplainer())

    learner = conn.execute(
        "SELECT status, meaning, user_edited FROM terms WHERE canonical_text = ?",
        ("learner",),
    ).fetchone()
    stat = conn.execute(
        """
        SELECT frequency
        FROM article_term_stats ats
        JOIN terms t ON t.id = ats.term_id
        WHERE ats.article_id = ? AND t.canonical_text = ?
        """,
        (second_article_id, "learner"),
    ).fetchone()
    occurrences = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM term_occurrences o
        JOIN terms t ON t.id = o.term_id
        WHERE o.article_id = ? AND t.canonical_text = ?
        """,
        (second_article_id, "learner"),
    ).fetchone()

    assert learner["status"] == "familiar"
    assert learner["meaning"] == "用户修订含义"
    assert learner["user_edited"] == 1
    assert stat["frequency"] == 1
    assert occurrences["count"] == 1


def test_analyze_article_retries_pending_generated_meanings(tmp_path):
    db_path = tmp_path / "learn.db"
    conn = get_connection(db_path)
    create_schema(conn)
    conn.execute(
        "INSERT INTO articles (title, content, status) VALUES (?, ?, ?)",
        ("Retry", "Learners look up words.", "new"),
    )
    article_id = conn.execute("SELECT id FROM articles").fetchone()["id"]
    analyze_article(conn, article_id, FailingExplainer())

    explainer = SuccessfulExplainer()
    analyze_article(conn, article_id, explainer)

    learner = conn.execute(
        "SELECT meaning FROM terms WHERE type = 'word' AND canonical_text = 'learner'",
    ).fetchone()

    assert {"type": "word", "canonical_text": "learner"} in explainer.terms
    assert learner["meaning"] == "learner 的解释"


def test_schema_enforces_unique_term_identity(tmp_path):
    conn = get_connection(tmp_path / "learn.db")
    create_schema(conn)

    conn.execute(
        "INSERT INTO terms (type, canonical_text, meaning, status) VALUES (?, ?, ?, ?)",
        ("word", "learn", "学习", "unknown"),
    )

    try:
        conn.execute(
            "INSERT INTO terms (type, canonical_text, meaning, status) VALUES (?, ?, ?, ?)",
            ("word", "learn", "学习", "unknown"),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("duplicate terms should be rejected")
