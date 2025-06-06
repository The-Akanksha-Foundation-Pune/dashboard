import logging
from flask import Blueprint, render_template, flash, redirect, url_for, current_app, jsonify, request, session
from datetime import datetime, timedelta
from models import AllAssessments, db, StudentAssessmentData, ActiveStudentData, StudentAttendanceData, NonStandardisedAssessment
from sqlalchemy import func
from collections import defaultdict

# Define the Blueprint
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
def view():
    """Dashboard overview page."""
    from app import get_db_connection

    # Check if user is logged in using session
    if "user_email" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("index"))

    try:
        # Get user info from session
        user_info = {
            'name': session.get("user_name"),
            'email': session.get("user_email"),
            'picture': session.get("user_picture")
        }

        # Get dashboard summary data
        conn = get_db_connection()
        if not conn:
            flash("Unable to connect to database", "danger")
            return redirect(url_for("index"))

        try:
            # Skip database queries for now - we're showing a "Coming Soon" page
            pass
        finally:
            conn.close()

        return render_template(
            "dashboard_new.html",
            active_page='dashboard',
            name=user_info.get('name'),
            email=user_info.get('email'),
            picture=user_info.get('picture'),
            role=session.get("user_role"),
            school=session.get("user_school")
        )

    except Exception as e:
        current_app.logger.error(f"Error in dashboard route: {e}")
        flash("An error occurred. Please try again.", "danger")
        return redirect(url_for("index"))

@dashboard_bp.route('/attendance_summary', methods=['GET'])
def get_attendance_summary():
    """Get attendance summary for the dashboard cards."""
    from app import get_db_connection

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                # Get today's attendance
                cursor.execute("""
                    SELECT
                        COUNT(CASE WHEN is_present = 1 THEN 1 END) as present_count,
                        COUNT(*) as total_count
                    FROM student_attendance_data
                    WHERE DATE(attendance_date) = CURDATE()
                """)
                today = cursor.fetchone()

                # Get this week's attendance
                cursor.execute("""
                    SELECT
                        COUNT(CASE WHEN is_present = 1 THEN 1 END) as present_count,
                        COUNT(*) as total_count
                    FROM student_attendance_data
                    WHERE YEARWEEK(attendance_date) = YEARWEEK(CURDATE())
                """)
                this_week = cursor.fetchone()

                # Get this month's attendance
                cursor.execute("""
                    SELECT
                        COUNT(CASE WHEN is_present = 1 THEN 1 END) as present_count,
                        COUNT(*) as total_count
                    FROM student_attendance_data
                    WHERE MONTH(attendance_date) = MONTH(CURDATE())
                    AND YEAR(attendance_date) = YEAR(CURDATE())
                """)
                this_month = cursor.fetchone()

                # Calculate percentages
                today_percentage = (today['present_count'] / today['total_count'] * 100) if today['total_count'] > 0 else 0
                week_percentage = (this_week['present_count'] / this_week['total_count'] * 100) if this_week['total_count'] > 0 else 0
                month_percentage = (this_month['present_count'] / this_month['total_count'] * 100) if this_month['total_count'] > 0 else 0

                return jsonify({
                    "today": round(today_percentage, 1),
                    "this_week": round(week_percentage, 1),
                    "this_month": round(month_percentage, 1)
                })

        finally:
            conn.close()

    except Exception as e:
        current_app.logger.error(f"Error getting attendance summary: {e}")
        return jsonify({"error": "Failed to fetch attendance summary"}), 500

@dashboard_bp.route('/leadership_metrics', methods=['GET'])
def get_leadership_metrics():
    """Get key metrics for leadership dashboard graphs."""
    from app import get_db_connection

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                # 1. Program Success Rate
                cursor.execute("""
                    SELECT
                        p.program_name,
                        COUNT(DISTINCT e.student_id) as total_students,
                        COUNT(DISTINCT CASE WHEN a.final_score >= 75 THEN e.student_id END) as successful_students,
                        AVG(a.final_score) as avg_score
                    FROM program_enrollment e
                    JOIN program_assessments a ON e.enrollment_id = a.enrollment_id
                    JOIN programs p ON e.program_id = p.program_id
                    WHERE e.enrollment_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                    GROUP BY p.program_name
                """)
                program_success = cursor.fetchall()

                # 2. Teacher Performance Impact
                cursor.execute("""
                    SELECT
                        t.teacher_name,
                        COUNT(DISTINCT s.student_id) as students_taught,
                        AVG(a.improvement_score) as avg_improvement,
                        COUNT(DISTINCT CASE WHEN a.improvement_score > 20 THEN s.student_id END) as high_improvement_count
                    FROM teachers t
                    JOIN class_assignments ca ON t.teacher_id = ca.teacher_id
                    JOIN student_assignments s ON ca.class_id = s.class_id
                    JOIN academic_progress a ON s.student_id = a.student_id
                    WHERE ca.assignment_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                    GROUP BY t.teacher_id, t.teacher_name
                    ORDER BY avg_improvement DESC
                    LIMIT 10
                """)
                teacher_impact = cursor.fetchall()

                # 3. Resource Utilization
                cursor.execute("""
                    SELECT
                        r.resource_type,
                        COUNT(ru.usage_id) as total_uses,
                        COUNT(DISTINCT ru.student_id) as unique_students,
                        AVG(ru.duration_minutes) as avg_duration
                    FROM resource_usage ru
                    JOIN resources r ON ru.resource_id = r.resource_id
                    WHERE ru.usage_date >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
                    GROUP BY r.resource_type
                """)
                resource_usage = cursor.fetchall()

                # 4. Student Progress Timeline
                cursor.execute("""
                    SELECT
                        DATE_FORMAT(assessment_date, '%Y-%m') as month,
                        AVG(score_improvement) as avg_improvement,
                        COUNT(DISTINCT student_id) as students_assessed
                    FROM student_progress_tracking
                    WHERE assessment_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                    GROUP BY month
                    ORDER BY month
                """)
                progress_timeline = cursor.fetchall()

                # 5. Financial Metrics
                cursor.execute("""
                    SELECT
                        DATE_FORMAT(transaction_date, '%Y-%m') as month,
                        SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
                        SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expense,
                        COUNT(DISTINCT CASE WHEN type = 'income' THEN student_id END) as paying_students
                    FROM financial_transactions
                    WHERE transaction_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                    GROUP BY month
                    ORDER BY month
                """)
                financial_metrics = cursor.fetchall()

                # 6. Community Engagement Score
                cursor.execute("""
                    SELECT
                        c.city_name,
                        COUNT(DISTINCT e.event_id) as total_events,
                        AVG(e.attendance_rate) as avg_attendance_rate,
                        COUNT(DISTINCT v.volunteer_id) as volunteer_count,
                        AVG(e.satisfaction_score) as avg_satisfaction
                    FROM community_events e
                    JOIN cities c ON e.city_id = c.city_id
                    LEFT JOIN event_volunteers v ON e.event_id = v.event_id
                    WHERE e.event_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                    GROUP BY c.city_id, c.city_name
                """)
                community_engagement = cursor.fetchall()

                return jsonify({
                    "program_success": [dict(row) for row in program_success],
                    "teacher_impact": [dict(row) for row in teacher_impact],
                    "resource_usage": [dict(row) for row in resource_usage],
                    "progress_timeline": [dict(row) for row in progress_timeline],
                    "financial_metrics": [dict(row) for row in financial_metrics],
                    "community_engagement": [dict(row) for row in community_engagement]
                })

        finally:
            conn.close()

    except Exception as e:
        current_app.logger.error(f"Error getting leadership metrics: {e}")
        return jsonify({"error": "Failed to fetch leadership metrics"}), 500

