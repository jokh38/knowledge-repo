import ollama
import requests
from typing import Dict
import logging
import os
import time
from src.retry import retry
from src.llm_utils import make_llm_request, make_ollama_client_request

logger = logging.getLogger(__name__)


def _get_model_config(base_url: str) -> tuple:
    """Get appropriate model configuration based on server type"""
    if base_url.endswith(":8080"):
        # llama.cpp server
        return 'Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf', 'Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf'
    else:
        # Standard Ollama server
        return 'Qwen3-Coder-30B', 'Qwen3-Coder-30B'

@retry(max_attempts=3, delay=2)
def summarize_content(content: str, max_length: int = 4000) -> Dict[str, str]:
    """Summarize web content using local LLM"""
    summarize_start = time.time()
    logger.info(f"[SUMMARIZER] Starting content summarization")
    logger.info(f"[SUMMARIZER] Original content length: {len(content)} characters")

    # Truncate long content
    truncated = content[:max_length]
    logger.info(f"[SUMMARIZER] Truncated content length: {len(truncated)} characters")

    prompt = f"""다음 웹 콘텐츠를 분석하여:
1. 핵심 내용을 3-5개 불렛 포인트로 요약
2. 주요 키워드 3-5개 추출
3. 콘텐츠 카테고리 제안 (예: Technology, Business, Health 등)

콘텐츠:
{truncated}

응답 형식:
## 요약
- [불렛 포인트]

## 키워드
[키워드1, 키워드2, ...]

## 카테고리
[카테고리]
"""
    logger.info(f"[SUMMARIZER] Generated prompt length: {len(prompt)} characters")

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    logger.info(f"[SUMMARIZER] Using LLM server at: {base_url}")

    model_name, model_display_name = _get_model_config(base_url)
    logger.info(f"[SUMMARIZER] Using model: {model_display_name}")

    try:
        # Try HTTP request first (better compatibility with llama.cpp)
        logger.info(f"[SUMMARIZER] Attempting HTTP request method")
        request_start = time.time()
        content = make_llm_request(prompt, model_name, base_url, temperature=0.3)
        request_time = time.time() - request_start
        total_time = time.time() - summarize_start
        logger.info(f"[SUMMARIZER] HTTP request successful in {request_time:.2f}s, got {len(content)} characters")
        logger.info(f"[SUMMARIZER] Summarization completed in {total_time:.2f}s")
        return {
            'summary': content,
            'model': model_display_name
        }

    except Exception as http_error:
        logger.warning(f"[SUMMARIZER] HTTP request method failed: {http_error}. Trying Ollama client...")
        logger.debug(f"[SUMMARIZER] HTTP error details: {type(http_error).__name__}: {str(http_error)}")

        # Try Ollama client as fallback
        try:
            logger.info(f"[SUMMARIZER] Attempting Ollama client method")
            request_start = time.time()
            content = make_ollama_client_request(prompt, model_name, base_url, temperature=0.3)
            request_time = time.time() - request_start
            total_time = time.time() - summarize_start
            logger.info(f"[SUMMARIZER] Ollama client successful in {request_time:.2f}s, got {len(content)} characters")
            logger.info(f"[SUMMARIZER] Summarization completed in {total_time:.2f}s")
            return {
                'summary': content,
                'model': model_display_name
            }

        except Exception as client_error:
            total_time = time.time() - summarize_start
            logger.error(f"[SUMMARIZER] Both HTTP and Ollama client methods failed after {total_time:.2f}s")
            logger.error(f"[SUMMARIZER] HTTP error: {type(http_error).__name__}: {str(http_error)}")
            logger.error(f"[SUMMARIZER] Client error: {type(client_error).__name__}: {str(client_error)}")
            raise Exception(f"All summarization methods failed. HTTP: {str(http_error)}; Client: {str(client_error)}")

@retry(max_attempts=2, delay=1)
def extract_keywords(content: str, max_keywords: int = 5) -> list:
    """Extract keywords from content using LLM"""

    truncated = content[:2000]  # Shorter for keyword extraction

    prompt = f"""다음 콘텐츠에서 가장 중요한 키워드 {max_keywords}개를 추출하세요.
콤마로 구분하여 응답하세요.

콘텐츠:
{truncated}

키워드:
"""

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name, _ = _get_model_config(base_url)

    try:
        # Try HTTP request first
        keywords_text = make_llm_request(prompt, model_name, base_url, temperature=0.2, timeout=30)
        keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
        return keywords[:max_keywords]

    except Exception as http_error:
        logger.warning(f"HTTP request failed for keyword extraction: {http_error}. Trying Ollama client...")

        try:
            # Try Ollama client as fallback
            keywords_text = make_ollama_client_request(prompt, model_name, base_url, temperature=0.2)
            keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
            return keywords[:max_keywords]

        except Exception as client_error:
            logger.error(f"Both methods failed for keyword extraction. HTTP: {http_error}; Client: {client_error}")
            return []

@retry(max_attempts=2, delay=1)
def categorize_content(content: str) -> str:
    """Categorize content using LLM"""

    truncated = content[:2000]

    prompt = f"""다음 콘텐츠의 카테고리를 하나만 선택하세요:
Technology, Business, Science, Health, Education, Entertainment, Politics, Sports, Other

콘텐츠:
{truncated}

카테고리:
"""

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name, _ = _get_model_config(base_url)

    try:
        # Try HTTP request first
        category = make_llm_request(prompt, model_name, base_url, temperature=0.1, timeout=30)
        return category.strip()

    except Exception as http_error:
        logger.warning(f"HTTP request failed for categorization: {http_error}. Trying Ollama client...")

        try:
            # Try Ollama client as fallback
            category = make_ollama_client_request(prompt, model_name, base_url, temperature=0.1)
            return category.strip()

        except Exception as client_error:
            logger.error(f"Both methods failed for categorization. HTTP: {http_error}; Client: {client_error}")
            return "Other"