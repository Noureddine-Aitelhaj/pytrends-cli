# Dockerfile - Replace the entire content with this code
FROM python:3.9-slim

WORKDIR /app

# Install necessary tools for debugging
RUN apt-get update && apt-get install -y \
    dos2unix \
    procps \
    curl \
    net-tools \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Fix line endings in scripts
RUN dos2unix start.sh

# Make scripts executable
RUN chmod +x start.sh

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Set the entrypoint
CMD ["bash", "-c", "echo 'Container starting' && python server.py"]
