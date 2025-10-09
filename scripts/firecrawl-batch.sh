#!/bin/bash

# Firecrawl Batch Script
# Usage: ./firecrawl-batch.sh <URL>

set -e

# Check if URL is provided
if [ $# -eq 0 ]; then
    echo "Error: No URL provided"
    echo "Usage: $0 <URL>"
    exit 1
fi

URL="$1"

# Check if FIRECRAWL_API_KEY is set
if [ -z "$FIRECRAWL_API_KEY" ]; then
    echo "Error: FIRECRAWL_API_KEY environment variable not set"
    exit 1
fi

# Use Firecrawl API via curl
response=$(curl -s -X POST "https://api.firecrawl.dev/v0/scrape" \
    -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"$URL\", \"formats\": [\"markdown\"]}")

# Check if the request was successful
if echo "$response" | grep -q '"success": true'; then
    # Extract markdown content
    echo "$response" | grep -o '"markdown":"[^"]*"' | sed 's/"markdown":"//;s/"$//' | sed 's/\\n/\n/g; s/\\"/"/g'
else
    echo "Error: Failed to scrape URL"
    echo "$response"
    exit 1
fi