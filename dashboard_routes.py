import logging
from flask import Blueprint, render_template, flash, redirect, url_for, current_app, jsonify, request, session
from datetime import datetime, timedelta
from models import AllAssessments, db

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
