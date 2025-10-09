#!/bin/bash

# Cleanup function for Knowledge Repository services
# This script stops any existing services on ports 8000 and 7860

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to stop services on specific port
stop_service_on_port() {
    local port=$1
    local service_name=$2

    # Find PIDs using the port
    local pids=$(lsof -ti:$port 2>/dev/null || true)

    if [ -n "$pids" ]; then
        print_status "Stopping $service_name services on port $port..."
        for pid in $pids; do
            if kill -0 "$pid" 2>/dev/null; then
                # Check if it's a Python process related to our services
                if ps -p "$pid" -o command= | grep -q "python3.*\(main\|ui\|simple_server\)\.py"; then
                    print_status "Killing process $pid ($service_name)"
                    kill -TERM "$pid" 2>/dev/null || true
                    sleep 2
                    # Force kill if still running
                    if kill -0 "$pid" 2>/dev/null; then
                        print_warning "Force killing process $pid"
                        kill -KILL "$pid" 2>/dev/null || true
                    fi
                else
                    print_warning "Port $port is used by non-service process $pid - skipping"
                fi
            fi
        done

        # Wait for port to be released
        local count=0
        while lsof -ti:$port >/dev/null 2>&1 && [ $count -lt 10 ]; do
            sleep 1
            count=$((count + 1))
        done

        if lsof -ti:$port >/dev/null 2>&1; then
            print_error "Failed to release port $port"
        else
            print_status "Port $port released successfully"
        fi
    else
        print_status "No $service_name services found on port $port"
    fi
}

# Main cleanup process
print_status "Cleaning up existing Knowledge Repository services..."

# Stop API server on port 8000
stop_service_on_port 8000 "API Server"

# Stop Web UI on port 7860
stop_service_on_port 7860 "Web UI"

# Also clean up any zombie Python processes
print_status "Cleaning up zombie Python processes..."
pkill -f "python3.*\(main\|ui\|simple_server\)\.py" 2>/dev/null || true

# Wait a moment for everything to settle
sleep 2

print_status "Cleanup completed. Ports should now be available."