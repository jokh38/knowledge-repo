from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
from dotenv import load_dotenv
import time
import os
import sys
import logging
import warnings
from typing import Optional

# Add project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress specific deprecation warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pydantic._internal._generate_schema')

# Load environment variables FIRST
load_dotenv()

# Import modules AFTER loading environment variables
from src import scraper, summarizer, obsidian_writer, retriever
from src.auth import verify_token, optional_auth
from src.logging_config import setup_logging, log_request_info, log_response_info, log_error, log_api_call

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Knowledge Repository API",
    description="Personal knowledge management system with web content collection and semantic search",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files serving
@app.get("/simple_ui.html", response_class=FileResponse)
async def serve_simple_ui():
    """Serve the simple UI HTML file"""
    return FileResponse("simple_ui.html")

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    log_request_info(request)
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        log_response_info(response, process_time)
        return response
    except Exception as e:
        process_time = time.time() - start_time
        log_error(e, f"Request processing failed after {process_time:.3f}s")
        raise

# Pydantic models
class CaptureRequest(BaseModel):
    url: HttpUrl
    method: Optional[str] = None  # 'bash' or 'python'

class CaptureResponse(BaseModel):
    success: bool
    file_path: str
    title: str
    message: str

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5

class QueryResponse(BaseModel):
    answer: str
    sources: list
    query: str

class ReindexRequest(BaseModel):
    force: bool = False

class HealthResponse(BaseModel):
    status: str
    ollama: str
    vault_path: str
    chroma_db: str

# Routes
@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "message": "Knowledge Repository API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "Not configured")
        chroma_db = os.getenv("CHROMA_DB_PATH", "./chroma_db")
        
        # Check if vault path exists
        vault_exists = os.path.exists(vault_path) if vault_path != "Not configured" else False
        
        return HealthResponse(
            status="healthy",
            ollama="connected",  # Would need actual health check
            vault_path=vault_path,
            chroma_db=chroma_db
        )
    except Exception as e:
        log_error(e, "Health check failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/capture", response_model=CaptureResponse)
async def capture_url(request: CaptureRequest, token: str = Depends(verify_token)):
    """Capture URL and save to Obsidian with auto-indexing"""
    start_time = time.time()
    
    try:
        logger.info(f"Capturing URL: {request.url}")
        log_api_call("/capture", {"url": str(request.url), "method": request.method})

        # Step 1: Scrape content
        scraped = scraper.scrape_url(str(request.url), request.method)

        # Step 2: Summarize
        result = summarizer.summarize_content(scraped['content'])

        # Step 3: Save to Obsidian
        file_path = obsidian_writer.save_to_obsidian(
            url=scraped['url'],
            title=scraped['title'],
            content=scraped['content'],
            summary=result['summary']
        )

        # Step 4: Add incremental indexing
        try:
            retriever.incremental_index(file_path)
            logger.info(f"Successfully indexed: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to index file: {e}")

        duration = time.time() - start_time
        logger.info(f"Successfully saved to: {file_path} in {duration:.2f}s")
        log_api_call("/capture", {"url": str(request.url)}, True, None)

        return CaptureResponse(
            success=True,
            file_path=file_path,
            title=scraped['title'],
            message="콘텐츠가 성공적으로 저장되었습니다."
        )

    except Exception as e:
        duration = time.time() - start_time
        log_error(e, f"Capture failed after {duration:.2f}s")
        log_api_call("/capture", {"url": str(request.url)}, False, str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=QueryResponse)
async def query_knowledge(request: QueryRequest, token: Optional[str] = Depends(optional_auth)):
    """Query the knowledge base"""
    start_time = time.time()
    
    try:
        logger.info(f"Query: {request.query}")
        log_api_call("/query", {"query": request.query, "top_k": request.top_k})

        result = retriever.query_vault(request.query, request.top_k)
        
        duration = time.time() - start_time
        logger.info(f"Query completed in {duration:.2f}s")
        log_api_call("/query", {"query": request.query}, True, None)

        return QueryResponse(**result)
    except Exception as e:
        duration = time.time() - start_time
        log_error(e, f"Query failed after {duration:.2f}s")
        log_api_call("/query", {"query": request.query}, False, str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reindex")
async def reindex_vault(request: ReindexRequest, token: str = Depends(verify_token)):
    """Reindex the entire vault"""
    try:
        log_api_call("/reindex", {"force": request.force})
        retriever.index_vault(force_reindex=request.force)
        log_api_call("/reindex", {"force": request.force}, True, None)
        return {"message": "Reindexing complete"}
    except Exception as e:
        log_error(e, "Reindexing failed")
        log_api_call("/reindex", {"force": request.force}, False, str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats(token: str = Depends(verify_token)):
    """Get system statistics"""
    try:
        index_stats = retriever.get_index_stats()
        return {
            "index_stats": index_stats,
            "vault_path": os.getenv("OBSIDIAN_VAULT_PATH"),
            "chroma_db_path": os.getenv("CHROMA_DB_PATH"),
            "ollama_base_url": os.getenv("OLLAMA_BASE_URL")
        }
    except Exception as e:
        log_error(e, "Stats retrieval failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    log_error(exc, f"Unhandled exception in {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    import socket

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    # Check if port is already in use and find available port if needed
    def find_available_port(start_port):
        """Find an available port starting from start_port"""
        for port_num in range(start_port, start_port + 10):  # Try 10 ports
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    result = sock.connect_ex((host, port_num))
                    if result != 0:  # Port is available
                        return port_num
            except Exception:
                continue
        raise RuntimeError(f"No available ports found in range {start_port}-{start_port + 9}")

    try:
        # Try to bind to the configured port first
        logger.info(f"Starting Knowledge Repository API on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
    except OSError as e:
        if "Address already in use" in str(e):
            logger.warning(f"Port {port} is already in use, finding available port...")
            available_port = find_available_port(port + 1)
            logger.info(f"Starting Knowledge Repository API on {host}:{available_port}")
            uvicorn.run(app, host=host, port=available_port)
        else:
            raise