import os
from typing import Dict, Optional
import logging
import time
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
    logger.info(f"[SCRAPER] Starting BeautifulSoup scraping for URL: {url}")
    request_start = time.time()

    try:
        # Set a User-Agent to prevent being blocked as a bot
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        logger.debug(f"[SCRAPER] Sending HTTP GET request to {url}")
        response = requests.get(url, headers=headers, timeout=30)
        request_time = time.time() - request_start
        logger.info(f"[SCRAPER] HTTP request completed in {request_time:.2f}s, status: {response.status_code}")
        response.raise_for_status()  # Raise an exception for bad HTTP status codes

        # Parse the HTML content using BeautifulSoup
        logger.debug(f"[SCRAPER] Parsing HTML content with BeautifulSoup")
        soup = BeautifulSoup(response.content, 'html.parser')
        parse_time = time.time() - request_start
        logger.debug(f"[SCRAPER] HTML parsing completed in {parse_time:.2f}s")

        # Extract the page title
        title = soup.title.string if soup.title else 'No Title Found'
        title = title.strip() if title else 'No Title Found'
        logger.info(f"[SCRAPER] Extracted page title: '{title}'")

        # Remove unnecessary tags like script and style for cleaner text
        logger.debug(f"[SCRAPER] Removing script and style tags")
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()

        # Try to find main content areas for better extraction
        content_selectors = [
            'main', 'article', '[role="main"]',
            '.content', '.post-content', '.entry-content',
            '#content', '#main'
        ]

        content_element = None
        logger.debug(f"[SCRAPER] Searching for main content element")
        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                logger.info(f"[SCRAPER] Found content element using selector: '{selector}'")
                break

        if not content_element:
            # Fallback to body if no main content found
            content_element = soup.find('body') or soup
            logger.info(f"[SCRAPER] Using fallback content element (body)")

        # Convert to markdown-like format
        logger.debug(f"[SCRAPER] Extracting content to markdown format")
        content = ""
        extraction_start = time.time()

        # Extract headings
        headings = content_element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        logger.debug(f"[SCRAPER] Found {len(headings)} headings")
        for heading in headings:
            level = int(heading.name[1])
            content += f"{'#' * level} {heading.get_text().strip()}\n\n"

        # Extract paragraphs
        paragraphs = content_element.find_all('p')
        logger.debug(f"[SCRAPER] Found {len(paragraphs)} paragraphs")
        for para in paragraphs:
            text = para.get_text().strip()
            if text:
                content += f"{text}\n\n"

        # Extract lists
        lists = content_element.find_all(['ul', 'ol'])
        logger.debug(f"[SCRAPER] Found {len(lists)} lists")
        for list_elem in lists:
            for li in list_elem.find_all('li'):
                text = li.get_text().strip()
                if text:
                    content += f"- {text}\n"
            content += "\n"

        # If no content was extracted, get all text
        if not content.strip():
            logger.warning(f"[SCRAPER] No structured content found, extracting all text")
            content = content_element.get_text(separator='\n', strip=True)

        # Clean up content
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = content.strip()

        extraction_time = time.time() - extraction_start
        total_time = time.time() - request_start

        if not content:
            content = f"Unable to extract content from {url}"
            logger.warning(f"[SCRAPER] {content}")

        logger.info(f"[SCRAPER] Content extraction completed in {extraction_time:.2f}s")
        logger.info(f"[SCRAPER] Successfully scraped '{title}'. Content length: {len(content)} characters. Total time: {total_time:.2f}s")

        return {
            "url": url,
            "title": title,
            "content": content
        }
    except requests.exceptions.RequestException as e:
        total_time = time.time() - request_start
        logger.error(f"[SCRAPER] HTTP request failed after {total_time:.2f}s: {type(e).__name__}: {str(e)}")
        raise
    except Exception as e:
        total_time = time.time() - request_start
        logger.error(f"[SCRAPER] Parsing error after {total_time:.2f}s: {type(e).__name__}: {str(e)}")
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