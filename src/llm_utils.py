"""
Utility functions for LLM response parsing and API calls
Reduces code duplication and improves maintainability
"""
import requests
import ollama
import json
import logging
import time
from typing import Dict, Optional, List
from requests.exceptions import ConnectionError, Timeout, HTTPError

logger = logging.getLogger(__name__)

def extract_content_from_response(data: Dict) -> Optional[str]:
    """
    Extract content from various LLM response formats

    Args:
        data: Response data from LLM API

    Returns:
        Extracted content string or None if not found
    """
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
    return None

def handle_ollama_response(response) -> Optional[str]:
    """
    Handle response from Ollama client (both object and dict formats)

    Args:
        response: Response from ollama client

    Returns:
        Extracted content or None if not found
    """
    logger.debug(f"[DEBUG] Processing Ollama client response")
    logger.debug(f"[DEBUG] Response type: {type(response)}")
    logger.debug(f"[DEBUG] Response attributes: {dir(response)}")

    content = None

    # Handle object response
    if hasattr(response, 'message') and response.message:
        logger.debug(f"[DEBUG] Found response.message attribute")
        logger.debug(f"[DEBUG] Message type: {type(response.message)}")
        if hasattr(response.message, 'content'):
            content = response.message.content
            logger.debug(f"[DEBUG] Extracted content from response.message.content: {len(content) if content else 0} chars")

    # Handle dictionary response
    elif isinstance(response, dict):
        logger.debug(f"[DEBUG] Response is a dict with keys: {list(response.keys())}")
        content = extract_content_from_response(response)

    if not content:
        logger.error(f"[DEBUG] Unable to extract content from response")
        logger.error(f"[DEBUG] Full response: {response}")
        logger.error(f"[DEBUG] Response type: {type(response)}")
        if isinstance(response, dict):
            logger.error(f"[DEBUG] Response keys: {list(response.keys())}")

    return content

def make_llm_request(prompt: str, model: str, base_url: str, temperature: float = 0.3, timeout: int = 60) -> str:
    """
    Make LLM request with automatic fallback between different API formats

    Args:
        prompt: The prompt to send to LLM
        model: Model name
        base_url: Base URL for LLM API
        temperature: Sampling temperature
        timeout: Request timeout in seconds

    Returns:
        LLM response content

    Raises:
        Various exceptions based on error type
    """
    request_start = time.time()
    logger.info(f"[LLM] Starting request to {base_url} with model {model}")
    logger.debug(f"[LLM] Prompt length: {len(prompt)} characters")

    # Test connectivity first
    logger.debug(f"[LLM] Testing connectivity to {base_url}")
    try:
        health_url = f"{base_url}/health" if base_url.endswith(":8080") else f"{base_url}/api/tags"
        test_response = requests.get(health_url, timeout=5)
        logger.debug(f"[LLM] Connectivity test successful: {test_response.status_code}")
    except Exception as connectivity_error:
        logger.warning(f"[LLM] Connectivity test failed: {type(connectivity_error).__name__}: {str(connectivity_error)}")
        if "connection" in str(connectivity_error).lower() or "timeout" in str(connectivity_error).lower():
            logger.error(f"[LLM] Network connection error detected: {connectivity_error}")

    # Try OpenAI-compatible endpoint first
    api_url = f"{base_url}/v1/chat/completions"
    logger.info(f"[LLM] Trying OpenAI-compatible endpoint: {api_url}")

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature
    }
    logger.debug(f"[LLM] Request payload size: {len(json.dumps(payload))} bytes")

    try:
        logger.debug(f"[LLM] Sending HTTP POST request (timeout: {timeout}s)")
        response = requests.post(api_url, json=payload, timeout=timeout)
        request_duration = time.time() - request_start
        logger.info(f"[LLM] Request completed in {request_duration:.2f}s with status {response.status_code}")
        logger.debug(f"[LLM] Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            content = extract_content_from_response(data)
            if content:
                return content

        # If OpenAI endpoint fails, try native Ollama endpoint
        logger.warning(f"OpenAI endpoint failed: {response.status_code}, trying native Ollama endpoint...")
        logger.debug(f"[DEBUG] OpenAI endpoint response text: {response.text[:500]}...")

    except (ConnectionError, Timeout, HTTPError) as e:
        logger.warning(f"OpenAI-compatible endpoint failed: {type(e).__name__}: {str(e)}")
        request_duration = time.time() - request_start
        logger.debug(f"[LLM] Request failed after {request_duration:.2f}s")

    # Try native Ollama endpoint
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

    try:
        response = requests.post(api_url, json=payload, timeout=timeout)
        logger.debug(f"[DEBUG] Native Ollama response status: {response.status_code}")
        logger.debug(f"[DEBUG] Native Ollama response headers: {dict(response.headers)}")

        response.raise_for_status()
        data = response.json()
        content = extract_content_from_response(data)
        if content:
            return content

    except (ConnectionError, Timeout, HTTPError) as e:
        logger.error(f"Native Ollama endpoint failed: {type(e).__name__}: {str(e)}")

    raise ValueError(f"Could not extract content from any LLM endpoint")

def make_ollama_client_request(prompt: str, model: str, base_url: str, temperature: float = 0.3) -> str:
    """
    Make request using Ollama Python client

    Args:
        prompt: The prompt to send to LLM
        model: Model name
        base_url: Base URL for Ollama server
        temperature: Sampling temperature

    Returns:
        LLM response content

    Raises:
        Various exceptions based on error type
    """
    try:
        logger.debug(f"[LLM] Initializing Ollama client")
        client = ollama.Client(host=base_url)
        logger.debug(f"[LLM] Sending chat request via Ollama client")

        response = client.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': temperature}
        )

        content = handle_ollama_response(response)
        if content:
            logger.debug(f"[LLM] Successfully extracted content: {len(content)} characters")
            return content
        else:
            raise ValueError("Unable to extract content from Ollama client response")

    except Exception as e:
        logger.error(f"Ollama client failed: {str(e)}")
        logger.debug(f"[DEBUG] Ollama client error details: {type(e).__name__}: {str(e)}")
        raise