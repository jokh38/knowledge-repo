import ollama
import requests
from typing import Dict
import logging
import os
import json
from utils.retry import retry

logger = logging.getLogger(__name__)

def _ollama_chat_via_request(prompt: str, model: str = 'Qwen3-Coder-30B', temperature: float = 0.3) -> str:
    """Fallback Ollama chat using direct HTTP request"""
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        api_url = f"{base_url}/v1/chat/completions"

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }

        response = requests.post(api_url, json=payload, timeout=60)
        response.raise_for_status()

        data = response.json()

        # Handle OpenAI-like format
        if 'choices' in data and data['choices']:
            return data['choices'][0]['message']['content']
        else:
            raise ValueError(f"Unexpected response format: {data}")

    except Exception as e:
        logger.error(f"Error in fallback Ollama request: {str(e)}")
        raise

@retry(max_attempts=3, delay=2)
def summarize_content(content: str, max_length: int = 4000) -> Dict[str, str]:
    """Summarize web content using local LLM"""

    # Truncate long content
    truncated = content[:max_length]

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

    try:
        # Get Ollama base URL from environment
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        # Configure ollama client with custom base URL
        client = ollama.Client(host=base_url)

        response = client.chat(
            model='Qwen3-Coder-30B',
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.3}  # Lower temperature for consistent summaries
        )

        # Handle different response formats
        content = None
        if hasattr(response, 'message') and response.message:
            content = response.message.content
        elif isinstance(response, dict):
            # Try OpenAI-like format first
            if 'choices' in response and response['choices']:
                content = response['choices'][0].get('message', {}).get('content')
            # Try original Ollama format
            elif 'message' in response and response['message']:
                content = response['message'].get('content')

        if not content:
            raise ValueError(f"Unable to extract content from response: {response}")

        return {
            'summary': content,
            'model': 'Qwen3-Coder-30B'
        }
    except Exception as e:
        logger.warning(f"Ollama client failed: {e}. Using fallback HTTP request...")
        # Use fallback HTTP request method
        try:
            content = _ollama_chat_via_request(prompt, 'Qwen3-Coder-30B', 0.3)
            return {
                'summary': content,
                'model': 'Qwen3-Coder-30B'
            }
        except Exception as fallback_error:
            logger.error(f"Both Ollama client and fallback failed: {str(fallback_error)}")
            raise

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
    
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        # Configure ollama client with custom base URL
        client = ollama.Client(host=base_url)

        response = client.chat(
            model='Qwen3-Coder-30B',
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.2}
        )

        # Handle different response formats
        content = None
        if hasattr(response, 'message') and response.message:
            content = response.message.content
        elif isinstance(response, dict):
            # Try OpenAI-like format first
            if 'choices' in response and response['choices']:
                content = response['choices'][0].get('message', {}).get('content')
            # Try original Ollama format
            elif 'message' in response and response['message']:
                content = response['message'].get('content')

        if not content:
            logger.error(f"Unable to extract content from response: {response}")
            return []

        keywords_text = content.strip()
        keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]

        return keywords[:max_keywords]
    except Exception as e:
        logger.error(f"Error extracting keywords: {str(e)}")
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
    
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        # Configure ollama client with custom base URL
        client = ollama.Client(host=base_url)

        response = client.chat(
            model='Qwen3-Coder-30B',
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.1}
        )

        # Handle different response formats
        content = None
        if hasattr(response, 'message') and response.message:
            content = response.message.content
        elif isinstance(response, dict):
            # Try OpenAI-like format first
            if 'choices' in response and response['choices']:
                content = response['choices'][0].get('message', {}).get('content')
            # Try original Ollama format
            elif 'message' in response and response['message']:
                content = response['message'].get('content')

        if not content:
            logger.error(f"Unable to extract content from response: {response}")
            return "Other"

        category = content.strip()
        return category
    except Exception as e:
        logger.error(f"Error categorizing content: {str(e)}")
        return "Other"