#!/bin/bash

# Smart Cleanup function for Knowledge Repository services
# This script ONLY stops the specific services launched by our start script
# It will NOT interfere with other services using the same ports

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Function to check if a process is our Knowledge Repository service
is_knowledge_repo_service() {
    local pid=$1
    local expected_patterns=("run_with_env.py.*main.py" "main.py" "simple_server.py" "ui.py")
    local cmd=$(ps -p "$pid" -o command= 2>/dev/null || echo "")

    # Check if the command contains our expected patterns and is python3
    if echo "$cmd" | grep -q "python3"; then
        for pattern in "${expected_patterns[@]}"; do
            if echo "$cmd" | grep -q "$pattern"; then
                return 0  # This is our service
            fi
        done
    fi

    return 1  # Not our service
}

# Function to stop our specific services on specific port
stop_service_on_port() {
    local port=$1
    local service_name=$2
    local found_our_service=false

    # Find PIDs using the port
    local pids=$(lsof -ti:$port 2>/dev/null || true)

    if [ -n "$pids" ]; then
        print_info "Found processes on port $port..."
        for pid in $pids; do
            if kill -0 "$pid" 2>/dev/null; then
                # Check if it's specifically our Knowledge Repository service
                if is_knowledge_repo_service "$pid"; then
                    local cmd=$(ps -p "$pid" -o command= | head -c 80)
                    print_status "Stopping Knowledge Repository $service_name (PID: $pid)"
                    print_info "Process: $cmd..."
                    kill -TERM "$pid" 2>/dev/null || true
                    sleep 2
                    # Force kill if still running
                    if kill -0 "$pid" 2>/dev/null; then
                        print_warning "Force killing process $pid"
                        kill -KILL "$pid" 2>/dev/null || true
                    fi
                    found_our_service=true
                else
                    local cmd=$(ps -p "$pid" -o command= | head -c 80)
                    print_warning "Port $port is used by external process $pid - NOT stopping"
                    print_info "External process: $cmd..."
                fi
            fi
        done

        if [ "$found_our_service" = true ]; then
            # Wait for our services to release the port
            local count=0
            while lsof -ti:$port >/dev/null 2>&1 && [ $count -lt 10 ]; do
                sleep 1
                count=$((count + 1))
            done

            if lsof -ti:$port >/dev/null 2>&1; then
                print_error "Failed to release port $port from our services"
            else
                print_status "Knowledge Repository port $port released successfully"
            fi
        else
            print_warning "No Knowledge Repository services found on port $port"
            print_info "Port $port is used by other services - leaving them alone"
        fi
    else
        print_status "No processes found on port $port"
    fi
}

# Main cleanup process
print_status "Smart cleaning Knowledge Repository services..."
print_info "This will ONLY stop services launched by our start script"
print_info "Other services using the same ports will be left alone"

# Stop API server on port 8000 (only our run_with_env.py main.py)
print_status "Checking API server on port 8000..."
stop_service_on_port 8000 "API Server"

# Stop Web UI on port 7860 (only our simple_server.py or ui.py)
print_status "Checking Web UI on port 7860..."
stop_service_on_port 7860 "Web UI"

# Additional cleanup: Find and stop any remaining Knowledge Repository processes
print_status "Checking for any remaining Knowledge Repository processes..."
remaining_pids=$(pgrep -f "python3.*\(run_with_env.py.*main.py\|simple_server.py\|ui.py\)" 2>/dev/null || true)

if [ -n "$remaining_pids" ]; then
    for pid in $remaining_pids; do
        if kill -0 "$pid" 2>/dev/null; then
            local cmd=$(ps -p "$pid" -o command= | head -c 80)
            print_warning "Found stray Knowledge Repository process $pid"
            print_info "Process: $cmd..."
            print_status "Stopping stray process $pid"
            kill -TERM "$pid" 2>/dev/null || true
            sleep 1
            if kill -0 "$pid" 2>/dev/null; then
                print_warning "Force killing stray process $pid"
                kill -KILL "$pid" 2>/dev/null || true
            fi
        fi
    done
else
    print_status "No stray Knowledge Repository processes found"
fi

# Wait a moment for everything to settle
sleep 2

print_status "✅ Smart cleanup completed!"
print_info "Only Knowledge Repository services were stopped"
print_info "Other services on ports 8000/7860 were left untouched"