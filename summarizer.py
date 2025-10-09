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
            choice = data['choices'][0]
            if 'message' in choice and 'content' in choice['message']:
                return choice['message']['content']
            elif 'text' in choice:  # Alternative format
                return choice['text']

        # Handle llama.cpp specific format
        if 'content' in data:
            return data['content']

        # Try to extract content from response text directly
        if 'response' in data:
            return data['response']

        logger.error(f"Response format: {data}")
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
        # Use direct HTTP request for llama.cpp server compatibility
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        # Check if this is a llama.cpp server (OpenAI-compatible)
        if base_url.endswith(":8080"):
            content = _ollama_chat_via_request(prompt, 'Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf', 0.3)
            return {
                'summary': content,
                'model': 'Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf'
            }
        else:
            # Try Ollama client for native Ollama servers
            client = ollama.Client(host=base_url)
            response = client.chat(
                model='Qwen3-Coder-30B',
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.3}
            )

            # Handle different response formats
            content = None
            if hasattr(response, 'message') and response.message:
                content = response.message.content
            elif isinstance(response, dict):
                # Try OpenAI-like format first
                if 'choices' in response and response['choices']:
                    choice = response['choices'][0]
                    if 'message' in choice:
                        content = choice['message'].get('content')
                    elif 'text' in choice:
                        content = choice['text']
                # Try original Ollama format
                elif 'message' in response and response['message']:
                    content = response['message'].get('content')
                # Try llama.cpp format
                elif 'content' in response:
                    content = response['content']
                elif 'response' in response:
                    content = response['response']

            if not content:
                logger.error(f"Response format: {response}")
                raise ValueError(f"Unable to extract content from response: {response}")

            return {
                'summary': content,
                'model': 'Qwen3-Coder-30B'
            }
    except Exception as e:
        logger.warning(f"Direct LLM call failed: {e}. Using fallback HTTP request...")
        # Use fallback HTTP request method
        try:
            content = _ollama_chat_via_request(prompt, 'Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf', 0.3)
            return {
                'summary': content,
                'model': 'Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf'
            }
        except Exception as fallback_error:
            logger.error(f"Both primary and fallback failed: {str(fallback_error)}")
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

        # Check if this is a llama.cpp server (OpenAI-compatible)
        if base_url.endswith(":8080"):
            keywords_text = _ollama_chat_via_request(prompt, 'Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf', 0.2)
            keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
            return keywords[:max_keywords]
        else:
            # Try Ollama client for native Ollama servers
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

        # Check if this is a llama.cpp server (OpenAI-compatible)
        if base_url.endswith(":8080"):
            category = _ollama_chat_via_request(prompt, 'Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf', 0.1)
            return category.strip()
        else:
            # Try Ollama client for native Ollama servers
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