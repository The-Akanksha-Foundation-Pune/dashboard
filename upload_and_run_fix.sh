#!/bin/bash

# Upload the fix script to the server
scp -i ~/Downloads/ssh/id_rsa.pem fix_routes.py webappor@190.92.174.28:~/dashboard.webapporbit.com/

# Run the fix script on the server
ssh -i ~/Downloads/ssh/id_rsa.pem webappor@190.92.174.28 "cd ~/dashboard.webapporbit.com && python fix_routes.py"
