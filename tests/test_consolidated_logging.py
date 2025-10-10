#!/usr/bin/env python3
"""
Test script to verify the consolidated std_log.log functionality.
"""

import sys
import os
import logging
import time
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_consolidated_logging():
    """Test the consolidated console logging system"""
    print("=== Testing Consolidated Console Logging ===")

    # Initialize console capture
    from src.console_capture import setup_global_console_logging
    capture = setup_global_console_logging()

    print("1. Testing stdout messages...")
    print("This stdout message should go to std_log.log")
    print("Another stdout message with some details")

    print("2. Testing stderr messages...")
    print("This stderr message should also go to std_log.log", file=sys.stderr)
    print("Error message with details", file=sys.stderr)

    print("3. Testing Python logging...")
    logger = logging.getLogger("test_consolidated")
    logger.info("This Python logging message should go to std_log.log")
    logger.warning("This warning should also be in std_log.log")
    logger.error("This error should be in std_log.log")
    logger.debug("This debug message should be in std_log.log")

    print("4. Testing mixed output...")
    print("Mixed stdout message", file=sys.stdout)
    logger.info("Mixed logging message")
    print("Mixed stderr message", file=sys.stderr)

    print("=== Consolidated Logging Test Completed ===")
    print(f"Check the consolidated log file: {capture.std_log}")

    # Wait a moment for logs to be written
    time.sleep(1)

    # Verify the consolidated log file exists and has content
    if capture.std_log.exists():
        size = capture.std_log.stat().st_size
        print(f"✓ Consolidated log file exists: {capture.std_log}")
        print(f"✓ File size: {size} bytes")

        # Show last few lines
        try:
            with open(capture.std_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                print(f"✓ Total lines in file: {len(lines)}")
                if lines:
                    print("Last 5 lines:")
                    for line in lines[-5:]:
                        print(f"  {line.strip()}")
        except Exception as e:
            print(f"Error reading file: {e}")
    else:
        print(f"✗ Log file not found: {capture.std_log}")

    capture.stop_capture()

if __name__ == "__main__":
    test_consolidated_logging()