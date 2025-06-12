from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

db = SQLAlchemy()

# Helper functions for datetime defaults (compatible with Python 3.6)
def get_utc_now():
    return datetime.now(pytz.utc)

class UserRole(db.Model):
    """User authentication and role information."""
    __tablename__ = 'user_roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False)
    school = db.Column(db.String(255), nullable=True)
    login_count = db.Column(db.Integer, default=0)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=get_utc_now)

    def __repr__(self):
        return f'<UserRole {self.email}>'


class City(db.Model):
    """City information linked to schools."""
    __tablename__ = 'city'
    __table_args__ = (
        db.Index('idx_city_city', 'city'),
    )

    school_name = db.Column(db.String(50), primary_key=True, nullable=True)
    city = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f'<City {self.city} - {self.school_name}>'


class ActiveStudentData(db.Model):
    """Student information."""
    __tablename__ = 'active_student_data'
    __table_args__ = (
        db.Index('idx_asd_school_name', 'school_name'),
        db.Index('idx_asd_academic_year', 'academic_year'),
        db.Index('idx_asd_gender', 'gender'),
        db.Index('idx_asd_school_year_gender', 'school_name', 'academic_year', 'gender'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    school_name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=True)
    grade_name = db.Column(db.String(50), nullable=True)
    student_name = db.Column(db.String(500), nullable=False)
    student_id = db.Column(db.String(50), nullable=False)
    gender = db.Column(db.String(50), nullable=True)
    division_name = db.Column(db.String(10), nullable=False)
    academic_year = db.Column(db.String(10), nullable=False)
    unique_key = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<ActiveStudentData {self.student_id}>'


class StudentAttendanceData(db.Model):
    """Student attendance records."""
    __tablename__ = 'student_attendance_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    academic_year = db.Column(db.String(9), nullable=True)
    school_name = db.Column(db.String(50), nullable=True)
    grade_name = db.Column(db.String(50), nullable=True)
    student_name = db.Column(db.String(255), nullable=True)
    month = db.Column(db.String(20), nullable=True)
    course_name = db.Column(db.String(4), nullable=True)
    student_id = db.Column(db.String(50), nullable=True)
    gender = db.Column(db.String(7), nullable=True)
    attendance_percentage = db.Column(db.Float, nullable=True)
    no_of_working_days = db.Column(db.Integer, nullable=True)
    date = db.Column(db.Date, nullable=True)
    division_name = db.Column(db.String(2), nullable=True)
    no_of_present_days = db.Column(db.Integer, nullable=True)
    student_attendance_data_unique_key = db.Column(db.String(150), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<StudentAttendanceData {self.student_id} - {self.month}>'


class PTMAttendanceData(db.Model):
    """Parent-Teacher Meeting attendance records."""
    __tablename__ = 'ptm_attendance_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    academic_year = db.Column(db.String(10), nullable=False)
    present_ptm = db.Column(db.Integer, nullable=False)
    school_name = db.Column(db.String(255), nullable=False)
    grade_name = db.Column(db.String(10), nullable=False)
    student_name = db.Column(db.String(255), nullable=False)
    month = db.Column(db.String(15), nullable=False)
    course_name = db.Column(db.String(255), nullable=True)
    student_id = db.Column(db.String(50), nullable=False)
    total_no_of_ptm = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=False)
    attendance_percentage = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=True)
    division_name = db.Column(db.String(10), nullable=True)
    ptm_attendance_data_unique_key = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<PTMAttendanceData {self.student_id} - {self.month}>'


class SWPTMAttendanceData(db.Model):
    """Social Worker-Parent Meeting attendance records."""
    __tablename__ = 'swptm_attendance_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    academic_year = db.Column(db.String(10), nullable=False)
    month = db.Column(db.String(15), nullable=False)
    school_name = db.Column(db.String(255), nullable=False)
    grade_name = db.Column(db.String(10), nullable=False)
    student_name = db.Column(db.String(255), nullable=False)
    present_swptm = db.Column(db.Integer, nullable=False)
    course_name = db.Column(db.String(255), nullable=True)
    student_id = db.Column(db.String(50), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    attendance_percentage = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=True)
    division_name = db.Column(db.String(10), nullable=False)
    total_no_of_swptm = db.Column(db.Integer, nullable=False)
    swptm_unique_key = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<SWPTMAttendanceData {self.student_id} - {self.month}>'


