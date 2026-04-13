#!/bin/bash
# Stop WildeBackyard Web Server

echo "Stopping web server (port 8001)..."
pkill -f "manage.py runserver 8001"
echo "Web server stopped."
