FROM python:3.9-slim

WORKDIR /app

# Copy installation script
COPY install_dependencies.sh .
RUN chmod +x install_dependencies.sh

# Install dependencies using the script
RUN ./install_dependencies.sh

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
