FROM python:3.9-slim

# Install Chrome dependencies
RUN apt-get update && \
    apt-get install -y wget gnupg && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installation files
COPY requirements.txt .
COPY install_dependencies.sh .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    chmod +x install_dependencies.sh && \
    ./install_dependencies.sh

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Start the server
CMD ["python", "server.py"]