class Program(db.Model):
    """Program information."""
    __tablename__ = 'programs'

    program_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    program_name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<Program {self.program_name}>'


# The following models are commented out because they don't exist in the database yet.
# They can be uncommented and used when the corresponding tables are created.

# class ProgramEnrollment(db.Model):
#     """Student enrollment in programs."""
#     __tablename__ = 'program_enrollment'
#
#     enrollment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     student_id = db.Column(db.String(50), nullable=False)
#     program_id = db.Column(db.Integer, nullable=False)
#     enrollment_date = db.Column(db.Date, nullable=False)
#     status = db.Column(db.String(50), nullable=True)
#     created_at = db.Column(db.DateTime, nullable=True)
#     updated_at = db.Column(db.DateTime, nullable=True)
#
#     def __repr__(self):
#         return f'<ProgramEnrollment {self.student_id} - {self.program_id}>'


# class ProgramAssessment(db.Model):
#     """Assessment scores for enrolled students."""
#     __tablename__ = 'program_assessments'
#
#     assessment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     enrollment_id = db.Column(db.Integer, nullable=False)
#     assessment_date = db.Column(db.Date, nullable=False)
#     final_score = db.Column(db.Float, nullable=False)
#     comments = db.Column(db.Text, nullable=True)
#     created_at = db.Column(db.DateTime, nullable=True)
#     updated_at = db.Column(db.DateTime, nullable=True)
#
#     def __repr__(self):
#         return f'<ProgramAssessment {self.enrollment_id} - {self.assessment_date}>'


# class ResourceUsage(db.Model):
#     """Resource usage tracking."""
#     __tablename__ = 'resource_usage'
#
#     usage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     resource_id = db.Column(db.Integer, nullable=False)
#     student_id = db.Column(db.String(50), nullable=False)
#     usage_date = db.Column(db.Date, nullable=False)
#     duration_minutes = db.Column(db.Integer, nullable=True)
#     notes = db.Column(db.Text, nullable=True)
#     created_at = db.Column(db.DateTime, nullable=True)
#     updated_at = db.Column(db.DateTime, nullable=True)
#
#     def __repr__(self):
#         return f'<ResourceUsage {self.student_id} - {self.resource_id}>'


# class StudentProgressTracking(db.Model):
#     """Student progress over time."""
#     __tablename__ = 'student_progress_tracking'
#
#     progress_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     student_id = db.Column(db.String(50), nullable=False)
#     assessment_date = db.Column(db.Date, nullable=False)
#     score_improvement = db.Column(db.Float, nullable=False)
#     notes = db.Column(db.Text, nullable=True)
#     created_at = db.Column(db.DateTime, nullable=True)
#     updated_at = db.Column(db.DateTime, nullable=True)
#
#     def __repr__(self):
#         return f'<StudentProgressTracking {self.student_id} - {self.assessment_date}>'


# class FinancialTransaction(db.Model):
#     """Financial transaction records."""
#     __tablename__ = 'financial_transactions'
#
#     transaction_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     student_id = db.Column(db.String(50), nullable=True)
#     transaction_date = db.Column(db.Date, nullable=False)
#     type = db.Column(db.String(50), nullable=False)  # 'income' or 'expense'
#     amount = db.Column(db.Float, nullable=False)
#     description = db.Column(db.Text, nullable=True)
#     created_at = db.Column(db.DateTime, nullable=True)
#     updated_at = db.Column(db.DateTime, nullable=True)
#
#     def __repr__(self):
#         return f'<FinancialTransaction {self.transaction_id} - {self.type}>'


