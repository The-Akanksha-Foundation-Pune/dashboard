#!/usr/bin/env python3
"""
Script to import SQL data into a specific table in the database.
"""
import os
import sys
import pymysql
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database connection parameters from environment variables
db_config = {
    'host': os.getenv('DB_HOST', '190.92.174.212'),
    'user': os.getenv('DB_USER', 'webappor_IT'),
    'password': os.getenv('DB_PASSWORD', 'Motoming@123'),
    'db': os.getenv('DB_NAME', 'webappor_AFDW'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def execute_sql_file(file_path):
    """Execute SQL commands from a file."""
    # Check if file exists
    if not os.path.isfile(file_path):
        print(f"Error: File {file_path} does not exist.")
        return False

    # Read SQL file
    with open(file_path, 'r') as f:
        sql_commands = f.read()

    # Connect to the database
    try:
        connection = pymysql.connect(**db_config)
        print(f"Connected to database {db_config['db']} on {db_config['host']}")
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return False

    try:
        with connection.cursor() as cursor:
            # Execute SQL commands
            print(f"Executing SQL commands from {file_path}...")
            cursor.execute(sql_commands)

        # Commit changes
        connection.commit()
        print(f"Successfully imported data from {file_path}")
        return True

    except Exception as e:
        print(f"Error executing SQL commands: {e}")
        return False

    finally:
        connection.close()
        print("Database connection closed.")

def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python import_sql.py <path_to_sql_file>")
        return

    file_path = sys.argv[1]
    execute_sql_file(file_path)

if __name__ == "__main__":
    main()