@dashboard_bp.route('/student_insights', methods=['GET'])
def get_student_insights():
    """Get advanced student insights for the leadership dashboard."""
    from app import get_db_connection

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cursor:
                # Get student distribution with performance metrics
                cursor.execute("""
                    SELECT
                        city,
                        grade,
                        COUNT(*) as student_count,
                        AVG(academic_score) as avg_performance,
                        COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_count,
                        COUNT(CASE WHEN attendance_rate >= 0.9 THEN 1 END) as high_attendance_count,
                        AVG(CASE
                            WHEN gender = 'Female' THEN 1
                            WHEN gender = 'Male' THEN 0
                            ELSE 0.5
                        END) as gender_ratio
                    FROM active_student_data
                    GROUP BY city, grade
                    ORDER BY city, grade
                """)
                distribution_data = cursor.fetchall()

                return jsonify({
                    "student_distribution": [dict(row) for row in distribution_data]
                })

        finally:
            conn.close()
    except Exception as e:
        current_app.logger.error(f"Error getting student insights: {e}")
        return jsonify({"error": "Failed to fetch student insights"}), 500

@dashboard_bp.route('/assessments')
def assessments():
    """Redirect to the assessment dashboard."""
    return redirect(url_for("assessment.view"))

@dashboard_bp.route('/get_assessment_filters', methods=['GET'])
def get_assessment_filters():
    """Get available filters for assessments."""
    try:
        # Query unique academic years
        academic_years = db.session.query(AllAssessments.academic_year).distinct().all()
        academic_years = [year[0] for year in academic_years if year[0]]

        # Query unique exam types
        exam_types = db.session.query(AllAssessments.exam_type).distinct().all()
        exam_types = [type[0] for type in exam_types if type[0]]

        # Query unique assessment types
        assessment_types = db.session.query(AllAssessments.assessment_type).distinct().all()
        assessment_types = [type[0] for type in assessment_types if type[0]]

        # Query unique subjects
        subjects = db.session.query(AllAssessments.subject_name).distinct().all()
        subjects = [subject[0] for subject in subjects if subject[0]]

        return jsonify({
            'academic_years': sorted(academic_years),
            'exam_types': sorted(exam_types),
            'assessment_types': sorted(assessment_types),
            'subjects': sorted(subjects)
        })
    except Exception as e:
        current_app.logger.error(f"Error getting assessment filters: {e}")
        return jsonify({"error": "Failed to fetch assessment filters"}), 500

@dashboard_bp.route('/get_assessment_data', methods=['POST'])
def get_assessment_data():
    """Get assessment data based on selected filters."""
    try:
        filters = request.get_json()
        if not filters:
            return jsonify({"error": "Missing filter data"}), 400

        # Extract filter values
        academic_years = filters.get('academic_years', [])
        exam_types = filters.get('exam_types', [])
        assessment_types = filters.get('assessment_types', [])
        subjects = filters.get('subjects', [])

        # Build the query
        query = db.session.query(AllAssessments)

        # Apply filters
        if academic_years:
            query = query.filter(AllAssessments.academic_year.in_(academic_years))
        if exam_types:
            query = query.filter(AllAssessments.exam_type.in_(exam_types))
        if assessment_types:
            query = query.filter(AllAssessments.assessment_type.in_(assessment_types))
        if subjects:
            query = query.filter(AllAssessments.subject_name.in_(subjects))

        # Execute the query with limit to avoid memory issues
        results = query.limit(10000).all()

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
                'obtained_marks': assessment.obtained_marks,
                'max_marks': assessment.max_marks,
                'percentage': assessment.percentage,
                'competency_level_name': assessment.competency_level_name,
                'academic_year': assessment.academic_year,
                'exam_type': assessment.exam_type,
                'assessment_date': assessment.assessment_date.strftime('%Y-%m-%d') if assessment.assessment_date else None
            })

        return jsonify(assessment_data)
    except Exception as e:
        current_app.logger.error(f"Error getting assessment data: {e}")
        return jsonify({"error": f"Failed to fetch assessment data: {str(e)}"}), 500

@dashboard_bp.route('/kaleidoscope', methods=['GET'])
def kaleidoscope_dashboard():
    """Render the Kaleidoscope dashboard with all tabs on a single page."""
    # Query unique values for filters
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
    grades = ['All'] + grades  # Add 'All' option at the top

    divisions = db.session.query(StudentAssessmentData.division_name).distinct().all()
    divisions = sorted([division[0] for division in divisions if division[0]])

    return render_template(
        'kaleidoscope.html',
        academic_years=academic_years,
        subjects=subjects,
        schools=schools,
        assessment_types=assessment_types,
        grades=grades,
        divisions=divisions
    )

