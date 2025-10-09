import subprocess
import os
from typing import Dict, Optional
from firecrawl import FirecrawlApp
import logging
from utils.retry import retry
import requests
from bs4 import BeautifulSoup
import re

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
        # Try the correct method name for current Firecrawl API
        result = app.scrape_url(
            url,
            params={'pageOptions': {'onlyMainContent': True}}
        )
        return {
            'content': result.get('markdown', ''),
            'title': result.get('metadata', {}).get('title', 'Untitled'),
            'url': url
        }
    except AttributeError as e:
        # If scrape_url doesn't exist, try alternative method
        if 'scrape_url' in str(e):
            logger.warning("scrape_url method not found, trying alternative...")
            try:
                result = app.sync_scrape_url(
                    url,
                    params={'pageOptions': {'onlyMainContent': True}}
                )
                return {
                    'content': result.get('markdown', ''),
                    'title': result.get('metadata', {}).get('title', 'Untitled'),
                    'url': url
                }
            except Exception as e2:
                logger.error(f"Alternative Firecrawl method failed: {str(e2)}")
                raise Exception(f"Firecrawl API method not available: {str(e2)}")
        else:
            raise
    except Exception as e:
        logger.error(f"Error scraping {url}: {str(e)}")
        raise

@retry(max_attempts=3, delay=2)
def scrape_url_with_requests(url: str) -> Dict[str, str]:
    """Simple fallback scraper using requests and BeautifulSoup"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Extract title
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else url.split('/')[-1]

        # Extract main content
        # Try to find main content areas
        content_selectors = [
            'main', 'article', '[role="main"]',
            '.content', '.post-content', '.entry-content',
            '#content', '#main'
        ]

        content_element = None
        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                break

        if not content_element:
            # Fallback to body if no main content found
            content_element = soup.find('body') or soup

        # Convert to markdown-like format
        content = ""

        # Extract headings
        for heading in content_element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            level = int(heading.name[1])
            content += f"{'#' * level} {heading.get_text().strip()}\n\n"

        # Extract paragraphs
        for para in content_element.find_all('p'):
            text = para.get_text().strip()
            if text:
                content += f"{text}\n\n"

        # Extract lists
        for list_elem in content_element.find_all(['ul', 'ol']):
            for li in list_elem.find_all('li'):
                text = li.get_text().strip()
                if text:
                    content += f"- {text}\n"
            content += "\n"

        # If no content was extracted, get all text
        if not content.strip():
            content = content_element.get_text()
            content = re.sub(r'\n\s*\n', '\n\n', content)

        # Clean up content
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = content.strip()

        if not content:
            content = f"Unable to extract content from {url}"

        return {
            'content': content,
            'title': title,
            'url': url
        }

    except Exception as e:
        logger.error(f"Error scraping {url} with requests: {str(e)}")
        raise

def scrape_url(url: str, method: Optional[str] = None) -> Dict[str, str]:
    """
    Scrape URL content using available method

    Args:
        url: URL to scrape
        method: 'bash', 'python', or 'auto'. If None, will try bash, then python, then requests

    Returns:
        Dictionary with content, title, and url
    """
    if method == 'bash':
        return scrape_url_with_bash(url)
    elif method == 'python':
        return scrape_url_with_python(url)
    elif method == 'requests':
        return scrape_url_with_requests(url)
    else:
        # Try bash first, then python, then requests as fallback
        try:
            return scrape_url_with_bash(url)
        except Exception as e:
            logger.warning(f"Bash method failed: {e}. Trying Python method...")
            try:
                return scrape_url_with_python(url)
            except Exception as e2:
                logger.warning(f"Python method failed: {e2}. Using requests fallback...")
                return scrape_url_with_requests(url)