class StudentAssessmentData(db.Model):
    """Standardized student assessment data."""
    __tablename__ = 'student_assessment_data'
    __table_args__ = (
        db.Index('idx_sad_dashboard_filters',
            'assessment_type',
            'academic_year',
            'subject_name',
            'school_name',
            'grade_name',
            'division_name'
        ),
        db.Index('idx_sad_student_id', 'student_id'),
        db.Index('idx_sad_competency_level', 'competency_level_name'),
        db.Index('idx_sad_student_name', 'student_name'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(100), nullable=True)
    student_name = db.Column(db.String(255), nullable=True)
    gender = db.Column(db.String(1), nullable=True)
    school_name = db.Column(db.String(100), nullable=True)
    subject_name = db.Column(db.String(100), nullable=True)
    assessment_type = db.Column(db.String(50), nullable=True)
    academic_year = db.Column(db.String(20), nullable=True)
    grade_name = db.Column(db.String(50), nullable=True)
    course_name = db.Column(db.String(100), nullable=True)
    division_name = db.Column(db.String(10), nullable=True)
    competency_level_name = db.Column(db.Text, nullable=True)
    assessment_category = db.Column(db.String(50), nullable=True)
    assessment_date = db.Column(db.Date, nullable=True)
    obtained_marks = db.Column(db.Float, nullable=True)
    max_marks = db.Column(db.Float, nullable=True)
    percentage = db.Column(db.Float, nullable=True)
    description = db.Column(db.Text, nullable=True)
    question_name = db.Column(db.Text, nullable=True)
    present_absent = db.Column(db.String(1), nullable=True)
    created_at = db.Column(db.DateTime, nullable=True)
    last_updated_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<StudentAssessmentData {self.student_id} - {self.assessment_type}>'


class NonStandardisedAssessment(db.Model):
    """Non-standardized assessment data."""
    __tablename__ = 'non_standardised_assessment'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    obtained_marks = db.Column(db.Integer, nullable=True)
    subject_name = db.Column(db.String(20), nullable=True)
    school_name = db.Column(db.String(20), nullable=True)
    percentage = db.Column(db.Float, nullable=True)
    grade_name = db.Column(db.String(50), nullable=True)
    assessment_id = db.Column(db.String(255), nullable=True)
    student_id = db.Column(db.String(100), nullable=True)
    course_name = db.Column(db.String(10), nullable=True)
    division_name = db.Column(db.String(5), nullable=True)
    assessment_date = db.Column(db.String(20), nullable=True)
    description = db.Column(db.Text, nullable=True)
    student_name = db.Column(db.String(255), nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    question_name = db.Column(db.String(255), nullable=True)
    present_absent = db.Column(db.String(1), nullable=True)
    max_marks = db.Column(db.Float, nullable=True)
    academic_year = db.Column(db.String(100), nullable=True)
    assessment_type = db.Column(db.String(10), nullable=True)
    assessment_id2 = db.Column(db.String(300), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<NonStandardisedAssessment {self.student_id} - {self.assessment_id}>'


class AllAssessments(db.Model):
    """Combined view of standardized and non-standardized assessments."""
    __tablename__ = 'all_assessments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    assessment_type = db.Column(db.String(20), nullable=False)  # 'standardized' or 'non-standardized'
    obtained_marks = db.Column(db.Float, nullable=True)
    subject_name = db.Column(db.String(255), nullable=True)
    school_name = db.Column(db.String(255), nullable=True)
    percentage = db.Column(db.Float, nullable=True)
    grade_name = db.Column(db.String(50), nullable=True)
    assessment_id = db.Column(db.String(255), nullable=True)
    student_id = db.Column(db.String(100), nullable=True)
    course_name = db.Column(db.String(50), nullable=True)
    competency_level_name = db.Column(db.String(255), nullable=True)  # Maps to description in non-standardized
    division_name = db.Column(db.String(10), nullable=True)
    assessment_date = db.Column(db.Date, nullable=True)  # Standardized format for both
    question_name = db.Column(db.String(1000), nullable=True)
    student_name = db.Column(db.String(255), nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    present_absent = db.Column(db.String(10), nullable=True)
    max_marks = db.Column(db.Float, nullable=True)
    academic_year = db.Column(db.String(100), nullable=True)
    exam_type = db.Column(db.String(10), nullable=True)  # MOY, EOY, etc.
    unique_key = db.Column(db.String(500), nullable=True)  # Combined unique key
    source_table = db.Column(db.String(50), nullable=False)  # 'student_assessment_data' or 'non_standardised_assessment'
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<AllAssessments {self.student_id} - {self.assessment_id} - {self.assessment_type}>'
