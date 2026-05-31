from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from collections.abc import Iterator
import threading
import uuid

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import APP_ROOT, DEFAULT_DB_PATH
from app.db import create_schema, get_connection
from app.services.analysis_store import analyze_article
from app.services.ollama_client import get_explainer
import httpx
import logging

logger = logging.getLogger(__name__)


app = FastAPI(title="朗朗上口先读英语")
templates = Jinja2Templates(directory=str(APP_ROOT / "app" / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_ROOT / "app" / "static")), name="static")
app.state.explainer = get_explainer()
app.state.analysis_jobs = {}
app.state.analysis_jobs_lock = threading.Lock()

@app.get("/debug/ollama")
def debug_ollama():
    explainer = get_explainer()
    result = {
        "provider": type(explainer).__name__,
        "base_url": explainer.base_url,
        "model": explainer.model,
        "connectivity": None,
        "error": None,
    }
    try:
        if result["provider"] == "OllamaExplainer":
            r = httpx.get(f"{explainer.base_url}/api/tags", timeout=10)
            result["connectivity"] = r.status_code
            result["models"] = [m["name"] for m in r.json().get("models", [])]
        else:
            r = httpx.get(f"{explainer.base_url}/models", headers={"Authorization": f"Bearer {getattr(explainer, 'api_key', '')}"}, timeout=10)
            result["connectivity"] = r.status_code
    except Exception as e:
        import traceback
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        result["traceback"] = traceback.format_exc().split("\n")[-4:]
    return result

@app.get("/debug/env")
def debug_env():
    from app.config import (
        EXPLAINER_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL,
        OPENAI_BASE_URL, OPENAI_MODEL, LOG_LEVEL,
    )
    return {
        "EXPLAINER_PROVIDER": EXPLAINER_PROVIDER,
        "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
        "OLLAMA_MODEL": OLLAMA_MODEL,
        "OPENAI_BASE_URL": OPENAI_BASE_URL,
        "OPENAI_MODEL": OPENAI_MODEL,
        "LOG_LEVEL": LOG_LEVEL,
    }


def get_db(db_path: str | Path = str(DEFAULT_DB_PATH)) -> Iterator[sqlite3.Connection]:
    conn = get_connection(db_path)
    create_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


@app.get("/", response_class=HTMLResponse)
def index(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> HTMLResponse:
    articles = conn.execute(
        """
        SELECT id, title, status, created_at
        FROM articles
        ORDER BY created_at DESC, id DESC
        LIMIT 6
        """
    ).fetchall()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"articles": articles},
    )


