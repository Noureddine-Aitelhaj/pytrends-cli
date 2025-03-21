#!/bin/bash
# start.sh - Replace the entire content with this code

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting application..."
echo "Current directory: $(pwd)"
echo "Files in directory: $(ls -la)"
echo "Python version: $(python --version)"
echo "Available disk space: $(df -h)"
echo "Memory usage: $(free -m)"

# Run the server directly with error redirection
python server.py 2>&1 | tee /app/server.log

# If we get here, the server exited
echo "Server exited with code $?"
