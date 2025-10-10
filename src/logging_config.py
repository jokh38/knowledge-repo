import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(log_level: str = "DEBUG", log_file: str = "knowledge_api.log"):
    """Configure application logging"""

    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    log_path = logs_dir / log_file

    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.DEBUG)

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    simple_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )

    # File handler with rotation (captures all levels)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(detailed_formatter)
    file_handler.setLevel(numeric_level)

    # Console handler (show INFO and above in console)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(simple_formatter)
    console_handler.setLevel(logging.INFO)  # Show info, warnings, and errors in console

    # Additional file handler specifically for console output capture
    console_log_path = logs_dir / "console_output.log"
    console_file_handler = RotatingFileHandler(
        console_log_path,
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )
    console_file_handler.setFormatter(detailed_formatter)
    console_file_handler.setLevel(logging.INFO)  # Capture console-level messages

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Add handlers to root logger
    root_logger.addHandler(file_handler)        # Main log file
    root_logger.addHandler(console_handler)     # Console output
    root_logger.addHandler(console_file_handler) # Console log file

    # Configure Uvicorn loggers specifically
    uvicorn_loggers = ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]
    for logger_name in uvicorn_loggers:
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.setLevel(logging.INFO)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = 1  # Make sure they propagate to root logger

    # Configure all existing loggers to also use our handlers
    for logger_name in logging.Logger.manager.loggerDict.keys():
        existing_logger = logging.getLogger(logger_name)
        # Don't change level for loggers we've already configured
        if logger_name not in uvicorn_loggers:
            existing_logger.setLevel(numeric_level)
        existing_logger.handlers.clear()
        existing_logger.propagate = 1  # Make sure they propagate to root logger

    # Set specific logger levels for noisy third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("charset_normalizer").setLevel(logging.WARNING)
    logging.getLogger("chardet.charsetprober").setLevel(logging.WARNING)
    logging.getLogger("fsspec.local").setLevel(logging.WARNING)
    logging.getLogger("llama_index.core.node_parser.node_utils").setLevel(logging.WARNING)
    logging.getLogger("llama_index.vector_stores.chroma.base").setLevel(logging.WARNING)
    logging.getLogger("llama_index.core.indices.utils").setLevel(logging.WARNING)
    logging.getLogger("llama_index.core.response_synthesizers.refine").setLevel(logging.WARNING)
    logging.getLogger("llama_index_instrumentation.dispatcher").setLevel(logging.WARNING)
    logging.getLogger("torch._dynamo").setLevel(logging.WARNING)
    logging.getLogger("torch._subclasses.fake_tensor").setLevel(logging.WARNING)

    # Force configuration of our application loggers
    app_loggers = ["__main__", "src.scraper", "src.summarizer", "src.obsidian_writer", "src.retriever", "src.custom_llm"]
    for logger_name in app_loggers:
        app_logger = logging.getLogger(logger_name)
        app_logger.setLevel(numeric_level)
        app_logger.propagate = 1  # Ensure propagation to root logger

    # Configure uvicorn's access logging to be captured
    logging.getLogger("uvicorn.access").propagate = 1
    logging.getLogger("uvicorn.error").propagate = 1

    return root_logger

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name"""
    return logging.getLogger(name)

def log_request_info(request):
    """Log FastAPI request information"""
    logger = get_logger("request")
    
    client_ip = request.client.host if hasattr(request, 'client') else "unknown"
    method = request.method if hasattr(request, 'method') else "unknown"
    url = str(request.url) if hasattr(request, 'url') else "unknown"
    
    logger.info(f"Request: {method} {url} from {client_ip}")

def log_response_info(response, request_time: float = 0):
    """Log FastAPI response information"""
    logger = get_logger("response")
    
    status_code = response.status_code if hasattr(response, 'status_code') else "unknown"
    logger.info(f"Response: {status_code} in {request_time:.3f}s")

def log_error(error: Exception, context: str = ""):
    """Log error with context"""
    logger = get_logger("error")
    context_str = f" [{context}]" if context else ""
    logger.error(f"Error{context_str}: {str(error)}", exc_info=True)

def log_api_call(endpoint: str, params: dict | None = None, success: bool = True, error: str | None = None):
    """Log API call information"""
    logger = get_logger("api")
    
    params_str = f" with params {params}" if params else ""
    if success:
        logger.info(f"API call to {endpoint}{params_str} successful")
    else:
        logger.error(f"API call to {endpoint}{params_str} failed: {error}")

def log_model_interaction(model_name: str, operation: str, tokens: int | None = None, duration: float | None = None):
    """Log LLM model interaction"""
    logger = get_logger("model")
    
    tokens_str = f", tokens: {tokens}" if tokens else ""
    duration_str = f", duration: {duration:.2f}s" if duration else ""
    logger.info(f"Model {model_name} - {operation}{tokens_str}{duration_str}")

def log_vector_operation(operation: str, count: int | None = None, duration: float | None = None):
    """Log vector database operation"""
    logger = get_logger("vector")
    
    count_str = f", count: {count}" if count else ""
    duration_str = f", duration: {duration:.2f}s" if duration else ""
    logger.info(f"Vector DB {operation}{count_str}{duration_str}")