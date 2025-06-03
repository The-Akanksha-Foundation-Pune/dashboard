#!/bin/bash

# Exit on error
set -e

echo "Packaging the application for deployment (no sudo access)..."

# Create a start script
cat > start.sh << 'EOF'
#!/bin/bash

# Change to the application directory
cd ~/dashboard

# Activate the virtual environment
source venv/bin/activate

# Start the application with Gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 app:app >> ~/dashboard/logs/app.log 2>&1
EOF

# Create a deployment package including the start script and ngrok scripts
tar -czvf dashboard.tar.gz app.py models.py dashboard_routes.py demographics_routes.py requirements.txt .env static templates start.sh deploy_no_sudo.sh setup_ngrok.sh start_with_ngrok.sh

echo "Package created: dashboard.tar.gz"
echo ""
echo "To deploy the application, follow these steps:"
echo ""
echo "1. Transfer the package to the server:"
echo "   scp -i ~/Downloads/ssh/id_rsa.pem dashboard.tar.gz webappor@190.92.174.28:~/"
echo ""
echo "2. Connect to the server:"
echo "   ssh -i ~/Downloads/ssh/id_rsa.pem webappor@190.92.174.28"
echo ""
echo "3. Follow the instructions in deployment_guide_no_sudo.md to complete the deployment"
echo ""
echo "Packaging completed successfully!"
