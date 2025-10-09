#!/bin/bash

# Stop script for Knowledge Repository services
# This script stops all running services

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_status "Stopping Knowledge Repository services..."

# Use the cleanup script if available
if [ -f "./cleanup.sh" ]; then
    ./cleanup.sh
else
    # Direct cleanup
    pkill -f "python3.*\(main\|ui\|simple_server\)\.py" 2>/dev/null || true
    sleep 2
fi

print_status "All Knowledge Repository services stopped."