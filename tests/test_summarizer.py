import pytest
import os
from unittest.mock import patch, MagicMock
import summarizer

class TestSummarizer:
    """Test cases for summarizer module"""
    
    @patch('summarizer.ollama.Client')
    def test_summarize_content_success(self, mock_client):
        """Test successful content summarization"""
        # Mock ollama client
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.return_value = {
            'message': {
                'content': '## 요약\n- 테스트 요약 내용\n\n## 키워드\n테스트, 요약\n\n## 카테고리\nTechnology'
            }
        }
        
        with patch.dict(os.environ, {'OLLAMA_BASE_URL': 'http://test:11434'}):
            result = summarizer.summarize_content("Test content")
            
            assert 'summary' in result
            assert result['model'] == 'Qwen3-Coder-30B'
            assert '요약' in result['summary']
    
    @patch('summarizer.ollama.Client')
    def test_summarize_content_long_content(self, mock_client):
        """Test summarization with long content (truncation)"""
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.return_value = {
            'message': {
                'content': '## 요약\n- 긴 내용 요약'
            }
        }
        
        # Create content longer than max_length
        long_content = "A" * 5000
        
        with patch.dict(os.environ, {'OLLAMA_BASE_URL': 'http://test:11434'}):
            result = summarizer.summarize_content(long_content, max_length=1000)
            
            # Check that the client was called with truncated content
            mock_instance.chat.assert_called_once()
            call_args = mock_instance.chat.call_args
            prompt = call_args[1]['messages'][0]['content']
            assert len(prompt) < len(long_content)  # Should be truncated
    
    @patch('summarizer.ollama.Client')
    def test_summarize_content_failure(self, mock_client):
        """Test summarization failure"""
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.side_effect = Exception("Ollama error")
        
        with patch.dict(os.environ, {'OLLAMA_BASE_URL': 'http://test:11434'}):
            with pytest.raises(Exception):
                summarizer.summarize_content("Test content")
    
    @patch('summarizer.ollama.Client')
    def test_extract_keywords_success(self, mock_client):
        """Test successful keyword extraction"""
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.return_value = {
            'message': {
                'content': '키워드1, 키워드2, 키워드3'
            }
        }
        
        with patch.dict(os.environ, {'OLLAMA_BASE_URL': 'http://test:11434'}):
            keywords = summarizer.extract_keywords("Test content for keyword extraction")
            
            assert len(keywords) == 3
            assert '키워드1' in keywords
            assert '키워드2' in keywords
            assert '키워드3' in keywords
    
    @patch('summarizer.ollama.Client')
    def test_extract_keywords_empty_response(self, mock_client):
        """Test keyword extraction with empty response"""
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.return_value = {
            'message': {
                'content': ''
            }
        }
        
        with patch.dict(os.environ, {'OLLAMA_BASE_URL': 'http://test:11434'}):
            keywords = summarizer.extract_keywords("Test content")
            
            assert keywords == []
    
    @patch('summarizer.ollama.Client')
    def test_extract_keywords_failure(self, mock_client):
        """Test keyword extraction failure"""
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.side_effect = Exception("Ollama error")
        
        with patch.dict(os.environ, {'OLLAMA_BASE_URL': 'http://test:11434'}):
            keywords = summarizer.extract_keywords("Test content")
            
            assert keywords == []
    
    @patch('summarizer.ollama.Client')
    def test_categorize_content_success(self, mock_client):
        """Test successful content categorization"""
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.return_value = {
            'message': {
                'content': 'Technology'
            }
        }
        
        with patch.dict(os.environ, {'OLLAMA_BASE_URL': 'http://test:11434'}):
            category = summarizer.categorize_content("Article about AI and machine learning")
            
            assert category == "Technology"
    
    @patch('summarizer.ollama.Client')
    def test_categorize_content_failure(self, mock_client):
        """Test categorization failure"""
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.side_effect = Exception("Ollama error")
        
        with patch.dict(os.environ, {'OLLAMA_BASE_URL': 'http://test:11434'}):
            category = summarizer.categorize_content("Test content")
            
            assert category == "Other"
    
    @patch('summarizer.ollama.Client')
    def test_default_base_url(self, mock_client):
        """Test default base URL when environment variable is not set"""
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.return_value = {
            'message': {
                'content': 'Test summary'
            }
        }
        
        with patch.dict(os.environ, {}, clear=True):
            summarizer.summarize_content("Test content")
            
            # Check that client was called with default URL
            mock_client.assert_called_once_with(host="http://localhost:11434")