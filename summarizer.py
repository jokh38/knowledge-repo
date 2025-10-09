import ollama
from typing import Dict
import logging
import os
from utils.retry import retry

logger = logging.getLogger(__name__)

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

        return {
            'summary': response['message']['content'],
            'model': 'Qwen3-Coder-30B'
        }
    except Exception as e:
        logger.error(f"Error summarizing content: {str(e)}")
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
        
        keywords_text = response['message']['content'].strip()
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
        
        category = response['message']['content'].strip()
        return category
    except Exception as e:
        logger.error(f"Error categorizing content: {str(e)}")
        return "Other"