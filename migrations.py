"""
Database migration script for Python 3.6 compatibility.
This script helps manage database migrations using Flask-Migrate.
"""
import os
from dotenv import load_dotenv
from flask import Flask
from flask_migrate import Migrate
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
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database with the app
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

if __name__ == '__main__':
    print("This script is used with Flask-Migrate commands.")
    print("Usage examples:")
    print("  flask db init     - Initialize migrations repository")
    print("  flask db migrate  - Generate migration script")
    print("  flask db upgrade  - Apply migrations to the database")
    print("  flask db --help   - Show all available commands")
