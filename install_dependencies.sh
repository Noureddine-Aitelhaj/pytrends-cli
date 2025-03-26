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
pip install facebook-page-scraper
pip install selenium
pip install webdriver-manager
pip install python-dateutil
pip install selenium-wire

echo "Installation completed successfully"
pip list