@dashboard_bp.route('/kaleidoscope/data', methods=['GET'])
def kaleidoscope_data():
    """Return assessment data as JSON for the Kaleidoscope dashboard based on filters."""
    assessment_type = request.args.get('assessment_type')
    academic_year = request.args.get('academic_year')
    subject = request.args.get('subject')
    school = request.args.get('school')
    grade = request.args.get('grade')
    division = request.args.get('division')

    query = db.session.query(
        StudentAssessmentData.competency_level_name,
        StudentAssessmentData.obtained_marks,
        StudentAssessmentData.max_marks,
        StudentAssessmentData.subject_name,
        StudentAssessmentData.grade_name,
        StudentAssessmentData.division_name,
        StudentAssessmentData.assessment_type,
        StudentAssessmentData.academic_year
    )
    if assessment_type:
        query = query.filter(StudentAssessmentData.assessment_type == assessment_type)
    if academic_year:
        query = query.filter(StudentAssessmentData.academic_year == academic_year)
    if subject:
        query = query.filter(StudentAssessmentData.subject_name == subject)
    if school:
        query = query.filter(StudentAssessmentData.school_name == school)
    if grade:
        query = query.filter(StudentAssessmentData.grade_name == grade)
    if division:
        query = query.filter(StudentAssessmentData.division_name == division)

    results = query.all()
    data = [
        {
            'competency_level_name': r.competency_level_name,
            'obtained_marks': r.obtained_marks,
            'max_marks': r.max_marks,
            'subject_name': r.subject_name,
            'grade_name': r.grade_name,
            'division_name': r.division_name,
            'assessment_type': r.assessment_type,
            'academic_year': r.academic_year
        }
        for r in results
    ]
    return jsonify(data)

@dashboard_bp.route('/kaleidoscope/bucket_data', methods=['GET'])
def kaleidoscope_bucket_data():
    """Return stacked bar data for Bucket Analysis: unique student counts per competency and overall."""
    assessment_type = request.args.get('assessment_type')
    academic_year = request.args.get('academic_year')
    subject = request.args.get('subject')
    school = request.args.get('school')
    grade = request.args.get('grade')
    division = request.args.get('division')

    query = db.session.query(
        StudentAssessmentData.student_id,
        StudentAssessmentData.competency_level_name,
        StudentAssessmentData.obtained_marks,
        StudentAssessmentData.max_marks
    )
    if assessment_type:
        query = query.filter(StudentAssessmentData.assessment_type == assessment_type)
    if academic_year:
        query = query.filter(StudentAssessmentData.academic_year == academic_year)
    if subject:
        query = query.filter(StudentAssessmentData.subject_name == subject)
    if school:
        query = query.filter(StudentAssessmentData.school_name == school)
    if grade:
        query = query.filter(StudentAssessmentData.grade_name == grade)
    if division:
        query = query.filter(StudentAssessmentData.division_name == division)

    # Structure: {competency: {student_id: {'obtained': x, 'max': y}}}
    comp_student_totals = {}
    overall_student_totals = {}
    for row in query:
        if not row.student_id or not row.competency_level_name:
            continue
        # Per-competency
        comp = row.competency_level_name
        if comp not in comp_student_totals:
            comp_student_totals[comp] = {}
        if row.student_id not in comp_student_totals[comp]:
            comp_student_totals[comp][row.student_id] = {'obtained': 0, 'max': 0}
        comp_student_totals[comp][row.student_id]['obtained'] += row.obtained_marks or 0
        comp_student_totals[comp][row.student_id]['max'] += row.max_marks or 0
        # Overall
        if row.student_id not in overall_student_totals:
            overall_student_totals[row.student_id] = {'obtained': 0, 'max': 0}
        overall_student_totals[row.student_id]['obtained'] += row.obtained_marks or 0
        overall_student_totals[row.student_id]['max'] += row.max_marks or 0

    # For each competency, count unique students in each bucket
    competencies = sorted(comp_student_totals.keys())
    bucket_names = ['Red', 'Blue', 'Green']
    bucket_counts = {b: [] for b in bucket_names}
    for comp in competencies:
        # Use a set to ensure unique student IDs per bucket
        bucket_students = {'Red': set(), 'Blue': set(), 'Green': set()}
        for student_id, totals in comp_student_totals[comp].items():
            if totals['max'] > 0:
                percent = (totals['obtained'] / totals['max']) * 100
                if percent > 60:
                    bucket_students['Green'].add(student_id)
                elif percent >= 35:
                    bucket_students['Blue'].add(student_id)
                else:
                    bucket_students['Red'].add(student_id)
        for b in bucket_names:
            bucket_counts[b].append(len(bucket_students[b]))

    # Overall bucket counts (unique students)
    overall_bucket_students = {'Red': set(), 'Blue': set(), 'Green': set()}
    for student_id, totals in overall_student_totals.items():
        if totals['max'] > 0:
            percent = (totals['obtained'] / totals['max']) * 100
            if percent > 60:
                overall_bucket_students['Green'].add(student_id)
            elif percent >= 35:
                overall_bucket_students['Blue'].add(student_id)
            else:
                overall_bucket_students['Red'].add(student_id)
    for b in bucket_names:
        bucket_counts[b].append(len(overall_bucket_students[b]))
    competencies_with_overall = competencies + ['Overall']
    return jsonify({
        'competencies': competencies_with_overall,
        'Red': bucket_counts['Red'],
        'Blue': bucket_counts['Blue'],
        'Green': bucket_counts['Green']
    })

