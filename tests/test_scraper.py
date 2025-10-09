import pytest
import os
from unittest.mock import patch, MagicMock
from src import scraper

class TestScraper:
    """Test cases for scraper module"""

    @patch('src.scraper.requests.get')
    def test_scrape_with_beautifulsoup_success(self, mock_get):
        """Test successful BeautifulSoup scraping"""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = '''
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Main Title</h1>
                <p>This is a test paragraph.</p>
                <p>Another paragraph with content.</p>
                <ul>
                    <li>List item 1</li>
                    <li>List item 2</li>
                </ul>
            </body>
        </html>
        '''
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = scraper.scrape_with_beautifulsoup("https://example.com")

        assert result['content'] != ""
        assert result['title'] == "Test Page"
        assert result['url'] == "https://example.com"
        assert "# Main Title" in result['content']
        assert "This is a test paragraph." in result['content']
        assert "- List item 1" in result['content']

    @patch('src.scraper.requests.get')
    def test_scrape_with_beautifulsoup_http_error(self, mock_get):
        """Test BeautifulSoup scraping with HTTP error"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as exc_info:
            scraper.scrape_with_beautifulsoup("https://example.com")

        assert "HTTP 404 Not Found" in str(exc_info.value)

    @patch('src.scraper.requests.get')
    def test_scrape_with_beautifulsoup_no_title(self, mock_get):
        """Test BeautifulSoup scraping with no title"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = '<html><body><p>No title here</p></body></html>'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = scraper.scrape_with_beautifulsoup("https://example.com")

        assert result['title'] == "No Title Found"
        assert result['url'] == "https://example.com"
        assert "No title here" in result['content']

    @patch('src.scraper.scrape_with_beautifulsoup')
    def test_scrape_url_function(self, mock_beautifulsoup):
        """Test main scrape_url function"""
        mock_beautifulsoup.return_value = {
            'content': 'Test content',
            'title': 'Test Title',
            'url': 'https://example.com'
        }

        # Test with method parameter (should be ignored)
        result = scraper.scrape_url("https://example.com", method="bash")

        assert result['content'] == "Test content"
        assert result['title'] == "Test Title"
        assert result['url'] == "https://example.com"
        mock_beautifulsoup.assert_called_once_with("https://example.com")

        # Test without method parameter
        result2 = scraper.scrape_url("https://example.com")

        assert result2['content'] == "Test content"
        assert mock_beautifulsoup.call_count == 2