#!/bin/bash

# Knowledge Repository Start Script

set -e

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

# Check if conda environment exists
if ! conda info --envs | grep -q "krepo"; then
    print_error "Conda environment 'krepo' not found. Please create it first."
    exit 1
fi

# Activate conda environment
print_status "Activating conda environment..."
source $(conda info --base)/etc/profile.d/conda.sh
conda activate krepo

# Check if requirements are installed
print_status "Checking dependencies..."
if ! python3 -c "import fastapi" 2>/dev/null; then
    print_status "Installing dependencies..."
    pip install -r requirements.txt
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found. Please create it based on .env.example"
    exit 1
fi

# Cleanup existing services before starting new ones
print_status "Cleaning up existing services..."
if [ -f "./cleanup.sh" ]; then
    ./cleanup.sh
else
    print_warning "cleanup.sh not found, performing basic cleanup..."
    # Basic cleanup if cleanup.sh is not available
    pkill -f "python3.*\(main\|ui\|simple_server\)\.py" 2>/dev/null || true
    sleep 2
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p logs
mkdir -p chroma_db

# Check if Obsidian vault path exists
VAULT_PATH=$(python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('OBSIDIAN_VAULT_PATH', ''))")
if [ -z "$VAULT_PATH" ]; then
    print_warning "OBSIDIAN_VAULT_PATH not set in .env file"
elif [ ! -d "$VAULT_PATH" ]; then
    print_warning "Obsidian vault path does not exist: $VAULT_PATH"
    print_status "Creating vault directory structure..."
    mkdir -p "$VAULT_PATH/00_Inbox/Clippings"
    mkdir -p "$VAULT_PATH/01_Processed"
fi

# Start services
print_status "Starting Knowledge Repository services..."

# Start API server in background
print_status "Starting API server on port 8000..."
python3 main.py &
API_PID=$!

# Wait a moment for API server to start
sleep 3

# Start Simple Web UI (instead of problematic gradio)
print_status "Starting Simple Web UI on port 7860..."
python3 simple_server.py &
UI_PID=$!

# Function to cleanup on exit
cleanup() {
    print_status "Shutting down services..."
    kill $API_PID 2>/dev/null || true
    kill $UI_PID 2>/dev/null || true
    print_status "Services stopped. Goodbye!"
    exit 0
}

# Trap signals for cleanup
trap cleanup SIGINT SIGTERM

print_status "Services started successfully!"
print_status "API Server: http://localhost:8000"
print_status "Simple UI: http://localhost:7860/simple_ui.html"
print_status "API Docs: http://localhost:8000/docs"
print_status ""
print_status "Press Ctrl+C to stop all services"

# Wait for services
wait