# Deployment Guide for Dashboard Application

This guide will walk you through the steps to deploy the Dashboard application on an Ubuntu server.

## Prerequisites

- Ubuntu server with SSH access
- SSH key file: `~/Downloads/ssh/id_rsa.pem`
- Server credentials: `webappor@190.92.174.28`

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

## Step 3: Prepare the Server

1. Update the system packages:
   ```bash
   sudo apt-get update
   sudo apt-get upgrade -y
   ```

2. Install required system packages:
   ```bash
   sudo apt-get install -y python3-pip python3-venv nginx supervisor
   ```

3. Create the application directory:
   ```bash
   sudo mkdir -p /var/www/dashboard
   sudo chown webappor:webappor /var/www/dashboard
   ```

## Step 4: Transfer Files to the Server

1. Open a new terminal window (keep the SSH session open in the first window)

2. Transfer the deployment package to the server:
   ```bash
   scp -i ~/Downloads/ssh/id_rsa.pem dashboard.tar.gz webappor@190.92.174.28:/var/www/dashboard/
   ```

## Step 5: Set Up the Application

1. Go back to the SSH session and navigate to the application directory:
   ```bash
   cd /var/www/dashboard
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

## Step 6: Configure Nginx

1. Create an Nginx configuration file:
   ```bash
   sudo nano /etc/nginx/sites-available/dashboard
   ```

2. Add the following configuration:
   ```nginx
   server {
       listen 80;
       server_name _;

       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

3. Enable the site and remove the default site:
   ```bash
   sudo ln -sf /etc/nginx/sites-available/dashboard /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default
   ```

4. Test the Nginx configuration:
   ```bash
   sudo nginx -t
   ```

5. Restart Nginx:
   ```bash
   sudo systemctl restart nginx
   ```

## Step 7: Configure Supervisor

1. Create a Supervisor configuration file:
   ```bash
   sudo nano /etc/supervisor/conf.d/dashboard.conf
   ```

2. Add the following configuration:
   ```ini
   [program:dashboard]
   directory=/var/www/dashboard
   command=/var/www/dashboard/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app
   autostart=true
   autorestart=true
   stderr_logfile=/var/log/dashboard/dashboard.err.log
   stdout_logfile=/var/log/dashboard/dashboard.out.log
   user=webappor
   ```

3. Create the log directory:
   ```bash
   sudo mkdir -p /var/log/dashboard
   sudo chown -R webappor:webappor /var/log/dashboard
   ```

4. Update Supervisor and start the application:
   ```bash
   sudo supervisorctl reread
   sudo supervisorctl update
   sudo supervisorctl start dashboard
   ```

## Step 8: Configure MySQL Database

1. Install MySQL if not already installed:
   ```bash
   sudo apt-get install -y mysql-server
   ```

2. Secure the MySQL installation:
   ```bash
   sudo mysql_secure_installation
   ```

3. Create a database and user:
   ```bash
   sudo mysql -e "CREATE DATABASE AFDW;"
   sudo mysql -e "CREATE USER 'root'@'127.0.0.1' IDENTIFIED BY 'your_password';"
   sudo mysql -e "GRANT ALL PRIVILEGES ON AFDW.* TO 'root'@'127.0.0.1';"
   sudo mysql -e "FLUSH PRIVILEGES;"
   ```

4. Update the .env file with the correct database credentials:
   ```bash
   nano .env
   ```

## Step 9: Test the Application

1. Check if the application is running:
   ```bash
   sudo supervisorctl status dashboard
   ```

2. Check the application logs:
   ```bash
   tail -f /var/log/dashboard/dashboard.out.log
   ```

3. Access the application in a web browser by navigating to your server's IP address:
   ```
   http://190.92.174.28
   ```

## Troubleshooting

If you encounter any issues, check the following logs:

1. Application logs:
   ```bash
   tail -f /var/log/dashboard/dashboard.out.log
   tail -f /var/log/dashboard/dashboard.err.log
   ```

2. Nginx logs:
   ```bash
   tail -f /var/log/nginx/access.log
   tail -f /var/log/nginx/error.log
   ```

3. Supervisor logs:
   ```bash
   tail -f /var/log/supervisor/supervisord.log
   ```

## Updating the Application

To update the application after making changes:

1. Transfer the updated files to the server
2. Restart the application:
   ```bash
   sudo supervisorctl restart dashboard
   ```

## Backup and Restore

To backup the application:

1. Backup the application files:
   ```bash
   tar -czvf /tmp/dashboard_backup.tar.gz /var/www/dashboard
   ```

2. Backup the database:
   ```bash
   mysqldump -u root -p AFDW > /tmp/afdw_backup.sql
   ```

To restore from backup:

1. Restore the application files:
   ```bash
   tar -xzvf /tmp/dashboard_backup.tar.gz -C /
   ```

2. Restore the database:
   ```bash
   mysql -u root -p AFDW < /tmp/afdw_backup.sql
   ```
