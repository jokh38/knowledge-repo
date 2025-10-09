import pytest
import os
import tempfile
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path
import obsidian_writer

class TestObsidianWriter:
    """Test cases for obsidian_writer module"""
    
    def test_save_to_obsidian_success(self):
        """Test successful file saving to Obsidian"""
        with patch('builtins.open', mock_open()) as mock_file:
            with patch('os.getenv') as mock_getenv:
                with patch('pathlib.Path.mkdir') as mock_mkdir:
                    # Mock environment variable
                    mock_getenv.return_value = "/test/vault"
                    
                    # Call function
                    result = obsidian_writer.save_to_obsidian(
                        url="https://example.com",
                        title="Test Title",
                        content="Test content",
                        summary="Test summary"
                    )
                    
                    # Verify calls
                    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
                    mock_file.assert_called_once()
                    
                    # Check result contains file path
                    assert result.endswith(".md")
                    assert "Test Title" in result
    
    def test_save_to_obsidian_no_vault_path(self):
        """Test saving with no vault path configured"""
        with patch('os.getenv') as mock_getenv:
            mock_getenv.return_value = None
            
            with pytest.raises(ValueError, match="OBSIDIAN_VAULT_PATH"):
                obsidian_writer.save_to_obsidian(
                    url="https://example.com",
                    title="Test Title",
                    content="Test content",
                    summary="Test summary"
                )
    
    def test_save_to_obsidian_file_write_error(self):
        """Test handling of file write errors"""
        with patch('os.getenv') as mock_getenv:
            with patch('pathlib.Path.mkdir'):
                mock_getenv.return_value = "/test/vault"
                
                # Mock open to raise an exception
                with patch('builtins.open', side_effect=IOError("Write error")):
                    with pytest.raises(IOError):
                        obsidian_writer.save_to_obsidian(
                            url="https://example.com",
                            title="Test Title",
                            content="Test content",
                            summary="Test summary"
                        )
    
    def test_save_to_obsidian_safe_filename(self):
        """Test safe filename generation"""
        with patch('builtins.open', mock_open()) as mock_file:
            with patch('os.getenv') as mock_getenv:
                with patch('pathlib.Path.mkdir'):
                    mock_getenv.return_value = "/test/vault"

                    # Test with special characters
                    result = obsidian_writer.save_to_obsidian(
                        url="https://example.com",
                        title="Test/Title\\With:Special*Characters",
                        content="Test content",
                        summary="Test summary"
                    )

                    # Extract just the filename part
                    filename = Path(result).name

                    # Check that special characters were removed from filename
                    assert "/" not in filename
                    assert "\\" not in filename
                    assert ":" not in filename
                    assert "*" not in filename
                    # Should be "2025-10-09 - TestTitleWithSpecialCharacters.md" format
                    assert "TestTitleWithSpecialCharacters" in filename
    
    def test_update_obsidian_file_with_frontmatter(self):
        """Test updating file with existing frontmatter"""
        test_content = """---
source: https://example.com
date_saved: 2023-01-01
---
# Test Title
Content here"""
        
        with patch('builtins.open', mock_open(read_data=test_content)) as mock_file:
            with patch('os.path.exists', return_value=True):
                
                result = obsidian_writer.update_obsidian_file(
                    "/test/file.md",
                    metadata={"status": "processed"}
                )
                
                # Verify file was written
                mock_file.assert_called()
                assert result == "/test/file.md"
    
    def test_update_obsidian_file_without_frontmatter(self):
        """Test updating file without frontmatter"""
        test_content = "# Test Title\nContent here"
        
        with patch('builtins.open', mock_open(read_data=test_content)):
            with patch('os.path.exists', return_value=True):
                
                result = obsidian_writer.update_obsidian_file(
                    "/test/file.md",
                    metadata={"status": "processed"}
                )
                
                assert result == "/test/file.md"
    
    def test_update_obsidian_file_no_metadata(self):
        """Test updating file with no metadata"""
        test_content = """---
source: https://example.com
---
# Test Title"""
        
        with patch('builtins.open', mock_open(read_data=test_content)):
            with patch('os.path.exists', return_value=True):
                
                result = obsidian_writer.update_obsidian_file("/test/file.md")
                
                assert result == "/test/file.md"
    
    def test_move_to_processed_success(self):
        """Test successful file move to processed folder"""
        with patch('os.getenv') as mock_getenv:
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.mkdir'):
                    with patch('pathlib.Path.rename') as mock_rename:
                        # Mock environment
                        mock_getenv.return_value = "/test/vault"
                        
                        # Mock path to return the processed path after move
                        with patch('pathlib.Path.__str__', return_value="/test/vault/01_Processed/Processed/file.md"):
                            result = obsidian_writer.move_to_processed("/test/file.md")

                            mock_rename.assert_called_once()
                            assert "01_Processed" in result
    
    def test_move_to_processed_no_vault_path(self):
        """Test moving file with no vault path configured"""
        with patch('os.getenv') as mock_getenv:
            mock_getenv.return_value = None
            
            with pytest.raises(ValueError, match="OBSIDIAN_VAULT_PATH"):
                obsidian_writer.move_to_processed("/test/file.md")
    
    def test_move_to_processed_file_not_found(self):
        """Test moving non-existent file"""
        with patch('os.getenv') as mock_getenv:
            with patch('pathlib.Path.exists', return_value=False):
                mock_getenv.return_value = "/test/vault"
                
                with pytest.raises(FileNotFoundError):
                    obsidian_writer.move_to_processed("/test/nonexistent.md")
    
    def test_get_file_stats_success(self):
        """Test successful file stats retrieval"""
        test_content = "# Test Title\nSome content here"
        
        with patch('builtins.open', mock_open(read_data=test_content)):
            with patch('os.path.getmtime', return_value=1672531200):  # Mock timestamp
                
                stats = obsidian_writer.get_file_stats("/test/file.md")
                
                assert stats['file_size'] == len(test_content)
                assert stats['word_count'] == 6  # "# Test Title Some content here" (6 words total)
                assert stats['line_count'] == 2
                assert stats['has_frontmatter'] is False
                assert 'last_modified' in stats
    
    def test_get_file_stats_with_frontmatter(self):
        """Test file stats with frontmatter"""
        test_content = """---
source: https://example.com
---
# Test Title
Content"""
        
        with patch('builtins.open', mock_open(read_data=test_content)):
            with patch('os.path.getmtime', return_value=1672531200):
                
                stats = obsidian_writer.get_file_stats("/test/file.md")
                
                assert stats['has_frontmatter'] is True
    
    def test_get_file_stats_file_error(self):
        """Test handling of file read errors"""
        with patch('builtins.open', side_effect=IOError("Read error")):
            stats = obsidian_writer.get_file_stats("/test/nonexistent.md")
            
            assert stats == {}