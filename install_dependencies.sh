#!/bin/bash
# install_dependencies.sh

set -e

echo "Installing NumPy first to ensure compatibility..."
pip install numpy

echo "Installing other dependencies..."
pip install pandas
pip install urllib3==1.25.11
pip install pytrends
pip install requests
pip install googlesearch-python

echo "Installation completed successfully"
pip list
