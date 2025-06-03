# This script adds a second route to the get_attendance_pivot_data function
# to fix the issue with the URL not being found

import re

# Read the demographics_routes.py file
with open('demographics_routes.py', 'r') as f:
    content = f.read()

# Check if the second route is already added
if '@demographics_bp.route(\'/get_attendance_pivot_data\', methods=[\'POST\'])' not in content:
    # Add the second route
    content = content.replace(
        '@demographics_bp.route(\'/attendance_pivot\', methods=[\'POST\'])',
        '@demographics_bp.route(\'/attendance_pivot\', methods=[\'POST\'])\n@demographics_bp.route(\'/get_attendance_pivot_data\', methods=[\'POST\'])  # Add a second route with the function name'
    )

    # Write the modified content back to the file
    with open('demographics_routes.py', 'w') as f:
        f.write(content)
    
    print("Added second route to get_attendance_pivot_data function")
else:
    print("Second route already exists")

# Touch the restart.txt file to restart the application
import os
if os.path.exists('tmp'):
    try:
        with open('tmp/restart.txt', 'w') as f:
            f.write('')
        print("Touched tmp/restart.txt to restart the application")
    except Exception as e:
        print(f"Error touching tmp/restart.txt: {e}")
else:
    print("tmp directory not found")
