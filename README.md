# Dashboard Application with Google OAuth

This is a Flask application with Google OAuth login using Flask-Dance and SQLAlchemy models for database management.

## Setup

1.  **Clone the repository (or ensure you have the files).**

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up Google API Credentials:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.
    *   Navigate to "APIs & Services" > "Credentials".
    *   Click "Create Credentials" > "OAuth client ID".
    *   Configure the OAuth consent screen if you haven't already. Select "External" user type for testing, add your email to test users.
    *   Choose "Web application" as the application type.
    *   Add an "Authorized JavaScript origin": `http://localhost:5000` (or your development URL).
    *   Add an "Authorized redirect URI": `http://localhost:5000/login/google/authorized` (matches the Flask-Dance default).
    *   Click "Create". You will get a **Client ID** and **Client Secret**.

4.  **Create a `.env` file:**
    In the project's root directory, create a file named `.env` and add your credentials:
    ```dotenv
    GOOGLE_OAUTH_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID
    GOOGLE_OAUTH_CLIENT_SECRET=YOUR_GOOGLE_CLIENT_SECRET
    # Required for session security:
    FLASK_SECRET_KEY=generate_a_strong_random_secret_key

    # Database configuration
    DB_HOST=127.0.0.1
    DB_PORT=3306
    DB_USER=your_database_user
    DB_PASSWORD=your_database_password
    DB_NAME=your_database_name
    OAUTHLIB_INSECURE_TRANSPORT=1  # Only for development
    ```
    Replace the placeholder values with your actual credentials. Generate a strong secret key for `FLASK_SECRET_KEY` (e.g., using `python -c 'import os; print(os.urandom(24).hex())'`).

## Running the Application

### Setting up a Virtual Environment (Python 3.6)

1. **Create a virtual environment:**
   ```bash
   python3.6 -m venv venv
   ```

2. **Activate the virtual environment:**
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Database Setup

1. **Initialize the database (Option 1 - Direct creation):**
   ```bash
   python init_db.py
   ```
   This will create all the necessary tables in your database.

2. **Initialize the database (Option 2 - Using migrations):**
   ```bash
   # Set the FLASK_APP environment variable
   export FLASK_APP=migrations.py  # On Windows: set FLASK_APP=migrations.py

   # Initialize the migrations repository
   flask db init

   # Create the initial migration
   flask db migrate -m "Initial migration"

   # Apply the migration to the database
   flask db upgrade
   ```
   This approach allows you to track changes to your database schema over time.

### Running the Application

1. **Make sure your `.env` file is correctly set up.**

2. **Run the Flask development server:**
   ```bash
   python app.py
   ```

3. **Open your web browser** and navigate to `http://localhost:5000`.

4. **Click the "Login with Google"** button and follow the prompts.

## Notes

*   This setup uses the Flask development server, which is not suitable for production.
*   For production, use a production-ready WSGI server like Gunicorn or uWSGI and configure HTTPS.
*   Ensure your Redirect URI in the Google Cloud Console exactly matches `http://localhost:5000/login/google/authorized` (or the equivalent if you change the port or `url_prefix`).
*   The application uses SQLAlchemy models that will automatically create database tables when deployed.
*   Python 3.6 compatibility has been ensured throughout the codebase.

## Production Deployment

1. **Set up your production database** and update the `.env` file with production credentials.

2. **Initialize the database** using one of these methods:
   - Simple method: Run the `init_db.py` script
   ```bash
   python init_db.py
   ```

   - Using migrations (recommended for production):
   ```bash
   export FLASK_APP=migrations.py
   flask db upgrade
   ```
   This will apply all migrations to your production database.

3. **Configure a production WSGI server** like Gunicorn:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

4. **Set up a reverse proxy** like Nginx to handle HTTPS and serve static files.
