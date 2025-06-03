#!/usr/bin/env python3
"""
Assessment Performance Report Generator

This script generates a comprehensive assessment performance report with the following visualizations:
1. Overall performance by grade level
2. Performance by city (Mumbai, Pune, Nagpur)
3. Performance by school
4. Performance by subject

Averages are calculated as sum(obtained_marks) / sum(max_marks) for accuracy.
"""
import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
import matplotlib.ticker as mtick

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

# Define performance categories
PERFORMANCE_CATEGORIES = {
    'Less than 25%': (0, 25),
    '25% to 50%': (25, 50),
    '50% to 75%': (50, 75),
    'More than 75%': (75, 100)
}

# Define grade order
GRADE_ORDER = ['JR.KG', 'SR.KG', 'GRADE 1', 'GRADE 2', 'GRADE 3', 'GRADE 4', 'GRADE 5', 'GRADE 6', 'GRADE 7', 'GRADE 8', 'GRADE 9', 'GRADE 10']
GRADE_DISPLAY = ['Jr.KG', 'Sr.KG', 'Gr. 1', 'Gr. 2', 'Gr. 3', 'Gr. 4', 'Gr. 5', 'Gr. 6', 'Gr. 7', 'Gr. 8', 'Gr. 9', 'Gr. 10']

# Define subject order
SUBJECT_ORDER = ['Math', 'English', 'Hindi', 'Marathi', 'Science', 'Computer']
SUBJECT_MAP = {
    'Math': 'Mat',
    'English': 'Eng',
    'Hindi': 'Hin',
    'Marathi': 'Mar',
    'Science': 'Sci',
    'Computer': 'Com'
}