@dashboard_bp.route('/kaleidoscope/sorted_list', methods=['GET'])
def kaleidoscope_sorted_list():
    """Return, for each competency and overall, a sorted list of students with their average and bucket."""
    assessment_type = request.args.get('assessment_type')
    academic_year = request.args.get('academic_year')
    subject = request.args.get('subject')
    school = request.args.get('school')
    grade = request.args.get('grade')
    division = request.args.get('division')

    query = db.session.query(
        StudentAssessmentData.student_id,
        StudentAssessmentData.student_name,
        StudentAssessmentData.competency_level_name,
        StudentAssessmentData.obtained_marks,
        StudentAssessmentData.max_marks
    )
    if assessment_type:
        query = query.filter(StudentAssessmentData.assessment_type == assessment_type)
    if academic_year:
        query = query.filter(StudentAssessmentData.academic_year == academic_year)
    if subject:
        query = query.filter(StudentAssessmentData.subject_name == subject)
    if school:
        query = query.filter(StudentAssessmentData.school_name == school)
    if grade:
        query = query.filter(StudentAssessmentData.grade_name == grade)
    if division:
        query = query.filter(StudentAssessmentData.division_name == division)

    # Structure: {competency: {student_id: {'name': ..., 'obtained': x, 'max': y}}}
    comp_student_totals = {}
    overall_student_totals = {}
    student_names = {}
    for row in query:
        if not row.student_id:
            continue
        comp = row.competency_level_name or 'Unknown'
        if comp not in comp_student_totals:
            comp_student_totals[comp] = {}
        if row.student_id not in comp_student_totals[comp]:
            comp_student_totals[comp][row.student_id] = {'obtained': 0, 'max': 0}
            student_names[row.student_id] = row.student_name
        comp_student_totals[comp][row.student_id]['obtained'] += row.obtained_marks or 0
        comp_student_totals[comp][row.student_id]['max'] += row.max_marks or 0
        # Overall
        if row.student_id not in overall_student_totals:
            overall_student_totals[row.student_id] = {'obtained': 0, 'max': 0}
        overall_student_totals[row.student_id]['obtained'] += row.obtained_marks or 0
        overall_student_totals[row.student_id]['max'] += row.max_marks or 0

    # For each competency, build sorted list
    result = {}
    for comp in sorted(comp_student_totals.keys()):
        students = []
        for student_id, totals in comp_student_totals[comp].items():
            if totals['max'] > 0:
                avg = (totals['obtained'] / totals['max']) * 100
                if avg > 60:
                    bucket = 'Green'
                elif avg >= 35:
                    bucket = 'Blue'
                else:
                    bucket = 'Red'
                students.append({
                    'student_name': student_names[student_id],
                    'average': round(avg, 2),
                    'bucket': bucket
                })
        students.sort(key=lambda x: x['average'], reverse=True)
        result[comp] = students
    # Overall
    overall_students = []
    for student_id, totals in overall_student_totals.items():
        if totals['max'] > 0:
            avg = (totals['obtained'] / totals['max']) * 100
            if avg > 60:
                bucket = 'Green'
            elif avg >= 35:
                bucket = 'Blue'
            else:
                bucket = 'Red'
            overall_students.append({
                'student_name': student_names.get(student_id, ''),
                'average': round(avg, 2),
                'bucket': bucket
            })
    overall_students.sort(key=lambda x: x['average'], reverse=True)
    result['Overall'] = overall_students
    return jsonify(result)

@dashboard_bp.route('/kaleidoscope/average_table', methods=['GET'])
def kaleidoscope_average_table():
    """Return a table of average scores: rows=grades, columns=subjects, cells=average percentage for that grade+subject."""
    assessment_type = request.args.get('assessment_type')
    academic_year = request.args.get('academic_year')
    subject = request.args.get('subject')
    school = request.args.get('school')
    grade = request.args.get('grade')
    division = request.args.get('division')

    query = db.session.query(
        StudentAssessmentData.grade_name,
        StudentAssessmentData.subject_name,
        StudentAssessmentData.obtained_marks,
        StudentAssessmentData.max_marks
    )
    if assessment_type:
        query = query.filter(StudentAssessmentData.assessment_type == assessment_type)
    if academic_year:
        query = query.filter(StudentAssessmentData.academic_year == academic_year)
    if school:
        query = query.filter(StudentAssessmentData.school_name == school)

    # Aggregate sums for each (grade, subject)
    table = {}
    grades_set = set()
    subjects_set = set()
    for row in query:
        if not row.grade_name or not row.subject_name:
            continue
        grades_set.add(row.grade_name)
        subjects_set.add(row.subject_name)
        key = (row.grade_name, row.subject_name)
        if key not in table:
            table[key] = {'obtained': 0, 'max': 0}
        table[key]['obtained'] += row.obtained_marks or 0
        table[key]['max'] += row.max_marks or 0

    # Define desired order
    SUBJECT_ORDER = ['English', 'Math', 'Hindi', 'Marathi', 'Science', 'Computer']
    GRADE_ORDER = [
        'Jr.KG', 'Sr.KG',
        'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Grade 5',
        'Grade 6', 'Grade 7', 'Grade 8', 'Grade 9', 'Grade 10',
        'Grade 11', 'Grade 12'
    ]
    # Only include grades/subjects present in the data, in the specified order
    grades = [g for g in GRADE_ORDER if g in grades_set]
    # Add any grades not in the order at the end (sorted)
    grades += sorted([g for g in grades_set if g not in GRADE_ORDER])
    subjects = [s for s in SUBJECT_ORDER if s in subjects_set]
    # Add any subjects not in the order at the end (sorted)
    subjects += sorted([s for s in subjects_set if s not in SUBJECT_ORDER])

    data = {g: {} for g in grades}
    # Calculate per-grade, per-subject averages
    for g in grades:
        for s in subjects:
            key = (g, s)
            if key in table and table[key]['max'] > 0:
                avg = (table[key]['obtained'] / table[key]['max']) * 100
                data[g][s] = round(avg, 2)
            else:
                data[g][s] = None
    # Calculate Overall column (average for all subjects for each grade)
    for g in grades:
        total = 0
        count = 0
        for s in subjects:
            if data[g][s] is not None:
                total += data[g][s]
                count += 1
        data[g]['Overall'] = round(total / count, 2) if count > 0 else None
    # Calculate Overall row (average for all grades for each subject)
    overall_row = {}
    for s in subjects:
        total = 0
        count = 0
        for g in grades:
            if data[g][s] is not None:
                total += data[g][s]
                count += 1
        overall_row[s] = round(total / count, 2) if count > 0 else None
    # Calculate grand overall (bottom-right cell)
    total = 0
    count = 0
    for g in grades:
        for s in subjects:
            if data[g][s] is not None:
                total += data[g][s]
                count += 1
    overall_row['Overall'] = round(total / count, 2) if count > 0 else None
    # Add Overall row to data
    data['Overall'] = overall_row
    # Add 'Overall' to subjects and grades at the end
    subjects_with_overall = subjects + ['Overall']
    grades_with_overall = grades + ['Overall']
    return jsonify({'grades': grades_with_overall, 'subjects': subjects_with_overall, 'data': data})

