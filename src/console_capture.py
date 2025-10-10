#!/usr/bin/env python3
"""
Console capture wrapper that redirects all stdout/stderr to log files
This ensures that every console message from any process is captured.
"""

import sys
import os
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import TextIO

class ConsoleCapture:
    """
    A comprehensive console capture system that redirects stdout and stderr
    to both console and a single consolidated log file while maintaining real-time display.
    """

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Use a single consolidated log file for all sessions
        self.std_log = self.log_dir / "std_log.log"

        # Store original streams
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        # Initialize logging
        self._setup_logging()

        # Start capture
        self._start_capture()

    def _setup_logging(self):
        """Setup logging configuration for console capture"""
        # Create logger for console capture
        self.logger = logging.getLogger("console_capture")
        self.logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        self.logger.handlers.clear()

        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        simple_formatter = logging.Formatter('%(message)s')

        # File handler for consolidated std output
        std_handler = logging.FileHandler(self.std_log, mode='a', encoding='utf-8')
        std_handler.setFormatter(detailed_formatter)
        std_handler.setLevel(logging.DEBUG)

        # Add handlers
        self.logger.addHandler(std_handler)

        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False

    def _start_capture(self):
        """Start capturing stdout and stderr"""
        # Create tee-like writers that write to both original stream and log file
        sys.stdout = TeeWriter(self.original_stdout, self.std_log, self.logger, "STDOUT")
        sys.stderr = TeeWriter(self.original_stderr, self.std_log, self.logger, "STDERR")

        self.logger.info("=== Console Capture Started ===")
        self.logger.info(f"Consolidated std log: {self.std_log}")

    def stop_capture(self):
        """Stop capturing and restore original streams"""
        if hasattr(sys.stdout, 'stop'):
            sys.stdout.stop()
        if hasattr(sys.stderr, 'stop'):
            sys.stderr.stop()

        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

        self.logger.info("=== Console Capture Stopped ===")


class TeeWriter:
    """
    A writer that duplicates output to both the original stream and a single consolidated log file
    """

    def __init__(self, original_stream: TextIO, log_file: Path, logger: logging.Logger, stream_type: str):
        self.original_stream = original_stream
        self.log_file = log_file
        self.logger = logger
        self.stream_type = stream_type
        self._lock = threading.Lock()

        # Open log file in append mode with UTF-8 encoding
        self.file_handle = open(log_file, mode='a', encoding='utf-8', buffering=1)

    def write(self, text: str):
        """Write text to both original stream and log file"""
        if not text:
            return

        with self._lock:
            # Write to original stream (console)
            self.original_stream.write(text)
            self.original_stream.flush()

            # Write to log file
            try:
                self.file_handle.write(text)
                self.file_handle.flush()

                # Also log to the main logger for structured logging
                if text.strip():  # Only log non-empty lines
                    self.logger.debug(f"[{self.stream_type}] {text.rstrip()}")
            except Exception as e:
                # If file writing fails, at least log to the main logger
                self.logger.error(f"Failed to write to {self.stream_type} log: {e}")

    def flush(self):
        """Flush both streams"""
        with self._lock:
            try:
                self.original_stream.flush()
                self.file_handle.flush()
            except Exception as e:
                self.logger.error(f"Failed to flush {self.stream_type}: {e}")

    def stop(self):
        """Close the file handle"""
        with self._lock:
            try:
                self.file_handle.close()
            except Exception as e:
                self.logger.error(f"Failed to close {self.stream_type} log: {e}")

    def __getattr__(self, name):
        """Delegate all other attributes to the original stream"""
        return getattr(self.original_stream, name)


def initialize_console_capture(log_dir: str = "logs") -> ConsoleCapture:
    """
    Initialize console capture for the current process.

    Args:
        log_dir: Directory to store log files

    Returns:
        ConsoleCapture instance
    """
    return ConsoleCapture(log_dir)


def setup_global_console_logging():
    """
    Setup comprehensive console logging that captures all output from all entry points.
    This function should be called at the very beginning of any Python script.
    """
    # Only setup once
    if hasattr(setup_global_console_logging, '_initialized'):
        return

    setup_global_console_logging._initialized = True

    # Initialize console capture
    capture = initialize_console_capture()

    # Setup standard Python logging
    import logging
    from pathlib import Path

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Create file handler for Python logs (also use std_log.log for consistency)
    python_log = logs_dir / "std_log.log"
    file_handler = logging.FileHandler(python_log, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(file_handler)

    # Log initialization
    logger = logging.getLogger(__name__)
    logger.info("Global console logging initialized")
    logger.info(f"Consolidated std log file: {python_log}")
    logger.info(f"Console capture active: {capture.std_log}")

    return capture


if __name__ == "__main__":
    # Test the console capture
    capture = setup_global_console_logging()

    print("This is a test message to stdout")
    print("This is an error message to stderr", file=sys.stderr)

    import logging
    test_logger = logging.getLogger("test")
    test_logger.info("This is a logging message")
    test_logger.error("This is a logging error")

    capture.stop_capture()
    print("Console capture test completed")