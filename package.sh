#!/bin/bash

# Exit on error
set -e

echo "Packaging the application for deployment..."

# Create a deployment package
tar -czvf dashboard.tar.gz app.py models.py dashboard_routes.py demographics_routes.py requirements.txt .env static templates

echo "Package created: dashboard.tar.gz"
echo ""
echo "To deploy the application, follow these steps:"
echo ""
echo "1. Transfer the package to the server:"
echo "   scp -i ~/Downloads/ssh/id_rsa.pem dashboard.tar.gz webappor@190.92.174.28:/tmp/"
echo ""
echo "2. Connect to the server:"
echo "   ssh -i ~/Downloads/ssh/id_rsa.pem webappor@190.92.174.28"
echo ""
echo "3. Follow the instructions in deployment_guide.md to complete the deployment"
echo ""
echo "Packaging completed successfully!"
