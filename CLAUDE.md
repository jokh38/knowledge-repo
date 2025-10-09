# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# Activate existing conda environment
conda activate krepo

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Start both API server and Web UI using the start script
./start.sh

# Or start services individually:
python3 main.py  # API server on port 8000
python3 ui.py    # Web UI on port 7860
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ -v --cov=. --cov-report=html

# Run specific test file
pytest tests/test_scraper.py -v
```

### Code Quality
```bash
# Format code
black *.py

# Lint code
flake8 *.py

# Type checking
mypy *.py
```

### Database Operations
```bash
# Reindex entire vault (force rebuild)
curl -X POST http://localhost:8000/reindex \
  -H "Authorization: Bearer your_token" \
  -H "Content-Type: application/json" \
  -d '{"force": true}'

# Check API health
curl http://localhost:8000/health
```

## Architecture Overview

This is a personal knowledge management system that collects web content, summarizes it using LLM, and provides semantic search capabilities.

### Core Components

**FastAPI Server** (`main.py`): Main API server with endpoints for URL capture, knowledge query, and vault management.

**Content Pipeline**:
1. **Scraper** (`scraper.py`): Dual-method web scraping (bash script + Firecrawl API)
2. **Summarizer** (`summarizer.py`): LLM-powered content summarization using Qwen3-Coder-30B
3. **Obsidian Writer** (`obsidian_writer.py`): Saves processed content as markdown files
4. **Retriever** (`retriever.py`): RAG-based semantic search using ChromaDB vector store

**Web UI** (`ui.py`): Gradio-based interface providing Korean-language UI for all operations.

### Key Dependencies

- **LLM**: Ollama with Qwen3-Coder-30B model for summarization and query responses
- **Vector Store**: ChromaDB with sentence-transformers multilingual embeddings
- **Web Scraping**: Firecrawl (both bash script and Python API)
- **Authentication**: Simple token-based auth with optional JWT support

### Data Flow

1. **URL Capture**: `/capture` endpoint processes URL → scrapes content → LLM summarization → saves to Obsidian vault → updates vector index
2. **Knowledge Query**: `/query` endpoint searches vector store → retrieves relevant documents → generates LLM response with sources
3. **Reindexing**: `/reindex` endpoint rebuilds entire vector index from markdown files

### Environment Configuration

Required environment variables in `.env`:
- `OBSIDIAN_VAULT_PATH`: Path to Obsidian vault directory
- `OLLAMA_BASE_URL`: Ollama API server URL (default: http://localhost:11434)
- `CHROMA_DB_PATH`: Vector database storage path (default: ./chroma_db)
- `API_TOKEN`: Simple authentication token
- `API_HOST/API_PORT`: Server configuration

### File Structure

The system stores content in a structured Obsidian vault:
- `00_Inbox/Clippings/`: Raw captured content
- `01_Processed/`: Processed and summarized content
- Vector index stored in `chroma_db/` directory
- Application logs in `logs/` directory

### Error Handling

The system includes comprehensive error handling and retry logic via `utils/retry.py`. All operations are logged and monitored through structured logging in `logging_config.py`.