#!/bin/bash

# Exit on error
set -e

# Configuration
SSH_KEY="~/Downloads/ssh/id_rsa.pem"
SERVER_USER="webappor"
SERVER_IP="190.92.174.28"
REMOTE_DIR="/var/www/dashboard"

# Make sure the SSH key has the right permissions
chmod 600 $SSH_KEY

# Create a temporary directory for the files to transfer
echo "Creating temporary directory for files..."
TEMP_DIR=$(mktemp -d)

# Copy all necessary files to the temporary directory
echo "Copying files to temporary directory..."
cp -r app.py models.py dashboard_routes.py demographics_routes.py requirements.txt .env static templates deploy.sh $TEMP_DIR/

# Create the remote directory if it doesn't exist
echo "Creating remote directory..."
ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP "sudo mkdir -p $REMOTE_DIR && sudo chown $SERVER_USER:$SERVER_USER $REMOTE_DIR"

# Transfer files to the server
echo "Transferring files to server..."
scp -i $SSH_KEY -r $TEMP_DIR/* $SERVER_USER@$SERVER_IP:$REMOTE_DIR/

# Make the deploy script executable
echo "Making deploy script executable..."
ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP "chmod +x $REMOTE_DIR/deploy.sh"

# Run the deploy script
echo "Running deploy script on server..."
ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP "$REMOTE_DIR/deploy.sh"

# Clean up
echo "Cleaning up temporary directory..."
rm -rf $TEMP_DIR

echo "Transfer completed successfully!"
