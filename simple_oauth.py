"""
A simple OAuth implementation for Google authentication.
This bypasses Flask-Dance to avoid the state management issues.
"""
import os
import requests
from flask import redirect, request, session, url_for
from urllib.parse import urlencode

# Load environment variables
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')

# The redirect URI is now dynamically generated in get_google_auth_url
# and get_google_token to ensure it matches the current server scheme (HTTP/HTTPS)

# Google OAuth endpoints
AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'
TOKEN_URI = 'https://oauth2.googleapis.com/token'
USER_INFO_URI = 'https://www.googleapis.com/oauth2/v2/userinfo'

def get_google_auth_url():
    """Generate the Google OAuth authorization URL."""
    # Use url_for to dynamically generate the redirect URI
    redirect_uri = url_for('authorized', _external=True)
    
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'scope': 'openid email profile',
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent'
    }
    return f"{AUTH_URI}?{urlencode(params)}"

def get_google_token(code):
    """Exchange authorization code for access token."""
    # Use url_for to dynamically generate the redirect URI
    redirect_uri = url_for('authorized', _external=True)

    data = {
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'code': code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }
    response = requests.post(TOKEN_URI, data=data)
    if response.status_code == 200:
        return response.json()
    return None

def get_user_info(token):
    """Get user info from Google API."""
    headers = {'Authorization': f"Bearer {token['access_token']}"}
    response = requests.get(USER_INFO_URI, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None
