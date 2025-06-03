#!/usr/bin/env python3
"""
Test script for the Assessment Dashboard functionality.
This script tests the database queries and data processing without running the full application.
"""
import os
import sys
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv
import pymysql
from pymysql.cursors import DictCursor

# Load environment variables
load_dotenv()

# Database connection parameters
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '190.92.174.212'),
    'user': os.getenv('DB_USER', 'webappor_IT'),
    'password': os.getenv('DB_PASSWORD', 'Motoming@123'),
    'db': os.getenv('DB_NAME', 'webappor_AFDW'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'charset': 'utf8mb4',
    'cursorclass': DictCursor
}

def get_connection():
    """Get a database connection."""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        print(f"Successfully connected to {DB_CONFIG['db']} on {DB_CONFIG['host']}")
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

def get_filter_options(connection):
    """Get all available filter options."""
    try:
        with connection.cursor() as cursor:
            # Get academic years
            cursor.execute("SELECT DISTINCT academic_year FROM student_assessment_data WHERE academic_year IS NOT NULL ORDER BY academic_year DESC")
            academic_years = [row['academic_year'] for row in cursor.fetchall()]

            # Get subjects
            cursor.execute("SELECT DISTINCT subject_name FROM student_assessment_data WHERE subject_name IS NOT NULL ORDER BY subject_name")
            subjects = [row['subject_name'] for row in cursor.fetchall()]

            # Get schools
            cursor.execute("SELECT DISTINCT school_name FROM student_assessment_data WHERE school_name IS NOT NULL ORDER BY school_name")
            schools = [row['school_name'] for row in cursor.fetchall()]

            # Get assessment types
            cursor.execute("SELECT DISTINCT assessment_type FROM student_assessment_data WHERE assessment_type IS NOT NULL ORDER BY assessment_type")
            assessment_types = [row['assessment_type'] for row in cursor.fetchall()]

            # Get grades
            cursor.execute("SELECT DISTINCT grade_name FROM student_assessment_data WHERE grade_name IS NOT NULL ORDER BY grade_name")
            grades = [row['grade_name'] for row in cursor.fetchall()]

            # Get competency levels
            cursor.execute("SELECT DISTINCT competency_level_name FROM student_assessment_data WHERE competency_level_name IS NOT NULL ORDER BY competency_level_name")
            competency_levels = [row['competency_level_name'] for row in cursor.fetchall()]

            # Get divisions
            cursor.execute("SELECT DISTINCT division_name FROM student_assessment_data WHERE division_name IS NOT NULL ORDER BY division_name")
            divisions = [row['division_name'] for row in cursor.fetchall()]

            # Get genders
            cursor.execute("SELECT DISTINCT gender FROM student_assessment_data WHERE gender IS NOT NULL ORDER BY gender")
            genders = [row['gender'] for row in cursor.fetchall()]

            # Get min and max assessment dates
            cursor.execute("SELECT MIN(assessmentDate) as min_date, MAX(assessmentDate) as max_date FROM student_assessment_data")
            date_range = cursor.fetchone()

            return {
                'academic_years': academic_years,
                'subjects': subjects,
                'schools': schools,
                'assessment_types': assessment_types,
                'grades': grades,
                'competency_levels': competency_levels,
                'divisions': divisions,
                'genders': genders,
                'date_range': {
                    'min': date_range['min_date'].strftime('%Y-%m-%d') if date_range['min_date'] else None,
                    'max': date_range['max_date'].strftime('%Y-%m-%d') if date_range['max_date'] else None
                }
            }
    except Exception as e:
        print(f"Error getting filter options: {e}")
        return {}

def get_dashboard_data(connection, filters=None):
    """Get assessment data based on selected filters."""
    if filters is None:
        filters = {}

    try:
        # Build the query
        query = "SELECT * FROM student_assessment_data WHERE 1=1"
        params = []

        # Apply filters
        if filters.get('academic_year') and filters['academic_year'] != 'All':
            query += " AND academic_year = %s"
            params.append(filters['academic_year'])

        if filters.get('subject') and filters['subject'] != 'All':
            query += " AND subject_name = %s"
            params.append(filters['subject'])

        if filters.get('school') and filters['school'] != 'All':
            query += " AND school_name = %s"
            params.append(filters['school'])

        if filters.get('assessment_type') and filters['assessment_type'] != 'All':
            query += " AND assessment_type = %s"
            params.append(filters['assessment_type'])

        if filters.get('grade') and filters['grade'] != 'All':
            query += " AND grade_name = %s"
            params.append(filters['grade'])

        if filters.get('competency_level') and filters['competency_level'] != 'All':
            query += " AND competency_level_name = %s"
            params.append(filters['competency_level'])

        if filters.get('division') and filters['division'] != 'All':
            query += " AND division_name = %s"
            params.append(filters['division'])

        if filters.get('gender') and filters['gender'] != 'All':
            query += " AND gender = %s"
            params.append(filters['gender'])

        if filters.get('start_date') and filters.get('end_date'):
            query += " AND assessmentDate BETWEEN %s AND %s"
            params.append(filters['start_date'])
            params.append(filters['end_date'])

        # No limit to get all records

        # Execute the query
        with connection.cursor() as cursor:
            print(f"Executing query: {query} with params: {params}")
            cursor.execute(query, params)
            results = cursor.fetchall()
            print(f"Query returned {len(results)} records")
            return results
    except Exception as e:
        print(f"Error getting dashboard data: {e}")
        return []

