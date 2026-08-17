#!/bin/bash
# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.

# Start WildeBackyard Web Server

cd "$(dirname "$0")"

# Kill any existing web server on port 8001
echo "Stopping existing web server..."
pkill -f "manage.py runserver 8001"
sleep 1

# Start the web server
echo "Starting web server on port 8001..."
source .venv/bin/activate
python manage.py runserver 8001 --settings=config.settings.local
