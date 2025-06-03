from app import app, db
import sqlalchemy as sa

with app.app_context():
    inspector = sa.inspect(db.engine)
    tables = inspector.get_table_names()
    
    print("Database Tables:")
    for table in tables:
        print(f"Table: {table}")
        columns = inspector.get_columns(table)
        print("  Columns:")
        for column in columns:
            print(f"    {column['name']} ({column['type']})")
        print()