@dashboard_bp.route('/kaleidoscope/student_search')
def kaleidoscope_student_search():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify([])
    students = (db.session.query(ActiveStudentData.student_id, ActiveStudentData.student_name)
        .filter((ActiveStudentData.student_name.ilike(f'%{q}%')) | (ActiveStudentData.student_id.ilike(f'%{q}%')))
        .order_by(ActiveStudentData.student_name)
        .all())
    # Deduplicate by student_id
    seen = set()
    unique_students = []
    for s in students:
        if s.student_id not in seen:
            unique_students.append({'student_id': s.student_id, 'student_name': s.student_name})
            seen.add(s.student_id)
    return jsonify(unique_students)

@dashboard_bp.route('/kaleidoscope/portfolio_data')
def kaleidoscope_portfolio_data():
    student_id = request.args.get('student_id')
    if not student_id:
        return jsonify({'error': 'Missing student_id'}), 400
    # Subject-wise averages for all assessment types (standardized)
    std_query = db.session.query(
        StudentAssessmentData.subject_name,
        StudentAssessmentData.assessment_type,
        StudentAssessmentData.academic_year,
        func.sum(StudentAssessmentData.obtained_marks).label('obtained'),
        func.sum(StudentAssessmentData.max_marks).label('max')
    ).filter(StudentAssessmentData.student_id == student_id)
    std_query = std_query.group_by(StudentAssessmentData.subject_name, StudentAssessmentData.assessment_type, StudentAssessmentData.academic_year)
    std_results = std_query.all()
    # Subject-wise averages for all assessment types (non-standardized)
    nonstd_query = db.session.query(
        NonStandardisedAssessment.subject_name,
        NonStandardisedAssessment.assessment_type,
        NonStandardisedAssessment.academic_year,
        func.sum(NonStandardisedAssessment.obtained_marks).label('obtained'),
        func.sum(NonStandardisedAssessment.max_marks).label('max')
    ).filter(NonStandardisedAssessment.student_id == student_id)
    nonstd_query = nonstd_query.group_by(NonStandardisedAssessment.subject_name, NonStandardisedAssessment.assessment_type, NonStandardisedAssessment.academic_year)
    nonstd_results = nonstd_query.all()
    # Attendance by month and academic year
    att_query = db.session.query(
        StudentAttendanceData.month,
        StudentAttendanceData.academic_year,
        func.sum(StudentAttendanceData.no_of_present_days).label('present'),
        func.sum(StudentAttendanceData.no_of_working_days).label('working'),
        func.avg(StudentAttendanceData.attendance_percentage).label('attendance_percentage')
    ).filter(StudentAttendanceData.student_id == student_id)
    att_query = att_query.group_by(StudentAttendanceData.month, StudentAttendanceData.academic_year)
    att_results = att_query.all()
    attendance = [
        {
            'month': r.month,
            'academic_year': r.academic_year,
            'present': r.present,
            'working': r.working,
            'attendance_percentage': r.attendance_percentage
        }
        for r in att_results
    ]
    # Combine standardized and non-standardized, group by (subject, assessment_type, academic_year)
    combined = defaultdict(lambda: {'obtained': 0, 'max': 0})
    for r in std_results:
        key = (r.subject_name, r.assessment_type, r.academic_year)
        combined[key]['obtained'] += float(r.obtained) if r.obtained is not None else 0
        combined[key]['max'] += float(r.max) if r.max is not None else 0
    for r in nonstd_results:
        key = (r.subject_name, r.assessment_type, r.academic_year)
        combined[key]['obtained'] += float(r.obtained) if r.obtained is not None else 0
        combined[key]['max'] += float(r.max) if r.max is not None else 0
    assessment_averages = []
    for (subject, assessment_type, academic_year), vals in combined.items():
        avg = (vals['obtained'] / vals['max'] * 100) if vals['max'] else None
        assessment_averages.append({
            'subject': subject,
            'assessment_type': assessment_type,
            'academic_year': academic_year,
            'average': avg
        })
    # Competency strengths and areas to improve (group by subject, academic_year, assessment_type)
    comp_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'obtained': 0, 'max': 0}))))
    # Standardized
    std_comp_query = db.session.query(
        StudentAssessmentData.subject_name,
        StudentAssessmentData.competency_level_name,
        StudentAssessmentData.academic_year,
        StudentAssessmentData.assessment_type,
        func.sum(StudentAssessmentData.obtained_marks).label('obtained'),
        func.sum(StudentAssessmentData.max_marks).label('max')
    ).filter(StudentAssessmentData.student_id == student_id)
    std_comp_query = std_comp_query.group_by(StudentAssessmentData.subject_name, StudentAssessmentData.competency_level_name, StudentAssessmentData.academic_year, StudentAssessmentData.assessment_type)
    for r in std_comp_query:
        if r.subject_name and r.competency_level_name and r.academic_year and r.assessment_type:
            comp_data[r.subject_name][r.academic_year][r.assessment_type][r.competency_level_name]['obtained'] += float(r.obtained) if r.obtained is not None else 0
            comp_data[r.subject_name][r.academic_year][r.assessment_type][r.competency_level_name]['max'] += float(r.max) if r.max is not None else 0
    # Non-standardized
    nonstd_comp_query = db.session.query(
        NonStandardisedAssessment.subject_name,
        NonStandardisedAssessment.description.label('competency_level_name'),
        NonStandardisedAssessment.academic_year,
        NonStandardisedAssessment.assessment_type,
        func.sum(NonStandardisedAssessment.obtained_marks).label('obtained'),
        func.sum(NonStandardisedAssessment.max_marks).label('max')
    ).filter(NonStandardisedAssessment.student_id == student_id)
    nonstd_comp_query = nonstd_comp_query.group_by(NonStandardisedAssessment.subject_name, NonStandardisedAssessment.description, NonStandardisedAssessment.academic_year, NonStandardisedAssessment.assessment_type)
    for r in nonstd_comp_query:
        if r.subject_name and r.competency_level_name and r.academic_year and r.assessment_type:
            comp_data[r.subject_name][r.academic_year][r.assessment_type][r.competency_level_name]['obtained'] += float(r.obtained) if r.obtained is not None else 0
            comp_data[r.subject_name][r.academic_year][r.assessment_type][r.competency_level_name]['max'] += float(r.max) if r.max is not None else 0
    # Build summary
    competency_summary = {}
    for subject, year_dict in comp_data.items():
        subject_summary = {}
        for year, type_dict in year_dict.items():
            year_summary = {}
            for assessment_type, comp_dict in type_dict.items():
                good = []
                needs_improvement = []
                for comp, vals in comp_dict.items():
                    if vals['max'] > 0:
                        avg = (vals['obtained'] / vals['max']) * 100
                        if avg > 60:
                            good.append(comp)
                        elif avg < 35:
                            needs_improvement.append(comp)
                year_summary[assessment_type] = {
                    'good': sorted(good),
                    'needs_improvement': sorted(needs_improvement)
                }
            subject_summary[year] = year_summary
        competency_summary[subject] = subject_summary
    # Competency progression: for each subject and competency, show avg % for each (academic_year, assessment_type)
    progression_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'obtained': 0, 'max': 0})))
    # Standardized
    std_prog_query = db.session.query(
        StudentAssessmentData.subject_name,
        StudentAssessmentData.competency_level_name,
        StudentAssessmentData.academic_year,
        StudentAssessmentData.assessment_type,
        func.sum(StudentAssessmentData.obtained_marks).label('obtained'),
        func.sum(StudentAssessmentData.max_marks).label('max')
    ).filter(StudentAssessmentData.student_id == student_id)
    std_prog_query = std_prog_query.group_by(StudentAssessmentData.subject_name, StudentAssessmentData.competency_level_name, StudentAssessmentData.academic_year, StudentAssessmentData.assessment_type)
    for r in std_prog_query:
        if r.subject_name and r.competency_level_name and r.academic_year and r.assessment_type:
            progression_data[r.subject_name][r.competency_level_name][(r.academic_year, r.assessment_type)]['obtained'] += float(r.obtained) if r.obtained is not None else 0
            progression_data[r.subject_name][r.competency_level_name][(r.academic_year, r.assessment_type)]['max'] += float(r.max) if r.max is not None else 0
    # Non-standardized
    nonstd_prog_query = db.session.query(
        NonStandardisedAssessment.subject_name,
        NonStandardisedAssessment.description.label('competency_level_name'),
        NonStandardisedAssessment.academic_year,
        NonStandardisedAssessment.assessment_type,
        func.sum(NonStandardisedAssessment.obtained_marks).label('obtained'),
        func.sum(NonStandardisedAssessment.max_marks).label('max')
    ).filter(NonStandardisedAssessment.student_id == student_id)
    nonstd_prog_query = nonstd_prog_query.group_by(NonStandardisedAssessment.subject_name, NonStandardisedAssessment.description, NonStandardisedAssessment.academic_year, NonStandardisedAssessment.assessment_type)
    for r in nonstd_prog_query:
        if r.subject_name and r.competency_level_name and r.academic_year and r.assessment_type:
            progression_data[r.subject_name][r.competency_level_name][(r.academic_year, r.assessment_type)]['obtained'] += float(r.obtained) if r.obtained is not None else 0
            progression_data[r.subject_name][r.competency_level_name][(r.academic_year, r.assessment_type)]['max'] += float(r.max) if r.max is not None else 0
    # Build progression summary (only include competencies common across assessment types)
    competency_progression = {}
    for subject, comp_dict in progression_data.items():
        subject_dict = {}
        for comp, year_type_dict in comp_dict.items():
            # Find unique assessment types for this competency
            types_set = set(typ for (year, typ) in year_type_dict.keys())
            if len(types_set) <= 1:
                continue  # Only keep if present in more than one assessment type
            points = []
            for (year, typ), vals in year_type_dict.items():
                if vals['max'] > 0:
                    avg = (vals['obtained'] / vals['max']) * 100
                    points.append({'year': year, 'type': typ, 'avg': avg, 'obtained': vals['obtained'], 'max': vals['max']})
            # Sort by year asc, then type (MOY > EOY > others reverse alpha)
            def type_priority(t):
                if t == 'MOY': return 2
                if t == 'EOY': return 1
                return 0
            points.sort(key=lambda x: (x['year'], -type_priority(x['type']), x['type']), reverse=False)
            if points:
                subject_dict[comp] = points
        if subject_dict:
            competency_progression[subject] = subject_dict
    return jsonify({
        'assessment_averages': assessment_averages,
        'attendance': attendance,
        'competency_summary': competency_summary,
        'competency_progression': competency_progression
    })

