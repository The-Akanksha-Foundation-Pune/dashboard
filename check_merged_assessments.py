from app import app, db
from models import AllAssessments
import pandas as pd

with app.app_context():
    # Get total count
    total_count = AllAssessments.query.count()
    print(f"Total records in all_assessments: {total_count}")
    
    # Get count by assessment type
    std_count = AllAssessments.query.filter_by(assessment_type='standardized').count()
    non_std_count = AllAssessments.query.filter_by(assessment_type='non-standardized').count()
    print(f"Standardized assessments: {std_count}")
    print(f"Non-standardized assessments: {non_std_count}")
    
    # Get a sample of each type
    print("\n=== Sample Standardized Assessment ===")
    std_sample = AllAssessments.query.filter_by(assessment_type='standardized').first()
    if std_sample:
        for column in AllAssessments.__table__.columns:
            value = getattr(std_sample, column.name)
            print(f"  {column.name}: {value}")
    
    print("\n=== Sample Non-Standardized Assessment ===")
    non_std_sample = AllAssessments.query.filter_by(assessment_type='non-standardized').first()
    if non_std_sample:
        for column in AllAssessments.__table__.columns:
            value = getattr(non_std_sample, column.name)
            print(f"  {column.name}: {value}")
    
    # Get unique academic years
    academic_years = db.session.query(AllAssessments.academic_year).distinct().all()
    print(f"\nAcademic Years: {[year[0] for year in academic_years if year[0]]}")
    
    # Get unique exam types
    exam_types = db.session.query(AllAssessments.exam_type).distinct().all()
    print(f"Exam Types: {[type[0] for type in exam_types if type[0]]}")
    
    # Get unique subjects (limited to 10)
    subjects = db.session.query(AllAssessments.subject_name).distinct().limit(10).all()
    print(f"Sample Subjects: {[subj[0] for subj in subjects if subj[0]]}")
    
    # Get unique schools (limited to 10)
    schools = db.session.query(AllAssessments.school_name).distinct().limit(10).all()
    print(f"Sample Schools: {[school[0] for school in schools if school[0]]}")
    
    # Get unique grades (limited to 20)
    grades = db.session.query(AllAssessments.grade_name).distinct().limit(20).all()
    print(f"Sample Grades: {[grade[0] for grade in grades if grade[0]]}")