@app.post("/articles")
def create_article(
    title: str = Form(""),
    content: str = Form(...),
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    clean_title = title.strip() or "未命名文章"
    cursor = conn.execute(
        "INSERT INTO articles (title, content, status) VALUES (?, ?, 'new')",
        (clean_title, content.strip()),
    )
    conn.commit()
    return RedirectResponse(f"/articles/{cursor.lastrowid}", status_code=303)


@app.post("/articles/{article_id}/analyze")
def analyze_article_route(
    article_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> RedirectResponse:
    analyze_article(conn, article_id, request.app.state.explainer)
    return RedirectResponse(f"/articles/{article_id}", status_code=303)


@app.post("/articles/{article_id}/analysis-jobs")
def start_analysis_job(
    article_id: int,
    request: Request,
    db_path: str = str(DEFAULT_DB_PATH),
) -> dict[str, object]:
    job_id = uuid.uuid4().hex
    redirect_url = f"/articles/{article_id}"
    _set_analysis_job(
        request.app,
        job_id,
        {
            "job_id": job_id,
            "article_id": article_id,
            "status": "queued",
            "progress": 0,
            "message": "等待开始",
            "redirect_url": redirect_url,
            "error": None,
            "updated_at": _utc_now(),
        },
    )
    thread = threading.Thread(
        target=_run_analysis_job,
        args=(request.app, job_id, article_id, Path(db_path), request.app.state.explainer),
        daemon=True,
    )
    thread.start()
    payload = _get_analysis_job(request.app, job_id)
    payload["status_url"] = f"/analysis-jobs/{job_id}"
    return payload


@app.get("/analysis-jobs/{job_id}")
def get_analysis_job_status(job_id: str, request: Request) -> dict[str, object]:
    payload = _get_analysis_job(request.app, job_id)
    if not payload:
        return {
            "job_id": job_id,
            "status": "missing",
            "progress": 0,
            "message": "任务不存在",
            "redirect_url": None,
            "error": "not found",
        }
    payload["status_url"] = f"/analysis-jobs/{job_id}"
    return payload


@app.get("/articles/{article_id}", response_class=HTMLResponse)
def article_detail(
    article_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    article = conn.execute(
        "SELECT * FROM articles WHERE id = ?",
        (article_id,),
    ).fetchone()
    paragraphs = conn.execute(
        """
        SELECT *
        FROM paragraphs
        WHERE article_id = ?
        ORDER BY paragraph_number
        """,
        (article_id,),
    ).fetchall()
    word_terms = _article_terms(conn, article_id, "word")
    phrase_terms = _article_terms(conn, article_id, "phrase")
    word_status_map = {t["canonical_text"]: t["status"] for t in word_terms}

    # Familiarity stats
    def _stats(terms):
        total = sum(t["frequency"] for t in terms)
        unknown = sum(t["frequency"] for t in terms if t["status"] == "unknown")
        unique_total = len(terms)
        unique_unknown = sum(1 for t in terms if t["status"] == "unknown")
        return {
            "total": total,
            "unknown": unknown,
            "known": total - unknown,
            "unique_total": unique_total,
            "unique_unknown": unique_unknown,
            "unique_known": unique_total - unique_unknown,
        }

    word_stats = _stats(word_terms)
    phrase_stats = _stats(phrase_terms)

    return templates.TemplateResponse(
        request,
        "article_detail.html",
        {
            "article": article,
            "paragraphs": paragraphs,
            "word_terms": word_terms,
            "phrase_terms": phrase_terms,
            "word_status_map_json": json.dumps(word_status_map, ensure_ascii=False),
            "word_stats": word_stats,
            "phrase_stats": phrase_stats,
        },
    )


@app.get("/articles", response_class=HTMLResponse)
def article_history(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    articles = conn.execute(
        """
        SELECT id, title, status, created_at, analyzed_at
        FROM articles
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    return templates.TemplateResponse(
        request,
        "articles.html",
        {"articles": articles},
    )



@app.post("/lookup")
def lookup_word(
    request: Request,
    word: str = Form(...),
):
    word = word.strip().lower()
    if not word:
        return {"meaning": "", "error": "请输入单词"}
    try:
        results = request.app.state.explainer.explain_terms([
            {"canonical_text": word, "type": "word"}
        ])
        result = results.get(word)
        if result is None:
            return {"meaning": "", "error": "未获取到释义"}
        if result.error:
            return {"meaning": "", "error": result.error}
        return {"meaning": result.meaning or "", "error": ""}
    except Exception as exc:
        logger.exception("Lookup failed for word: %s", word)
        return {"meaning": "", "error": str(exc)}

@app.get("/terms", response_class=HTMLResponse)
def term_index(
    request: Request,
    type: str = "",
    status: str = "",
    q: str = "",
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    clauses = []
    params: list[str] = []
    if type in {"word", "phrase"}:
        clauses.append("t.type = ?")
        params.append(type)
    if status in {"unknown", "confusing", "familiar"}:
        clauses.append("t.status = ?")
        params.append(status)
    if q.strip():
        clauses.append("t.canonical_text LIKE ?")
        params.append(f"%{q.strip()}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    terms = conn.execute(
        f"""
        SELECT
            t.*,
            COALESCE(SUM(ats.frequency), 0) AS total_frequency,
            COUNT(DISTINCT ats.article_id) AS article_count
        FROM terms t
        LEFT JOIN article_term_stats ats ON ats.term_id = t.id
        {where}
        GROUP BY t.id
        ORDER BY total_frequency DESC, t.canonical_text ASC
        """,
        params,
    ).fetchall()
    return templates.TemplateResponse(
        request,
        "terms.html",
        {"terms": terms, "filters": {"type": type, "status": status, "q": q}},
    )


@app.patch("/terms/{term_id}", response_class=HTMLResponse)
def update_term(
    term_id: int,
    request: Request,
    meaning: str = Form(...),
    status: str = Form(...),
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    if status not in {"unknown", "confusing", "familiar"}:
        status = "unknown"
    clean_meaning = meaning.strip()
    user_edited = 1 if clean_meaning else 0
    conn.execute(
        """
        UPDATE terms
        SET meaning = ?, status = ?, user_edited = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (clean_meaning or None, status, user_edited, term_id),
    )
    conn.commit()
    term = conn.execute("SELECT * FROM terms WHERE id = ?", (term_id,)).fetchone()
    return templates.TemplateResponse(
        request,
        "_term_editor.html",
        {"term": term},
    )


@app.get("/terms/{term_id}/references", response_class=HTMLResponse)
def term_references(
    term_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    term = conn.execute("SELECT * FROM terms WHERE id = ?", (term_id,)).fetchone()
    references = conn.execute(
        """
        SELECT DISTINCT
            a.id AS article_id,
            a.title,
            p.paragraph_number,
            p.text
        FROM term_occurrences o
        JOIN articles a ON a.id = o.article_id
        JOIN paragraphs p ON p.id = o.paragraph_id
        WHERE o.term_id = ?
        ORDER BY a.created_at DESC, a.id DESC, p.paragraph_number ASC
        """,
        (term_id,),
    ).fetchall()
    return templates.TemplateResponse(
        request,
        "_references.html",
        {"term": term, "references": references, "total_refs": len(references), "article_count": len(set(r["article_id"] for r in references))},
    )

@app.get("/terms/{term_id}/occurrences")
def term_occurrences(
    term_id: int,
    article_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT
            p.paragraph_number,
            o.char_start,
            o.char_end,
            o.original_text
        FROM term_occurrences o
        JOIN paragraphs p ON p.id = o.paragraph_id
        WHERE o.term_id = ? AND o.article_id = ?
        ORDER BY p.paragraph_number ASC, o.char_start ASC
        """,
        (term_id, article_id),
    ).fetchall()
    return [
        {
            "paragraph_number": row["paragraph_number"],
            "char_start": row["char_start"],
            "char_end": row["char_end"],
            "original_text": row["original_text"],
        }
        for row in rows
    ]


def _article_terms(
    conn: sqlite3.Connection,
    article_id: int,
    term_type: str,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            t.*,
            ats.frequency,
            ats.first_paragraph_number,
            ats.sort_weight
        FROM article_term_stats ats
        JOIN terms t ON t.id = ats.term_id
        WHERE ats.article_id = ? AND t.type = ?
        ORDER BY ats.sort_weight ASC
        """,
        (article_id, term_type),
    ).fetchall()


def _run_analysis_job(
    app_instance: FastAPI,
    job_id: str,
    article_id: int,
    db_path: Path,
    explainer: OllamaExplainer | object,
) -> None:
    def progress(percent: int, message: str) -> None:
        _update_analysis_job(
            app_instance,
            job_id,
            status="running",
            progress=percent,
            message=message,
        )

    conn = get_connection(db_path)
    try:
        create_schema(conn)
        progress(3, "开始分析")
        analyze_article(conn, article_id, explainer, progress_callback=progress)
        _update_analysis_job(
            app_instance,
            job_id,
            status="succeeded",
            progress=100,
            message="学习清单已生成",
        )
    except Exception as exc:
        _update_analysis_job(
            app_instance,
            job_id,
            status="failed",
            progress=100,
            message="分析失败",
            error=str(exc),
        )
    finally:
        conn.close()


def _set_analysis_job(app_instance: FastAPI, job_id: str, payload: dict[str, object]) -> None:
    with app_instance.state.analysis_jobs_lock:
        app_instance.state.analysis_jobs[job_id] = payload


def _update_analysis_job(
    app_instance: FastAPI,
    job_id: str,
    **changes: object,
) -> None:
    with app_instance.state.analysis_jobs_lock:
        payload = app_instance.state.analysis_jobs[job_id]
        payload.update(changes)
        payload["updated_at"] = _utc_now()


def _get_analysis_job(app_instance: FastAPI, job_id: str) -> dict[str, object]:
    with app_instance.state.analysis_jobs_lock:
        payload = app_instance.state.analysis_jobs.get(job_id, {}).copy()
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
