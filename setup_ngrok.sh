#!/bin/bash

# Exit on error
set -e

echo "Setting up ngrok for remote access..."

# Create directory for ngrok
mkdir -p ~/ngrok

# Download ngrok (Linux 64-bit version)
echo "Downloading ngrok..."
cd ~/ngrok
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz

# Extract ngrok
echo "Extracting ngrok..."
tar -xvzf ngrok-v3-stable-linux-amd64.tgz

# Make ngrok executable
chmod +x ngrok

# Create a configuration file for ngrok
echo "Configuring ngrok..."
cat > ~/ngrok/ngrok.yml << EOF
version: "2"
authtoken: "" # You'll need to add your authtoken here
region: us
tunnels:
  dashboard:
    proto: http
    addr: 5000
EOF

echo "Ngrok setup complete!"
echo ""
echo "IMPORTANT: You need to add your ngrok authtoken to the configuration file."
echo "1. Sign up for a free account at https://ngrok.com/"
echo "2. Get your authtoken from the ngrok dashboard"
echo "3. Add your authtoken to ~/ngrok/ngrok.yml"
echo ""
echo "To start ngrok and expose your application, run:"
echo "cd ~/ngrok && ./ngrok start dashboard --config=ngrok.yml"
echo ""
echo "Once ngrok is running, it will display a URL that you can use to access your application from anywhere."
