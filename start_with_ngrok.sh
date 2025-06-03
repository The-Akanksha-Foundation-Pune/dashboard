#!/bin/bash

# Exit on error
set -e

echo "Starting the application with ngrok..."

# Check if ngrok is installed
if [ ! -f ~/ngrok/ngrok ]; then
    echo "Ngrok not found. Please run setup_ngrok.sh first."
    exit 1
fi

# Check if the authtoken is set
if ! grep -q "authtoken: \"[a-zA-Z0-9]" ~/ngrok/ngrok.yml; then
    echo "Ngrok authtoken not set. Please add your authtoken to ~/ngrok/ngrok.yml"
    exit 1
fi

# Start the application in the background
echo "Starting the dashboard application..."
cd ~/dashboard
source venv/bin/activate
nohup gunicorn --bind 0.0.0.0:5000 --workers 4 app:app > ~/dashboard/logs/app.log 2>&1 &
APP_PID=$!

# Wait for the application to start
echo "Waiting for the application to start..."
sleep 5

# Start ngrok
echo "Starting ngrok..."
cd ~/ngrok
./ngrok start dashboard --config=ngrok.yml

# If ngrok is stopped, also stop the application
echo "Ngrok stopped. Stopping the application..."
kill $APP_PID

echo "Application and ngrok have been stopped."
