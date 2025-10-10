from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl, ValidationError
from dotenv import load_dotenv
import time
import os
import sys
import logging
import warnings
from typing import Optional
import requests
from requests.exceptions import ConnectionError, Timeout, HTTPError

# Add project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress specific deprecation warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pydantic._internal._generate_schema')

# Initialize comprehensive console capture FIRST
from src.console_capture import setup_global_console_logging
console_capture = setup_global_console_logging()

# Load environment variables AFTER console capture is set up
load_dotenv()

# Import modules AFTER loading environment variables
from src import scraper, summarizer, obsidian_writer, retriever
from src.auth import verify_token, optional_auth, generate_api_token
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
# For development, allow localhost origins. In production, update to specific domains.
allowed_origins = [
    "http://localhost:7860",    # Simple web UI
    "http://localhost:8000",    # API server itself
    "http://127.0.0.1:7860",    # Alternative localhost
    "http://127.0.0.1:8000",    # Alternative localhost
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # More restrictive methods
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
    except (ValueError, KeyError) as e:
        log_error(e, "Health check failed due to configuration error")
        raise HTTPException(status_code=503, detail=f"Service configuration error: {str(e)}")
    except Exception as e:
        log_error(e, "Health check failed unexpectedly")
        raise HTTPException(status_code=503, detail="Service unavailable")

@app.post("/capture", response_model=CaptureResponse)
async def capture_url(request: CaptureRequest):
    """Capture URL and save to Obsidian with auto-indexing"""
    start_time = time.time()

    try:
        logger.info(f"Capturing URL: {request.url}")
        logger.debug(f"[DEBUG] Capture request - URL: {request.url}, Method: {request.method}")
        log_api_call("/capture", {"url": str(request.url), "method": request.method})

        # Step 1: Scrape content
        logger.info(f"[CAPTURE] Step 1/4: Starting URL scraping for {request.url}")
        scrape_start = time.time()
        try:
            logger.debug(f"[CAPTURE] Calling scraper.scrape_url() with method: {request.method}")
            scraped = scraper.scrape_url(str(request.url), request.method)
            scrape_duration = time.time() - scrape_start
            logger.info(f"[CAPTURE] Scraping completed successfully in {scrape_duration:.2f}s")
            logger.debug(f"[CAPTURE] Scraped title: {scraped.get('title', 'N/A')}")
            logger.debug(f"[CAPTURE] Scraped content length: {len(scraped.get('content', ''))} characters")
        except Exception as e:
            scrape_duration = time.time() - scrape_start
            logger.error(f"[CAPTURE] Scraping failed after {scrape_duration:.2f}s: {type(e).__name__}: {str(e)}")
            raise

        # Step 2: Summarize
        logger.info(f"[CAPTURE] Step 2/4: Starting content summarization")
        summarize_start = time.time()
        try:
            logger.debug(f"[CAPTURE] Calling summarizer.summarize_content() with {len(scraped.get('content', ''))} characters")
            result = summarizer.summarize_content(scraped['content'])
            summarize_duration = time.time() - summarize_start
            logger.info(f"[CAPTURE] Summarization completed successfully in {summarize_duration:.2f}s")
            logger.debug(f"[CAPTURE] Summary length: {len(result.get('summary', ''))} characters")
            logger.debug(f"[CAPTURE] Model used: {result.get('model', 'Unknown')}")
        except Exception as e:
            summarize_duration = time.time() - summarize_start
            logger.error(f"[CAPTURE] Summarization failed after {summarize_duration:.2f}s: {type(e).__name__}: {str(e)}")
            # Check if it's a network-related error
            if "network" in str(e).lower() or "connection" in str(e).lower() or "timeout" in str(e).lower():
                logger.error(f"[CAPTURE] Network-related error detected during summarization: {e}")
            raise

        # Step 3: Save to Obsidian
        logger.info(f"[CAPTURE] Step 3/4: Saving to Obsidian vault")
        save_start = time.time()
        try:
            logger.debug(f"[CAPTURE] Calling obsidian_writer.save_to_obsidian()")
            file_path = obsidian_writer.save_to_obsidian(
                url=scraped['url'],
                title=scraped['title'],
                content=scraped['content'],
                summary=result['summary']
            )
            save_duration = time.time() - save_start
            logger.info(f"[CAPTURE] File saved successfully in {save_duration:.2f}s: {file_path}")
        except Exception as e:
            save_duration = time.time() - save_start
            logger.error(f"[CAPTURE] File saving failed after {save_duration:.2f}s: {type(e).__name__}: {str(e)}")
            raise

        # Step 4: Add incremental indexing
        logger.info(f"[CAPTURE] Step 4/4: Starting incremental indexing")
        index_start = time.time()
        try:
            logger.debug(f"[CAPTURE] Calling retriever.incremental_index() for file: {file_path}")
            retriever.incremental_index(file_path)
            index_duration = time.time() - index_start
            logger.info(f"[CAPTURE] Incremental indexing completed successfully in {index_duration:.2f}s")
        except Exception as e:
            index_duration = time.time() - index_start
            logger.error(f"[CAPTURE] Indexing failed after {index_duration:.2f}s: {type(e).__name__}: {str(e)}")
            # Check if it's a network-related error
            if "network" in str(e).lower() or "connection" in str(e).lower() or "timeout" in str(e).lower():
                logger.error(f"[CAPTURE] Network-related error detected during indexing: {e}")
            logger.warning(f"[CAPTURE] Continuing despite indexing failure - file was saved successfully")
            # Don't raise - we want to return success even if indexing fails

        duration = time.time() - start_time
        logger.info(f"Successfully saved to: {file_path} in {duration:.2f}s")
        logger.debug(f"[DEBUG] Total capture process completed in {duration:.2f}s")
        log_api_call("/capture", {"url": str(request.url)}, True, None)

        return CaptureResponse(
            success=True,
            file_path=file_path,
            title=scraped['title'],
            message="콘텐츠가 성공적으로 저장되었습니다."
        )

    except (ConnectionError, Timeout) as e:
        duration = time.time() - start_time
        logger.error(f"Network error during capture after {duration:.2f}s: {str(e)}")
        log_api_call("/capture", {"url": str(request.url)}, False, f"Network error: {str(e)}")
        raise HTTPException(status_code=503, detail="External service unavailable. Please try again later.")
    except ValidationError as e:
        duration = time.time() - start_time
        logger.error(f"Validation error during capture after {duration:.2f}s: {str(e)}")
        log_api_call("/capture", {"url": str(request.url)}, False, f"Validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=f"Invalid request format: {str(e)}")
    except (ValueError, KeyError) as e:
        duration = time.time() - start_time
        logger.error(f"Data error during capture after {duration:.2f}s: {str(e)}")
        log_api_call("/capture", {"url": str(request.url)}, False, f"Data error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid data provided: {str(e)}")
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Unexpected error during capture after {duration:.2f}s: {type(e).__name__}: {str(e)}")
        import traceback
        logger.debug(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        log_api_call("/capture", {"url": str(request.url)}, False, "Internal server error")
        raise HTTPException(status_code=500, detail="An unexpected error occurred. Please try again.")

@app.post("/query", response_model=QueryResponse)
async def query_knowledge(request: QueryRequest, token: Optional[str] = Depends(optional_auth)):
    """Query the knowledge base"""
    start_time = time.time()

    try:
        logger.info(f"Query: {request.query}")
        logger.debug(f"[DEBUG] Query request - Query: {request.query}, Top_k: {request.top_k}")
        log_api_call("/query", {"query": request.query, "top_k": request.top_k})

        logger.debug(f"[DEBUG] Starting vault query process")
        result = retriever.query_vault(request.query, request.top_k)
        logger.debug(f"[DEBUG] Vault query completed successfully")
        logger.debug(f"[DEBUG] Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        logger.debug(f"[DEBUG] Answer length: {len(result.get('answer', ''))}")
        logger.debug(f"[DEBUG] Number of sources: {len(result.get('sources', []))}")

        duration = time.time() - start_time
        logger.info(f"Query completed in {duration:.2f}s")
        logger.debug(f"[DEBUG] Total query process completed in {duration:.2f}s")
        log_api_call("/query", {"query": request.query}, True, None)

        return QueryResponse(**result)
    except (ConnectionError, Timeout) as e:
        duration = time.time() - start_time
        logger.error(f"Network error during query after {duration:.2f}s: {str(e)}")
        log_api_call("/query", {"query": request.query}, False, f"Network error: {str(e)}")
        raise HTTPException(status_code=503, detail="Knowledge base service unavailable. Please try again later.")
    except (ValueError, KeyError) as e:
        duration = time.time() - start_time
        logger.error(f"Data error during query after {duration:.2f}s: {str(e)}")
        log_api_call("/query", {"query": request.query}, False, f"Data error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid query or data format: {str(e)}")
    except ValidationError as e:
        duration = time.time() - start_time
        logger.error(f"Validation error during query after {duration:.2f}s: {str(e)}")
        log_api_call("/query", {"query": request.query}, False, f"Validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=f"Invalid request format: {str(e)}")
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Unexpected error during query after {duration:.2f}s: {type(e).__name__}: {str(e)}")
        import traceback
        logger.debug(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        log_api_call("/query", {"query": request.query}, False, "Internal server error")
        raise HTTPException(status_code=500, detail="An unexpected error occurred. Please try again.")

@app.post("/reindex")
async def reindex_vault(request: ReindexRequest):
    """Reindex the entire vault"""
    try:
        log_api_call("/reindex", {"force": request.force})
        retriever.index_vault(force_reindex=request.force)
        log_api_call("/reindex", {"force": request.force}, True, None)
        return {"message": "Reindexing complete"}
    except (ConnectionError, Timeout) as e:
        log_error(e, "Reindexing failed due to network error")
        log_api_call("/reindex", {"force": request.force}, False, f"Network error: {str(e)}")
        raise HTTPException(status_code=503, detail="Database service unavailable. Please try again later.")
    except (ValueError, KeyError) as e:
        log_error(e, "Reindexing failed due to data error")
        log_api_call("/reindex", {"force": request.force}, False, f"Data error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid data format during reindexing: {str(e)}")
    except Exception as e:
        log_error(e, "Reindexing failed unexpectedly")
        log_api_call("/reindex", {"force": request.force}, False, "Internal server error")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during reindexing. Please try again.")

@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    try:
        index_stats = retriever.get_index_stats()
        return {
            "index_stats": index_stats,
            "vault_path": os.getenv("OBSIDIAN_VAULT_PATH"),
            "chroma_db_path": os.getenv("CHROMA_DB_PATH"),
            "ollama_base_url": os.getenv("OLLAMA_BASE_URL")
        }
    except (ConnectionError, Timeout) as e:
        log_error(e, "Stats retrieval failed due to network error")
        raise HTTPException(status_code=503, detail="Database service unavailable. Please try again later.")
    except (ValueError, KeyError) as e:
        log_error(e, "Stats retrieval failed due to data error")
        raise HTTPException(status_code=400, detail=f"Data format error: {str(e)}")
    except Exception as e:
        log_error(e, "Stats retrieval failed unexpectedly")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while retrieving statistics.")

@app.post("/token")
async def generate_token():
    """Generate a JWT token for API access"""
    try:
        # Generate token for API usage
        token = generate_api_token("api_user")
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": os.getenv("JWT_EXPIRE_MINUTES", 30)
        }
    except Exception as e:
        log_error(e, "Token generation failed")
        raise HTTPException(status_code=500, detail="Failed to generate token")

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
        uvicorn.run(app, host=host, port=port, log_config=None)  # Use our logging config
    except OSError as e:
        if "Address already in use" in str(e):
            logger.warning(f"Port {port} is already in use, finding available port...")
            available_port = find_available_port(port + 1)
            logger.info(f"Starting Knowledge Repository API on {host}:{available_port}")
            uvicorn.run(app, host=host, port=available_port, log_config=None)  # Use our logging config
        else:
            raise