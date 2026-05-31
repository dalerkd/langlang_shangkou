from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Iterable

import httpx

logger = logging.getLogger(__name__)

from app.config import (
    EXPLAINER_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_BATCH_SIZE,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_BATCH_SIZE,
    OPENAI_MODEL,
    OPENAI_TIMEOUT_SECONDS,
)


@dataclass(frozen=True)
class ExplanationResult:
    meaning: str | None
    error: str | None = None


class OllamaExplainer:
    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        timeout: float = OLLAMA_TIMEOUT_SECONDS,
        batch_size: int = OLLAMA_BATCH_SIZE,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.batch_size = batch_size
        logger.debug(f"OllamaExplainer init: base_url={self.base_url}, model={self.model}")

    def explain_terms(self, terms: Iterable[dict[str, str]]) -> dict[str, ExplanationResult]:
        results: dict[str, ExplanationResult] = {}
        term_list = list(terms)
        logger.info(f"Ollama: explaining {len(term_list)} terms in batches of {self.batch_size}")
        for batch in _chunks(term_list, self.batch_size):
            prompt = _build_batch_prompt(batch)
            logger.debug(f"Ollama batch: {len(batch)} terms -> {[t['canonical_text'] for t in batch]}")
            try:
                url = f"{self.base_url}/api/generate"
                logger.debug(f"Ollama request POST {url}")
                response = httpx.post(
                    url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0},
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
                logger.debug(f"Ollama response status={response.status_code}")
                meanings = _parse_json_response(str(payload.get("response", "")))
                for term in batch:
                    canonical = term["canonical_text"]
                    meaning = str(meanings.get(canonical, "")).strip()
                    if not meaning:
                        logger.warning(f"Ollama missing explanation for '{canonical}'")
                    results[canonical] = ExplanationResult(
                        meaning=meaning or None,
                        error=None if meaning else "missing explanation",
                    )
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
                logger.error(f"Ollama request failed: {exc}")
                for term in batch:
                    results[term["canonical_text"]] = ExplanationResult(
                        meaning=None,
                        error=str(exc),
                    )
        return results


class OpenAIExplainer:
    """OpenAI 兼容接口释义客户端（如 OpenAI、Claude、本地 vLLM 等）。默认不启用。"""

    def __init__(
        self,
        base_url: str = OPENAI_BASE_URL,
        api_key: str = OPENAI_API_KEY,
        model: str = OPENAI_MODEL,
        timeout: float = OPENAI_TIMEOUT_SECONDS,
        batch_size: int = OPENAI_BATCH_SIZE,
    ) -> None:
        if not base_url:
            raise ValueError("OPENAI_BASE_URL is required when using OpenAI-compatible explainer")
        if not model:
            raise ValueError("OPENAI_MODEL is required when using OpenAI-compatible explainer")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.batch_size = batch_size
        logger.debug(f"OpenAIExplainer init: base_url={self.base_url}, model={self.model}")

    def explain_terms(self, terms: Iterable[dict[str, str]]) -> dict[str, ExplanationResult]:
        results: dict[str, ExplanationResult] = {}
        term_list = list(terms)
        logger.info(f"OpenAI: explaining {len(term_list)} terms in batches of {self.batch_size}")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        for batch in _chunks(term_list, self.batch_size):
            prompt = _build_batch_prompt(batch)
            logger.debug(f"OpenAI batch: {len(batch)} terms -> {[t['canonical_text'] for t in batch]}")
            try:
                url = f"{self.base_url}/v1/chat/completions"
                logger.debug(f"OpenAI request POST {url}")
                response = httpx.post(
                    url,
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                    },
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                logger.debug(f"OpenAI response status={response.status_code}")
                content = str(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
                meanings = _parse_json_response(content)
                for term in batch:
                    canonical = term["canonical_text"]
                    meaning = str(meanings.get(canonical, "")).strip()
                    if not meaning:
                        logger.warning(f"OpenAI missing explanation for '{canonical}'")
                    results[canonical] = ExplanationResult(
                        meaning=meaning or None,
                        error=None if meaning else "missing explanation",
                    )
            except (httpx.HTTPError, json.JSONDecodeError, ValueError, IndexError, KeyError) as exc:
                logger.error(f"OpenAI request failed: {exc}")
                for term in batch:
                    results[term["canonical_text"]] = ExplanationResult(
                        meaning=None,
                        error=str(exc),
                    )
        return results


def get_explainer() -> OllamaExplainer | OpenAIExplainer:
    """根据配置返回对应的释义客户端。"""
    logger.info(f"Explainer provider: {EXPLAINER_PROVIDER}")
    if EXPLAINER_PROVIDER == "openai":
        return OpenAIExplainer()
    return OllamaExplainer()


def _chunks(items: list[dict[str, str]], size: int) -> Iterable[list[dict[str, str]]]:
    chunk_size = max(1, size)
    for index in range(0, len(items), chunk_size):
        yield items[index : index + chunk_size]


def _build_batch_prompt(terms: list[dict[str, str]]) -> str:
    entries = [
        {
            "text": term["canonical_text"],
            "type": "短句" if term["type"] == "phrase" else "单词",
        }
        for term in terms
    ]
    return (
        "你是英语预习助手。请为下面英语学习项生成简洁中文解释，面向英文初学者。"
        "只返回一个 JSON 对象；键必须完全等于 text 字段；值是中文解释，"
        "不要 Markdown，不要编号，不要额外说明。\n"
        f"{json.dumps(entries, ensure_ascii=False)}"
    )


def _parse_json_response(response_text: str) -> dict[str, str]:
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("response is not a JSON object")
    return {str(key): str(value) for key, value in parsed.items()}
