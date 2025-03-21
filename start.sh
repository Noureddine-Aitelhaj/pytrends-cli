#!/bin/bash

# Default is to run the HTTP server
if [ "$1" = "server" ] || [ $# -eq 0 ]; then
    python server.py
else
    # Run the specified command
    exec "$@"
fi

# Keep the container running for Railway
tail -f /dev/null
