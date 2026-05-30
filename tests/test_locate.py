import sqlite3

from fastapi.testclient import TestClient

from app.db import create_schema, get_connection
from app.main import app, get_db
from app.services.analysis_store import analyze_article
from app.services.analyzer import analyze_text


def test_occurrence_char_offsets_match_paragraph_text(tmp_path):
    """Every occurrence's char_start/char_end must slice to original_text."""
    db_path = tmp_path / "learn.db"

    def override_db():
        conn = get_connection(db_path)
        create_schema(conn)
        return conn

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    response = client.post(
        "/articles",
        data={
            "title": "Locate Test",
            "content": "The cat sat on the mat.\n\nAnother cat walked by the mat.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    article_id = int(response.headers["location"].split("/")[-1])

    conn = get_connection(db_path)
    analyze_article(conn, article_id, explainer=None)

    rows = conn.execute(
        """
        SELECT p.paragraph_number, p.text, o.char_start, o.char_end, o.original_text
        FROM term_occurrences o
        JOIN paragraphs p ON p.id = o.paragraph_id
        WHERE o.article_id = ?
        ORDER BY p.paragraph_number, o.char_start
        """,
        (article_id,),
    ).fetchall()

    assert len(rows) > 0
    for row in rows:
        paragraph_text = row["text"]
        start = row["char_start"]
        end = row["char_end"]
        extracted = paragraph_text[start:end]
        assert extracted == row["original_text"], (
            f"P{row['paragraph_number']}: slice[{start}:{end}]={extracted!r} != db={row['original_text']!r}"
        )

    conn.close()


def test_rendered_paragraph_text_node_matches_db_text(tmp_path):
    """DOM textContent (trimmed) must equal DB text so frontend offsets line up."""
    db_path = tmp_path / "learn.db"

    def override_db():
        conn = get_connection(db_path)
        create_schema(conn)
        return conn

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    response = client.post(
        "/articles",
        data={
            "title": "DOM Test",
            "content": "Skills use progressive disclosure.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    article_id = int(response.headers["location"].split("/")[-1])

    conn = get_connection(db_path)
    analyze_article(conn, article_id, explainer=None)
    conn.close()

    page = client.get(f"/articles/{article_id}")
    html = page.text

    import re
    m = re.search(r'<p id="p1"[^>]*>(.*?)</p>', html, re.DOTALL)
    assert m, "Paragraph 1 not found in rendered HTML"
    p_inner = m.group(1)

    text_m = re.search(r'<span class="paragraph-text">(.*?)</span>', p_inner, re.DOTALL)
    text_only = text_m.group(1) if text_m else p_inner
    text_only = re.sub(r'<span class="paragraph-index">.*?</span>', '', text_only, flags=re.DOTALL)
    trimmed = text_only.strip()

    assert trimmed == "Skills use progressive disclosure.", (
        f"Rendered paragraph text {trimmed!r} does not match DB text"
    )
def test_rendered_paragraph_has_leading_whitespace_that_would_offset_js_slice(tmp_path):
    """
    The raw text node inside <p> includes Jinja2 indentation whitespace.
    If frontend uses childNodes[childNodes.length-1].textContent without trim(),
    all slice offsets will be wrong.
    """
    db_path = tmp_path / "learn.db"

    def override_db():
        conn = get_connection(db_path)
        create_schema(conn)
        return conn

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    response = client.post(
        "/articles",
        data={
            "title": "Whitespace Test",
            "content": "Skills use progressive disclosure.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    article_id = int(response.headers["location"].split("/")[-1])

    conn = get_connection(db_path)
    analyze_article(conn, article_id, explainer=None)
    db_text = conn.execute(
        "SELECT text FROM paragraphs WHERE article_id = ? AND paragraph_number = 1",
        (article_id,),
    ).fetchone()["text"]
    conn.close()

    page = client.get(f"/articles/{article_id}")
    html = page.text

    import re
    m = re.search(r'<p id="p1"[^>]*>(.*?)</p>', html, re.DOTALL)
    assert m
    p_inner = m.group(1)

    # Extract text from paragraph-text span; fallback to raw inner if no span
    text_m = re.search(r'<span class="paragraph-text">(.*?)</span>', p_inner, re.DOTALL)
    text_only = text_m.group(1) if text_m else p_inner
    # Remove paragraph-index span if still present
    text_only = re.sub(r'<span class="paragraph-index">.*?</span>', '', text_only, flags=re.DOTALL)

    # Paragraph text inside the span should equal db_text directly
    assert text_only == db_text, (
        f"Paragraph text {text_only!r} != DB text {db_text!r}"
    )
    # Verify there is still Jinja2 whitespace in the raw <p> inner HTML
    raw_leading = len(p_inner) - len(p_inner.lstrip())
    assert raw_leading > 0, "Expected leading whitespace from Jinja2 indentation"
def test_split_paragraphs_normalizes_crlf_to_lf():
    """Windows line endings must not leak into stored paragraph text."""
    result = analyze_text("First line\r\nSecond line.\n\nThird line\r\nFourth line.")
    assert result.paragraphs == [
        "First line\nSecond line.",
        "Third line\nFourth line.",
    ]


def test_analyzer_preserves_exact_char_offsets_after_crlf_normalization():
    """When text contains \\r\\n, occurrences after the newline must have correct offsets."""
    result = analyze_text("One\r\nTwo three.")
    words = {w.canonical: w for w in result.words}
    assert "two" in words
    occ = words["two"].occurrences[0]
    assert occ.char_start == 4
    assert occ.char_end == 7
    # Verify slice against the *stored* paragraph text (which has \\n, not \\r\\n)
    paragraph_text = result.paragraphs[0]
    assert paragraph_text[occ.char_start:occ.char_end] == "Two"
