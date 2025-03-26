#!/bin/bash
set -e

echo "Checking Chrome installation..."
if ! command -v google-chrome &> /dev/null; then
    echo "Chrome not found! Make sure it's installed in Dockerfile"
    exit 1
fi

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installation completed successfully"
pip list
