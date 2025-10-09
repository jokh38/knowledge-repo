import os
import re
from datetime import datetime
from pathlib import Path
import logging
from utils.retry import retry

logger = logging.getLogger(__name__)

@retry(max_attempts=3, delay=1)
def save_to_obsidian(url: str, title: str, content: str, summary: str) -> str:
    """Save content as Obsidian markdown file"""

    vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
    if not vault_path:
        raise ValueError("OBSIDIAN_VAULT_PATH environment variable not set")
    
    # Use Path for cross-platform compatibility
    inbox_path = Path(vault_path) / "00_Inbox" / "Clippings"
    inbox_path.mkdir(parents=True, exist_ok=True)

    # Generate filename with proper sanitization
    today = datetime.now().strftime("%Y-%m-%d")
    # Remove dangerous characters and limit length
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title)  # Remove invalid filename chars
    safe_title = re.sub(r'[\s-]+', '-', safe_title)  # Replace spaces with single dash
    safe_title = safe_title.strip('-_')[:50]  # Remove leading/trailing dashes and limit length
    if not safe_title:
        safe_title = "Untitled"

    filename = f"{today} - {safe_title}.md"

    # Additional security: validate the path stays within the intended directory
    filepath = inbox_path / filename

    # Path traversal protection
    try:
        resolved_path = filepath.resolve()
        inbox_resolved = inbox_path.resolve()

        # Ensure the file is within the intended directory
        if not str(resolved_path).startswith(str(inbox_resolved)):
            raise ValueError(f"Path traversal attempt detected: {filepath}")
    except (ValueError, RuntimeError) as e:
        logger.error(f"Invalid file path: {e}")
        raise ValueError(f"Invalid filename: {safe_title}")

    # Create markdown content with proper YAML frontmatter
    md_content = f"""---
source: {url}
date_saved: {today}
captured_by: automated_pipeline
status: inbox
---

# {title}

{summary}

---

## 원본 콘텐츠

{content}
"""

    # Write file
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"Successfully saved to: {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        raise

@retry(max_attempts=2, delay=1)
def update_obsidian_file(file_path: str, metadata: dict | None = None) -> str:
    """Update an existing Obsidian file with new metadata"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Simple YAML frontmatter update (basic implementation)
        if metadata and content.startswith('---\n'):
            # Find the end of frontmatter
            frontmatter_end = content.find('\n---\n', 4)
            if frontmatter_end == -1:
                frontmatter_end = content.find('\n---', 4)
            
            if frontmatter_end != -1:
                frontmatter = content[4:frontmatter_end]
                body = content[frontmatter_end+5:]
                
                # Add new metadata
                for key, value in metadata.items():
                    if f"{key}:" not in frontmatter:
                        frontmatter += f"\n{key}: {value}"
                
                # Reconstruct file
                updated_content = f"---\n{frontmatter}\n---\n{body}"
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                
                logger.info(f"Updated metadata for: {file_path}")
        
        return file_path
    except Exception as e:
        logger.error(f"Error updating file: {str(e)}")
        raise

def move_to_processed(file_path: str, category: str = "Processed") -> str:
    """Move file from Inbox to processed folder"""
    
    try:
        vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
        if not vault_path:
            raise ValueError("OBSIDIAN_VAULT_PATH environment variable not set")
        
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Create processed folder
        processed_path = Path(vault_path) / "01_Processed" / category
        processed_path.mkdir(parents=True, exist_ok=True)
        
        # Move file
        new_filepath = processed_path / file_path_obj.name
        file_path_obj.rename(new_filepath)
        
        logger.info(f"Moved file to: {new_filepath}")
        return str(new_filepath)
    except Exception as e:
        logger.error(f"Error moving file: {str(e)}")
        raise

def get_file_stats(file_path: str) -> dict:
    """Get basic statistics about a markdown file"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        stats = {
            'file_size': len(content),
            'word_count': len(content.split()),
            'line_count': content.count('\n') + 1,
            'has_frontmatter': content.startswith('---\n'),
            'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
        }
        
        return stats
    except Exception as e:
        logger.error(f"Error getting file stats: {str(e)}")
        return {}