#!/bin/bash

# This script sets up and runs the dashboard application locally with HTTPS support

# Create a virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate the virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Run the application
echo "Starting the application with HTTPS support..."
echo "The application will be available at https://127.0.0.1:5000"
echo "Note: You may see a browser warning about the self-signed certificate. This is normal for local development."
echo "Press Ctrl+C to stop the application."
python app.py