@dashboard_bp.route('/kaleidoscope/average_by_year_type', methods=['GET'])
def kaleidoscope_average_by_year_type():
    """Return averages grouped by academic year and assessment type for the Kaleidoscope dashboard."""
    assessment_type = request.args.get('assessment_type')
    academic_year = request.args.get('academic_year')
    subject = request.args.get('subject')
    school = request.args.get('school')
    grade = request.args.get('grade')
    division = request.args.get('division')

    query = db.session.query(
        StudentAssessmentData.academic_year,
        StudentAssessmentData.assessment_type,
        func.sum(StudentAssessmentData.obtained_marks).label('obtained'),
        func.sum(StudentAssessmentData.max_marks).label('max')
    )
    if assessment_type:
        query = query.filter(StudentAssessmentData.assessment_type == assessment_type)
    if academic_year:
        query = query.filter(StudentAssessmentData.academic_year == academic_year)
    if subject:
        query = query.filter(StudentAssessmentData.subject_name == subject)
    if school:
        query = query.filter(StudentAssessmentData.school_name == school)
    if grade:
        query = query.filter(StudentAssessmentData.grade_name == grade)
    if division:
        query = query.filter(StudentAssessmentData.division_name == division)

    query = query.group_by(StudentAssessmentData.academic_year, StudentAssessmentData.assessment_type)
    query = query.order_by(StudentAssessmentData.academic_year, StudentAssessmentData.assessment_type)
    results = query.all()

    data = [
        {
            'year': r.academic_year,
            'type': r.assessment_type,
            'average': round((r.obtained / r.max) * 100, 2) if r.max else None
        }
        for r in results
    ]
    return jsonify(data)

