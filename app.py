import os
import pymysql
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, render_template, session, flash, request, jsonify
from flask_migrate import Migrate
from models import db, UserRole

# Load environment variables from .env file first (if it exists)
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# --- Configuration Loading ---
# Set Flask configurations from environment variables
# Secret key is crucial for sessions and Flask-Dance
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
# Google OAuth credentials
app.config["GOOGLE_OAUTH_CLIENT_ID"] = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
# Database credentials
app.config['DB_HOST'] = os.getenv('DB_HOST', '127.0.0.1') # Default to localhost
app.config['DB_PORT'] = int(os.getenv('DB_PORT', 3306)) # Default to 3306
app.config['DB_USER'] = os.getenv('DB_USER')
app.config['DB_PASSWORD'] = os.getenv('DB_PASSWORD')
app.config['DB_NAME'] = os.getenv('DB_NAME')

# SQLAlchemy configuration
db_user = app.config['DB_USER']
db_password = app.config['DB_PASSWORD']
db_host = app.config['DB_HOST']
db_port = app.config['DB_PORT']
db_name = app.config['DB_NAME']

# Properly escape the password to handle special characters
import urllib.parse
escaped_password = urllib.parse.quote_plus(db_password)

# Configure SQLAlchemy with connection pooling settings
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{db_user}:{escaped_password}@{db_host}:{db_port}/{db_name}"
print(f"Database URI: mysql+pymysql://{db_user}:****@{db_host}:{db_port}/{db_name}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure connection pooling to handle the max_user_connections limit
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,  # Maximum number of connections to keep in the pool
    'max_overflow': 5,  # Maximum number of connections to create above pool_size
    'pool_timeout': 30,  # Timeout for getting a connection from the pool
    'pool_recycle': 1800,  # Recycle connections after 30 minutes
    'pool_pre_ping': True  # Check connection validity before using it
}

# Allow insecure transport for local development (HTTP), remove/disable in production (HTTPS)
if os.getenv('FLASK_ENV') == 'development':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.config['DEBUG'] = True
else:
    app.config['DEBUG'] = False

# --- Configuration Validation ---
# Ensure critical configs are loaded successfully
if not app.config.get("SECRET_KEY"):
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
    if not app.config.get("SECRET_KEY"):
        raise ValueError("SECRET_KEY must be set via FLASK_SECRET_KEY environment variable or .env file")
if not app.config.get("GOOGLE_OAUTH_CLIENT_ID") or not app.config.get("GOOGLE_OAUTH_CLIENT_SECRET"):
    app.config["GOOGLE_OAUTH_CLIENT_ID"] = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    if not app.config.get("GOOGLE_OAUTH_CLIENT_ID") or not app.config.get("GOOGLE_OAUTH_CLIENT_SECRET"):
        raise ValueError("GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set via environment variables or .env file")
if not app.config.get('DB_USER') or not app.config.get('DB_PASSWORD') or not app.config.get('DB_NAME'):
    raise ValueError("DB_USER, DB_PASSWORD, and DB_NAME must be set via environment variables or .env file")

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')

# --- Database Connection Helper ---
def get_db_connection():
    """Establishes a connection to the database."""
    try:
        connection = pymysql.connect(
            host=app.config['DB_HOST'],
            port=app.config['DB_PORT'],
            user=app.config['DB_USER'],
            password=app.config['DB_PASSWORD'],
            database=app.config['DB_NAME'],
            cursorclass=pymysql.cursors.DictCursor, # Return rows as dictionaries
            charset='utf8mb4'
        )
        app.logger.info("Database connection established successfully.") # Log success
        return connection
    except pymysql.Error as e:
        app.logger.error(f"Database connection failed: {e}") # Use Flask logger
        return None

