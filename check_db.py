"""
Script to check the existing database structure.
"""
import os
import pymysql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection parameters
db_host = os.getenv('DB_HOST', '127.0.0.1')
db_port = int(os.getenv('DB_PORT', 3306))
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
db_name = os.getenv('DB_NAME')

# Connect to the database
try:
    conn = pymysql.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    print(f"Connected to database: {db_host}:{db_port}/{db_name} as {db_user}")
    
    # Get list of tables
    with conn.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print("\nTables in the database:")
        for table in tables:
            table_name = list(table.values())[0]
            print(f"- {table_name}")
            
            # Get table structure
            cursor.execute(f"DESCRIBE {table_name}")
            columns = cursor.fetchall()
            print(f"\nStructure of table '{table_name}':")
            for column in columns:
                print(f"  {column['Field']} - {column['Type']} - {column['Null']} - {column['Key']} - {column['Default']}")
            
            # Get foreign keys
            cursor.execute(f"""
                SELECT 
                    COLUMN_NAME, 
                    REFERENCED_TABLE_NAME, 
                    REFERENCED_COLUMN_NAME 
                FROM 
                    INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                WHERE 
                    TABLE_SCHEMA = '{db_name}' AND 
                    TABLE_NAME = '{table_name}' AND 
                    REFERENCED_TABLE_NAME IS NOT NULL
            """)
            foreign_keys = cursor.fetchall()
            if foreign_keys:
                print(f"\nForeign keys in table '{table_name}':")
                for fk in foreign_keys:
                    print(f"  {fk['COLUMN_NAME']} -> {fk['REFERENCED_TABLE_NAME']}.{fk['REFERENCED_COLUMN_NAME']}")
            print("\n" + "-" * 50)
    
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'conn' in locals():
        conn.close()
        print("Database connection closed.")