@dashboard_bp.route('/kaleidoscope/skills_data')
def kaleidoscope_skills_data():
    """Return average scores for each skill (question_name) within a given competency, or all skills if no competency is specified, using filters."""
    competency = request.args.get('competency')
    academic_year = request.args.get('academic_year')
    subject = request.args.get('subject')
    school = request.args.get('school')
    grade = request.args.get('grade')
    division = request.args.get('division')
    assessment_type = request.args.get('assessment_type')

    query = db.session.query(
        StudentAssessmentData.question_name,
        func.sum(StudentAssessmentData.obtained_marks).label('obtained'),
        func.sum(StudentAssessmentData.max_marks).label('max')
    ).filter(
        StudentAssessmentData.question_name.isnot(None),
        StudentAssessmentData.max_marks.isnot(None),
        StudentAssessmentData.max_marks > 0
    )
    if competency:
        query = query.filter(StudentAssessmentData.competency_level_name == competency)
    if academic_year and academic_year != 'All':
        query = query.filter(StudentAssessmentData.academic_year == academic_year)
    if subject and subject != 'All':
        query = query.filter(StudentAssessmentData.subject_name == subject)
    if school and school != 'All':
        query = query.filter(StudentAssessmentData.school_name == school)
    if grade and grade != 'All':
        query = query.filter(StudentAssessmentData.grade_name == grade)
    if division and division != 'All':
        query = query.filter(StudentAssessmentData.division_name == division)
    if assessment_type and assessment_type != 'All':
        query = query.filter(StudentAssessmentData.assessment_type == assessment_type)

    query = query.group_by(StudentAssessmentData.question_name)
    results = query.all()
    skills = []
    for skill, obtained, max_marks in results:
        if max_marks and obtained is not None:
            avg = (obtained / max_marks) * 100
            skills.append({'skill': skill, 'avg': round(avg, 2)})
    # Sort by average descending
    skills.sort(key=lambda x: x['avg'], reverse=True)
    return jsonify(skills)

@dashboard_bp.route('/kaleidoscope/bucket_students', methods=['GET'])
def kaleidoscope_bucket_students():
    """Return student names for a given competency and bucket (Red, Blue, Green)."""
    assessment_type = request.args.get('assessment_type')
    academic_year = request.args.get('academic_year')
    subject = request.args.get('subject')
    school = request.args.get('school')
    grade = request.args.get('grade')
    division = request.args.get('division')
    competency = request.args.get('competency')
    bucket = request.args.get('bucket')  # 'Red', 'Blue', 'Green'

    query = db.session.query(
        StudentAssessmentData.student_id,
        StudentAssessmentData.student_name,
        StudentAssessmentData.competency_level_name,
        StudentAssessmentData.obtained_marks,
        StudentAssessmentData.max_marks
    )
    if assessment_type:
        query = query.filter(StudentAssessmentData.assessment_type == assessment_type)
    if academic_year:
        query = query.filter(StudentAssessmentData.academic_year == academic_year)
    if subject:
        query = query.filter(StudentAssessmentData.subject_name == subject)
    if school:
        query = query.filter(StudentAssessmentData.school_name == school)
    if grade:
        query = query.filter(StudentAssessmentData.grade_name == grade)
    if division:
        query = query.filter(StudentAssessmentData.division_name == division)
    if competency and competency != 'Overall':
        query = query.filter(StudentAssessmentData.competency_level_name == competency)

    # Structure: {student_id: {'name': ..., 'obtained': x, 'max': y}}
    student_totals = {}
    for row in query:
        if not row.student_id:
            continue
        if row.student_id not in student_totals:
            student_totals[row.student_id] = {'name': row.student_name, 'obtained': 0, 'max': 0}
        student_totals[row.student_id]['obtained'] += row.obtained_marks or 0
        student_totals[row.student_id]['max'] += row.max_marks or 0

    # Filter students by bucket
    result = []
    for student_id, info in student_totals.items():
        if info['max'] > 0:
            percent = (info['obtained'] / info['max']) * 100
            if bucket == 'Green' and percent > 60:
                result.append(info['name'])
            elif bucket == 'Blue' and 35 <= percent <= 60:
                result.append(info['name'])
            elif bucket == 'Red' and percent < 35:
                result.append(info['name'])
    result.sort()
    return jsonify({'students': result})

