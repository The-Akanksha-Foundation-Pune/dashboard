import pandas as pd
import logging
from datetime import datetime
from flask import Blueprint, render_template, flash, redirect, url_for, current_app, jsonify, request, session
from sqlalchemy import func, desc, asc
from contextlib import contextmanager
from models import StudentAssessmentData, City, db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a custom session manager to handle database connections
@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    try:
        yield db.session
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.session.close()

# Define the Blueprint
assessment_bp = Blueprint('assessment', __name__, url_prefix='/assessment')

@assessment_bp.route('/chart/gender_performance', methods=['POST'])
def get_gender_performance_chart():
    """Get data for the gender performance comparison chart."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Use our custom session scope
        with session_scope() as session:
            # Query for gender performance
            query = session.query(
                StudentAssessmentData.gender,
                func.sum(StudentAssessmentData.obtained_marks),
                func.sum(StudentAssessmentData.max_marks)
            ).filter(
                *conditions,
                StudentAssessmentData.gender.isnot(None),
                StudentAssessmentData.obtained_marks.isnot(None),
                StudentAssessmentData.max_marks.isnot(None),
                StudentAssessmentData.max_marks > 0
            ).group_by(
                StudentAssessmentData.gender
            )

            results = query.all()

        # Process results
        genders = []
        percentages = []

        for gender, obtained, maximum in results:
            if maximum > 0:
                genders.append(gender)
                percentages.append(round((obtained / maximum) * 100, 2))

        chart_data = {
            'labels': genders,
            'data': percentages
        }

        return jsonify(chart_data)

    except Exception as e:
        logger.error(f"Error getting gender performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/chart/consolidated_performance', methods=['POST'])
def get_consolidated_performance_chart():
    """Get consolidated performance data by grade and school."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Build filter conditions
        conditions = build_filter_conditions(filters)
        city = filters.get('city', 'All')

        # Use our custom session scope
        with session_scope() as session:
            # Query for school performance by grade
            query = session.query(
                StudentAssessmentData.school_name,
                StudentAssessmentData.grade_name,
                func.sum(StudentAssessmentData.obtained_marks),
                func.sum(StudentAssessmentData.max_marks)
            )
            if city != 'All':
                query = query.join(City, StudentAssessmentData.school_name == City.school_name)
                query = query.filter(City.city == city)
            query = query.filter(
                *conditions,
                StudentAssessmentData.school_name.isnot(None),
                StudentAssessmentData.grade_name.isnot(None),
                StudentAssessmentData.obtained_marks.isnot(None),
                StudentAssessmentData.max_marks.isnot(None),
                StudentAssessmentData.max_marks > 0
            ).group_by(
                StudentAssessmentData.school_name,
                StudentAssessmentData.grade_name
            )

            results = query.all()

            # Exclude Grade 9 and Grade 10
            exclude_grades = {'GRADE 9', 'Grade 9', 'Gr. 9', '9', 'GRADE 10', 'Grade 10', 'Gr. 10', '10'}
            filtered_results = [r for r in results if r[1] not in exclude_grades]

            # Get unique schools from the results
            schools = sorted(list(set([r[0] for r in filtered_results if r[0]])))
            grades = sorted(list(set([r[1] for r in filtered_results if r[1]])))

            # Sort grades in a logical order
            grade_order = {
                'Nursery': 0, 'Jr.KG': 1, 'JR.KG': 1, 'Jr.kG': 1,
                'SR.KG': 2, 'Sr.KG': 2, 'Sr.kG': 2,
                'GRADE 1': 3, 'Grade 1': 3, 'Gr. 1': 3, '1': 3,
                'GRADE 2': 4, 'Grade 2': 4, 'Gr. 2': 4, '2': 4,
                'GRADE 3': 5, 'Grade 3': 5, 'Gr. 3': 5, '3': 5,
                'GRADE 4': 6, 'Grade 4': 6, 'Gr. 4': 6, '4': 6,
                'GRADE 5': 7, 'Grade 5': 7, 'Gr. 5': 7, '5': 7,
                'GRADE 6': 8, 'Grade 6': 8, 'Gr. 6': 8, '6': 8,
                'GRADE 7': 9, 'Grade 7': 9, 'Gr. 7': 9, '7': 9,
                'GRADE 8': 10, 'Grade 8': 10, 'Gr. 8': 10, '8': 10
            }
            grades = sorted(grades, key=lambda x: grade_order.get(x, 999))

            # Initialize data structure
            performance_data = {}
            for school in schools:
                performance_data[school] = {
                    'grades': {},
                    'city': 'Unknown'
                }
                for grade in grades:
                    performance_data[school]['grades'][grade] = None

            # Fill in the data
            for school, grade, obtained, maximum in filtered_results:
                if school and grade and maximum > 0:
                    percentage = round((obtained / maximum) * 100, 2)
                    if school in performance_data:
                        performance_data[school]['grades'][grade] = percentage

            # Group schools by city
            cities = {}
            for school, data in performance_data.items():
                city = data['city']
                if city not in cities:
                    cities[city] = []
                cities[city].append(school)

            # Calculate city averages
            city_averages = {}
            for city, city_schools in cities.items():
                city_averages[city] = {'grades': {}}
                for grade in grades:
                    grade_values = []
                    for school in city_schools:
                        if school in performance_data and grade in performance_data[school]['grades']:
                            value = performance_data[school]['grades'].get(grade)
                            if value is not None:
                                grade_values.append(value)
                    if grade_values:
                        city_averages[city]['grades'][grade] = round(sum(grade_values) / len(grade_values), 2)
                    else:
                        city_averages[city]['grades'][grade] = None

            # Calculate overall averages (Akanksha)
            overall_averages = {'grades': {}}
            for grade in grades:
                grade_values = []
                for school in schools:
                    if school in performance_data and grade in performance_data[school]['grades']:
                        value = performance_data[school]['grades'].get(grade)
                        if value is not None:
                            grade_values.append(value)
                if grade_values:
                    overall_averages['grades'][grade] = round(sum(grade_values) / len(grade_values), 2)
                else:
                    overall_averages['grades'][grade] = None

            # Format the response
            response = {
                'grades': grades,
                'schools': performance_data,
                'cities': city_averages,
                'overall': overall_averages
            }

            return jsonify(response)
    except Exception as e:
        logger.error(f"Error getting consolidated performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/chart/subject_performance_by_school', methods=['POST'])
def get_subject_performance_by_school():
    """Get subject performance data by school."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Use our custom session scope
        with session_scope() as session:
            # Query for subject performance by school
            query = session.query(
                StudentAssessmentData.school_name,
                StudentAssessmentData.subject_name,
                func.sum(StudentAssessmentData.obtained_marks),
                func.sum(StudentAssessmentData.max_marks)
            ).filter(
                *conditions,
                StudentAssessmentData.school_name.isnot(None),
                StudentAssessmentData.subject_name.isnot(None),
                StudentAssessmentData.obtained_marks.isnot(None),
                StudentAssessmentData.max_marks.isnot(None),
                StudentAssessmentData.max_marks > 0
            ).group_by(
                StudentAssessmentData.school_name,
                StudentAssessmentData.subject_name
            )

            results = query.all()

            # Get unique schools from the results
            schools = sorted(list(set([r[0] for r in results if r[0]])))

            # Create a default city mapping
            school_to_city = {}
            for school in schools:
                # Default city assignment based on school name patterns
                if "Mumbai" in school or "NMMC" in school:
                    school_to_city[school] = "Mumbai"
                elif "Pune" in school:
                    school_to_city[school] = "Pune"
                elif "Nagpur" in school:
                    school_to_city[school] = "Nagpur"
                else:
                    school_to_city[school] = "Unknown"

            # Try to get city information from the City model if available
            try:
                city_query = session.query(
                    City.school_name,
                    City.city
                ).filter(
                    City.school_name.isnot(None),
                    City.city.isnot(None)
                ).distinct()

                city_results = city_query.all()

                # Update the mapping with actual data from the database
                for school, city in city_results:
                    if school and city:
                        school_to_city[school] = city
            except Exception as e:
                logger.warning(f"Could not fetch city data: {e}. Using default city assignments.")

        # Process results
        performance_data = {}

        # Get unique schools and subjects
        schools = sorted(list(set([r[0] for r in results if r[0]])))
        subjects = sorted(list(set([r[1] for r in results if r[1]])))

        # Map subject names to standard abbreviations
        subject_abbr = {
            'Mathematics': 'Mat',
            'Math': 'Mat',
            'Maths': 'Mat',
            'English': 'Eng',
            'Hindi': 'Hin',
            'Marathi': 'Mar',
            'Science': 'Sci',
            'Computer': 'Com',
            'Computer Science': 'Com',
            'Social Science': 'SST',
            'Social Studies': 'SST',
            'EVS': 'EVS',
            'Environmental Studies': 'EVS'
        }

        # Initialize data structure
        for school in schools:
            performance_data[school] = {
                'subjects': {},
                'city': school_to_city.get(school, 'Unknown')
            }

            for subject in subjects:
                performance_data[school]['subjects'][subject] = None

        # Fill in the data
        for school, subject, obtained, maximum in results:
            if school and subject and maximum > 0:
                percentage = round((obtained / maximum) * 100, 2)
                if school in performance_data:
                    performance_data[school]['subjects'][subject] = percentage

        # Group schools by city
        cities = {}
        for school, data in performance_data.items():
            city = data['city']
            if city not in cities:
                cities[city] = []
            cities[city].append(school)

        # Calculate city averages
        city_averages = {}
        for city, city_schools in cities.items():
            city_averages[city] = {'subjects': {}}
            for subject in subjects:
                subject_values = []
                for school in city_schools:
                    if school in performance_data and subject in performance_data[school]['subjects']:
                        value = performance_data[school]['subjects'].get(subject)
                        if value is not None:
                            subject_values.append(value)

                if subject_values:
                    city_averages[city]['subjects'][subject] = round(sum(subject_values) / len(subject_values), 2)
                else:
                    city_averages[city]['subjects'][subject] = None

        # Calculate overall averages (Akanksha)
        overall_averages = {'subjects': {}}
        for subject in subjects:
            subject_values = []
            for school in schools:
                if school in performance_data and subject in performance_data[school]['subjects']:
                    value = performance_data[school]['subjects'].get(subject)
                    if value is not None:
                        subject_values.append(value)

            if subject_values:
                overall_averages['subjects'][subject] = round(sum(subject_values) / len(subject_values), 2)
            else:
                overall_averages['subjects'][subject] = None

        # Format the response
        response = {
            'subjects': subjects,
            'subject_abbr': subject_abbr,
            'schools': performance_data,
            'cities': city_averages,
            'overall': overall_averages
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting subject performance by school data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/')
def view():
    """Assessment dashboard view."""
    # Check if user is logged in using session
    if "user_email" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("index"))

    try:
        return render_template(
            "assessment_dashboard_optimized.html",
            active_page='assessments',  # Match the menu item name
            name=session.get('user_name'),
            email=session.get('user_email'),
            picture=session.get('user_picture'),
            role=session.get('user_role', 'Admin'),
            school=session.get('user_school', 'All')
        )
    except Exception as e:
        current_app.logger.error(f"Error in assessment dashboard view: {e}")
        flash("An error occurred. Please try again.", "danger")
        return redirect(url_for("index"))

@assessment_bp.route('/get_filters', methods=['GET'])
def get_filters():
    """Get all available filter options for the assessment dashboard."""
    try:
        # Use our custom session scope
        with session_scope() as session:
            # Query unique values for each filter
            academic_years = session.query(StudentAssessmentData.academic_year).distinct().all()
            academic_years = sorted([year[0] for year in academic_years if year[0]], reverse=True)

            # Get assessment types with counts to show the most common ones first
            assessment_types_query = session.query(
                StudentAssessmentData.assessment_type,
                func.count(StudentAssessmentData.id).label('count')
            ).group_by(StudentAssessmentData.assessment_type).order_by(desc('count')).all()
            assessment_types = [type[0] for type in assessment_types_query if type[0]]

            # Get assessment categories
            assessment_categories_query = session.query(StudentAssessmentData.assessment_category).distinct().all()
            assessment_categories = sorted([cat[0] for cat in assessment_categories_query if cat[0]])

            # Get min and max assessment dates for date range picker
            min_date = session.query(db.func.min(StudentAssessmentData.assessmentDate)).scalar()
            max_date = session.query(db.func.max(StudentAssessmentData.assessmentDate)).scalar()

            min_date_str = min_date.strftime('%Y-%m-%d') if min_date else None
            max_date_str = max_date.strftime('%Y-%m-%d') if max_date else None

            # Get unique cities from the City table
            cities = session.query(City.city).distinct().all()
            cities = sorted([c[0] for c in cities if c[0]])

        return jsonify({
            'academic_years': academic_years,
            'assessment_types': assessment_types,
            'assessment_categories': assessment_categories,
            'date_range': {
                'min': min_date_str,
                'max': max_date_str
            },
            'cities': cities
        })
    except Exception as e:
        logger.error(f"Error getting assessment filters: {e}")
        return jsonify({"error": f"Failed to fetch assessment filters: {str(e)}"}), 500

@assessment_bp.route('/get_secondary_filters', methods=['POST'])
def get_secondary_filters():
    """Get secondary filters based on primary filter selections."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Extract primary filter values
        academic_year = filters.get('academic_year', 'All')
        assessment_type = filters.get('assessment_type', 'All')
        assessment_category = filters.get('assessment_category', 'All')

        # Use our custom session scope
        with session_scope() as session:
            # Get subjects
            subjects_query = session.query(
                StudentAssessmentData.subject_name,
                func.count(StudentAssessmentData.id).label('count')
            ).filter(StudentAssessmentData.subject_name.isnot(None))

            if academic_year != 'All':
                subjects_query = subjects_query.filter(StudentAssessmentData.academic_year == academic_year)
            if assessment_type != 'All':
                subjects_query = subjects_query.filter(StudentAssessmentData.assessment_type == assessment_type)
            if assessment_category != 'All':
                subjects_query = subjects_query.filter(StudentAssessmentData.assessment_category == assessment_category)

            subjects_query = subjects_query.group_by(StudentAssessmentData.subject_name).order_by(desc('count'))
            subjects = [subject[0] for subject in subjects_query.all() if subject[0]]

            # Get schools
            schools_query = session.query(
                StudentAssessmentData.school_name,
                func.count(StudentAssessmentData.id).label('count')
            ).filter(StudentAssessmentData.school_name.isnot(None))

            if academic_year != 'All':
                schools_query = schools_query.filter(StudentAssessmentData.academic_year == academic_year)
            if assessment_type != 'All':
                schools_query = schools_query.filter(StudentAssessmentData.assessment_type == assessment_type)
            if assessment_category != 'All':
                schools_query = schools_query.filter(StudentAssessmentData.assessment_category == assessment_category)

            schools_query = schools_query.group_by(StudentAssessmentData.school_name).order_by(desc('count'))
            schools = [school[0] for school in schools_query.all() if school[0]]

            # Get grades
            grades_query = session.query(
                StudentAssessmentData.grade_name,
                func.count(StudentAssessmentData.id).label('count')
            ).filter(StudentAssessmentData.grade_name.isnot(None))

            if academic_year != 'All':
                grades_query = grades_query.filter(StudentAssessmentData.academic_year == academic_year)
            if assessment_type != 'All':
                grades_query = grades_query.filter(StudentAssessmentData.assessment_type == assessment_type)
            if assessment_category != 'All':
                grades_query = grades_query.filter(StudentAssessmentData.assessment_category == assessment_category)

            grades_query = grades_query.group_by(StudentAssessmentData.grade_name).order_by(desc('count'))
            grades = [grade[0] for grade in grades_query.all() if grade[0]]

        return jsonify({
            'subjects': subjects,
            'schools': schools,
            'grades': grades
        })
    except Exception as e:
        logger.error(f"Error getting secondary filters: {e}")
        return jsonify({"error": f"Failed to fetch secondary filters: {str(e)}"}), 500

# Helper function to build filter conditions
def build_filter_conditions(filters):
    """Build SQLAlchemy filter conditions based on the provided filters."""
    conditions = []

    academic_year = filters.get('academic_year', 'All')
    subject = filters.get('subject', 'All')
    school = filters.get('school', 'All')
    assessment_type = filters.get('assessment_type', 'All')
    grade = filters.get('grade', 'All')
    gender = filters.get('gender', 'All')
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')

    if academic_year != 'All':
        conditions.append(StudentAssessmentData.academic_year == academic_year)
    if subject != 'All':
        conditions.append(StudentAssessmentData.subject_name == subject)
    if school != 'All':
        conditions.append(StudentAssessmentData.school_name == school)
    if assessment_type != 'All':
        conditions.append(StudentAssessmentData.assessment_type == assessment_type)
    if grade != 'All':
        conditions.append(StudentAssessmentData.grade_name == grade)
    if gender != 'All':
        conditions.append(StudentAssessmentData.gender == gender)
    if start_date and end_date:
        conditions.append(StudentAssessmentData.assessmentDate.between(start_date, end_date))

    return conditions

@assessment_bp.route('/get_paginated_data', methods=['POST'])
def get_paginated_data():
    """Get paginated assessment data based on selected filters."""
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({"error": "Missing request data"}), 400

        # Extract pagination parameters
        page = request_data.get('page', 1)
        page_size = request_data.get('page_size', 50)
        sort_by = request_data.get('sort_by', 'assessmentDate')
        sort_dir = request_data.get('sort_dir', 'desc')

        # Extract filters
        filters = request_data.get('filters', {})

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Use our custom session scope
        with session_scope() as session:
            # Calculate total records (for pagination)
            total_query = session.query(func.count(StudentAssessmentData.id))
            if conditions:
                total_query = total_query.filter(*conditions)
            total_records = total_query.scalar()

            # Build the main query with pagination
            query = session.query(
                StudentAssessmentData.id,
                StudentAssessmentData.student_id,
                StudentAssessmentData.student_name,
                StudentAssessmentData.school_name,
                StudentAssessmentData.grade_name,
                StudentAssessmentData.subject_name,
                StudentAssessmentData.obtained_marks,
                StudentAssessmentData.max_marks,
                StudentAssessmentData.percentage,
                StudentAssessmentData.competency_level_name,
                StudentAssessmentData.assessmentDate,
                StudentAssessmentData.gender,
                StudentAssessmentData.academic_year,
                StudentAssessmentData.assessment_type
            )

            # Apply filters
            if conditions:
                query = query.filter(*conditions)

            # Apply sorting
            if sort_dir.lower() == 'asc':
                query = query.order_by(asc(getattr(StudentAssessmentData, sort_by)))
            else:
                query = query.order_by(desc(getattr(StudentAssessmentData, sort_by)))

            # Apply pagination
            query = query.limit(page_size).offset((page - 1) * page_size)

            # Execute the query
            results = query.all()

            # Convert to dictionary format
            assessment_data = []
            for assessment in results:
                assessment_data.append({
                    'id': assessment.id,
                    'student_id': assessment.student_id,
                    'student_name': assessment.student_name,
                    'school_name': assessment.school_name,
                    'grade_name': assessment.grade_name,
                    'subject_name': assessment.subject_name,
                    'obtained_marks': float(assessment.obtained_marks) if assessment.obtained_marks else 0,
                    'max_marks': float(assessment.max_marks) if assessment.max_marks else 0,
                    'percentage': float(assessment.percentage) if assessment.percentage else 0,
                    'competency_level_name': assessment.competency_level_name,
                    'assessment_date': assessment.assessmentDate.strftime('%Y-%m-%d') if assessment.assessmentDate else None,
                    'gender': assessment.gender,
                    'academic_year': assessment.academic_year,
                    'assessment_type': assessment.assessment_type
                })

            # Calculate total pages
            total_pages = (total_records + page_size - 1) // page_size

        return jsonify({
            'data': assessment_data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_records': total_records,
                'total_pages': total_pages
            }
        })
    except Exception as e:
        logger.error(f"Error getting paginated assessment data: {e}")
        return jsonify({"error": f"Failed to fetch assessment data: {str(e)}"}), 500

