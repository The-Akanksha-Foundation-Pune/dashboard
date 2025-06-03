"""
Database initialization script for Python 3.6 compatibility.
Run this script to create all database tables defined in models.py.
"""
import os
from dotenv import load_dotenv
from flask import Flask
from models import db

# Load environment variables
load_dotenv()

# Create a minimal Flask app
app = Flask(__name__)

# Configure the app
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST', '127.0.0.1')
db_port = os.getenv('DB_PORT', 3306)
db_name = os.getenv('DB_NAME')

# Properly escape the password to handle special characters
import urllib.parse
escaped_password = urllib.parse.quote_plus(db_password)

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{db_user}:{escaped_password}@{db_host}:{db_port}/{db_name}"
print(f"Connecting to database: {db_host}:{db_port}/{db_name} as {db_user}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database with the app
db.init_app(app)

# Create all tables using the app context
with app.app_context():
    print("Creating database tables...")
    db.create_all()
    print("Database tables created successfully!")

if __name__ == '__main__':
    print("This script has been run directly.")
    print("Database tables should now be created in the database specified in your .env file.")
