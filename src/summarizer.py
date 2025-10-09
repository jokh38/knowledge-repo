import ollama
import requests
from typing import Dict
import logging
import os
import json
import time
from src.retry import retry

logger = logging.getLogger(__name__)

def _ollama_chat_via_request(prompt: str, model: str = 'Qwen3-Coder-30B', temperature: float = 0.3) -> str:
    """Fallback Ollama chat using direct HTTP request"""
    request_start = time.time()
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        logger.info(f"[SUMMARIZER] Starting LLM request to {base_url} with model {model}")
        logger.debug(f"[SUMMARIZER] Prompt length: {len(prompt)} characters")

        # Test connectivity first
        logger.debug(f"[SUMMARIZER] Testing connectivity to {base_url}")
        try:
            test_response = requests.get(f"{base_url}/health", timeout=5) if base_url.endswith(":8080") else requests.get(f"{base_url}/api/tags", timeout=5)
            logger.debug(f"[SUMMARIZER] Connectivity test successful: {test_response.status_code}")
        except Exception as connectivity_error:
            logger.warning(f"[SUMMARIZER] Connectivity test failed: {type(connectivity_error).__name__}: {str(connectivity_error)}")
            if "connection" in str(connectivity_error).lower() or "timeout" in str(connectivity_error).lower():
                logger.error(f"[SUMMARIZER] Network connection error detected: {connectivity_error}")

        # Try OpenAI-compatible endpoint first
        api_url = f"{base_url}/v1/chat/completions"
        logger.info(f"[SUMMARIZER] Trying OpenAI-compatible endpoint: {api_url}")

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }
        logger.debug(f"[SUMMARIZER] Request payload size: {len(json.dumps(payload))} bytes")

        logger.debug(f"[SUMMARIZER] Sending HTTP POST request (timeout: 60s)")
        response = requests.post(api_url, json=payload, timeout=60)
        request_duration = time.time() - request_start
        logger.info(f"[SUMMARIZER] Request completed in {request_duration:.2f}s with status {response.status_code}")
        logger.debug(f"[SUMMARIZER] Response headers: {dict(response.headers)}")

        # If OpenAI endpoint fails, try native Ollama endpoint
        if response.status_code != 200:
            logger.warning(f"OpenAI endpoint failed: {response.status_code}, trying native Ollama endpoint...")
            logger.debug(f"[DEBUG] OpenAI endpoint response text: {response.text[:500]}...")

            api_url = f"{base_url}/api/chat"
            logger.debug(f"[DEBUG] Trying native Ollama endpoint: {api_url}")
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            logger.debug(f"[DEBUG] Native Ollama payload: {payload}")

            response = requests.post(api_url, json=payload, timeout=60)
            logger.debug(f"[DEBUG] Native Ollama response status: {response.status_code}")
            logger.debug(f"[DEBUG] Native Ollama response headers: {dict(response.headers)}")

        response.raise_for_status()
        data = response.json()
        logger.debug(f"[DEBUG] Response data structure: {type(data)}")
        logger.debug(f"[DEBUG] Response data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        logger.debug(f"[DEBUG] Full response data: {data}")

        # Handle OpenAI-like format
        if 'choices' in data and data['choices']:
            logger.debug(f"[DEBUG] Found 'choices' field with {len(data['choices'])} items")
            choice = data['choices'][0]
            logger.debug(f"[DEBUG] First choice keys: {list(choice.keys()) if isinstance(choice, dict) else 'Not a dict'}")

            if 'message' in choice and 'content' in choice['message']:
                content = choice['message']['content']
                logger.debug(f"[DEBUG] Extracted content from choice.message.content: {len(content)} chars")
                return content
            elif 'text' in choice:  # Alternative format
                content = choice['text']
                logger.debug(f"[DEBUG] Extracted content from choice.text: {len(content)} chars")
                return content

        # Handle native Ollama format
        if 'message' in data and data['message']:
            logger.debug(f"[DEBUG] Found 'message' field in response")
            if 'content' in data['message']:
                content = data['message']['content']
                logger.debug(f"[DEBUG] Extracted content from message.content: {len(content)} chars")
                return content

        # Handle llama.cpp specific format
        if 'content' in data:
            content = data['content']
            logger.debug(f"[DEBUG] Extracted content from root content field: {len(content)} chars")
            return content

        # Try to extract content from response text directly
        if 'response' in data:
            content = data['response']
            logger.debug(f"[DEBUG] Extracted content from response field: {len(content)} chars")
            return content

        logger.error(f"[DEBUG] Could not extract content from response. Available fields: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        logger.error(f"[DEBUG] Full response data: {data}")
        raise ValueError(f"Unexpected response format: {data}")

    except Exception as e:
        request_duration = time.time() - request_start
        logger.error(f"[SUMMARIZER] Request failed after {request_duration:.2f}s: {type(e).__name__}: {str(e)}")

        # Detailed network error analysis
        if isinstance(e, requests.exceptions.ConnectionError):
            logger.error(f"[SUMMARIZER] Connection error - server may be down or network unreachable")
        elif isinstance(e, requests.exceptions.Timeout):
            logger.error(f"[SUMMARIZER] Timeout error - server took too long to respond")
        elif isinstance(e, requests.exceptions.HTTPError):
            logger.error(f"[SUMMARIZER] HTTP error - server returned error status")
        elif "connection" in str(e).lower() or "network" in str(e).lower():
            logger.error(f"[SUMMARIZER] Network-related error detected: {e}")
        elif "timeout" in str(e).lower():
            logger.error(f"[SUMMARIZER] Timeout-related error detected: {e}")

        logger.error(f"[SUMMARIZER] Full error details: {repr(e)}")
        raise

@retry(max_attempts=3, delay=2)
def summarize_content(content: str, max_length: int = 4000) -> Dict[str, str]:
    """Summarize web content using local LLM"""
    logger.debug(f"[DEBUG] Starting content summarization")
    logger.debug(f"[DEBUG] Original content length: {len(content)} characters")

    # Truncate long content
    truncated = content[:max_length]
    logger.debug(f"[DEBUG] Truncated content length: {len(truncated)} characters")

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
    logger.debug(f"[DEBUG] Generated prompt length: {len(prompt)} characters")

    try:
        # Use direct HTTP request for llama.cpp server compatibility
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        logger.debug(f"[DEBUG] Using base URL: {base_url}")

        # Check if this is a llama.cpp server (OpenAI-compatible)
        if base_url.endswith(":8080"):
            logger.debug(f"[DEBUG] Detected llama.cpp server, using specific model")
            content = _ollama_chat_via_request(prompt, 'Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf', 0.3)
            return {
                'summary': content,
                'model': 'Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf'
            }
        else:
            logger.debug(f"[DEBUG] Using standard Ollama server")
            # Try fallback HTTP request method first to avoid Ollama client issues
            try:
                logger.debug(f"[DEBUG] Trying HTTP fallback method first")
                content = _ollama_chat_via_request(prompt, 'Qwen3-Coder-30B', 0.3)
                logger.debug(f"[DEBUG] HTTP fallback successful, got {len(content)} characters")
                return {
                    'summary': content,
                    'model': 'Qwen3-Coder-30B'
                }
            except Exception as fallback_error:
                logger.warning(f"Fallback HTTP request failed: {fallback_error}. Trying Ollama client...")
                logger.debug(f"[DEBUG] Fallback error details: {type(fallback_error).__name__}: {str(fallback_error)}")

                # Try Ollama client as last resort
                try:
                    logger.debug(f"[DEBUG] Initializing Ollama client")
                    client = ollama.Client(host=base_url)
                    logger.debug(f"[DEBUG] Sending chat request via Ollama client")

                    response = client.chat(
                        model='Qwen3-Coder-30B',
                        messages=[{'role': 'user', 'content': prompt}],
                        options={'temperature': 0.3}
                    )
                    logger.debug(f"[DEBUG] Ollama client response received")
                    logger.debug(f"[DEBUG] Response type: {type(response)}")
                    logger.debug(f"[DEBUG] Response attributes: {dir(response)}")

                    # Handle different response formats
                    content = None
                    if hasattr(response, 'message') and response.message:
                        logger.debug(f"[DEBUG] Found response.message attribute")
                        logger.debug(f"[DEBUG] Message type: {type(response.message)}")
                        if hasattr(response.message, 'content'):
                            content = response.message.content
                            logger.debug(f"[DEBUG] Extracted content from response.message.content: {len(content)} chars")
                    elif isinstance(response, dict):
                        logger.debug(f"[DEBUG] Response is a dict with keys: {list(response.keys())}")
                        # Try OpenAI-like format first
                        if 'choices' in response and response['choices']:
                            logger.debug(f"[DEBUG] Found 'choices' field with {len(response['choices'])} items")
                            choice = response['choices'][0]
                            logger.debug(f"[DEBUG] First choice keys: {list(choice.keys()) if isinstance(choice, dict) else 'Not a dict'}")
                            if 'message' in choice:
                                content = choice['message'].get('content')
                                logger.debug(f"[DEBUG] Extracted content from choice.message.content: {len(content) if content else 0} chars")
                            elif 'text' in choice:
                                content = choice['text']
                                logger.debug(f"[DEBUG] Extracted content from choice.text: {len(content) if content else 0} chars")
                        # Try original Ollama format
                        elif 'message' in response and response['message']:
                            logger.debug(f"[DEBUG] Found 'message' field in response dict")
                            content = response['message'].get('content')
                            logger.debug(f"[DEBUG] Extracted content from message.content: {len(content) if content else 0} chars")
                        # Try llama.cpp format
                        elif 'content' in response:
                            content = response['content']
                            logger.debug(f"[DEBUG] Extracted content from root content field: {len(content) if content else 0} chars")
                        elif 'response' in response:
                            content = response['response']
                            logger.debug(f"[DEBUG] Extracted content from response field: {len(content) if content else 0} chars")

                    if not content:
                        logger.error(f"[DEBUG] Unable to extract content from response")
                        logger.error(f"[DEBUG] Full response: {response}")
                        logger.error(f"[DEBUG] Response type: {type(response)}")
                        if isinstance(response, dict):
                            logger.error(f"[DEBUG] Response keys: {list(response.keys())}")
                        raise ValueError(f"Unable to extract content from response: {response}")

                    logger.debug(f"[DEBUG] Successfully extracted content: {len(content)} characters")
                    return {
                        'summary': content,
                        'model': 'Qwen3-Coder-30B'
                    }
                except Exception as ollama_error:
                    logger.error(f"Ollama client failed: {str(ollama_error)}")
                    logger.debug(f"[DEBUG] Ollama client error details: {type(ollama_error).__name__}: {str(ollama_error)}")
                    raise Exception(f"Both HTTP fallback and Ollama client failed: {str(fallback_error)}; {str(ollama_error)}")
    except Exception as e:
        logger.error(f"[DEBUG] All summarization methods failed: {str(e)}")
        logger.error(f"[DEBUG] Final error details: {type(e).__name__}: {str(e)}")
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