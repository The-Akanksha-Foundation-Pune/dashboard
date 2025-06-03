#!/bin/bash

# Exit on error
set -e

# Configuration
SSH_KEY="~/Downloads/ssh/id_rsa.pem"
SERVER_USER="webappor"
SERVER_IP="190.92.174.28"
PASSPHRASE="Motoming@123"

echo "Starting deployment process..."

# Create a temporary expect script to handle the passphrase
cat > /tmp/ssh_expect.exp << EOF
#!/usr/bin/expect -f
spawn scp -i $SSH_KEY dashboard.tar.gz $SERVER_USER@$SERVER_IP:~/
expect "Enter passphrase for key"
send "$PASSPHRASE\r"
expect eof
EOF

# Make the expect script executable
chmod +x /tmp/ssh_expect.exp

# Run the expect script to transfer the file
echo "Transferring files to server..."
/tmp/ssh_expect.exp

# Create another expect script for SSH commands
cat > /tmp/ssh_commands.exp << EOF
#!/usr/bin/expect -f
spawn ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP
expect "Enter passphrase for key"
send "$PASSPHRASE\r"
expect "$SERVER_USER@"
send "mkdir -p ~/dashboard ~/dashboard/logs\r"
expect "$SERVER_USER@"
send "mv ~/dashboard.tar.gz ~/dashboard/\r"
expect "$SERVER_USER@"
send "cd ~/dashboard\r"
expect "$SERVER_USER@"
send "tar -xzvf dashboard.tar.gz\r"
expect "$SERVER_USER@"
send "chmod +x start.sh deploy_no_sudo.sh\r"
expect "$SERVER_USER@"
send "./deploy_no_sudo.sh\r"
expect "$SERVER_USER@"
send "exit\r"
expect eof
EOF

# Make the expect script executable
chmod +x /tmp/ssh_commands.exp

# Run the expect script to execute commands on the server
echo "Executing deployment commands on server..."
/tmp/ssh_commands.exp

# Clean up
rm /tmp/ssh_expect.exp /tmp/ssh_commands.exp

echo "Deployment process completed!"
echo "Your application should now be accessible at: http://$SERVER_IP:5000"
