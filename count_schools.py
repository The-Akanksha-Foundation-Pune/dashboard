from models import db, StudentAssessmentData
from app import app

def count_unique_schools():
    with app.app_context():
        # Query unique schools
        unique_schools = db.session.query(StudentAssessmentData.school_name).distinct().all()
        
        # Filter out None values and get a clean list
        schools = sorted([s[0] for s in unique_schools if s[0]])
        
        # Print the results
        print(f'Total unique schools: {len(schools)}')
        print('\nSchools:')
        for school in schools:
            print(f'- {school}')

if __name__ == "__main__":
    count_unique_schools()
