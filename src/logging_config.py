import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(log_level: str = "INFO", log_file: str = "knowledge_api.log"):
    """Configure application logging"""

    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    log_path = logs_dir / log_file
    
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Set specific logger levels
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    
    return logger

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