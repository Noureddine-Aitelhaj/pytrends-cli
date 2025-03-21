#!/bin/bash
# install_dependencies.sh - Create this file

set -e

echo "Installing NumPy first to ensure compatibility..."
pip install numpy==1.23.5

echo "Installing other dependencies..."
pip install pandas==1.5.3
pip install pytrends==4.9.2
pip install youtube-transcript-api==0.6.1
pip install requests==2.31.0

echo "Installation completed successfully"
pip list