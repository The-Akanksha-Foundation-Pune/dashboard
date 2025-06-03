# Deployment Guide for Dashboard Application (No Sudo Access)

This guide will walk you through the steps to deploy the Dashboard application on an Ubuntu server without sudo access.

## Prerequisites

- Ubuntu server with SSH access
- SSH key file: `~/Downloads/ssh/id_rsa.pem`
- Server credentials: `webappor@190.92.174.28`
- No sudo access required

## Step 1: Prepare the Local Files

1. Make sure you have all the necessary files in your local directory:
   - app.py
   - models.py
   - dashboard_routes.py
   - demographics_routes.py
   - requirements.txt
   - .env
   - static/ directory
   - templates/ directory

2. Create a deployment package:
   ```bash
   tar -czvf dashboard.tar.gz app.py models.py dashboard_routes.py demographics_routes.py requirements.txt .env static templates
   ```

## Step 2: Connect to the Server

1. Connect to your server using SSH:
   ```bash
   ssh -i ~/Downloads/ssh/id_rsa.pem webappor@190.92.174.28
   ```

## Step 3: Prepare the Server Environment

1. Create application directories in your home directory:
   ```bash
   mkdir -p ~/dashboard
   mkdir -p ~/dashboard/logs
   ```

## Step 4: Transfer Files to the Server

1. Open a new terminal window (keep the SSH session open in the first window)

2. Transfer the deployment package to the server:
   ```bash
   scp -i ~/Downloads/ssh/id_rsa.pem dashboard.tar.gz webappor@190.92.174.28:~/dashboard/
   ```

## Step 5: Set Up the Application

1. Go back to the SSH session and navigate to the application directory:
   ```bash
   cd ~/dashboard
   ```

2. Extract the deployment package:
   ```bash
   tar -xzvf dashboard.tar.gz
   ```

3. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   pip install gunicorn
   ```

## Step 6: Create a Startup Script

1. Create a startup script:
   ```bash
   nano ~/dashboard/start.sh
   ```

2. Add the following content:
   ```bash
   #!/bin/bash

   # Change to the application directory
   cd ~/dashboard

   # Activate the virtual environment
   source venv/bin/activate

   # Start the application with Gunicorn
   gunicorn --bind 0.0.0.0:5000 --workers 4 app:app >> ~/dashboard/logs/app.log 2>&1
   ```

3. Make the script executable:
   ```bash
   chmod +x ~/dashboard/start.sh
   ```

## Step 7: Create a Systemd User Service (if available)

Some servers allow user-level systemd services even without sudo access. If this is available:

1. Create the systemd user directory if it doesn't exist:
   ```bash
   mkdir -p ~/.config/systemd/user
   ```

2. Create a service file:
   ```bash
   nano ~/.config/systemd/user/dashboard.service
   ```

3. Add the following content:
   ```ini
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
   ```

4. Enable and start the service:
   ```bash
   systemctl --user enable dashboard
   systemctl --user start dashboard
   ```

5. Check the status:
   ```bash
   systemctl --user status dashboard
   ```

## Step 8: Use Screen or tmux (Alternative to systemd)

If user-level systemd services are not available, you can use Screen or tmux:

1. Install Screen if not already available:
   ```bash
   # Check if screen is available
   which screen

   # If not available and you can't install it with sudo, you might need to ask the server admin to install it
   ```

2. Start a new Screen session:
   ```bash
   screen -S dashboard
   ```

3. Run the application:
   ```bash
   ~/dashboard/start.sh
   ```

4. Detach from the Screen session by pressing `Ctrl+A` followed by `D`.

5. To reattach to the session later:
   ```bash
   screen -r dashboard
   ```

## Step 9: Configure MySQL Database Connection

1. Update the .env file with the correct database credentials:
   ```bash
   nano ~/dashboard/.env
   ```

   Make sure the database URI is correct and points to the MySQL server you have access to.

## Step 10: Test the Application

1. If using systemd user service, check if the application is running:
   ```bash
   systemctl --user status dashboard
   ```

2. If using Screen, check if the Screen session is running:
   ```bash
   screen -ls
   ```

3. Check the application logs:
   ```bash
   tail -f ~/dashboard/logs/app.log
   ```

4. Access the application in a web browser by navigating to your server's IP address and port:
   ```
   http://190.92.174.28:5000
   ```

## Troubleshooting

If you encounter any issues:

1. Check the application logs:
   ```bash
   tail -f ~/dashboard/logs/app.log
   ```

2. Make sure the port 5000 is open and accessible:
   ```bash
   # Test if the port is in use
   netstat -tuln | grep 5000
   ```

3. If the port is blocked by a firewall, you may need to ask the server administrator to open it.

## Updating the Application

To update the application after making changes:

1. Transfer the updated files to the server
2. Restart the application:
   - If using systemd user service:
     ```bash
     systemctl --user restart dashboard
     ```
   - If using Screen:
     ```bash
     # Reattach to the screen session
     screen -r dashboard

     # Stop the application with Ctrl+C

     # Start it again
     ~/dashboard/start.sh

     # Detach from the screen session with Ctrl+A followed by D
     ```

## Backup and Restore

To backup the application:

1. Backup the application files:
   ```bash
   tar -czvf ~/dashboard_backup.tar.gz ~/dashboard
   ```

To restore from backup:

1. Restore the application files:
   ```bash
   tar -xzvf ~/dashboard_backup.tar.gz -C ~/
   ```

## Setting Up Ngrok for Internet Access

If you want to make your application accessible over the internet, you can use ngrok:

1. Run the ngrok setup script:
   ```bash
   cd ~/dashboard
   chmod +x setup_ngrok.sh
   ./setup_ngrok.sh
   ```

2. Sign up for a free account at https://ngrok.com/

3. Get your authtoken from the ngrok dashboard

4. Add your authtoken to the ngrok configuration file:
   ```bash
   nano ~/ngrok/ngrok.yml
   ```
   Replace the empty authtoken with your actual token:
   ```yaml
   authtoken: "your_actual_token_here"
   ```

5. Start your application with ngrok:
   ```bash
   cd ~/dashboard
   chmod +x start_with_ngrok.sh
   ./start_with_ngrok.sh
   ```

6. Ngrok will display a URL (like `https://abc123.ngrok.io`) that you can use to access your application from anywhere on the internet.

## Additional Notes

1. Since you don't have sudo access, you're limited to using ports above 1024. Port 5000 is a common choice for development servers.

2. If you need to run the application on port 80 (the default HTTP port), you'll need to ask the server administrator to set up a reverse proxy (like Nginx or Apache) to forward requests from port 80 to your application on port 5000.

3. For a more robust setup, consider asking the server administrator to:
   - Install and configure Nginx as a reverse proxy
   - Set up SSL/TLS certificates for HTTPS
   - Configure a proper process manager like Supervisor
   - Set up proper logging and monitoring

4. The free version of ngrok has some limitations:
   - The URL changes each time you restart ngrok
   - Limited to 40 connections per minute
   - Only one tunnel can be active at a time

   If you need more features, consider upgrading to a paid plan.
