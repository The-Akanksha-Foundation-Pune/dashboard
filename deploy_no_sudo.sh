#!/bin/bash

# Exit on error
set -e

echo "Deploying the application (no sudo access)..."

# Create application directories
mkdir -p ~/dashboard
mkdir -p ~/dashboard/logs

# Move to the dashboard directory
cd ~/dashboard

# Extract the deployment package if it exists in the home directory
if [ -f ~/dashboard.tar.gz ]; then
    tar -xzvf ~/dashboard.tar.gz
    echo "Extracted dashboard.tar.gz"
else
    echo "Error: dashboard.tar.gz not found in home directory"
    exit 1
fi

# Make the start script executable
chmod +x start.sh

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the required Python packages
pip install -r requirements.txt
pip install gunicorn

# Create a systemd user service if possible
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/dashboard.service << 'EOF'
[Unit]
Description=Dashboard Application
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/dashboard
ExecStart=%h/dashboard/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 app:app
Restart=always

[Install]
WantedBy=default.target
EOF

# Try to enable and start the service
echo "Attempting to enable and start the systemd user service..."
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user enable dashboard
    systemctl --user start dashboard
    systemctl --user status dashboard
    echo "Systemd user service started successfully"
else
    echo "Systemd not available. Using Screen instead..."
    
    # Check if Screen is available
    if command -v screen >/dev/null 2>&1; then
        # Start a new Screen session
        screen -dmS dashboard ./start.sh
        echo "Started application in a Screen session"
        echo "To attach to the session, run: screen -r dashboard"
    else
        echo "Screen not available. Starting the application directly..."
        echo "The application will stop when you close the terminal."
        echo "Press Ctrl+C to stop the application."
        ./start.sh
    fi
fi

echo "Deployment completed successfully!"
echo ""
echo "Your application should now be running on port 5000."
echo "Access it at: http://190.92.174.28:5000"
echo ""
echo "To check the logs, run: tail -f ~/dashboard/logs/app.log"
