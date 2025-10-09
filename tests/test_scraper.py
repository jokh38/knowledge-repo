import pytest
import os
from unittest.mock import patch, MagicMock
import scraper

class TestScraper:
    """Test cases for scraper module"""
    
    def test_scrape_url_with_bash_success(self):
        """Test successful bash scraping"""
        with patch('subprocess.run') as mock_run:
            with patch('os.path.exists', return_value=True):
                # Mock successful subprocess result
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "Test content"
                mock_run.return_value = mock_result

                with patch.dict(os.environ, {'FIRECRAWL_SCRIPT_PATH': '/path/to/script'}):
                    result = scraper.scrape_url_with_bash("https://example.com")

                    assert result['content'] == "Test content"
                    assert result['url'] == "https://example.com"
                    assert 'title' in result
    
    def test_scrape_url_with_bash_failure(self):
        """Test bash scraping failure"""
        with patch('subprocess.run') as mock_run:
            # Mock failed subprocess result
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Script failed"
            mock_run.return_value = mock_result
            
            with patch.dict(os.environ, {'FIRECRAWL_SCRIPT_PATH': '/path/to/script'}):
                with pytest.raises(Exception):
                    scraper.scrape_url_with_bash("https://example.com")
    
    def test_scrape_url_with_bash_no_script(self):
        """Test bash scraping with no script path"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                scraper.scrape_url_with_bash("https://example.com")
    
    def test_scrape_url_with_python_success(self):
        """Test successful Python scraping"""
        with patch('scraper.FirecrawlApp') as mock_app:
            # Mock FirecrawlApp
            mock_instance = MagicMock()
            mock_app.return_value = mock_instance
            mock_instance.scrape_url.return_value = {
                'markdown': 'Test content',
                'metadata': {'title': 'Test Title'}
            }
            
            with patch.dict(os.environ, {'FIRECRAWL_API_KEY': 'test_key'}):
                result = scraper.scrape_url_with_python("https://example.com")
                
                assert result['content'] == "Test content"
                assert result['title'] == "Test Title"
                assert result['url'] == "https://example.com"
    
    def test_scrape_url_with_python_no_api_key(self):
        """Test Python scraping with no API key"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                scraper.scrape_url_with_python("https://example.com")
    
    @patch('scraper.scrape_url_with_bash')
    @patch('scraper.scrape_url_with_python')
    def test_scrape_url_auto_fallback(self, mock_python, mock_bash):
        """Test auto method fallback from bash to python"""
        # Mock bash failure
        mock_bash.side_effect = Exception("Bash failed")
        # Mock python success
        mock_python.return_value = {
            'content': 'Python content',
            'title': 'Python Title',
            'url': 'https://example.com'
        }
        
        result = scraper.scrape_url("https://example.com", method=None)
        
        assert result['content'] == "Python content"
        mock_bash.assert_called_once_with("https://example.com")
        mock_python.assert_called_once_with("https://example.com")
    
    @patch('scraper.scrape_url_with_bash')
    def test_scrape_url_bash_method(self, mock_bash):
        """Test explicit bash method"""
        mock_bash.return_value = {
            'content': 'Bash content',
            'title': 'Bash Title',
            'url': 'https://example.com'
        }
        
        result = scraper.scrape_url("https://example.com", method="bash")
        
        assert result['content'] == "Bash content"
        mock_bash.assert_called_once_with("https://example.com")
    
    @patch('scraper.scrape_url_with_python')
    def test_scrape_url_python_method(self, mock_python):
        """Test explicit python method"""
        mock_python.return_value = {
            'content': 'Python content',
            'title': 'Python Title',
            'url': 'https://example.com'
        }
        
        result = scraper.scrape_url("https://example.com", method="python")
        
        assert result['content'] == "Python content"
        mock_python.assert_called_once_with("https://example.com")