# City mapping
CITY_MAP = {
    'Mumbai': ['ABMPS', 'DNMPS', 'LNMPS', 'MLMPS', 'NMMC93', 'NNMPS', 'SMCMPS', 'SMPS', 'WBMPS'],
    'Pune': ['ANWEMS', 'BOPEMS', 'CSMEMS', 'KCTVN', 'LAPMEMS', 'LDRKEMS', 'MEMS', 'PKGEMS', 'SBP', 'SBP-MO'],
    'Nagpur': ['LBBNPS', 'BNPS', 'LGMNPS', 'RDNPS', 'RMNPS', 'RNPS']
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

def get_assessment_data(connection, academic_year='2024-2025', assessment_type='EOY'):
    """Get assessment data for the specified academic year and assessment type."""
    try:
        query = """
        SELECT 
            school_name, grade_name, subject_name, obtained_marks, max_marks, 
            percentage, student_id, student_name, gender, division_name
        FROM 
            student_assessment_data
        WHERE 
            academic_year = %s AND assessment_type = %s
            AND obtained_marks IS NOT NULL AND max_marks IS NOT NULL
            AND max_marks > 0
        """
        
        with connection.cursor() as cursor:
            cursor.execute(query, (academic_year, assessment_type))
            results = cursor.fetchall()
            
        if not results:
            print(f"No data found for {academic_year} {assessment_type}")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(results)
        
        # Map school to city
        def map_school_to_city(school):
            for city, schools in CITY_MAP.items():
                if school in schools:
                    return city
            return 'Other'
            
        df['city'] = df['school_name'].apply(map_school_to_city)
        
        # Clean subject names
        df['subject_clean'] = df['subject_name'].apply(lambda x: x.strip().title())
        
        # Filter for core subjects only
        core_subjects = ['Math', 'English', 'Hindi', 'Marathi', 'Science', 'Computer']
        df = df[df['subject_clean'].isin(core_subjects)]
        
        print(f"Loaded {len(df)} records for {academic_year} {assessment_type}")
        return df
        
    except Exception as e:
        print(f"Error getting assessment data: {e}")
        return None

def calculate_performance_metrics(df):
    """Calculate performance metrics by different dimensions."""
    metrics = {}
    
    # Function to calculate correct average (sum of obtained / sum of max)
    def calculate_avg_percentage(group):
        return (group['obtained_marks'].sum() / group['max_marks'].sum()) * 100
    
    # Overall performance by grade
    grade_performance = df.groupby('grade_name').apply(calculate_avg_percentage).reset_index()
    grade_performance.columns = ['grade_name', 'avg_percentage']
    
    # Sort by grade order
    grade_performance['grade_order'] = grade_performance['grade_name'].apply(
        lambda x: GRADE_ORDER.index(x) if x in GRADE_ORDER else 999)
    grade_performance = grade_performance.sort_values('grade_order')
    
    metrics['grade_performance'] = grade_performance
    
    # Performance by city and grade
    city_grade_performance = df.groupby(['city', 'grade_name']).apply(calculate_avg_percentage).reset_index()
    city_grade_performance.columns = ['city', 'grade_name', 'avg_percentage']
    
    # Sort by city and grade order
    city_grade_performance['grade_order'] = city_grade_performance['grade_name'].apply(
        lambda x: GRADE_ORDER.index(x) if x in GRADE_ORDER else 999)
    city_grade_performance = city_grade_performance.sort_values(['city', 'grade_order'])
    
    metrics['city_grade_performance'] = city_grade_performance
    
    # Performance by school and grade
    school_grade_performance = df.groupby(['school_name', 'grade_name']).apply(calculate_avg_percentage).reset_index()
    school_grade_performance.columns = ['school_name', 'grade_name', 'avg_percentage']
    
    # Sort by school and grade order
    school_grade_performance['grade_order'] = school_grade_performance['grade_name'].apply(
        lambda x: GRADE_ORDER.index(x) if x in GRADE_ORDER else 999)
    school_grade_performance = school_grade_performance.sort_values(['school_name', 'grade_order'])
    
    # Add city information
    school_grade_performance['city'] = school_grade_performance['school_name'].apply(map_school_to_city)
    
    metrics['school_grade_performance'] = school_grade_performance
    
    # Performance by subject
    subject_performance = df.groupby('subject_clean').apply(calculate_avg_percentage).reset_index()
    subject_performance.columns = ['subject_clean', 'avg_percentage']
    
    # Sort by subject order
    subject_order_map = {subject: i for i, subject in enumerate(SUBJECT_ORDER)}
    subject_performance['subject_order'] = subject_performance['subject_clean'].apply(
        lambda x: subject_order_map.get(x, 999))
    subject_performance = subject_performance.sort_values('subject_order')
    
    metrics['subject_performance'] = subject_performance
    
    # Performance by school and subject
    school_subject_performance = df.groupby(['school_name', 'subject_clean']).apply(calculate_avg_percentage).reset_index()
    school_subject_performance.columns = ['school_name', 'subject_clean', 'avg_percentage']
    
    # Sort by school and subject order
    school_subject_performance['subject_order'] = school_subject_performance['subject_clean'].apply(
        lambda x: subject_order_map.get(x, 999))
    school_subject_performance = school_subject_performance.sort_values(['school_name', 'subject_order'])
    
    # Add city information
    school_subject_performance['city'] = school_subject_performance['school_name'].apply(map_school_to_city)
    
    metrics['school_subject_performance'] = school_subject_performance
    
    # Performance by city and subject
    city_subject_performance = df.groupby(['city', 'subject_clean']).apply(calculate_avg_percentage).reset_index()
    city_subject_performance.columns = ['city', 'subject_clean', 'avg_percentage']
    
    # Sort by city and subject order
    city_subject_performance['subject_order'] = city_subject_performance['subject_clean'].apply(
        lambda x: subject_order_map.get(x, 999))
    city_subject_performance = city_subject_performance.sort_values(['city', 'subject_order'])
    
    metrics['city_subject_performance'] = city_subject_performance
    
    return metrics

def map_school_to_city(school):
    """Map school to city."""
    for city, schools in CITY_MAP.items():
        if school in schools:
            return city
    return 'Other'

def generate_visualizations(metrics, academic_year, assessment_type):
    """Generate visualizations from the metrics."""
    # Set the style
    plt.style.use('seaborn-v0_8-whitegrid')
    
    # Create a directory for the visualizations
    os.makedirs('assessment_reports', exist_ok=True)
    
    # 1. Overall performance by grade
    generate_grade_performance_chart(metrics['grade_performance'], academic_year, assessment_type)
    
    # 2. Performance by city and grade
    generate_city_grade_performance_chart(metrics['city_grade_performance'], academic_year, assessment_type)
    
    # 3. Performance by school and grade
    generate_school_grade_performance_chart(metrics['school_grade_performance'], academic_year, assessment_type)
    
    # 4. Performance by subject
    generate_subject_performance_chart(metrics['subject_performance'], academic_year, assessment_type)
    
    # 5. Performance by school and subject
    generate_school_subject_performance_chart(metrics['school_subject_performance'], academic_year, assessment_type)
    
    # 6. Performance by city and subject
    generate_city_subject_performance_chart(metrics['city_subject_performance'], academic_year, assessment_type)
    
    print(f"Visualizations generated in the 'assessment_reports' directory")

def generate_grade_performance_chart(grade_performance, academic_year, assessment_type):
    """Generate overall performance by grade chart."""
    plt.figure(figsize=(12, 6))
    
    # Map grade names to display names
    grade_map = {g: d for g, d in zip(GRADE_ORDER, GRADE_DISPLAY)}
    grade_performance['grade_display'] = grade_performance['grade_name'].map(grade_map)
    
    # Create the bar chart
    ax = sns.barplot(x='grade_display', y='avg_percentage', data=grade_performance, 
                    palette='Blues_d', order=grade_performance['grade_display'])
    
    # Add percentage labels on top of bars
    for i, p in enumerate(ax.patches):
        ax.annotate(f"{p.get_height():.0f}%", 
                   (p.get_x() + p.get_width() / 2., p.get_height()), 
                   ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # Set chart title and labels
    plt.title(f"{assessment_type} {academic_year}: Overall Performance by Grade", fontsize=14, fontweight='bold')
    plt.xlabel("Grade", fontsize=12)
    plt.ylabel("Average Score (%)", fontsize=12)
    
    # Format y-axis as percentage
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(100))
    
    # Set y-axis limits
    plt.ylim(0, 100)
    
    # Add a horizontal line at 75%
    plt.axhline(y=75, color='green', linestyle='--', alpha=0.7, label='>75% (Excellent)')
    
    # Add a horizontal line at 50%
    plt.axhline(y=50, color='orange', linestyle='--', alpha=0.7, label='50-75% (Good)')
    
    # Add a horizontal line at 25%
    plt.axhline(y=25, color='red', linestyle='--', alpha=0.7, label='<50% (Needs Improvement)')
    
    plt.legend(loc='lower right')
    plt.tight_layout()
    
    # Save the chart
    plt.savefig(f"assessment_reports/{assessment_type}_{academic_year}_grade_performance.png", dpi=300)
    plt.close()
