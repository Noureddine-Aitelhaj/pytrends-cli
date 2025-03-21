FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Make scripts executable
RUN chmod +x cli.py start.sh

# Create data directory
RUN mkdir -p /app/data

# Expose port for web server
EXPOSE 8080

# Set the entry point
ENTRYPOINT ["/bin/bash", "/app/start.sh"]
