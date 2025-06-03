#!/bin/bash

# Change to the application directory
cd ~/dashboard

# Activate the virtual environment
source venv/bin/activate

# Start the application with Gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 app:app >> ~/dashboard/logs/app.log 2>&1
