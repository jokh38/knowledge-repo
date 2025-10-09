import os
from typing import Dict, Optional
import logging
from src.retry import retry
import requests
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

@retry(max_attempts=3, delay=2)
def scrape_with_beautifulsoup(url: str) -> Dict[str, str]:
    """
    Scrapes a web page using the requests and BeautifulSoup libraries.
    This is the main scraping method replacing Firecrawl dependency.
    """
    try:
        # Set a User-Agent to prevent being blocked as a bot
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()  # Raise an exception for bad HTTP status codes

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract the page title
        title = soup.title.string if soup.title else 'No Title Found'
        title = title.strip() if title else 'No Title Found'

        # Remove unnecessary tags like script and style for cleaner text
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()

        # Try to find main content areas for better extraction
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
            content = content_element.get_text(separator='\n', strip=True)

        # Clean up content
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = content.strip()

        if not content:
            content = f"Unable to extract content from {url}"

        logger.info(f"Successfully scraped '{title}'. Content length: {len(content)} characters.")

        return {
            "url": url,
            "title": title,
            "content": content
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during request to URL: {url}, Error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error parsing with BeautifulSoup: {e}")
        raise



def scrape_url(url: str, method: Optional[str] = None) -> Dict[str, str]:
    """
    Scrape URL content using BeautifulSoup

    This function now defaults to using BeautifulSoup and has replaced all Firecrawl dependencies.

    Args:
        url: URL to scrape
        method: Parameter kept for backward compatibility, but always uses BeautifulSoup

    Returns:
        Dictionary with content, title, and url
    """
    logger.debug(f"[DEBUG] Starting URL scraping with BeautifulSoup")
    logger.debug(f"[DEBUG] URL: {url}")
    logger.debug(f"[DEBUG] Method parameter (ignored): {method}")

    logger.info(f"Starting scrape with BeautifulSoup for URL: {url}")
    return scrape_with_beautifulsoup(url)