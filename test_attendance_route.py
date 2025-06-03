"""
Test script to check if the attendance_pivot route is working correctly.
"""
import requests
import json

# URL for the attendance_pivot route
url = "http://127.0.0.1:5000/demographics/get_attendance_pivot_data"

# Test data
data = {
    "academic_year": "All",
    "month": "All",
    "city": "All",
    "gender": "All"
}

# Make the request
response = requests.post(url, json=data)

# Print the response
print(f"Status code: {response.status_code}")
print(f"Headers: {response.headers}")

# Try to parse the response as JSON
try:
    json_response = response.json()
    print("JSON response:")
    print(json.dumps(json_response, indent=2))
except Exception as e:
    print(f"Error parsing JSON: {e}")
    print("Response text:")
    print(response.text[:500])  # Print first 500 characters
