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

        # Clear existing handlers to prevent duplicates
        self.logger.handlers.clear()

        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # File handler for console capture messages only
        std_handler = logging.FileHandler(self.std_log, mode='a', encoding='utf-8')
        std_handler.setFormatter(detailed_formatter)
        std_handler.setLevel(logging.DEBUG)

        # Add handler
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
        self._stopped = False

        # Open log file in append mode with UTF-8 encoding
        try:
            self.file_handle = open(log_file, mode='a', encoding='utf-8', buffering=1)
        except Exception as e:
            self.logger.error(f"Failed to open log file {log_file}: {e}")
            self.file_handle = None

    def write(self, text: str):
        """Write text to both original stream and log file"""
        if not text or self._stopped:
            return

        with self._lock:
            # Write to original stream (console)
            try:
                self.original_stream.write(text)
                self.original_stream.flush()
            except Exception as e:
                # Ignore broken pipe errors during shutdown
                if not ("Broken pipe" in str(e) or "BrokenPipeError" in str(e)):
                    self.logger.error(f"Failed to write to {self.stream_type}: {e}")

            # Write to log file
            if self.file_handle:
                try:
                    self.file_handle.write(f"{text}")
                    self.file_handle.flush()
                except Exception as e:
                    # Ignore broken pipe errors during shutdown
                    if not ("Broken pipe" in str(e) or "BrokenPipeError" in str(e)):
                        self.logger.error(f"Failed to write to {self.stream_type} file: {e}")

    def flush(self):
        """Flush both streams"""
        if self._stopped:
            return

        with self._lock:
            try:
                self.original_stream.flush()
            except Exception as e:
                # Ignore broken pipe errors during shutdown
                if not ("Broken pipe" in str(e) or "BrokenPipeError" in str(e)):
                    self.logger.error(f"Failed to flush {self.stream_type}: {e}")

            if self.file_handle:
                try:
                    self.file_handle.flush()
                except Exception as e:
                    # Ignore broken pipe errors during shutdown
                    if not ("Broken pipe" in str(e) or "BrokenPipeError" in str(e)):
                        self.logger.error(f"Failed to flush {self.stream_type} file: {e}")

    def stop(self):
        """Close the file handle"""
        if self._stopped:
            return

        with self._lock:
            self._stopped = True
            if self.file_handle:
                try:
                    self.file_handle.close()
                except Exception as e:
                    # Ignore errors during cleanup
                    pass
                self.file_handle = None

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

    # Setup standard Python logging first (but without file handler to avoid duplicates)
    import logging
    from pathlib import Path

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Configure root logger for console output only
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Only add console handler if not already present
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Initialize console capture (this will handle file logging)
    capture = initialize_console_capture()

    # Log initialization
    logger = logging.getLogger(__name__)
    logger.info("Global console logging initialized")
    logger.info(f"Consolidated std log file: {capture.std_log}")
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