@dashboard_bp.route('/kaleidoscope/student_competency_averages')
def kaleidoscope_student_competency_averages():
    """Return a student's average for each competency and overall, for the current filters."""
    assessment_type = request.args.get('assessment_type')
    academic_year = request.args.get('academic_year')
    subject = request.args.get('subject')
    school = request.args.get('school')
    grade = request.args.get('grade')
    division = request.args.get('division')
    student_name = request.args.get('student_name')
    query = db.session.query(
        StudentAssessmentData.student_name,
        StudentAssessmentData.competency_level_name,
        StudentAssessmentData.obtained_marks,
        StudentAssessmentData.max_marks
    )
    if assessment_type:
        query = query.filter(StudentAssessmentData.assessment_type == assessment_type)
    if academic_year:
        query = query.filter(StudentAssessmentData.academic_year == academic_year)
    if subject:
        query = query.filter(StudentAssessmentData.subject_name == subject)
    if school:
        query = query.filter(StudentAssessmentData.school_name == school)
    if grade:
        query = query.filter(StudentAssessmentData.grade_name == grade)
    if division:
        query = query.filter(StudentAssessmentData.division_name == division)
    if student_name:
        query = query.filter(StudentAssessmentData.student_name == student_name)
    # Structure: {competency: {'obtained': x, 'max': y}}
    comp_totals = {}
    overall_obtained = 0
    overall_max = 0
    for row in query:
        comp = row.competency_level_name or 'Unknown'
        if comp not in comp_totals:
            comp_totals[comp] = {'obtained': 0, 'max': 0}
        comp_totals[comp]['obtained'] += row.obtained_marks or 0
        comp_totals[comp]['max'] += row.max_marks or 0
        overall_obtained += row.obtained_marks or 0
        overall_max += row.max_marks or 0
    averages = {}
    for comp, vals in comp_totals.items():
        if vals['max'] > 0:
            averages[comp] = round((vals['obtained'] / vals['max']) * 100, 2)
        else:
            averages[comp] = None
    overall = round((overall_obtained / overall_max) * 100, 2) if overall_max > 0 else None
    return jsonify({'averages': averages, 'overall': overall})

@dashboard_bp.route('/kaleidoscope/bucket_students_averages')
def kaleidoscope_bucket_students_averages():
    """Return, for a given competency and bucket, all students in that bucket and their averages for all competencies and overall."""
    assessment_type = request.args.get('assessment_type')
    academic_year = request.args.get('academic_year')
    subject = request.args.get('subject')
    school = request.args.get('school')
    grade = request.args.get('grade')
    division = request.args.get('division')
    competency = request.args.get('competency')
    bucket = request.args.get('bucket')
    # First, get all students in the selected bucket for the selected competency
    query = db.session.query(
        StudentAssessmentData.student_id,
        StudentAssessmentData.student_name,
        StudentAssessmentData.competency_level_name,
        StudentAssessmentData.obtained_marks,
        StudentAssessmentData.max_marks
    )
    if assessment_type:
        query = query.filter(StudentAssessmentData.assessment_type == assessment_type)
    if academic_year:
        query = query.filter(StudentAssessmentData.academic_year == academic_year)
    if subject:
        query = query.filter(StudentAssessmentData.subject_name == subject)
    if school:
        query = query.filter(StudentAssessmentData.school_name == school)
    if grade:
        query = query.filter(StudentAssessmentData.grade_name == grade)
    if division:
        query = query.filter(StudentAssessmentData.division_name == division)
    if competency and competency != 'Overall':
        query = query.filter(StudentAssessmentData.competency_level_name == competency)
    # Build student totals for the selected competency
    student_totals = {}
    for row in query:
        if not row.student_id:
            continue
        if row.student_id not in student_totals:
            student_totals[row.student_id] = {'name': row.student_name, 'obtained': 0, 'max': 0}
        student_totals[row.student_id]['obtained'] += row.obtained_marks or 0
        student_totals[row.student_id]['max'] += row.max_marks or 0
    # Determine which students are in the selected bucket
    bucket_students = set()
    for student_id, info in student_totals.items():
        if info['max'] > 0:
            percent = (info['obtained'] / info['max']) * 100
            if bucket == 'Green' and percent > 60:
                bucket_students.add(student_id)
            elif bucket == 'Blue' and 35 <= percent <= 60:
                bucket_students.add(student_id)
            elif bucket == 'Red' and percent < 35:
                bucket_students.add(student_id)
    if not bucket_students:
        return jsonify({'students': [], 'competencies': []})
    # Now, for these students, get their averages for all competencies and overall
    query2 = db.session.query(
        StudentAssessmentData.student_id,
        StudentAssessmentData.student_name,
        StudentAssessmentData.competency_level_name,
        StudentAssessmentData.obtained_marks,
        StudentAssessmentData.max_marks
    )
    if assessment_type:
        query2 = query2.filter(StudentAssessmentData.assessment_type == assessment_type)
    if academic_year:
        query2 = query2.filter(StudentAssessmentData.academic_year == academic_year)
    if subject:
        query2 = query2.filter(StudentAssessmentData.subject_name == subject)
    if school:
        query2 = query2.filter(StudentAssessmentData.school_name == school)
    if grade:
        query2 = query2.filter(StudentAssessmentData.grade_name == grade)
    if division:
        query2 = query2.filter(StudentAssessmentData.division_name == division)
    query2 = query2.filter(StudentAssessmentData.student_id.in_(bucket_students))
    # Structure: {student_id: {'name':..., 'comp_totals':{comp: {'obtained':x,'max':y}}, 'overall_obtained':x, 'overall_max':y}}
    students = {}
    all_competencies = set()
    for row in query2:
        if not row.student_id:
            continue
        if row.student_id not in students:
            students[row.student_id] = {'student_name': row.student_name, 'comp_totals': {}, 'overall_obtained': 0, 'overall_max': 0}
        comp = row.competency_level_name or 'Unknown'
        all_competencies.add(comp)
        if comp not in students[row.student_id]['comp_totals']:
            students[row.student_id]['comp_totals'][comp] = {'obtained': 0, 'max': 0}
        students[row.student_id]['comp_totals'][comp]['obtained'] += row.obtained_marks or 0
        students[row.student_id]['comp_totals'][comp]['max'] += row.max_marks or 0
        students[row.student_id]['overall_obtained'] += row.obtained_marks or 0
        students[row.student_id]['overall_max'] += row.max_marks or 0
    comp_list = sorted(all_competencies)
    # Build result rows
    result = []
    for student_id, info in students.items():
        averages = {}
        for comp in comp_list:
            vals = info['comp_totals'].get(comp, {'obtained': 0, 'max': 0})
            if vals['max'] > 0:
                averages[comp] = round((vals['obtained'] / vals['max']) * 100, 2)
            else:
                averages[comp] = None
        overall = round((info['overall_obtained'] / info['overall_max']) * 100, 2) if info['overall_max'] > 0 else None
        result.append({'student_name': info['student_name'], 'averages': averages, 'overall': overall})
    # Sort by student name
    result.sort(key=lambda x: x['student_name'])
    return jsonify({'students': result, 'competencies': comp_list})
