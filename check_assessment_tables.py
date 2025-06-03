from app import app, db
from models import StudentAssessmentData, NonStandardisedAssessment
import pandas as pd

with app.app_context():
    # Check StudentAssessmentData
    print("=== StudentAssessmentData Table ===")
    try:
        # Get column names
        columns = [column.name for column in StudentAssessmentData.__table__.columns]
        print(f"Columns: {columns}")

        # Get a sample record (limit query to avoid timeout)
        sample = StudentAssessmentData.query.limit(1).first()
        if sample:
            print("\nSample record found")
            for column in columns:
                value = getattr(sample, column)
                print(f"  {column}: {value}")
        else:
            print("No records found in StudentAssessmentData")
    except Exception as e:
        print(f"Error querying StudentAssessmentData: {e}")

    # Check NonStandardisedAssessment
    print("\n\n=== NonStandardisedAssessment Table ===")
    try:
        # Get column names
        columns = [column.name for column in NonStandardisedAssessment.__table__.columns]
        print(f"Columns: {columns}")

        # Get a sample record (limit query to avoid timeout)
        sample = NonStandardisedAssessment.query.limit(1).first()
        if sample:
            print("\nSample record found")
            for column in columns:
                value = getattr(sample, column)
                print(f"  {column}: {value}")
        else:
            print("No records found in NonStandardisedAssessment")
    except Exception as e:
        print(f"Error querying NonStandardisedAssessment: {e}")