@assessment_bp.route('/get_summary_stats', methods=['POST'])
def get_summary_stats():
    """Get summary statistics based on selected filters."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Use our custom session scope
        with session_scope() as session:
            # Get total students
            students_query = session.query(func.count(func.distinct(StudentAssessmentData.student_id)))
            if conditions:
                students_query = students_query.filter(*conditions)
            total_students = students_query.scalar() or 0

            # Get total assessments
            assessments_query = session.query(func.count(StudentAssessmentData.id))
            if conditions:
                assessments_query = assessments_query.filter(*conditions)
            total_assessments = assessments_query.scalar() or 0

            # Get average score
            avg_score_query = session.query(
                func.avg(
                    (StudentAssessmentData.obtained_marks / StudentAssessmentData.max_marks) * 100
                )
            ).filter(StudentAssessmentData.max_marks > 0)
            if conditions:
                avg_score_query = avg_score_query.filter(*conditions)
            avg_score = avg_score_query.scalar() or 0

            # Get total schools
            schools_query = session.query(func.count(func.distinct(StudentAssessmentData.school_name)))
            if conditions:
                schools_query = schools_query.filter(*conditions)
            total_schools = schools_query.scalar() or 0

        return jsonify({
            'total_students': total_students,
            'total_assessments': total_assessments,
            'average_score': round(avg_score, 2),
            'total_schools': total_schools
        })
    except Exception as e:
        logger.error(f"Error getting summary statistics: {e}")
        return jsonify({"error": f"Failed to fetch summary statistics: {str(e)}"}), 500

@assessment_bp.route('/chart/overall_performance', methods=['POST'])
def get_overall_performance_chart():
    """Get data for the overall performance pie chart."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Use our custom session scope
        with session_scope() as session:
            # Query for competency level distribution
            query = session.query(
                StudentAssessmentData.competency_level_name,
                func.count(StudentAssessmentData.id)
            ).filter(
                *conditions,
                StudentAssessmentData.competency_level_name.isnot(None)
            ).group_by(
                StudentAssessmentData.competency_level_name
            )

            results = query.all()

        # Process results
        labels = []
        data = []
        colors = []

        # Define color mapping for competency levels
        color_map = {
            'Excellent': '#212529',  # Black
            'Good': '#343a40',       # Dark Gray
            'Satisfactory': '#ffc107', # Yellow
            'Needs Improvement': '#e0a800', # Dark Yellow
            'Poor': '#6c757d'        # Gray
        }

        for competency, count in results:
            labels.append(competency)
            data.append(count)
            # Assign color based on competency level or use a default
            colors.append(color_map.get(competency, '#212529'))  # Default to black

        chart_data = {
            'labels': labels,
            'data': data,
            'colors': colors
        }

        return jsonify(chart_data)

    except Exception as e:
        logger.error(f"Error getting overall performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/chart/school_performance', methods=['POST'])
def get_school_performance_chart():
    """Get data for the school performance bar chart."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Use our custom session scope
        with session_scope() as session:
            # Query for school performance
            query = session.query(
                StudentAssessmentData.school_name,
                func.sum(StudentAssessmentData.obtained_marks),
                func.sum(StudentAssessmentData.max_marks)
            ).filter(
                *conditions,
                StudentAssessmentData.school_name.isnot(None),
                StudentAssessmentData.obtained_marks.isnot(None),
                StudentAssessmentData.max_marks.isnot(None),
                StudentAssessmentData.max_marks > 0
            ).group_by(
                StudentAssessmentData.school_name
            )

            results = query.all()

        # Process results
        schools = []
        percentages = []

        for school, obtained, maximum in results:
            if maximum > 0:
                schools.append(school)
                percentages.append(round((obtained / maximum) * 100, 2))

        # Sort by percentage (descending)
        sorted_data = sorted(zip(schools, percentages), key=lambda x: x[1], reverse=True)
        schools = [item[0] for item in sorted_data]
        percentages = [item[1] for item in sorted_data]

        # Limit to top 10 schools
        if len(schools) > 10:
            schools = schools[:10]
            percentages = percentages[:10]

        chart_data = {
            'labels': schools,
            'data': percentages
        }

        return jsonify(chart_data)

    except Exception as e:
        logger.error(f"Error getting school performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/chart/subject_performance', methods=['POST'])
def get_subject_performance_chart():
    """Get data for the subject performance bar chart."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Use our custom session scope
        with session_scope() as session:
            # Query for subject performance
            query = session.query(
                StudentAssessmentData.subject_name,
                func.sum(StudentAssessmentData.obtained_marks),
                func.sum(StudentAssessmentData.max_marks)
            ).filter(
                *conditions,
                StudentAssessmentData.subject_name.isnot(None),
                StudentAssessmentData.obtained_marks.isnot(None),
                StudentAssessmentData.max_marks.isnot(None),
                StudentAssessmentData.max_marks > 0
            ).group_by(
                StudentAssessmentData.subject_name
            )

            results = query.all()

        # Process results
        subjects = []
        percentages = []

        for subject, obtained, maximum in results:
            if maximum > 0:
                subjects.append(subject)
                percentages.append(round((obtained / maximum) * 100, 2))

        # Sort by percentage (descending)
        sorted_data = sorted(zip(subjects, percentages), key=lambda x: x[1], reverse=True)
        subjects = [item[0] for item in sorted_data]
        percentages = [item[1] for item in sorted_data]

        chart_data = {
            'labels': subjects,
            'data': percentages
        }

        return jsonify(chart_data)

    except Exception as e:
        logger.error(f"Error getting subject performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/compare', methods=['POST'])
def compare_assessments():
    """Compare assessment data between different periods."""
    try:
        comparison_data = request.get_json()
        if not comparison_data:
            return jsonify({"error": "Missing comparison data"}), 400

        # Extract comparison parameters
        period1 = comparison_data.get('period1', {})
        period2 = comparison_data.get('period2', {})

        if not period1 or not period2:
            return jsonify({"error": "Missing period data for comparison"}), 400

        # Build filter conditions for each period
        conditions1 = build_filter_conditions(period1)
        conditions2 = build_filter_conditions(period2)

        # Get summary stats for period 1
        stats1 = get_period_stats(conditions1)

        # Get summary stats for period 2
        stats2 = get_period_stats(conditions2)

        # Get subject performance for both periods
        subjects1 = get_subject_performance(conditions1)
        subjects2 = get_subject_performance(conditions2)

        # Combine subject data for comparison
        subject_comparison = combine_subject_data(subjects1, subjects2)

        # Get competency level distribution for both periods
        competency1 = get_competency_distribution(conditions1)
        competency2 = get_competency_distribution(conditions2)

        # Calculate improvement metrics
        improvement = calculate_improvement(stats1, stats2)

        return jsonify({
            'period1': {
                'label': get_period_label(period1),
                'stats': stats1,
                'competency': competency1
            },
            'period2': {
                'label': get_period_label(period2),
                'stats': stats2,
                'competency': competency2
            },
            'subject_comparison': subject_comparison,
            'improvement': improvement
        })

    except Exception as e:
        current_app.logger.error(f"Error comparing assessment data: {e}")
        return jsonify({"error": f"Failed to compare assessment data: {str(e)}"}), 500

def get_period_label(period):
    """Generate a human-readable label for the period."""
    academic_year = period.get('academic_year', 'All')
    assessment_type = period.get('assessment_type', 'All')

    if academic_year != 'All' and assessment_type != 'All':
        return f"{academic_year} {assessment_type}"
    elif academic_year != 'All':
        return academic_year
    elif assessment_type != 'All':
        return assessment_type
    else:
        return "All Periods"

def get_period_stats(conditions):
    """Get summary statistics for a specific period."""
    # Use our custom session scope
    with session_scope() as session:
        # Get total students
        students_query = session.query(func.count(func.distinct(StudentAssessmentData.student_id)))
        if conditions:
            students_query = students_query.filter(*conditions)
        total_students = students_query.scalar() or 0

        # Get total assessments
        assessments_query = session.query(func.count(StudentAssessmentData.id))
        if conditions:
            assessments_query = assessments_query.filter(*conditions)
        total_assessments = assessments_query.scalar() or 0

        # Get average score
        avg_score_query = session.query(
            func.avg(
                (StudentAssessmentData.obtained_marks / StudentAssessmentData.max_marks) * 100
            )
        ).filter(StudentAssessmentData.max_marks > 0)
        if conditions:
            avg_score_query = avg_score_query.filter(*conditions)
        avg_score = avg_score_query.scalar() or 0

    return {
        'total_students': total_students,
        'total_assessments': total_assessments,
        'average_score': round(avg_score, 2)
    }

def get_subject_performance(conditions):
    """Get subject performance data for a specific period."""
    # Use our custom session scope
    with session_scope() as session:
        # Query for subject performance
        query = session.query(
            StudentAssessmentData.subject_name,
            func.sum(StudentAssessmentData.obtained_marks),
            func.sum(StudentAssessmentData.max_marks)
        ).filter(
            *conditions,
            StudentAssessmentData.subject_name.isnot(None),
            StudentAssessmentData.obtained_marks.isnot(None),
            StudentAssessmentData.max_marks.isnot(None),
            StudentAssessmentData.max_marks > 0
        ).group_by(
            StudentAssessmentData.subject_name
        )

        results = query.all()

    # Process results
    subject_data = {}

    for subject, obtained, maximum in results:
        if maximum > 0:
            subject_data[subject] = round((obtained / maximum) * 100, 2)

    return subject_data

def get_competency_distribution(conditions):
    """Get competency level distribution for a specific period."""
    # Use our custom session scope
    with session_scope() as session:
        # Query for competency level distribution
        query = session.query(
            StudentAssessmentData.competency_level_name,
            func.count(StudentAssessmentData.id)
        ).filter(
            *conditions,
            StudentAssessmentData.competency_level_name.isnot(None)
        ).group_by(
            StudentAssessmentData.competency_level_name
        )

        results = query.all()

    # Process results
    competency_data = {}

    for competency, count in results:
        competency_data[competency] = count

    return competency_data

def combine_subject_data(subjects1, subjects2):
    """Combine subject performance data from two periods for comparison."""
    all_subjects = set(list(subjects1.keys()) + list(subjects2.keys()))

    comparison = []

    for subject in all_subjects:
        comparison.append({
            'subject': subject,
            'period1': subjects1.get(subject, 0),
            'period2': subjects2.get(subject, 0),
            'difference': round(subjects2.get(subject, 0) - subjects1.get(subject, 0), 2)
        })

    # Sort by absolute difference (descending)
    comparison.sort(key=lambda x: abs(x['difference']), reverse=True)

    return comparison

def calculate_improvement(stats1, stats2):
    """Calculate improvement metrics between two periods."""
    avg_score_diff = stats2['average_score'] - stats1['average_score']

    return {
        'average_score_change': round(avg_score_diff, 2),
        'average_score_percent_change': round((avg_score_diff / stats1['average_score']) * 100 if stats1['average_score'] > 0 else 0, 2),
        'assessment_count_change': stats2['total_assessments'] - stats1['total_assessments'],
        'student_count_change': stats2['total_students'] - stats1['total_students']
    }

@assessment_bp.route('/export_data', methods=['POST'])
def export_data():
    """Export assessment data to CSV based on selected filters."""
    try:
        # Get filters from form data
        filters = {
            'academic_year': request.form.get('academic_year', 'All'),
            'assessment_type': request.form.get('assessment_type', 'All'),
            'subject': request.form.get('subject', 'All'),
            'school': request.form.get('school', 'All'),
            'grade': request.form.get('grade', 'All'),
            'gender': request.form.get('gender', 'All'),
            'start_date': request.form.get('start_date'),
            'end_date': request.form.get('end_date')
        }

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Use our custom session scope
        with session_scope() as session:
            # Build the query
            query = session.query(
                StudentAssessmentData.student_id,
                StudentAssessmentData.student_name,
                StudentAssessmentData.school_name,
                StudentAssessmentData.grade_name,
                StudentAssessmentData.subject_name,
                StudentAssessmentData.obtained_marks,
                StudentAssessmentData.max_marks,
                StudentAssessmentData.percentage,
                StudentAssessmentData.competency_level_name,
                StudentAssessmentData.assessmentDate,
                StudentAssessmentData.gender,
                StudentAssessmentData.academic_year,
                StudentAssessmentData.assessment_type
            )

            # Apply filters
            if conditions:
                query = query.filter(*conditions)

            # Order by assessment date (descending)
            query = query.order_by(StudentAssessmentData.assessmentDate.desc())

            # Execute the query
            results = query.all()

        # Create a DataFrame
        df = pd.DataFrame([{
            'Student ID': r.student_id,
            'Student Name': r.student_name,
            'School': r.school_name,
            'Grade': r.grade_name,
            'Subject': r.subject_name,
            'Obtained Marks': r.obtained_marks,
            'Max Marks': r.max_marks,
            'Percentage': r.percentage,
            'Competency Level': r.competency_level_name,
            'Assessment Date': r.assessmentDate.strftime('%Y-%m-%d') if r.assessmentDate else None,
            'Gender': r.gender,
            'Academic Year': r.academic_year,
            'Assessment Type': r.assessment_type
        } for r in results])

        # Generate a filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"assessment_data_{timestamp}.csv"

        # Create a response with CSV data
        from flask import Response
        csv_data = df.to_csv(index=False)

        response = Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

        return response
    except Exception as e:
        logger.error(f"Error exporting assessment data: {e}")
        flash("An error occurred while exporting data. Please try again.", "danger")
        return redirect(url_for("assessment.view"))

@assessment_bp.route('/chart/school_subject_performance', methods=['POST'])
def get_school_subject_performance():
    """Get subject performance data by school (pivot table)."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Build filter conditions
        conditions = build_filter_conditions(filters)
        city = filters.get('city', 'All')

        # Use our custom session scope
        with session_scope() as session:
            # Query for subject performance by school
            query = session.query(
                StudentAssessmentData.school_name,
                StudentAssessmentData.subject_name,
                func.sum(StudentAssessmentData.obtained_marks),
                func.sum(StudentAssessmentData.max_marks)
            )
            if city != 'All':
                query = query.join(City, StudentAssessmentData.school_name == City.school_name)
                query = query.filter(City.city == city)
            query = query.filter(
                *conditions,
                StudentAssessmentData.school_name.isnot(None),
                StudentAssessmentData.subject_name.isnot(None),
                StudentAssessmentData.obtained_marks.isnot(None),
                StudentAssessmentData.max_marks.isnot(None),
                StudentAssessmentData.max_marks > 0
            ).group_by(
                StudentAssessmentData.school_name,
                StudentAssessmentData.subject_name
            )

            results = query.all()

            # Exclude subjects for Grade 9 and 10
            exclude_grades = {'GRADE 9', 'Grade 9', 'Gr. 9', '9', 'GRADE 10', 'Grade 10', 'Gr. 10', '10'}
            # Get mapping of (school, subject) to grade
            grade_query = session.query(
                StudentAssessmentData.school_name,
                StudentAssessmentData.subject_name,
                StudentAssessmentData.grade_name
            ).filter(
                *conditions,
                StudentAssessmentData.school_name.isnot(None),
                StudentAssessmentData.subject_name.isnot(None),
                StudentAssessmentData.grade_name.isnot(None)
            ).distinct()
            grade_map = {(row[0], row[1]): row[2] for row in grade_query if row[2] not in exclude_grades}
            filtered_results = [r for r in results if (r[0], r[1]) in grade_map]

            # Get unique schools and subjects
            schools = sorted(list(set([r[0] for r in filtered_results if r[0]])))
            subjects = sorted(list(set([r[1] for r in filtered_results if r[1]])))

            # Try to get city information from the City model if available
            school_to_city = {}
            try:
                city_query = session.query(
                    City.school_name,
                    City.city
                ).filter(
                    City.school_name.isnot(None),
                    City.city.isnot(None)
                ).distinct()
                city_results = city_query.all()
                for school, city in city_results:
                    if school and city:
                        school_to_city[school] = city
            except Exception as e:
                logger.warning(f"Could not fetch city data: {e}. Using default city assignments.")

            # Initialize data structure
            performance_data = {}
            for school in schools:
                performance_data[school] = {
                    'subjects': {},
                    'city': school_to_city.get(school, 'Unknown')
                }
                for subject in subjects:
                    performance_data[school]['subjects'][subject] = None

            # Fill in the data
            for school, subject, obtained, maximum in filtered_results:
                if school and subject and maximum > 0:
                    percentage = round((obtained / maximum) * 100, 2)
                    if school in performance_data:
                        performance_data[school]['subjects'][subject] = percentage

            # Group schools by city
            cities = {}
            for school, data in performance_data.items():
                city = data['city']
                if city not in cities:
                    cities[city] = []
                cities[city].append(school)

            # Calculate city averages
            city_averages = {}
            for city, city_schools in cities.items():
                city_averages[city] = {'subjects': {}}
                for subject in subjects:
                    subject_values = []
                    for school in city_schools:
                        if school in performance_data and subject in performance_data[school]['subjects']:
                            value = performance_data[school]['subjects'].get(subject)
                            if value is not None:
                                subject_values.append(value)
                    if subject_values:
                        city_averages[city]['subjects'][subject] = round(sum(subject_values) / len(subject_values), 2)
                    else:
                        city_averages[city]['subjects'][subject] = None

            # Calculate overall averages
            overall_averages = {'subjects': {}}
            for subject in subjects:
                subject_values = []
                for school in schools:
                    if school in performance_data and subject in performance_data[school]['subjects']:
                        value = performance_data[school]['subjects'].get(subject)
                        if value is not None:
                            subject_values.append(value)
                if subject_values:
                    overall_averages['subjects'][subject] = round(sum(subject_values) / len(subject_values), 2)
                else:
                    overall_averages['subjects'][subject] = None

            # Format the response
            response = {
                'subjects': subjects,
                'schools': performance_data,
                'cities': city_averages,
                'overall': overall_averages
            }
            return jsonify(response)
    except Exception as e:
        logger.error(f"Error getting school subject performance data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/chart/bucket_wise', methods=['POST'])
def get_bucket_wise_chart():
    """Get bucket-wise student % and unique student counts for each school (for stacked bar chart)."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Build filter conditions
        conditions = build_filter_conditions(filters)
        city = filters.get('city', 'All')

        with session_scope() as session:
            # Query all students with their total obtained and max marks per school
            query = session.query(
                StudentAssessmentData.school_name,
                StudentAssessmentData.student_id,
                func.sum(StudentAssessmentData.obtained_marks).label('obtained'),
                func.sum(StudentAssessmentData.max_marks).label('maximum')
            )
            if city != 'All':
                query = query.join(City, StudentAssessmentData.school_name == City.school_name)
                query = query.filter(City.city == city)
            query = query.filter(
                *conditions,
                StudentAssessmentData.school_name.isnot(None),
                StudentAssessmentData.student_id.isnot(None),
                StudentAssessmentData.obtained_marks.isnot(None),
                StudentAssessmentData.max_marks.isnot(None),
                StudentAssessmentData.max_marks > 0
            ).group_by(
                StudentAssessmentData.school_name,
                StudentAssessmentData.student_id
            )

            results = query.all()

            # Organize by school
            school_students = {}
            for school, student_id, obtained, maximum in results:
                if not school or not student_id or not maximum:
                    continue
                percent = (obtained / maximum) * 100 if maximum > 0 else None
                if school not in school_students:
                    school_students[school] = []
                school_students[school].append((student_id, percent))

            # Calculate bucket % and unique counts for each school
            bucket_data = []
            for school, student_percents in school_students.items():
                green_ids = set()
                blue_ids = set()
                red_ids = set()
                for student_id, percent in student_percents:
                    if percent is None:
                        continue
                    if percent > 60:
                        green_ids.add(student_id)
                    elif percent >= 35:
                        blue_ids.add(student_id)
                    else:
                        red_ids.add(student_id)
                total = len(set([sid for sid, p in student_percents if p is not None]))
                if total == 0:
                    continue
                green = len(green_ids)
                blue = len(blue_ids)
                red = len(red_ids)
                bucket_data.append({
                    'school': school,
                    'green': round(green / total * 100, 2),
                    'green_count': green,
                    'blue': round(blue / total * 100, 2),
                    'blue_count': blue,
                    'red': round(red / total * 100, 2),
                    'red_count': red
                })

            # Sort by green % descending
            bucket_data.sort(key=lambda x: x['green'], reverse=True)

        return jsonify(bucket_data)
    except Exception as e:
        logger.error(f"Error getting bucket-wise chart data: {e}")
        return jsonify({"error": f"Failed to fetch bucket-wise chart data: {str(e)}"}), 500
