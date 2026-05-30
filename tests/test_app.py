import time

from fastapi.testclient import TestClient

import sqlite3

import pytest

from app.db import create_schema, get_connection
from app.main import app, get_db
from app.services.ollama_client import ExplanationResult


class FakeExplainer:
    def explain_terms(self, terms):
        return {
            term["canonical_text"]: ExplanationResult(
                meaning=f"{term['canonical_text']} 的中文解释",
                error=None,
            )
            for term in terms
        }


class PendingExplainer:
    def explain_terms(self, terms):
        return {
            term["canonical_text"]: ExplanationResult(meaning=None, error="offline")
            for term in terms
        }


def test_article_flow_allows_analysis_editing_and_references(tmp_path):
    db_path = tmp_path / "learn.db"

    def override_db():
        conn = get_connection(db_path)
        create_schema(conn)
        return conn

    app.dependency_overrides[get_db] = override_db
    app.state.explainer = FakeExplainer()
    client = TestClient(app)

    response = client.post(
        "/articles",
        data={
            "title": "Practice",
            "content": "Learners look up words.\n\nLearners look up phrases.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    article_id = response.headers["location"].split("/")[-1]
    response = client.post(f"/articles/{article_id}/analyze", follow_redirects=False)
    assert response.status_code == 303

    page = client.get(f"/articles/{article_id}")
    assert page.status_code == 200
    assert "look up" in page.text
    assert "learner 的中文解释" in page.text

    terms_page = client.get("/terms")
    assert terms_page.status_code == 200
    assert "learner" in terms_page.text

    patch = client.patch(
        "/terms/1",
        data={"meaning": "学习者", "status": "familiar"},
    )
    assert patch.status_code == 200
    assert "学习者" in patch.text

    refs = client.get("/terms/1/references")
    assert refs.status_code == 200
    assert "Learners look up words." in refs.text

    app.dependency_overrides.clear()


def test_pending_meaning_is_placeholder_not_textarea_value(tmp_path):
    db_path = tmp_path / "learn.db"

    def override_db():
        conn = get_connection(db_path)
        create_schema(conn)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_db
    app.state.explainer = PendingExplainer()
    client = TestClient(app)

    response = client.post(
        "/articles",
        data={"title": "Pending", "content": "Learners look up words."},
        follow_redirects=False,
    )
    article_id = response.headers["location"].split("/")[-1]
    client.post(f"/articles/{article_id}/analyze", follow_redirects=False)

    page = client.get(f"/articles/{article_id}")

    assert 'placeholder="待生成"' in page.text
    assert ">待生成</textarea>" not in page.text
    app.dependency_overrides.clear()


def test_analysis_job_reports_progress_and_finishes(tmp_path):
    db_path = tmp_path / "learn.db"
    app.state.explainer = FakeExplainer()
    client = TestClient(app)

    response = client.post(
        "/articles",
        params={"db_path": str(db_path)},
        data={"title": "Progress", "content": "Learners look up words."},
        follow_redirects=False,
    )
    article_id = response.headers["location"].split("/")[-1]

    start = client.post(
        f"/articles/{article_id}/analysis-jobs",
        params={"db_path": str(db_path)},
    )
    payload = start.json()

    assert start.status_code == 200
    assert payload["status"] in {"queued", "running"}
    assert payload["progress"] >= 0

    final = None
    for _ in range(30):
        status = client.get(payload["status_url"]).json()
        if status["status"] in {"succeeded", "failed"}:
            final = status
            break
        time.sleep(0.05)

    assert final is not None
    assert final["status"] == "succeeded"
    assert final["progress"] == 100
    assert final["redirect_url"] == f"/articles/{article_id}"

    page = client.get(f"/articles/{article_id}", params={"db_path": str(db_path)})
    assert "learner 的中文解释" in page.text


def test_db_dependency_closes_connection_after_request(tmp_path):
    dependency = get_db(tmp_path / "learn.db")

    conn = next(dependency)
    conn.execute("SELECT 1")

    with pytest.raises(StopIteration):
        next(dependency)
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
