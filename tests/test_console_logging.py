#!/usr/bin/env python3
"""
Test script to verify comprehensive console logging functionality.
This script tests all logging mechanisms to ensure complete capture.
"""

import sys
import os
import logging
import time
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_console_capture():
    """Test the comprehensive console capture system"""
    print("=== Testing Console Capture System ===")

    # Initialize console capture
    from src.console_capture import setup_global_console_logging
    capture = setup_global_console_logging()

    print("1. Testing stdout capture...")
    print("This message should appear in both console and log files")

    print("2. Testing stderr capture...")
    print("This error message should also be captured", file=sys.stderr)

    print("3. Testing Python logging...")
    logger = logging.getLogger("test_logger")
    logger.info("This is an INFO log message")
    logger.warning("This is a WARNING log message")
    logger.error("This is an ERROR log message")
    logger.debug("This is a DEBUG log message")

    print("4. Testing different log levels from application modules...")
    from src.logging_config import setup_logging, get_logger

    # Setup standard logging
    setup_logging(log_file="test_application.log")
    app_logger = get_logger("test_application")

    app_logger.info("Application INFO message")
    app_logger.debug("Application DEBUG message")
    app_logger.warning("Application WARNING message")
    app_logger.error("Application ERROR message")

    print("5. Testing API call logging...")
    from src.logging_config import log_api_call, log_request_info, log_response_info, log_error

    # Mock request object
    class MockRequest:
        def __init__(self):
            self.client = type('Client', (), {'host': '127.0.0.1'})()
            self.method = 'GET'
            self.url = type('URL', (), {'__str__': lambda: 'http://localhost:8000/test'})()

    request = MockRequest()
    log_request_info(request)
    log_api_call("/test_endpoint", {"param": "value"}, True)
    log_response_info(type('Response', (), {'status_code': 200})(), 0.123)

    try:
        raise ValueError("This is a test error")
    except Exception as e:
        log_error(e, "Test context")

    print("6. Testing model and vector operation logging...")
    from src.logging_config import log_model_interaction, log_vector_operation

    log_model_interaction("test-model", "test-operation", tokens=100, duration=1.5)
    log_vector_operation("test-indexing", count=50, duration=2.3)

    print("=== Console Capture Test Completed ===")
    print(f"Check the following log files:")
    print(f"- Combined console log: {capture.combined_log}")
    print(f"- Stdout log: {capture.stdout_log}")
    print(f"- Stderr log: {capture.stderr_log}")
    print(f"- Python output log: logs/python_output.log")
    print(f"- Application log: logs/test_application.log")
    print(f"- Console output log: logs/console_output.log")

    # Wait a moment for all logs to be written
    time.sleep(1)

    # Verify log files exist and have content
    log_files = [
        capture.combined_log,
        capture.stdout_log,
        capture.stderr_log,
        Path("logs/python_output.log"),
        Path("logs/test_application.log"),
        Path("logs/console_output.log")
    ]

    print("\n=== Log File Verification ===")
    for log_file in log_files:
        if log_file.exists():
            size = log_file.stat().st_size
            print(f"✓ {log_file.name}: {size} bytes")

            # Show last few lines
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        print(f"  Last line: {lines[-1].strip()}")
            except Exception as e:
                print(f"  Error reading file: {e}")
        else:
            print(f"✗ {log_file.name}: File not found")

    capture.stop_capture()

if __name__ == "__main__":
    test_console_capture()