def generate_visualizations(data):
    """Generate sample visualizations from the data."""
    if not data:
        print("No data available for visualizations")
        return

    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(data)

    # 1. Overall Student Performance by Competency Level (Pie Chart)
    try:
        plt.figure(figsize=(10, 6))
        competency_counts = df['competency_level_name'].value_counts()
        plt.pie(competency_counts, labels=competency_counts.index, autopct='%1.1f%%')
        plt.title('Distribution by Competency Level')
        plt.savefig('competency_distribution.png')
        plt.close()
        print("Generated competency distribution pie chart")
    except Exception as e:
        print(f"Error generating competency distribution chart: {e}")

    # 2. Average Performance by School (Bar Chart)
    try:
        plt.figure(figsize=(12, 6))
        school_avg = df.groupby('school_name')['percentage'].mean().sort_values(ascending=False).head(10)
        school_avg.plot(kind='bar')
        plt.title('Top 10 Schools by Average Performance')
        plt.xlabel('School')
        plt.ylabel('Average Score (%)')
        plt.tight_layout()
        plt.savefig('school_performance.png')
        plt.close()
        print("Generated school performance bar chart")
    except Exception as e:
        print(f"Error generating school performance chart: {e}")

    # 3. Performance by Subject (Bar Chart)
    try:
        plt.figure(figsize=(12, 6))
        subject_avg = df.groupby('subject_name')['percentage'].mean().sort_values(ascending=False)
        subject_avg.plot(kind='bar')
        plt.title('Performance by Subject')
        plt.xlabel('Subject')
        plt.ylabel('Average Score (%)')
        plt.tight_layout()
        plt.savefig('subject_performance.png')
        plt.close()
        print("Generated subject performance bar chart")
    except Exception as e:
        print(f"Error generating subject performance chart: {e}")

    # 4. Gender-based Performance (Bar Chart)
    try:
        plt.figure(figsize=(10, 6))
        gender_avg = df.groupby('gender')['percentage'].mean()
        gender_avg.plot(kind='bar')
        plt.title('Performance by Gender')
        plt.xlabel('Gender')
        plt.ylabel('Average Score (%)')
        plt.tight_layout()
        plt.savefig('gender_performance.png')
        plt.close()
        print("Generated gender performance bar chart")
    except Exception as e:
        print(f"Error generating gender performance chart: {e}")

    # 5. Top 10 Students Table
    try:
        top_students = df.sort_values('percentage', ascending=False).head(10)
        top_students_table = top_students[['student_name', 'student_id', 'school_name', 'subject_name', 'grade_name', 'obtained_marks', 'max_marks', 'percentage']]
        print("\nTop 10 Performing Students:")
        print(top_students_table.to_string(index=False))
    except Exception as e:
        print(f"Error generating top students table: {e}")

def main():
    """Main function."""
    # Connect to the database
    connection = get_connection()

    try:
        # Get filter options
        print("\nGetting filter options...")
        filter_options = get_filter_options(connection)
        print("Available filter options:")
        print(json.dumps(filter_options, indent=2, default=str))

        # Test with no filters (all data)
        print("\nTesting with no filters...")
        all_data = get_dashboard_data(connection)
        print(f"Total records: {len(all_data)}")

        # Test with academic year filter
        if filter_options.get('academic_years') and len(filter_options['academic_years']) > 0:
            academic_year = filter_options['academic_years'][0]
            print(f"\nTesting with academic year filter: {academic_year}")
            year_data = get_dashboard_data(connection, {'academic_year': academic_year})
            print(f"Records for {academic_year}: {len(year_data)}")

        # Test with subject filter
        if filter_options.get('subjects') and len(filter_options['subjects']) > 0:
            subject = filter_options['subjects'][0]
            print(f"\nTesting with subject filter: {subject}")
            subject_data = get_dashboard_data(connection, {'subject': subject})
            print(f"Records for {subject}: {len(subject_data)}")

        # Generate visualizations
        print("\nGenerating visualizations...")
        generate_visualizations(all_data)

        print("\nTest completed successfully!")

    except Exception as e:
        print(f"Error during testing: {e}")

    finally:
        connection.close()
        print("Database connection closed")

if __name__ == "__main__":
    main()
