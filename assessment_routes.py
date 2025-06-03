import logging
import pandas as pd
import json
from datetime import datetime
from flask import Blueprint, render_template, flash, redirect, url_for, current_app, jsonify, request, session
from models import StudentAssessmentData, db

# Define the Blueprint
assessment_bp = Blueprint('assessment', __name__, url_prefix='/assessment')

@assessment_bp.route('/')
def view():
    """Assessment dashboard view."""
    # Check if user is logged in using session
    if "user_email" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("index"))

    try:
        return render_template(
            "assessment_dashboard.html",
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
        # Query unique values for each filter
        academic_years = db.session.query(StudentAssessmentData.academic_year).distinct().all()
        academic_years = sorted([year[0] for year in academic_years if year[0]], reverse=True)

        subjects = db.session.query(StudentAssessmentData.subject_name).distinct().all()
        subjects = sorted([subject[0] for subject in subjects if subject[0]])

        schools = db.session.query(StudentAssessmentData.school_name).distinct().all()
        schools = sorted([school[0] for school in schools if school[0]])

        assessment_types = db.session.query(StudentAssessmentData.assessment_type).distinct().all()
        assessment_types = sorted([type[0] for type in assessment_types if type[0]])

        grades = db.session.query(StudentAssessmentData.grade_name).distinct().all()
        grades = sorted([grade[0] for grade in grades if grade[0]])

        competency_levels = db.session.query(StudentAssessmentData.competency_level_name).distinct().all()
        competency_levels = sorted([level[0] for level in competency_levels if level[0]])

        divisions = db.session.query(StudentAssessmentData.division_name).distinct().all()
        divisions = sorted([division[0] for division in divisions if division[0]])

        genders = db.session.query(StudentAssessmentData.gender).distinct().all()
        genders = sorted([gender[0] for gender in genders if gender[0]])

        # Get min and max assessment dates for date range picker
        min_date = db.session.query(db.func.min(StudentAssessmentData.assessmentDate)).scalar()
        max_date = db.session.query(db.func.max(StudentAssessmentData.assessmentDate)).scalar()

        min_date_str = min_date.strftime('%Y-%m-%d') if min_date else None
        max_date_str = max_date.strftime('%Y-%m-%d') if max_date else None

        return jsonify({
            'academic_years': academic_years,
            'subjects': subjects,
            'schools': schools,
            'assessment_types': assessment_types,
            'grades': grades,
            'competency_levels': competency_levels,
            'divisions': divisions,
            'genders': genders,
            'date_range': {
                'min': min_date_str,
                'max': max_date_str
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error getting assessment filters: {e}")
        return jsonify({"error": f"Failed to fetch assessment filters: {str(e)}"}), 500

import hashlib
import json
import pandas as pd
import numpy as np
from functools import lru_cache
from sqlalchemy import func, and_

# Create simple cache dictionaries
dashboard_cache = {}
chart_cache = {}

@assessment_bp.route('/get_dashboard_data', methods=['POST'])
def get_dashboard_data():
    """Get assessment data based on selected filters for the dashboard."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Create a cache key based on the filters
        cache_key = hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()

        # Check if we have cached results for these filters
        if cache_key in dashboard_cache:
            current_app.logger.info(f"Using cached data for filters: {filters}")
            return jsonify(dashboard_cache[cache_key])

        current_app.logger.info(f"Fetching new data for filters: {filters}")

        # Extract filter values
        academic_year = filters.get('academic_year', 'All')
        subject = filters.get('subject', 'All')
        school = filters.get('school', 'All')
        assessment_type = filters.get('assessment_type', 'All')
        grade = filters.get('grade', 'All')
        competency_level = filters.get('competency_level', 'All')
        division = filters.get('division', 'All')
        gender = filters.get('gender', 'All')
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')

        # Build the query with only the columns we need
        query = db.session.query(
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
            StudentAssessmentData.division_name,
            StudentAssessmentData.assessmentDate,
            StudentAssessmentData.gender,
            StudentAssessmentData.present_absent,
            StudentAssessmentData.academic_year,
            StudentAssessmentData.assessment_type
        )

        # Apply filters
        if academic_year != 'All':
            query = query.filter(StudentAssessmentData.academic_year == academic_year)
        if subject != 'All':
            query = query.filter(StudentAssessmentData.subject_name == subject)
        if school != 'All':
            query = query.filter(StudentAssessmentData.school_name == school)
        if assessment_type != 'All':
            query = query.filter(StudentAssessmentData.assessment_type == assessment_type)
        if grade != 'All':
            query = query.filter(StudentAssessmentData.grade_name == grade)
        if competency_level != 'All':
            query = query.filter(StudentAssessmentData.competency_level_name == competency_level)
        if division != 'All':
            query = query.filter(StudentAssessmentData.division_name == division)
        if gender != 'All':
            query = query.filter(StudentAssessmentData.gender == gender)
        if start_date and end_date:
            query = query.filter(StudentAssessmentData.assessmentDate.between(start_date, end_date))

        # Execute the query to get all records
        results = query.all()

        # Convert to dictionary format
        assessment_data = []
        for assessment in results:
            assessment_data.append({
                'id': assessment.id,
                'assessment_type': assessment.assessment_type,
                'subject_name': assessment.subject_name,
                'school_name': assessment.school_name,
                'grade_name': assessment.grade_name,
                'student_name': assessment.student_name,
                'student_id': assessment.student_id,
                'obtained_marks': float(assessment.obtained_marks) if assessment.obtained_marks else 0,
                'max_marks': float(assessment.max_marks) if assessment.max_marks else 0,
                'percentage': float(assessment.percentage) if assessment.percentage else 0,
                'competency_level_name': assessment.competency_level_name,
                'division_name': assessment.division_name,
                'assessment_date': assessment.assessmentDate.strftime('%Y-%m-%d') if assessment.assessmentDate else None,
                'gender': assessment.gender,
                'present_absent': assessment.present_absent,
                'academic_year': assessment.academic_year,
                'assessment_type': assessment.assessment_type
            })

        # Cache the results
        dashboard_cache[cache_key] = assessment_data

        # Limit cache size to prevent memory issues (keep only the 10 most recent queries)
        if len(dashboard_cache) > 10:
            oldest_key = next(iter(dashboard_cache))
            dashboard_cache.pop(oldest_key)

        return jsonify(assessment_data)
    except Exception as e:
        current_app.logger.error(f"Error getting assessment dashboard data: {e}")
        return jsonify({"error": f"Failed to fetch assessment data: {str(e)}"}), 500

# Helper function to build filter conditions
def build_filter_conditions(filters):
    """Build SQLAlchemy filter conditions based on the provided filters."""
    conditions = []

    academic_year = filters.get('academic_year', 'All')
    subject = filters.get('subject', 'All')
    school = filters.get('school', 'All')
    assessment_type = filters.get('assessment_type', 'All')
    grade = filters.get('grade', 'All')
    competency_level = filters.get('competency_level', 'All')
    division = filters.get('division', 'All')
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
    if competency_level != 'All':
        conditions.append(StudentAssessmentData.competency_level_name == competency_level)
    if division != 'All':
        conditions.append(StudentAssessmentData.division_name == division)
    if gender != 'All':
        conditions.append(StudentAssessmentData.gender == gender)
    if start_date and end_date:
        conditions.append(StudentAssessmentData.assessmentDate.between(start_date, end_date))

    return conditions

@assessment_bp.route('/chart/overall_performance', methods=['POST'])
def get_overall_performance_chart():
    """Get data for the overall performance pie chart."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Create a cache key
        cache_key = f"overall_performance_{hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()}"

        # Check cache
        if cache_key in chart_cache:
            current_app.logger.info(f"Using cached data for overall performance chart")
            return jsonify(chart_cache[cache_key])

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Query for competency level distribution
        query = db.session.query(
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

        for competency, count in results:
            labels.append(competency)
            data.append(count)

        chart_data = {
            'labels': labels,
            'data': data
        }

        # Cache the results
        chart_cache[cache_key] = chart_data

        return jsonify(chart_data)

    except Exception as e:
        current_app.logger.error(f"Error getting overall performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/chart/school_performance', methods=['POST'])
def get_school_performance_chart():
    """Get data for the school performance bar chart."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Create a cache key
        cache_key = f"school_performance_{hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()}"

        # Check cache
        if cache_key in chart_cache:
            current_app.logger.info(f"Using cached data for school performance chart")
            return jsonify(chart_cache[cache_key])

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Query for school performance
        query = db.session.query(
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

        # Cache the results
        chart_cache[cache_key] = chart_data

        return jsonify(chart_data)

    except Exception as e:
        current_app.logger.error(f"Error getting school performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/chart/subject_performance', methods=['POST'])
def get_subject_performance_chart():
    """Get data for the subject performance bar chart."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Create a cache key
        cache_key = f"subject_performance_{hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()}"

        # Check cache
        if cache_key in chart_cache:
            current_app.logger.info(f"Using cached data for subject performance chart")
            return jsonify(chart_cache[cache_key])

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Query for subject performance
        query = db.session.query(
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

        # Cache the results
        chart_cache[cache_key] = chart_data

        return jsonify(chart_data)

    except Exception as e:
        current_app.logger.error(f"Error getting subject performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/chart/gender_performance', methods=['POST'])
def get_gender_performance_chart():
    """Get data for the gender performance bar chart."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Create a cache key
        cache_key = f"gender_performance_{hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()}"

        # Check cache
        if cache_key in chart_cache:
            current_app.logger.info(f"Using cached data for gender performance chart")
            return jsonify(chart_cache[cache_key])

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Query for gender performance
        query = db.session.query(
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
                genders.append("Male" if gender == "M" else "Female" if gender == "F" else gender)
                percentages.append(round((obtained / maximum) * 100, 2))

        chart_data = {
            'labels': genders,
            'data': percentages
        }

        # Cache the results
        chart_cache[cache_key] = chart_data

        return jsonify(chart_data)

    except Exception as e:
        current_app.logger.error(f"Error getting gender performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/chart/grade_performance', methods=['POST'])
def get_grade_performance_chart():
    """Get data for the grade performance bar chart."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Create a cache key
        cache_key = f"grade_performance_{hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()}"

        # Check cache
        if cache_key in chart_cache:
            current_app.logger.info(f"Using cached data for grade performance chart")
            return jsonify(chart_cache[cache_key])

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Query for grade performance
        query = db.session.query(
            StudentAssessmentData.grade_name,
            func.sum(StudentAssessmentData.obtained_marks),
            func.sum(StudentAssessmentData.max_marks)
        ).filter(
            *conditions,
            StudentAssessmentData.grade_name.isnot(None),
            StudentAssessmentData.obtained_marks.isnot(None),
            StudentAssessmentData.max_marks.isnot(None),
            StudentAssessmentData.max_marks > 0
        ).group_by(
            StudentAssessmentData.grade_name
        )

        results = query.all()

        # Define grade order
        grade_order = ['JR.KG', 'SR.KG', 'GRADE 1', 'GRADE 2', 'GRADE 3', 'GRADE 4', 'GRADE 5', 'GRADE 6', 'GRADE 7', 'GRADE 8', 'GRADE 9', 'GRADE 10']
        grade_display = ['Jr.KG', 'Sr.KG', 'Gr. 1', 'Gr. 2', 'Gr. 3', 'Gr. 4', 'Gr. 5', 'Gr. 6', 'Gr. 7', 'Gr. 8', 'Gr. 9', 'Gr. 10']

        # Process results
        grade_data = {}

        for grade, obtained, maximum in results:
            if maximum > 0:
                grade_data[grade] = {
                    'obtained': float(obtained),
                    'maximum': float(maximum),
                    'percentage': round((obtained / maximum) * 100, 2)
                }

        # Order grades
        ordered_grades = []
        ordered_percentages = []

        for i, grade in enumerate(grade_order):
            if grade in grade_data:
                ordered_grades.append(grade_display[i])
                ordered_percentages.append(grade_data[grade]['percentage'])

        chart_data = {
            'labels': ordered_grades,
            'data': ordered_percentages
        }

        # Cache the results
        chart_cache[cache_key] = chart_data

        return jsonify(chart_data)

    except Exception as e:
        current_app.logger.error(f"Error getting grade performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/chart/city_grade_performance', methods=['POST'])
def get_city_grade_performance_chart():
    """Get data for the city-grade performance chart."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Create a cache key
        cache_key = f"city_grade_performance_{hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()}"

        # Check cache
        if cache_key in chart_cache:
            current_app.logger.info(f"Using cached data for city-grade performance chart")
            return jsonify(chart_cache[cache_key])

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Define city mapping
        city_schools = {
            'Mumbai': ['ABMPS', 'DNMPS', 'LNMPS', 'MLMPS', 'NMMC93', 'NNMPS', 'SMCMPS', 'SMPS', 'WBMPS'],
            'Pune': ['ANWEMS', 'BOPEMS', 'CSMEMS', 'KCTVN', 'LAPMEMS', 'LDRKEMS', 'MEMS', 'PKGEMS', 'SBP', 'SBP-MO'],
            'Nagpur': ['LBBNPS', 'BNPS', 'LGMNPS', 'RDNPS', 'RMNPS', 'RNPS']
        }

        # Define grade order
        grade_order = ['JR.KG', 'SR.KG', 'GRADE 1', 'GRADE 2', 'GRADE 3', 'GRADE 4', 'GRADE 5', 'GRADE 6', 'GRADE 7', 'GRADE 8', 'GRADE 9', 'GRADE 10']
        grade_display = ['Jr.KG', 'Sr.KG', 'Gr. 1', 'Gr. 2', 'Gr. 3', 'Gr. 4', 'Gr. 5', 'Gr. 6', 'Gr. 7', 'Gr. 8', 'Gr. 9', 'Gr. 10']

        # Initialize data structure
        city_grade_data = {}
        for city in city_schools:
            city_grade_data[city] = {}
            for grade in grade_order:
                city_grade_data[city][grade] = {
                    'obtained': 0,
                    'maximum': 0
                }

        # Query for all data needed
        query = db.session.query(
            StudentAssessmentData.school_name,
            StudentAssessmentData.grade_name,
            func.sum(StudentAssessmentData.obtained_marks),
            func.sum(StudentAssessmentData.max_marks)
        ).filter(
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

        # Process results
        for school, grade, obtained, maximum in results:
            # Map school to city
            city = None
            for c, schools in city_schools.items():
                if school in schools:
                    city = c
                    break

            if city and grade in grade_order and maximum > 0:
                city_grade_data[city][grade]['obtained'] += float(obtained)
                city_grade_data[city][grade]['maximum'] += float(maximum)

        # Calculate percentages and prepare chart data
        chart_data = {
            'labels': [],
            'datasets': []
        }

        # Get grades that have data
        grades_with_data = []
        for i, grade in enumerate(grade_order):
            has_data = False
            for city in city_schools:
                if city_grade_data[city][grade]['maximum'] > 0:
                    has_data = True
                    break

            if has_data:
                grades_with_data.append((grade, grade_display[i]))

        # Set labels
        chart_data['labels'] = [g[1] for g in grades_with_data]

        # Create datasets
        colors = {
            'Mumbai': 'rgba(54, 162, 235, 0.6)',
            'Pune': 'rgba(255, 99, 132, 0.6)',
            'Nagpur': 'rgba(255, 206, 86, 0.6)'
        }

        for city in city_schools:
            dataset = {
                'label': city,
                'data': [],
                'backgroundColor': colors[city],
                'borderColor': colors[city].replace('0.6', '1'),
                'borderWidth': 1
            }

            for grade, _ in grades_with_data:
                data = city_grade_data[city][grade]
                if data['maximum'] > 0:
                    percentage = round((data['obtained'] / data['maximum']) * 100, 2)
                else:
                    percentage = 0
                dataset['data'].append(percentage)

            chart_data['datasets'].append(dataset)

        # Cache the results
        chart_cache[cache_key] = chart_data

        return jsonify(chart_data)

    except Exception as e:
        current_app.logger.error(f"Error getting city-grade performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/chart/city_subject_performance', methods=['POST'])
def get_city_subject_performance_chart():
    """Get data for the city-subject performance chart."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Create a cache key
        cache_key = f"city_subject_performance_{hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()}"

        # Check cache
        if cache_key in chart_cache:
            current_app.logger.info(f"Using cached data for city-subject performance chart")
            return jsonify(chart_cache[cache_key])

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Define city mapping
        city_schools = {
            'Mumbai': ['ABMPS', 'DNMPS', 'LNMPS', 'MLMPS', 'NMMC93', 'NNMPS', 'SMCMPS', 'SMPS', 'WBMPS'],
            'Pune': ['ANWEMS', 'BOPEMS', 'CSMEMS', 'KCTVN', 'LAPMEMS', 'LDRKEMS', 'MEMS', 'PKGEMS', 'SBP', 'SBP-MO'],
            'Nagpur': ['LBBNPS', 'BNPS', 'LGMNPS', 'RDNPS', 'RMNPS', 'RNPS']
        }

        # Define subject mapping
        subject_map = {
            'Math': ['Math', 'Mathematics', 'Maths'],
            'English': ['English', 'ENG'],
            'Hindi': ['Hindi', 'HIN'],
            'Marathi': ['Marathi', 'MAR'],
            'Science': ['Science', 'SCI'],
            'Computer': ['Computer', 'COM', 'Computer Science']
        }

        subject_display = {
            'Math': 'Mat',
            'English': 'Eng',
            'Hindi': 'Hin',
            'Marathi': 'Mar',
            'Science': 'Sci',
            'Computer': 'Com'
        }

        # Initialize data structure
        city_subject_data = {}
        for city in list(city_schools.keys()) + ['Akanksha']:
            city_subject_data[city] = {}
            for subject in subject_map:
                city_subject_data[city][subject] = {
                    'obtained': 0,
                    'maximum': 0
                }

        # Query for all data needed
        query = db.session.query(
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

        # Process results
        for school, subject, obtained, maximum in results:
            # Map school to city
            city = None
            for c, schools in city_schools.items():
                if school in schools:
                    city = c
                    break

            # Map subject to standardized subject
            std_subject = None
            for s, variations in subject_map.items():
                if any(v.lower() in subject.lower() for v in variations):
                    std_subject = s
                    break

            if std_subject and maximum > 0:
                # Add to city data if city was found
                if city:
                    city_subject_data[city][std_subject]['obtained'] += float(obtained)
                    city_subject_data[city][std_subject]['maximum'] += float(maximum)

                # Add to Akanksha (all schools)
                city_subject_data['Akanksha'][std_subject]['obtained'] += float(obtained)
                city_subject_data['Akanksha'][std_subject]['maximum'] += float(maximum)

        # Calculate percentages and prepare table data
        table_data = []

        # Add Akanksha row first, then other cities
        for city in ['Akanksha'] + list(city_schools.keys()):
            row = {'city': city}

            for subject in subject_map:
                data = city_subject_data[city][subject]
                if data['maximum'] > 0:
                    row[subject_display[subject]] = round((data['obtained'] / data['maximum']) * 100, 2)
                else:
                    row[subject_display[subject]] = None

            table_data.append(row)

        # Cache the results
        chart_cache[cache_key] = table_data

        return jsonify(table_data)

    except Exception as e:
        current_app.logger.error(f"Error getting city-subject performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500

@assessment_bp.route('/chart/school_grade_performance', methods=['POST'])
def get_school_grade_performance_chart():
    """Get data for the school-grade performance table."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Create a cache key
        cache_key = f"school_grade_performance_{hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()}"

        # Check cache
        if cache_key in chart_cache:
            current_app.logger.info(f"Using cached data for school-grade performance chart")
            return jsonify(chart_cache[cache_key])

        # Build filter conditions
        conditions = build_filter_conditions(filters)

        # Define city mapping
        city_schools = {
            'Mumbai': ['ABMPS', 'DNMPS', 'LNMPS', 'MLMPS', 'NMMC93', 'NNMPS', 'SMCMPS', 'SMPS', 'WBMPS'],
            'Pune': ['ANWEMS', 'BOPEMS', 'CSMEMS', 'KCTVN', 'LAPMEMS', 'LDRKEMS', 'MEMS', 'PKGEMS', 'SBP', 'SBP-MO'],
            'Nagpur': ['LBBNPS', 'BNPS', 'LGMNPS', 'RDNPS', 'RMNPS', 'RNPS']
        }

        # Get all schools
        all_schools = []
        for schools in city_schools.values():
            all_schools.extend(schools)

        # Define grade order
        grade_order = ['JR.KG', 'SR.KG', 'GRADE 1', 'GRADE 2', 'GRADE 3', 'GRADE 4', 'GRADE 5', 'GRADE 6', 'GRADE 7', 'GRADE 8', 'GRADE 9', 'GRADE 10']
        grade_display = ['Jr.KG', 'Sr.KG', 'Gr. 1', 'Gr. 2', 'Gr. 3', 'Gr. 4', 'Gr. 5', 'Gr. 6', 'Gr. 7', 'Gr. 8', 'Gr. 9', 'Gr. 10']

        # Initialize data structure
        school_grade_data = {}
        for school in all_schools:
            school_grade_data[school] = {}
            for grade in grade_order:
                school_grade_data[school][grade] = {
                    'obtained': 0,
                    'maximum': 0
                }

        # Query for all data needed
        query = db.session.query(
            StudentAssessmentData.school_name,
            StudentAssessmentData.grade_name,
            func.sum(StudentAssessmentData.obtained_marks),
            func.sum(StudentAssessmentData.max_marks)
        ).filter(
            *conditions,
            StudentAssessmentData.school_name.isnot(None),
            StudentAssessmentData.grade_name.isnot(None),
            StudentAssessmentData.obtained_marks.isnot(None),
            StudentAssessmentData.max_marks.isnot(None),
            StudentAssessmentData.max_marks > 0,
            StudentAssessmentData.school_name.in_(all_schools)
        ).group_by(
            StudentAssessmentData.school_name,
            StudentAssessmentData.grade_name
        )

        results = query.all()

        # Process results
        for school, grade, obtained, maximum in results:
            if grade in grade_order and maximum > 0:
                school_grade_data[school][grade]['obtained'] += float(obtained)
                school_grade_data[school][grade]['maximum'] += float(maximum)

        # Calculate percentages and prepare table data
        table_data = []

        # Map grade names to display names
        grade_name_map = dict(zip(grade_order, grade_display))

        # Create table data
        for school in all_schools:
            row = {'school': school}

            for grade in grade_order:
                data = school_grade_data[school][grade]
                if data['maximum'] > 0:
                    row[grade_name_map[grade]] = round((data['obtained'] / data['maximum']) * 100, 2)
                else:
                    row[grade_name_map[grade]] = None

            table_data.append(row)

        # Cache the results
        chart_cache[cache_key] = table_data

        return jsonify(table_data)

    except Exception as e:
        current_app.logger.error(f"Error getting school-grade performance chart data: {e}")
        return jsonify({"error": f"Failed to fetch chart data: {str(e)}"}), 500
