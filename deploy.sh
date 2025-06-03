#!/bin/bash

# Exit on error
set -e

# Update system packages
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install required system packages
echo "Installing required system packages..."
sudo apt-get install -y python3-pip python3-venv nginx supervisor

# Create application directory if it doesn't exist
echo "Setting up application directory..."
APP_DIR=/var/www/dashboard
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Create and activate virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv $APP_DIR/venv
source $APP_DIR/venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt
pip install gunicorn

# Configure Nginx
echo "Configuring Nginx..."
sudo tee /etc/nginx/sites-available/dashboard <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable the Nginx site
sudo ln -sf /etc/nginx/sites-available/dashboard /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Configure Supervisor to manage the application
echo "Configuring Supervisor..."
sudo tee /etc/supervisor/conf.d/dashboard.conf <<EOF
[program:dashboard]
directory=/var/www/dashboard
command=/var/www/dashboard/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app
autostart=true
autorestart=true
stderr_logfile=/var/log/dashboard/dashboard.err.log
stdout_logfile=/var/log/dashboard/dashboard.out.log
user=$USER
EOF

# Create log directory
sudo mkdir -p /var/log/dashboard
sudo chown -R $USER:$USER /var/log/dashboard

# Restart services
echo "Restarting services..."
sudo systemctl restart nginx
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart dashboard

echo "Deployment completed successfully!"