# Initialize SQLAlchemy with the Flask app
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# --- Blueprints --- #
# Import and register AFTER app and db connection are defined
from demographics_routes import demographics_bp
from dashboard_routes import dashboard_bp
from assessment_routes_optimized import assessment_bp
app.register_blueprint(demographics_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(assessment_bp)

# --- OAuth Setup --- #
# Set up session for our simple OAuth implementation
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-key-for-testing')

# Use Flask's built-in session
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour

# Import our simple OAuth implementation
from simple_oauth import get_google_auth_url, get_google_token, get_user_info

@app.route("/")
def index():
    """Home page."""
    logged_in = 'user_email' in session
    user_info = None
    if logged_in:
        user_info = {
            'email': session.get('user_email'),
            'name': session.get('user_name'),
            'picture': session.get('user_picture')
        }

    return render_template("index.html", logged_in=logged_in, user_info=user_info)

@app.route("/login/google")
def login():
    """Redirect to Google OAuth login page."""
    return redirect(get_google_auth_url())

@app.route("/login/google/authorized")
def authorized():
    """Handle the OAuth callback from Google."""
    code = request.args.get('code')
    if not code:
        flash("Authentication failed. Please try again.", "danger")
        return redirect(url_for("index"))

    # Exchange code for token
    token = get_google_token(code)
    if not token:
        flash("Failed to get access token. Please try again.", "danger")
        return redirect(url_for("index"))

    # Get user info
    user_info = get_user_info(token)
    if not user_info:
        flash("Failed to get user info. Please try again.", "danger")
        return redirect(url_for("index"))

    user_email = user_info.get("email")
    user_name = user_info.get("name")
    user_picture = user_info.get("picture")

    if not user_email:
        flash("Could not retrieve email from Google. Login aborted.", "danger")
        app.logger.error("Email missing from Google response in /authorized.")
        return redirect(url_for("index"))

    # Check user against database
    app.logger.info(f"Checking database for user: {user_email}")
    db_user_obj = UserRole.query.filter_by(email=user_email).first()
    app.logger.info(f"DB query result: {db_user_obj}")

    if db_user_obj:
        # User authorized! Update stats and store info in session
        app.logger.info("User found in DB. Updating stats...")
        try:
            # Use timezone-aware UTC time
            current_time = datetime.now(pytz.utc)
            db_user_obj.last_login = current_time
            db_user_obj.login_count += 1
            db.session.commit()
        except Exception as db_err:
            db.session.rollback()
            app.logger.error(f"Database error updating user stats: {db_err}")
            flash("Failed to update user stats. Please try again.", "danger")
            return redirect(url_for("index"))

        # Store relevant info in session for this user
        session["user_email"] = db_user_obj.email
        session["user_name"] = user_name
        session["user_role"] = db_user_obj.role
        session["user_school"] = db_user_obj.school
        session["user_picture"] = user_picture
        session["access_token"] = token.get("access_token")
        session.permanent = True

        app.logger.info(f"User {user_email} authorized. Redirecting to demographics.")
        return redirect(url_for("demographics.view"))
    else:
        # User email not found in the database - Unauthorized
        app.logger.warning(f"Unauthorized access attempt: Email '{user_email}' not in user_roles.")
        flash("Access Denied: Your email address is not authorized for this application.", "danger")
        return redirect(url_for("index"))

@app.route("/profile")
def profile():
    """User profile page - Redirects to demographics page."""
    if "user_email" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("index"))

    # Redirect to demographics page
    return redirect(url_for("demographics.view"))

@app.route("/dashboard")
@app.route("/dashboard/")
def dashboard():
    """Redirect to the dashboard blueprint."""
    return redirect(url_for("dashboard.view"))

@app.route("/attendance")
@app.route("/attendance/")
def attendance():
    """Attendance page with coming soon message."""
    if "user_email" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("index"))

    return render_template("attendance.html",
                          active_page="attendance",
                          name=session.get("user_name"),
                          email=session.get("user_email"),
                          picture=session.get("user_picture"),
                          role=session.get("user_role"),
                          school=session.get("user_school"))

@app.route("/reports")
@app.route("/reports/")
def reports():
    """Reports page with coming soon message."""
    if "user_email" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("index"))

    return render_template("reports.html",
                          active_page="reports",
                          name=session.get("user_name"),
                          email=session.get("user_email"),
                          picture=session.get("user_picture"),
                          role=session.get("user_role"),
                          school=session.get("user_school"))

@app.route("/logout")
def logout():
    """Logs the user out."""
    session.clear()  # Clear the entire session
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("index"))

# Create database tables if they don't exist
# Note: In Flask 2.0+, @app.before_first_request is deprecated
# We'll use the with app.app_context() approach instead

if __name__ == "__main__":
    # Important: Use HTTPS in production. For local dev, Flask dev server is fine.
    # Ensure debug=False in production
    try:
        with app.app_context():
            # Create tables when the app starts
            db.create_all()
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")
        print("Running without database connection. Some features may not work.")

    # Run with SSL for local HTTPS development
    # Note: This uses Flask's built-in SSL support which is not suitable for production
    # For production, use a proper WSGI server with SSL termination
    app.run(debug=True, port=5000, ssl_context='adhoc')
