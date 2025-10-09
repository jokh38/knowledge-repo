import subprocess
import os
from typing import Dict, Optional
from firecrawl import FirecrawlApp
import logging
from utils.retry import retry

logger = logging.getLogger(__name__)

@retry(max_attempts=3, delay=2)
def scrape_url_with_bash(url: str) -> Dict[str, str]:
    """Uses existing firecrawl bash script"""
    script_path = os.getenv("FIRECRAWL_SCRIPT_PATH")
    if not script_path or not os.path.exists(script_path):
        raise ValueError(f"Firecrawl script not found at: {script_path}")
    
    try:
        result = subprocess.run(
            [script_path, url],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            raise Exception(f"Firecrawl failed: {result.stderr}")

        # Extract title from content or use URL as fallback
        content = result.stdout
        title = url.split('/')[-1] if not content else "Untitled"
        
        return {
            'content': content,
            'title': title,
            'url': url
        }
    except subprocess.TimeoutExpired:
        raise Exception(f"Timeout while scraping {url}")
    except Exception as e:
        logger.error(f"Error scraping {url}: {str(e)}")
        raise

@retry(max_attempts=3, delay=2)
def scrape_url_with_python(url: str) -> Dict[str, str]:
    """Use Python Firecrawl library"""
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY environment variable not set")
    
    try:
        app = FirecrawlApp(api_key=api_key)
        result = app.scrape_url(
            url,
            {'pageOptions': {'onlyMainContent': True}}
        )
        return {
            'content': result.get('markdown', ''),
            'title': result.get('metadata', {}).get('title', 'Untitled'),
            'url': url
        }
    except Exception as e:
        logger.error(f"Error scraping {url}: {str(e)}")
        raise

def scrape_url(url: str, method: Optional[str] = None) -> Dict[str, str]:
    """
    Scrape URL content using available method
    
    Args:
        url: URL to scrape
        method: 'bash' or 'python'. If None, will try bash first, then python
    
    Returns:
        Dictionary with content, title, and url
    """
    if method == 'bash':
        return scrape_url_with_bash(url)
    elif method == 'python':
        return scrape_url_with_python(url)
    else:
        # Try bash first, then python
        try:
            return scrape_url_with_bash(url)
        except Exception as e:
            logger.warning(f"Bash method failed: {e}. Trying Python method...")
            return scrape_url_with_python(url)