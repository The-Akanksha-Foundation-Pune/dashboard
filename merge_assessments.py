from app import app, db
from models import StudentAssessmentData, NonStandardisedAssessment, AllAssessments
from datetime import datetime
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_all_assessments_table():
    """Create the all_assessments table if it doesn't exist."""
    with app.app_context():
        try:
            # Check if table exists
            inspector = sa.inspect(db.engine)
            if 'all_assessments' not in inspector.get_table_names():
                # Create the table
                AllAssessments.__table__.create(db.engine)
                logger.info("Created all_assessments table")
            else:
                logger.info("all_assessments table already exists")
        except Exception as e:
            logger.error(f"Error creating all_assessments table: {e}")
            raise

def convert_date_format(date_str):
    """Convert date string to datetime object."""
    if not date_str:
        return None
    
    try:
        # Try different date formats
        formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        # If none of the formats work, return None
        logger.warning(f"Could not parse date: {date_str}")
        return None
    except Exception as e:
        logger.error(f"Error converting date {date_str}: {e}")
        return None

def merge_assessments():
    """Merge data from both assessment tables into all_assessments."""
    with app.app_context():
        try:
            # First, clear the all_assessments table
            db.session.query(AllAssessments).delete()
            db.session.commit()
            logger.info("Cleared all_assessments table")
            
            # Process standardized assessments
            logger.info("Processing standardized assessments...")
            std_count = 0
            
            # Process in batches to avoid memory issues
            batch_size = 1000
            offset = 0
            
            while True:
                std_assessments = StudentAssessmentData.query.limit(batch_size).offset(offset).all()
                if not std_assessments:
                    break
                
                for assessment in std_assessments:
                    new_assessment = AllAssessments(
                        assessment_type='standardized',
                        obtained_marks=assessment.obtained_marks,
                        subject_name=assessment.subject_name,
                        school_name=assessment.school_name,
                        percentage=assessment.percentage,
                        grade_name=assessment.grade_name,
                        assessment_id=assessment.assessment_id,
                        student_id=assessment.student_id,
                        course_name=assessment.course_name,
                        competency_level_name=assessment.competency_level_name,
                        division_name=assessment.division_name,
                        assessment_date=assessment.assessmentDate,
                        question_name=assessment.question_name,
                        student_name=assessment.student_name,
                        gender=assessment.gender,
                        present_absent=assessment.present_absent,
                        max_marks=assessment.max_marks,
                        academic_year=assessment.academic_year,
                        exam_type=assessment.assessment_type,
                        unique_key=assessment.student_assessment_id_unique_key,
                        source_table='student_assessment_data'
                    )
                    db.session.add(new_assessment)
                    std_count += 1
                
                db.session.commit()
                logger.info(f"Processed {std_count} standardized assessments so far")
                offset += batch_size
            
            # Process non-standardized assessments
            logger.info("Processing non-standardized assessments...")
            non_std_count = 0
            offset = 0
            
            while True:
                non_std_assessments = NonStandardisedAssessment.query.limit(batch_size).offset(offset).all()
                if not non_std_assessments:
                    break
                
                for assessment in non_std_assessments:
                    # Convert date string to date object
                    assessment_date = convert_date_format(assessment.assessment_date)
                    
                    new_assessment = AllAssessments(
                        assessment_type='non-standardized',
                        obtained_marks=float(assessment.obtained_marks) if assessment.obtained_marks is not None else None,
                        subject_name=assessment.subject_name,
                        school_name=assessment.school_name,
                        percentage=assessment.percentage,
                        grade_name=assessment.grade_name,
                        assessment_id=assessment.assessment_id,
                        student_id=assessment.student_id,
                        course_name=assessment.course_name,
                        competency_level_name=assessment.description,  # Map description to competency_level_name
                        division_name=assessment.division_name,
                        assessment_date=assessment_date,
                        question_name=assessment.question_name,
                        student_name=assessment.student_name,
                        gender=assessment.gender,
                        present_absent=assessment.present_absent,
                        max_marks=assessment.max_marks,
                        academic_year=assessment.academic_year,
                        exam_type=assessment.assessment_type,
                        unique_key=assessment.assessment_id2,
                        source_table='non_standardised_assessment'
                    )
                    db.session.add(new_assessment)
                    non_std_count += 1
                
                db.session.commit()
                logger.info(f"Processed {non_std_count} non-standardized assessments so far")
                offset += batch_size
            
            logger.info(f"Merged {std_count} standardized and {non_std_count} non-standardized assessments")
            
            # Create indexes for better performance
            try:
                with db.engine.connect() as conn:
                    conn.execute(sa.text("CREATE INDEX idx_all_assessments_student_id ON all_assessments (student_id)"))
                    conn.execute(sa.text("CREATE INDEX idx_all_assessments_school_name ON all_assessments (school_name)"))
                    conn.execute(sa.text("CREATE INDEX idx_all_assessments_grade_name ON all_assessments (grade_name)"))
                    conn.execute(sa.text("CREATE INDEX idx_all_assessments_academic_year ON all_assessments (academic_year)"))
                    conn.execute(sa.text("CREATE INDEX idx_all_assessments_assessment_type ON all_assessments (assessment_type)"))
                logger.info("Created indexes on all_assessments table")
            except Exception as e:
                logger.warning(f"Error creating indexes (they may already exist): {e}")
            
            return std_count, non_std_count
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error merging assessments: {e}")
            raise

if __name__ == "__main__":
    try:
        # Create the table if it doesn't exist
        create_all_assessments_table()
        
        # Merge the data
        std_count, non_std_count = merge_assessments()
        
        print(f"Successfully merged {std_count} standardized and {non_std_count} non-standardized assessments")
        print("All assessments data is now available in the all_assessments table")
        
    except Exception as e:
        print(f"Error: {e}")
