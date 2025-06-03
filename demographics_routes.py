import os
import pymysql
import pandas as pd
import json
import logging
import re
from flask import Blueprint, jsonify, request, current_app, Response, render_template, flash, redirect, url_for
from io import BytesIO

# We will import get_db_connection locally within functions to avoid circular import

# Define the Blueprint
demographics_bp = Blueprint('demographics', __name__, url_prefix='/demographics')

@demographics_bp.route('/')
def view():
    """Main demographics view."""
    # Check if user is logged in using session
    from flask import session
    if "user_email" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("index"))

    try:
        # Get user info from session
        return render_template(
            "demographics.html",
            active_page='demographics',
            name=session.get("user_name"),
            email=session.get("user_email"),
            picture=session.get("user_picture"),
            role=session.get("user_role", "Admin"),  # Get role from session
            school=session.get("user_school", "All")  # Get school from session
        )
    except Exception as e:
        current_app.logger.error(f"Error in demographics view: {e}")
        flash("An error occurred. Please try again.", "danger")
        return redirect(url_for("index"))

# Configure logger for this blueprint (optional, but good practice)
# logger = logging.getLogger(__name__) # Or use current_app.logger

# --- Utility Function for Excel Generation ---
def create_excel_response(df: pd.DataFrame, filename_base: str) -> Response:
    """Creates a Flask Response object containing an Excel file from a DataFrame."""
    try:
        output = BytesIO()
        # Use ExcelWriter to potentially allow more advanced formatting later
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Sheet1', index=True) # Include index by default
            # You could add more sheets or formatting here if needed

        output.seek(0) # Rewind the buffer
        excel_data = output.getvalue()  # Get the bytes from BytesIO

        safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename_base) # Sanitize filename
        excel_filename = f"{safe_filename}.xlsx"

        current_app.logger.info(f"Sending Excel file: {excel_filename}")

        # Create a Response object directly instead of using send_file
        response = Response(
            excel_data,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename="{excel_filename}"'
            }
        )
        return response
    except Exception as e:
        current_app.logger.error(f"Error generating Excel file from DataFrame: {e}", exc_info=True)
        # Return a standard Flask error response
        return Response("Error generating Excel file.", status=500, mimetype='text/plain')

# --- Helper Function for Demographics Data Generation ---
def _transform_and_sort_grades(pivot_table: pd.DataFrame) -> pd.DataFrame:
    """Transforms grade names (e.g., grade 1 -> 1) and sorts columns chronologically."""
    try:
        current_app.logger.debug("Starting grade transformation and sorting.")
        original_columns = list(pivot_table.columns)
        if not original_columns:
            current_app.logger.debug("No columns to transform or sort.")
            return pivot_table

        # --- Transform Names ---
        def transform_grade_name(col_name):
            if isinstance(col_name, str):
                col_lower = col_name.lower().strip()
                if col_lower == 'jr.kg': return 'Jr.kG' # Consistent casing
                if col_lower == 'sr.kg': return 'Sr.KG' # Consistent casing
                match = re.match(r'grade\s*(\d+)', col_lower)
                if match:
                    return match.group(1) # Return just the number
            return col_name # Return original if no match or not string

        transformed_columns = [transform_grade_name(col) for col in original_columns]
        pivot_table.columns = transformed_columns
        current_app.logger.debug(f"Transformed column names from {original_columns} to {transformed_columns}")

        # --- Sort Columns ---
        # Check if 'Total' column exists
        has_total_col = 'Total' in transformed_columns
        columns_without_total = [col for col in transformed_columns if col != 'Total']

        # Define the desired order for core grades
        # Use the casing produced by transform_grade_name
        core_grade_order = ['Nursery','Jr.kG', 'Sr.KG'] + [str(i) for i in range(1, 11)]
        current_app.logger.debug(f"Desired core grade order: {core_grade_order}")

        # Sort existing grade columns based on the core order
        sorted_known_grades = [grade for grade in core_grade_order if grade in columns_without_total]
        # Find any other columns (unexpected grades?) that were not in the core order
        other_grades = [col for col in columns_without_total if col not in sorted_known_grades]
        current_app.logger.debug(f"Sorted known grades: {sorted_known_grades}, Other grades: {other_grades}")

        # Combine sorted known grades, other grades, and add Total at the end if it exists
        final_column_order = sorted_known_grades + other_grades
        if has_total_col:
            final_column_order.append('Total')

        # Verify all columns in final_column_order exist in pivot_table.columns
        missing_columns = [col for col in final_column_order if col not in pivot_table.columns]
        if missing_columns:
            current_app.logger.warning(f"Some columns in final_column_order are missing from pivot_table: {missing_columns}")
            # Only include columns that actually exist in the pivot table
            final_column_order = [col for col in final_column_order if col in pivot_table.columns]
            current_app.logger.info(f"Adjusted final_column_order: {final_column_order}")

        # Reindex the DataFrame columns
        if final_column_order:  # Only reindex if we have columns to reorder
            pivot_table = pivot_table[final_column_order]
            current_app.logger.info(f"Final reordered columns: {final_column_order}")
        else:
            current_app.logger.warning("No valid columns to reorder, keeping original order.")

    except Exception as e:
        current_app.logger.error(f"Error in _transform_and_sort_grades: {e}", exc_info=True)
        # Return the original pivot table if any error occurs
        # This ensures the function doesn't break the data flow

    return pivot_table

def _generate_demographics_data(filters):
    """Fetches data and generates the pivot table and scorecard data based on filters."""
    connection = None
    try:
        from app import get_db_connection # Local import inside helper
        connection = get_db_connection()
        if connection is None:
            return None, None, "Database connection failed.", 500

        # Extract filters
        academic_year_filter = filters.get('academic_year', 'All')
        city_filter = filters.get('city', 'All')
        gender_filter = filters.get('gender', 'All')
        current_app.logger.info(f"Generating demographics data with filters - Year: {academic_year_filter}, City: {city_filter}, Gender: {gender_filter}")

        # Build the SQL query with filters - Use correct table names
        sql = """
            SELECT
                asd.student_id,
                asd.school_name,
                asd.grade_name,
                asd.gender,
                c.city
            FROM active_student_data asd
            LEFT JOIN city c ON asd.school_name = c.school_name
        """
        params = []
        conditions = []
        if academic_year_filter != 'All':
            conditions.append("asd.academic_year = %s") # Assuming column name is academic_year
            params.append(academic_year_filter)
        if city_filter != 'All':
            conditions.append("c.city = %s") # Filter on city table alias
            params.append(city_filter)
        if gender_filter != 'All':
            conditions.append("asd.gender = %s") # Filter on active_student_data alias
            params.append(gender_filter)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, params)
            data = cursor.fetchall()

        if not data:
            current_app.logger.info("No data found for the selected filters.")
            # Return empty structure but indicate success
            empty_df = pd.DataFrame(columns=['School'])
            empty_df.index.name = 'School'
            empty_pivot = empty_df # Or an empty pivot table if needed
            empty_scorecard = {'total': 0, 'male': 0, 'female': 0}
            return empty_pivot, empty_scorecard, None, 200 # Indicate success but no data

        df = pd.DataFrame(data)
        current_app.logger.info(f"Created DataFrame with shape: {df.shape}")

        # --- Calculate Scorecard Data ---
        total_students = df['student_id'].nunique()
        male_students = df[df['gender'].str.lower() == 'm']['student_id'].nunique()
        female_students = df[df['gender'].str.lower() == 'f']['student_id'].nunique()
        scorecard_data = {
            'total': total_students,
            'male': male_students,
            'female': female_students
        }
        current_app.logger.info(f"Calculated scorecard data: {scorecard_data}")

        # --- Create Pivot Table with Totals ---
        pivot_table = pd.pivot_table(df,
                                       index='school_name',
                                       columns='grade_name',
                                       values='student_id',
                                       aggfunc=pd.Series.nunique,
                                       fill_value=0,
                                       margins=True,
                                       margins_name='Total')
        current_app.logger.info(f"Created pivot table with margins, shape: {pivot_table.shape}")

        # --- Customize Pivot Table (Renaming, Ordering) ---
        pivot_table.index.name = 'School'
        pivot_table.columns.name = 'Grade' # Set column axis name
        current_app.logger.debug("Renamed pivot table index name.")

        # Use the helper function for transformation and sorting
        pivot_table = _transform_and_sort_grades(pivot_table)

        return pivot_table, scorecard_data, None, 200 # Success

    except pymysql.Error as e:
        current_app.logger.error(f"Database error generating demographics data: {e}")
        return None, None, "Database error occurred.", 500
    except Exception as e:
        current_app.logger.error(f"Error generating demographics data: {e}", exc_info=True)
        return None, None, "An internal error occurred.", 500
    finally:
        if connection:
            connection.close()

# --- Route: Get Table Data --- #
@demographics_bp.route('/table_data', methods=['POST'])
def get_demographics_table_data():
    filters = request.get_json()
    if not filters:
        return jsonify({"error": "Missing filter data"}), 400

    pivot_table, scorecard_data, error_message, status_code = _generate_demographics_data(filters)

    if error_message:
        return jsonify({"error": error_message}), status_code

    if pivot_table is None or scorecard_data is None:
        # Should be handled by error message case, but as fallback:
        return jsonify({"error": "Failed to generate data"}), 500

    # If no data found (but successful execution), return empty state
    if pivot_table.empty and status_code == 200:
         return jsonify({
                "scorecards": scorecard_data, # Will contain zeros
                "html_table": "<p class='text-center text-muted'>No data available for the selected filters.</p>"
            }), 200

    try:
        # --- Apply Styling (Centering with Left-Aligned School) and Convert to HTML ---
        # Check for duplicate index or columns and make them unique if needed
        if pivot_table.index.duplicated().any():
            current_app.logger.warning("Duplicate index values found in pivot table. Making them unique.")
            # Create a new index with unique values by adding a suffix
            new_index = []
            seen = {}
            for idx in pivot_table.index:
                if idx in seen:
                    seen[idx] += 1
                    new_index.append(f"{idx} ({seen[idx]})")
                else:
                    seen[idx] = 0
                    new_index.append(idx)
            pivot_table.index = new_index

        if pivot_table.columns.duplicated().any():
            current_app.logger.warning("Duplicate column values found in pivot table. Making them unique.")
            # Create new column names with unique values by adding a suffix
            new_columns = []
            seen = {}
            for col in pivot_table.columns:
                if col in seen:
                    seen[col] += 1
                    new_columns.append(f"{col} ({seen[col]})")
                else:
                    seen[col] = 0
                    new_columns.append(col)
            pivot_table.columns = new_columns

        # Use Styler for CSS application
        styler = pivot_table.style

        # Center align data cells (td) by default
        styler = styler.set_properties(**{'text-align': 'center'})

        # Center align headers (th), then override for the School column (index)
        styler = styler.set_table_styles([
            # General header centering
            {'selector': 'th', 'props': [('text-align', 'center')]},
            # Left-align the School column header (index name)
            {'selector': 'thead th.index_name', 'props': [('text-align', 'left')]},
            # Left-align the School names themselves (index values)
            # Pandas uses <th> for row headers in tbody by default
            {'selector': 'tbody th.row_heading', 'props': [('text-align', 'left')]},
            # If pandas ever changes to use <td> for first column, this might be needed
            # {'selector': 'tbody td:first-child', 'props': [('text-align', 'left')]},
        ])

        # Add Bootstrap classes and generate HTML
        html_table = styler.set_table_attributes(
            'class="table table-striped table-bordered table-hover table-sm"'
        ).to_html(border=0)

        # --- Prepare Final JSON Response ---
        response_data = {
            'scorecards': scorecard_data,
            'html_table': html_table
        }
        return jsonify(response_data), 200

    except Exception as e:
        # Catch potential errors during styling/HTML conversion
        current_app.logger.error(f"Error styling or converting pivot table to HTML: {e}", exc_info=True)
        return jsonify({"error": "Failed to format table data."}), 500

# --- Route: Download Excel --- #
@demographics_bp.route('/download_excel', methods=['POST'])
def download_demographics_excel():
    filters = request.get_json()
    if not filters:
        return jsonify({"error": "Missing filter data"}), 400

    pivot_table, _, error_message, status_code = _generate_demographics_data(filters)

    if error_message:
        return jsonify({"error": error_message}), status_code

    if pivot_table is None:
        return jsonify({"error": "Failed to generate data for download"}), 500

    if pivot_table.empty:
        # You might want to return an empty file or an error message
        # For now, let's return an error indicating no data
        return jsonify({"error": "No data available for the selected filters to download."}), 404

    # Determine filename based on filters
    academic_year = filters.get('academic_year', 'All').replace('/', '-') # Replace slashes for filename
    city = filters.get('city', 'All')
    gender = filters.get('gender', 'All')
    filename_base = f"demographics_{academic_year}_{city}_{gender}"

    # Call the utility function to generate and send the response
    return create_excel_response(pivot_table, filename_base)

# --- Route: Get Filters --- #
@demographics_bp.route('/filters')
def get_demographics_filters():
    from app import get_db_connection # Local import
    connection = get_db_connection() # Declared outside try for finally block
    if not connection:
        # Use current_app.logger for consistency if get_db_connection uses it
        current_app.logger.error("Demographics Filters: Database connection failed.")
        return jsonify({"error": "Database connection failed"}), 500

    cities = []
    academic_years = []
    attendance_months = []

    try:
        # Fetch Academic Years from student_attendance_data
        with connection.cursor(pymysql.cursors.DictCursor) as cursor: # Use DictCursor for consistency
            sql_years = "SELECT DISTINCT academic_year FROM student_attendance_data ORDER BY academic_year DESC"
            cursor.execute(sql_years)
            result_years = cursor.fetchall()
            # Ensure years are strings, handle potential None values
            academic_years = [str(row['academic_year']) for row in result_years if row['academic_year'] is not None]
            current_app.logger.info(f"Fetched academic years for filter: {academic_years}")

        # Fetch Cities
        with connection.cursor(pymysql.cursors.DictCursor) as cursor: # Use DictCursor
            sql_cities = "SELECT DISTINCT city FROM city ORDER BY city"
            cursor.execute(sql_cities)
            result_cities = cursor.fetchall()
            cities = [row['city'] for row in result_cities if row['city']] # Handle potential None/empty strings
            current_app.logger.info(f"Fetched cities for filter: {cities}")

        # Fetch Attendance Months
        with connection.cursor(pymysql.cursors.DictCursor) as cursor: # Use DictCursor
            sql_months = "SELECT DISTINCT month FROM student_attendance_data;"
            cursor.execute(sql_months)
            months_result = cursor.fetchall()
            raw_months = [row['month'] for row in months_result if row['month']] # Handle None/empty
            current_app.logger.debug(f"Raw months fetched: {raw_months}")

            # Sort months chronologically
            month_order = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ]
            month_sort_key = {month: i for i, month in enumerate(month_order)}
            attendance_months = sorted(raw_months, key=lambda m: month_sort_key.get(m, 99))
            current_app.logger.info(f"Fetched and sorted attendance months for filter: {attendance_months}")
    except pymysql.Error as e:
        current_app.logger.error(f"Error fetching filter data: {e}")
        return jsonify({"error": "Failed to fetch filter data"}), 500
    finally:
        if connection:
            connection.close()

    genders = {'M': 'Male', 'F': 'Female'}
    current_app.logger.info(f"Defined genders for filter: {genders}")

    return jsonify({
        'cities': cities,
        'academic_years': academic_years,
        'genders': genders, # Add genders to the response
        'attendance_months': attendance_months # Add months to response
    })

# --- Helper Function for Attendance Pivot Data Generation ---
def _generate_attendance_pivot_data(filters):
    """Fetches attendance data, calculates average attendance %, and generates a pivot table."""
    connection = None
    try:
        from app import get_db_connection # Local import
        connection = get_db_connection()
        if connection is None:
            return None, "Database connection failed.", 500

        # Extract filters
        academic_year_filter = filters.get('academic_year', 'All')
        month_filter = filters.get('month', 'All') # Added month filter
        city_filter = filters.get('city', 'All')
        gender_filter = filters.get('gender', 'All') # Get gender filter
        current_app.logger.info(f"Generating attendance pivot with filters - Year: {academic_year_filter}, Month: {month_filter}, City: {city_filter}, Gender: {gender_filter}")

        # --- Build SQL Query ---
        # Use student_attendance_data directly since it has a gender column
        sql = """
            SELECT
                att.school_name,
                att.grade_name,
                SUM(att.no_of_present_days) AS total_present,
                SUM(att.no_of_working_days) AS total_working
            FROM student_attendance_data att
            LEFT JOIN city c ON att.school_name = c.school_name
        """
        params = []
        conditions = ["att.no_of_working_days > 0"] # Ensure we don't divide by zero later

        if academic_year_filter != 'All':
            conditions.append("att.academic_year = %s")
            params.append(academic_year_filter)
        if month_filter != 'All':
            conditions.append("att.month = %s")
            params.append(month_filter)
        if city_filter != 'All':
            conditions.append("c.city = %s")
            params.append(city_filter)
        if gender_filter != 'All':
            # Use gender directly from student_attendance_data
            conditions.append("att.gender = %s")
            params.append(gender_filter)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " GROUP BY att.school_name, att.grade_name" # Group for SUM aggregation
        sql += " ORDER BY att.school_name, att.grade_name;"

        current_app.logger.debug(f"Executing SQL for attendance pivot: {sql} with params: {params}")
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            try:
                cursor.execute(sql, params)
                data = cursor.fetchall()
                current_app.logger.info(f"Student attendance query returned {len(data)} rows")
            except Exception as sql_error:
                current_app.logger.error(f"SQL error in student attendance query: {sql_error}")
                # Try a simpler query without the joins to see if that works
                simplified_sql = """
                    SELECT
                        school_name,
                        grade_name,
                        SUM(no_of_present_days) AS total_present,
                        SUM(no_of_working_days) AS total_working
                    FROM student_attendance_data
                    WHERE no_of_working_days > 0
                    GROUP BY school_name, grade_name
                    ORDER BY school_name, grade_name;
                """
                current_app.logger.info(f"Trying simplified SQL: {simplified_sql}")
                cursor.execute(simplified_sql)
                data = cursor.fetchall()
                current_app.logger.info(f"Simplified query returned {len(data)} rows")

        if not data:
            current_app.logger.info("No attendance data found for the selected filters.")
            return pd.DataFrame(), None, 200 # Return empty DataFrame, success

        df = pd.DataFrame(data)
        current_app.logger.info(f"Created attendance DataFrame with shape: {df.shape}")

        # --- Calculate Attendance Percentage ---
        # Ensure numeric types for calculation
        df['total_present'] = pd.to_numeric(df['total_present'], errors='coerce').fillna(0)
        df['total_working'] = pd.to_numeric(df['total_working'], errors='coerce').fillna(0)

        # Calculate percentage, handle potential division by zero (though filtered in SQL)
        df['attendance_percentage'] = df.apply(
            lambda row: (row['total_present'] / row['total_working'] * 100) if row['total_working'] > 0 else 0,
            axis=1
        )
        current_app.logger.info("Calculated attendance percentage.")
        # current_app.logger.debug(f"DataFrame with percentages:\n{df.head()}") # DEBUG

        # --- Create Pivot Table ---
        # We need custom margin calculation for weighted average
        pivot_table_no_margins = pd.pivot_table(df,
                                        index='school_name',
                                        columns='grade_name',
                                        values='attendance_percentage',
                                        # aggfunc defaults to mean, which is fine here as we grouped in SQL
                                        fill_value=None) # Use None for missing values initially

        current_app.logger.info(f"Created initial attendance pivot table (no margins), shape: {pivot_table_no_margins.shape}")

        # --- Calculate Margins (Weighted Average) ---
        # Calculate overall totals for weighted averages
        overall_totals = df.groupby('school_name')[['total_present', 'total_working']].sum()
        overall_totals['Total'] = overall_totals.apply(
            lambda row: (row['total_present'] / row['total_working'] * 100) if row['total_working'] > 0 else 0,
            axis=1
        )

        grade_totals = df.groupby('grade_name')[['total_present', 'total_working']].sum()
        grade_totals['Total'] = grade_totals.apply(
            lambda row: (row['total_present'] / row['total_working'] * 100) if row['total_working'] > 0 else 0,
            axis=1
        )

        grand_total_present = df['total_present'].sum()
        grand_total_working = df['total_working'].sum()
        grand_total_percentage = (grand_total_present / grand_total_working * 100) if grand_total_working > 0 else 0

        # Add margins to the pivot table
        pivot_table = pivot_table_no_margins.copy()
        pivot_table['Total'] = overall_totals['Total'] # Add column totals
        pivot_table.loc['Total'] = grade_totals['Total'] # Add row totals (as Series)
        pivot_table.loc['Total', 'Total'] = grand_total_percentage # Add grand total

        current_app.logger.info(f"Added calculated margins. Pivot table shape: {pivot_table.shape}")
        # current_app.logger.debug(f"Pivot table with margins:\n{pivot_table}") # DEBUG

        # --- Customize Pivot Table (Renaming, Ordering) ---
        pivot_table.index.name = 'School'
        pivot_table.columns.name = 'Grade'
        current_app.logger.debug("Renamed pivot table axis names.")

        # Use the helper function for transformation and sorting
        pivot_table = _transform_and_sort_grades(pivot_table)

        # Format as percentages (after sorting, before HTML conversion)
        # Apply formatting to all columns except potentially non-numeric ones like 'School' (index)
        format_cols = [col for col in pivot_table.columns if col != 'School'] # Exclude index if it becomes a column
        try:
            # Use Styler for robust formatting
            styled_pivot = pivot_table.style.format("{:.1f}%", subset=pd.IndexSlice[:, format_cols], na_rep='-')
            current_app.logger.info("Formatted pivot table cells as percentages.")
            # Note: styled_pivot is now a Styler object, not a DataFrame
        except Exception as format_error:
             current_app.logger.error(f"Error formatting pivot table as percentage: {format_error}")
             # Fallback: return unformatted table if styling fails
             styled_pivot = pivot_table
        return styled_pivot, None, 200 # Return Styler object or DataFrame

    except pymysql.Error as e:
        current_app.logger.error(f"Database error generating attendance pivot: {e}")
        return None, "Database error occurred.", 500
    except Exception as e:
        current_app.logger.error(f"Error generating attendance pivot: {e}", exc_info=True)
        return None, "An internal error occurred.", 500
    finally:
        if connection:
            connection.close()

# --- Route: Get Attendance Pivot Table --- #
@demographics_bp.route('/attendance_pivot', methods=['POST'])
@demographics_bp.route('/get_attendance_pivot_data', methods=['POST'])  # Add a second route with the function name
def get_attendance_pivot_data():
    filters = request.get_json()
    current_app.logger.info(f"Received request for student attendance pivot with filters: {filters}")

    if not filters:
        current_app.logger.warning("Missing filter data in request")
        return jsonify({"error": "Missing filter data"}), 400

    # Log the database connection info
    try:
        from app import get_db_connection
        connection = get_db_connection()
        if connection:
            current_app.logger.info("Successfully connected to database for student attendance")
            connection.close()
        else:
            current_app.logger.error("Failed to connect to database for student attendance")
    except Exception as db_error:
        current_app.logger.error(f"Error checking database connection: {db_error}")

    pivot_data, error_message, status_code = _generate_attendance_pivot_data(filters)

    if error_message:
        return jsonify({"error": error_message}), status_code

    if pivot_data is None:
        return jsonify({"error": "Failed to generate attendance pivot data"}), 500

    # Check if the result is an empty DataFrame (no data found)
    if isinstance(pivot_data, pd.DataFrame) and pivot_data.empty and status_code == 200:
         return jsonify({
                "html_table": "<p class='text-center text-muted'>No attendance data available for the selected filters.</p>"
            }), 200

    try:
        # --- Apply Styling (Centering with Left-Aligned School) and Convert to HTML ---
        # Extract DataFrame if pivot_data is a Styler
        if isinstance(pivot_data, pd.io.formats.style.Styler):
            df = pivot_data.data
            styler = pivot_data
        else: # It should be a DataFrame if formatting failed
            df = pivot_data

            # Check for duplicate index or columns and make them unique if needed
            if df.index.duplicated().any():
                current_app.logger.warning("Duplicate index values found in attendance pivot table. Making them unique.")
                # Create a new index with unique values by adding a suffix
                new_index = []
                seen = {}
                for idx in df.index:
                    if idx in seen:
                        seen[idx] += 1
                        new_index.append(f"{idx} ({seen[idx]})")
                    else:
                        seen[idx] = 0
                        new_index.append(idx)
                df.index = new_index

            if df.columns.duplicated().any():
                current_app.logger.warning("Duplicate column values found in attendance pivot table. Making them unique.")
                # Create new column names with unique values by adding a suffix
                new_columns = []
                seen = {}
                for col in df.columns:
                    if col in seen:
                        seen[col] += 1
                        new_columns.append(f"{col} ({seen[col]})")
                    else:
                        seen[col] = 0
                        new_columns.append(col)
                df.columns = new_columns

            styler = df.style

        # Apply alignment styles (same as demographics table)
        styler = styler.set_properties(**{'text-align': 'center'})
        styler = styler.set_table_styles([
            {'selector': 'th', 'props': [('text-align', 'center')]},
            {'selector': 'thead th.index_name', 'props': [('text-align', 'left')]},
            {'selector': 'tbody th.row_heading', 'props': [('text-align', 'left')]},
        ])

        # Add Bootstrap classes and generate HTML
        html_table = styler.set_table_attributes(
            'class="table table-striped table-bordered table-hover table-sm"'
        ).to_html(border=0, na_rep='-') # Use na_rep for any remaining Nones

        response_data = {
            'html_table': html_table
        }
        return jsonify(response_data), 200

    except Exception as e:
        current_app.logger.error(f"Error styling or converting attendance pivot table to HTML: {e}", exc_info=True)
        return jsonify({"error": "Failed to format attendance table data."}), 500

# --- Route: Download Student Attendance Pivot Excel --- #
@demographics_bp.route('/download_attendance_pivot', methods=['POST'])
def download_student_attendance_pivot():
    """API endpoint to download STUDENT attendance PIVOT data as an Excel file based on filters from POST request."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    filters = request.get_json()
    current_app.logger.info(f"Received request for /download_attendance_pivot (Student Pivot Download) with filters: {filters}")

    # Assume _generate_student_attendance_pivot_data exists and takes filters
    # IMPORTANT: Verify this function name and its expected return values
    pivot_data, error_msg, status_code = _generate_attendance_pivot_data(filters)

    if error_msg:
        return Response(f"Error generating data for download: {error_msg}", status=status_code, mimetype='text/plain')

    # Check for empty DataFrame case
    if isinstance(pivot_data, pd.DataFrame) and pivot_data.empty and status_code == 200:
        return Response("No Student attendance data found for the selected filters to download.", status=404, mimetype='text/plain')

    # Extract DataFrame from Styler if necessary
    if isinstance(pivot_data, pd.io.formats.style.Styler):
        df_to_export = pivot_data.data
    elif isinstance(pivot_data, pd.DataFrame):
        df_to_export = pivot_data
    else:
        current_app.logger.error(f"Unexpected data type for Student Excel export: {type(pivot_data)}")
        return Response("Error preparing data for download.", status=500, mimetype='text/plain')

    # Format numbers (optional)
    try:
        format_cols = [col for col in df_to_export.columns if col != 'School']
        for col in format_cols:
             if col in df_to_export.columns and pd.api.types.is_numeric_dtype(df_to_export[col]):
                 df_to_export[col] = df_to_export[col].map('{:.1f}%'.format)
    except Exception as fmt_err:
        current_app.logger.warning(f"Could not apply percentage formatting to Student DataFrame for Excel export: {fmt_err}")

    # Create filename based on filters
    filename_parts = [
        "student_attendance_pivot",
        filters.get('academic_year', 'All'),
        filters.get('month', 'All'),
        filters.get('city', 'All'),
        filters.get('gender', 'All')
    ]
    safe_filename_base = "_".join(part for part in filename_parts if part != 'All')
    return create_excel_response(df_to_export, safe_filename_base or "student_attendance_pivot")

# --- Helper Function for PTM Attendance Data Generation ---
def _generate_ptm_attendance_pivot_data(filters):
    """Fetches Parent attendance data, calculates average attendance %, and generates a pivot table similar to student attendance."""
    connection = None
    try:
        from app import get_db_connection # Local import
        connection = get_db_connection()
        if connection is None:
            return None, "Database connection failed.", 500

        # Extract filters (Month, Year, City)
        month_filter = filters.get('month', 'All')
        academic_year_filter = filters.get('academic_year', 'All')
        city_filter = filters.get('city', 'All')
        gender_filter = filters.get('gender', 'All') # Get gender filter
        current_app.logger.info(f"Generating Parent PTM attendance pivot with filters - Month: {month_filter}, Year: {academic_year_filter}, City: {city_filter}, Gender: {gender_filter}")

        # --- Build SQL Query ---
        # Fetch sums needed for weighted averages
        sql = """
            SELECT
                pa.school_name,
                pa.grade_name,
                SUM(pa.present_ptm) AS total_present_ptm,
                SUM(pa.total_no_of_ptm) AS total_ptms
            FROM ptm_attendance_data pa
            INNER JOIN city c ON pa.school_name = c.school_name
        """
        params = []
        conditions = ["pa.total_no_of_ptm > 0"] # Ensure we don't divide by zero later

        # Add Academic Year filter condition (assuming column 'academic_year' exists)
        if academic_year_filter != 'All':
            # IMPORTANT: Verify 'academic_year' is the correct column name in ptm_attendance_data
            conditions.append("pa.academic_year = %s")
            params.append(academic_year_filter)

        if month_filter != 'All':
            conditions.append("pa.month = %s") # Assuming a 'month' column
            params.append(month_filter)

        if city_filter != 'All':
            conditions.append("c.city = %s")
            params.append(city_filter)

        if gender_filter != 'All':
            # Add Gender filter condition (assuming column 'gender' exists)
            conditions.append("pa.gender = %s")
            params.append(gender_filter)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " GROUP BY pa.school_name, pa.grade_name" # Group for SUM aggregation
        sql += " ORDER BY pa.school_name, pa.grade_name;"

        current_app.logger.debug(f"Executing SQL for PTM attendance pivot: {sql} with params: {params}")
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, params)
            data = cursor.fetchall()

        if not data:
            current_app.logger.info("No PTM attendance data found for the selected filters.")
            return pd.DataFrame(), None, 200 # Return empty DataFrame, success

        df = pd.DataFrame(data)
        current_app.logger.info(f"Created PTM attendance DataFrame with shape: {df.shape}")

        # --- Calculate Attendance Percentage ---
        df['total_present_ptm'] = pd.to_numeric(df['total_present_ptm'], errors='coerce').fillna(0)
        df['total_ptms'] = pd.to_numeric(df['total_ptms'], errors='coerce').fillna(0)
        df['ptm_attendance_percentage'] = df.apply(
            lambda row: (row['total_present_ptm'] / row['total_ptms'] * 100) if row['total_ptms'] > 0 else 0,
            axis=1
        )
        current_app.logger.info("Calculated PTM attendance percentage.")

        # --- Create Pivot Table ---
        pivot_table_no_margins = pd.pivot_table(df,
                                        index='school_name',
                                        columns='grade_name',
                                        values='ptm_attendance_percentage',
                                        fill_value=None)
        current_app.logger.info(f"Created initial PTM pivot table (no margins), shape: {pivot_table_no_margins.shape}")

        # --- Calculate Margins (Weighted Average) ---
        overall_totals = df.groupby('school_name')[['total_present_ptm', 'total_ptms']].sum()
        overall_totals['Total'] = overall_totals.apply(
            lambda row: (row['total_present_ptm'] / row['total_ptms'] * 100) if row['total_ptms'] > 0 else 0,
            axis=1
        )
        grade_totals = df.groupby('grade_name')[['total_present_ptm', 'total_ptms']].sum()
        grade_totals['Total'] = grade_totals.apply(
            lambda row: (row['total_present_ptm'] / row['total_ptms'] * 100) if row['total_ptms'] > 0 else 0,
            axis=1
        )
        grand_total_present = df['total_present_ptm'].sum()
        grand_total_ptms = df['total_ptms'].sum()
        grand_total_percentage = (grand_total_present / grand_total_ptms * 100) if grand_total_ptms > 0 else 0

        # Add margins
        pivot_table = pivot_table_no_margins.copy()
        pivot_table['Total'] = overall_totals['Total']
        pivot_table.loc['Total'] = grade_totals['Total']
        pivot_table.loc['Total', 'Total'] = grand_total_percentage
        current_app.logger.info(f"Added calculated margins to PTM pivot. Shape: {pivot_table.shape}")

        # --- Customize Pivot Table (Renaming, Ordering) ---
        pivot_table.index.name = 'School'
        pivot_table.columns.name = 'Grade'
        pivot_table = _transform_and_sort_grades(pivot_table) # Reuse existing sorter

        # --- Format as Percentages ---
        format_cols = [col for col in pivot_table.columns if col != 'School']
        try:
            styled_pivot = pivot_table.style.format("{:.1f}%", subset=pd.IndexSlice[:, format_cols], na_rep='-')
            current_app.logger.info("Formatted PTM pivot table cells as percentages.")
        except Exception as format_error:
             current_app.logger.error(f"Error formatting PTM pivot table as percentage: {format_error}")
             styled_pivot = pivot_table

        return styled_pivot, None, 200 # Return Styler object or DataFrame

    except pymysql.Error as e:
        current_app.logger.error(f"Database error generating PTM attendance pivot: {e}", exc_info=True)
        return None, "Database error occurred.", 500
    except Exception as e:
        current_app.logger.error(f"Error generating PTM attendance pivot: {e}", exc_info=True)
        return None, "An internal error occurred.", 500
    finally:
        if connection:
            connection.close()

# --- Route: Get PTM Attendance Table (Now Pivot) --- #
@demographics_bp.route('/get_ptm_attendance_data', methods=['POST'])
def get_parent_attendance_data(): # Keep function name for url_for consistency
    """API endpoint to get PARENT attendance data as an HTML PIVOT table based on JSON filters (expects month)."""
    filters = request.json
    current_app.logger.info(f"Received request for /get_ptm_attendance_data (Parent Pivot) with filters: {filters}")

    # Call the pivot generation helper function
    pivot_data, error_msg, status_code = _generate_ptm_attendance_pivot_data(filters) # Updated helper call

    if error_msg:
        return jsonify({"error": error_msg}), status_code

    if pivot_data is None:
        # This case might indicate an unexpected error in the helper
        return jsonify({"error": "Failed to generate parent attendance pivot data"}), 500

    # Check if the result is an empty DataFrame (no data found)
    if isinstance(pivot_data, pd.DataFrame) and pivot_data.empty and status_code == 200:
         return jsonify({
                "html_table": "<p class='text-center text-muted'>No Parent PTM attendance data available for the selected month.</p>"
            }), 200

    # --- Apply Styling and Convert to HTML (similar to student attendance route) ---
    try:
        # Extract DataFrame if pivot_data is a Styler
        if isinstance(pivot_data, pd.io.formats.style.Styler):
            df = pivot_data.data
            styler = pivot_data
        else: # Fallback if formatting failed in helper
            df = pivot_data

            # Check for duplicate index or columns and make them unique if needed
            if df.index.duplicated().any():
                current_app.logger.warning("Duplicate index values found in PTM pivot table. Making them unique.")
                # Create a new index with unique values by adding a suffix
                new_index = []
                seen = {}
                for idx in df.index:
                    if idx in seen:
                        seen[idx] += 1
                        new_index.append(f"{idx} ({seen[idx]})")
                    else:
                        seen[idx] = 0
                        new_index.append(idx)
                df.index = new_index

            if df.columns.duplicated().any():
                current_app.logger.warning("Duplicate column values found in PTM pivot table. Making them unique.")
                # Create new column names with unique values by adding a suffix
                new_columns = []
                seen = {}
                for col in df.columns:
                    if col in seen:
                        seen[col] += 1
                        new_columns.append(f"{col} ({seen[col]})")
                    else:
                        seen[col] = 0
                        new_columns.append(col)
                df.columns = new_columns

            styler = df.style

        # Apply alignment styles
        styler = styler.set_properties(**{'text-align': 'center'})
        styler = styler.set_table_styles([
            {'selector': 'th', 'props': [('text-align', 'center')]},
            {'selector': 'thead th.index_name', 'props': [('text-align', 'left')]},
            {'selector': 'tbody th.row_heading', 'props': [('text-align', 'left')]},
        ])

        # Add Bootstrap classes and generate HTML
        html_table = styler.set_table_attributes(
            'class="table table-striped table-bordered table-hover table-sm"'
        ).to_html(border=0, na_rep='-')

        return jsonify({"html_table": html_table})

    except Exception as e:
        current_app.logger.error(f"Error styling or converting Parent PTM pivot table to HTML: {e}", exc_info=True)
        return jsonify({"error": "Failed to render Parent PTM attendance table."}), 500

# --- Route: Download PTM Attendance Excel --- #
@demographics_bp.route('/download_ptm_attendance_data', methods=['POST', 'GET'])
def download_parent_attendance_data(): # Renamed function
    """API endpoint to download PARENT attendance PIVOT data as an Excel file based on filters."""
    if request.method == 'POST':
        filters = request.get_json()
    else:
        filters = {
            'academic_year': request.args.get('academic_year', 'All'),
            'month': request.args.get('month', 'All'),
            'city': request.args.get('city', 'All'),
            'gender': request.args.get('gender', 'All')
        }
    current_app.logger.info(f"Received request for /download_ptm_attendance_data (Parent Pivot Download) with filters: {filters}")

    # Generate the pivot data (returns DataFrame or Styler)
    pivot_data, error_msg, status_code = _generate_ptm_attendance_pivot_data(filters)

    if error_msg:
        return Response(f"Error generating data for download: {error_msg}", status=status_code, mimetype='text/plain')

    # Check for empty DataFrame case before attempting styling/conversion
    if isinstance(pivot_data, pd.DataFrame) and pivot_data.empty and status_code == 200:
         return Response("No Parent PTM attendance data found for the selected filters to download.", status=404, mimetype='text/plain')

    # Extract DataFrame from Styler if necessary for excel export
    if isinstance(pivot_data, pd.io.formats.style.Styler):
        df_to_export = pivot_data.data # Get the underlying DataFrame
    elif isinstance(pivot_data, pd.DataFrame):
        df_to_export = pivot_data
    else:
        # Handle unexpected return type
         current_app.logger.error(f"Unexpected data type for Excel export: {type(pivot_data)}")
         return Response("Error preparing data for download.", status=500, mimetype='text/plain')

    # Format numbers in the DataFrame before exporting to Excel (optional but nice)
    try:
        format_cols = [col for col in df_to_export.columns if col != 'School'] # Assuming index is 'School'
        for col in format_cols:
             # Check if column exists and is numeric before formatting
             if col in df_to_export.columns and pd.api.types.is_numeric_dtype(df_to_export[col]):
                 df_to_export[col] = df_to_export[col].map('{:.1f}%'.format) # Apply percentage format as string
    except Exception as fmt_err:
        current_app.logger.warning(f"Could not apply percentage formatting to DataFrame for Excel export: {fmt_err}")

    # Update filename to include all filters
    filename_parts = ["parent_ptm_attendance_pivot", filters['academic_year'], filters['month'], filters['city'], filters['gender']]
    safe_filename_base = "_".join(part for part in filename_parts if part != 'All')
    return create_excel_response(df_to_export, safe_filename_base or "parent_ptm_attendance_pivot")

# --- Helper Function for SW-Parent Attendance Pivot Data Generation ---
def _generate_sw_parent_attendance_pivot_data(filters):
    """Fetches SW-Parent attendance data (swptm_attendance_data), calculates average attendance %,
       and generates a pivot table similar to parent PTM attendance."""
    connection = None
    try:
        from app import get_db_connection # Local import
        connection = get_db_connection()
        if connection is None:
            return None, "Database connection failed.", 500

        # Extract filters (Month, Year, City)
        month_filter = filters.get('month', 'All')
        academic_year_filter = filters.get('academic_year', 'All')
        city_filter = filters.get('city', 'All')
        gender_filter = filters.get('gender', 'All') # Get gender filter
        current_app.logger.info(f"Generating SW Parent PTM attendance pivot with filters - Month: {month_filter}, Year: {academic_year_filter}, City: {city_filter}, Gender: {gender_filter}")

        # --- Build SQL Query ---
        # *** Use swptm_attendance_data table and columns ***
        sql = """
            SELECT
                swpa.school_name,
                swpa.grade_name,
                SUM(swpa.present_swptm) AS total_present_swptm,
                SUM(swpa.total_no_of_swptm) AS total_swptms
            FROM swptm_attendance_data swpa
            INNER JOIN city c ON swpa.school_name = c.school_name
        """
        params = []
        conditions = ["swpa.total_no_of_swptm > 0"] # Ensure we don't divide by zero later

        # Add Academic Year filter condition (assuming column 'academic_year' exists)
        if academic_year_filter != 'All':
            # IMPORTANT: Verify 'academic_year' is the correct column name in swptm_attendance_data
            conditions.append("swpa.academic_year = %s")
            params.append(academic_year_filter)

        if month_filter != 'All':
            conditions.append("swpa.month = %s") # Assuming a 'month' column
            params.append(month_filter)

        if city_filter != 'All':
            conditions.append("c.city = %s")
            params.append(city_filter)

        if gender_filter != 'All':
            # Add Gender filter condition (assuming column 'gender' exists)
            conditions.append("swpa.gender = %s")
            params.append(gender_filter)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " GROUP BY swpa.school_name, swpa.grade_name"
        sql += " ORDER BY swpa.school_name, swpa.grade_name;"

        current_app.logger.debug(f"Executing SQL for SW PTM attendance pivot: {sql} with params: {params}")
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, params)
            data = cursor.fetchall()

        if not data:
            current_app.logger.info("No SW PTM attendance data found for the selected filters.")
            return pd.DataFrame(), None, 200 # Return empty DataFrame, success

        df = pd.DataFrame(data)
        current_app.logger.info(f"Created SW PTM attendance DataFrame with shape: {df.shape}")

        # --- Calculate Attendance Percentage ---
        df['total_present_swptm'] = pd.to_numeric(df['total_present_swptm'], errors='coerce').fillna(0)
        df['total_swptms'] = pd.to_numeric(df['total_swptms'], errors='coerce').fillna(0)
        df['sw_ptm_attendance_percentage'] = df.apply(
            lambda row: (row['total_present_swptm'] / row['total_swptms'] * 100) if row['total_swptms'] > 0 else 0,
            axis=1
        )
        current_app.logger.info("Calculated SW PTM attendance percentage.")

        # --- Create Pivot Table ---
        pivot_table_no_margins = pd.pivot_table(df,
                                        index='school_name',
                                        columns='grade_name',
                                        values='sw_ptm_attendance_percentage',
                                        fill_value=None)
        current_app.logger.info(f"Created initial SW PTM pivot table (no margins), shape: {pivot_table_no_margins.shape}")

        # --- Calculate Margins (Weighted Average) ---
        overall_totals = df.groupby('school_name')[['total_present_swptm', 'total_swptms']].sum()
        overall_totals['Total'] = overall_totals.apply(
            lambda row: (row['total_present_swptm'] / row['total_swptms'] * 100) if row['total_swptms'] > 0 else 0,
            axis=1
        )
        grade_totals = df.groupby('grade_name')[['total_present_swptm', 'total_swptms']].sum()
        grade_totals['Total'] = grade_totals.apply(
            lambda row: (row['total_present_swptm'] / row['total_swptms'] * 100) if row['total_swptms'] > 0 else 0,
            axis=1
        )
        grand_total_present = df['total_present_swptm'].sum()
        grand_total_swptms = df['total_swptms'].sum()
        grand_total_percentage = (grand_total_present / grand_total_swptms * 100) if grand_total_swptms > 0 else 0

        # Add margins
        pivot_table = pivot_table_no_margins.copy()
        pivot_table['Total'] = overall_totals['Total']
        pivot_table.loc['Total'] = grade_totals['Total']
        pivot_table.loc['Total', 'Total'] = grand_total_percentage
        current_app.logger.info(f"Added calculated margins to SW PTM pivot. Shape: {pivot_table.shape}")

        # --- Customize Pivot Table (Renaming, Ordering) ---
        pivot_table.index.name = 'School'
        pivot_table.columns.name = 'Grade'
        pivot_table = _transform_and_sort_grades(pivot_table) # Reuse existing sorter

        # --- Format as Percentages ---
        format_cols = [col for col in pivot_table.columns if col != 'School']
        try:
            styled_pivot = pivot_table.style.format("{:.1f}%", subset=pd.IndexSlice[:, format_cols], na_rep='-')
            current_app.logger.info("Formatted SW PTM pivot table cells as percentages.")
        except Exception as format_error:
             current_app.logger.error(f"Error formatting SW PTM pivot table as percentage: {format_error}")
             styled_pivot = pivot_table

        return styled_pivot, None, 200 # Return Styler object or DataFrame

    except pymysql.Error as e:
        current_app.logger.error(f"Database error generating SW PTM attendance pivot: {e}", exc_info=True)
        return None, "Database error occurred.", 500
    except Exception as e:
        current_app.logger.error(f"Error generating SW PTM attendance pivot: {e}", exc_info=True)
        return None, "An internal error occurred.", 500
    finally:
        if connection:
            connection.close()
            current_app.logger.debug("SW PTM Attendance Pivot DB connection closed.")

# --- Route: Get SW Parent Attendance Table (Pivot) --- #
@demographics_bp.route('/get_sw_parent_attendance_data', methods=['POST'])
def get_sw_parent_attendance_data():
    """API endpoint to get SW-PARENT attendance data as an HTML PIVOT table based on JSON filters (expects month)."""
    filters = request.json
    current_app.logger.info(f"Received request for /get_sw_parent_attendance_data (SW Parent Pivot) with filters: {filters}")

    # Call the SW pivot generation helper function
    pivot_data, error_msg, status_code = _generate_sw_parent_attendance_pivot_data(filters)

    if error_msg:
        return jsonify({"error": error_msg}), status_code

    if pivot_data is None:
        return jsonify({"error": "Failed to generate SW parent attendance pivot data"}), 500

    # Check if the result is an empty DataFrame (no data found)
    if isinstance(pivot_data, pd.DataFrame) and pivot_data.empty and status_code == 200:
         return jsonify({
                "html_table": "<p class='text-center text-muted'>No SW Parent PTM attendance data available for the selected month.</p>"
            }), 200

    # --- Apply Styling and Convert to HTML ---
    try:
        # Extract DataFrame if pivot_data is a Styler
        if isinstance(pivot_data, pd.io.formats.style.Styler):
            df = pivot_data.data
            styler = pivot_data
        else:
            df = pivot_data

            # Check for duplicate index or columns and make them unique if needed
            if df.index.duplicated().any():
                current_app.logger.warning("Duplicate index values found in SW PTM pivot table. Making them unique.")
                # Create a new index with unique values by adding a suffix
                new_index = []
                seen = {}
                for idx in df.index:
                    if idx in seen:
                        seen[idx] += 1
                        new_index.append(f"{idx} ({seen[idx]})")
                    else:
                        seen[idx] = 0
                        new_index.append(idx)
                df.index = new_index

            if df.columns.duplicated().any():
                current_app.logger.warning("Duplicate column values found in SW PTM pivot table. Making them unique.")
                # Create new column names with unique values by adding a suffix
                new_columns = []
                seen = {}
                for col in df.columns:
                    if col in seen:
                        seen[col] += 1
                        new_columns.append(f"{col} ({seen[col]})")
                    else:
                        seen[col] = 0
                        new_columns.append(col)
                df.columns = new_columns

            styler = df.style

        # Apply alignment styles
        styler = styler.set_properties(**{'text-align': 'center'})
        styler = styler.set_table_styles([
            {'selector': 'th', 'props': [('text-align', 'center')]},
            {'selector': 'thead th.index_name', 'props': [('text-align', 'left')]},
            {'selector': 'tbody th.row_heading', 'props': [('text-align', 'left')]},
        ])

        # Add Bootstrap classes and generate HTML
        html_table = styler.set_table_attributes(
            'class="table table-striped table-bordered table-hover table-sm"'
        ).to_html(border=0, na_rep='-')

        return jsonify({"html_table": html_table})

    except Exception as e:
        current_app.logger.error(f"Error styling or converting SW Parent PTM pivot table to HTML: {e}", exc_info=True)
        return jsonify({"error": "Failed to render SW Parent PTM attendance table."}), 500

# --- Route: Download SW Parent Attendance Excel --- #
@demographics_bp.route('/download_sw_parent_attendance_data', methods=['POST', 'GET'])
def download_sw_parent_attendance_data():
    """API endpoint to download SW-PARENT attendance PIVOT data as an Excel file based on filters."""
    if request.method == 'POST':
        filters = request.get_json()
    else:
        filters = {
            'academic_year': request.args.get('academic_year', 'All'),
            'month': request.args.get('month', 'All'),
            'city': request.args.get('city', 'All'),
            'gender': request.args.get('gender', 'All')
        }
    current_app.logger.info(f"Received request for /download_sw_parent_attendance_data (SW Parent Pivot Download) with filters: {filters}")

    # Generate the pivot data (returns DataFrame or Styler)
    pivot_data, error_msg, status_code = _generate_sw_parent_attendance_pivot_data(filters)

    if error_msg:
        return Response(f"Error generating data for download: {error_msg}", status=status_code, mimetype='text/plain')

    # Check for empty DataFrame case
    if isinstance(pivot_data, pd.DataFrame) and pivot_data.empty and status_code == 200:
         return Response("No SW Parent PTM attendance data found for the selected filters to download.", status=404, mimetype='text/plain')

    # Extract DataFrame from Styler if necessary
    if isinstance(pivot_data, pd.io.formats.style.Styler):
        df_to_export = pivot_data.data
    elif isinstance(pivot_data, pd.DataFrame):
        df_to_export = pivot_data
    else:
         current_app.logger.error(f"Unexpected data type for SW Excel export: {type(pivot_data)}")
         return Response("Error preparing data for download.", status=500, mimetype='text/plain')

    # Format numbers in the DataFrame before exporting (optional)
    try:
        format_cols = [col for col in df_to_export.columns if col != 'School']
        for col in format_cols:
             if col in df_to_export.columns and pd.api.types.is_numeric_dtype(df_to_export[col]):
                 df_to_export[col] = df_to_export[col].map('{:.1f}%'.format)
    except Exception as fmt_err:
        current_app.logger.warning(f"Could not apply percentage formatting to SW DataFrame for Excel export: {fmt_err}")

    # Update filename
    filename_parts = ["sw_parent_ptm_attendance_pivot", filters['academic_year'], filters['month'], filters['city'], filters['gender']]
    safe_filename_base = "_".join(part for part in filename_parts if part != 'All')
    return create_excel_response(df_to_export, safe_filename_base or "sw_parent_ptm_attendance_pivot")

# --- Route: Get Monthly Student Attendance for a Specific School (for Modal Chart) --- #
@demographics_bp.route('/get_school_monthly_attendance', methods=['GET'])
def get_school_monthly_attendance():
    """API endpoint to get monthly average student attendance for a specific school."""
    school_name = request.args.get('school_name')
    academic_year = request.args.get('academic_year')
    gender = request.args.get('gender')
    current_app.logger.info(f"Received request for /get_school_monthly_attendance for school: {school_name}")
    current_app.logger.info(f"Filters received: Academic Year='{academic_year}', Gender='{gender}'")

    if not school_name:
        return jsonify({"error": "Missing 'school_name' parameter"}), 400

    connection = None
    try:
        from app import get_db_connection
        connection = get_db_connection()
        if connection is None:
            return jsonify({"error": "Database connection failed"}), 500

        # Define the correct order of months for the academic year
        month_order = [
            'June', 'July', 'August', 'September', 'October', 'November',
            'December', 'January', 'February', 'March', 'April', 'May'
        ]

        # Build the WHERE clause dynamically
        where_clauses = ["school_name = %s", "no_of_working_days > 0"]
        params = [school_name]

        if academic_year and academic_year != 'All':
            where_clauses.append("academic_year = %s")
            params.append(academic_year)
            current_app.logger.debug(f"Adding Academic Year filter: {academic_year}")

        if gender and gender != 'All':
            # Assuming gender is stored as 'M'/'F' in the student_details/student_attendance_data table
            # Adjust the column name (e.g., s.gender) and join condition if necessary
            # This example assumes student_attendance_data has a direct 'gender' column or similar
            where_clauses.append("gender = %s") # Needs adjustment if joining student_details
            params.append(gender)
            current_app.logger.debug(f"Adding Gender filter: {gender}")

        # Query to get monthly sums for the specific school
        # IMPORTANT: Ensure table/column names match your schema (student_attendance_data, present, total, month, school_name)
        sql = f"""
            SELECT
                month,
                SUM(no_of_present_days) AS monthly_present,
                SUM(no_of_working_days) AS monthly_total
            FROM student_attendance_data
            WHERE {" AND ".join(where_clauses)}
            GROUP BY month
            ORDER BY FIELD(month, 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'January', 'February', 'March', 'April', 'May');
            -- Using FIELD for sorting assumes 'month' column stores month names as strings
        """

        current_app.logger.debug(f"Executing SQL for school monthly attendance: {sql} with params: {params}")
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, tuple(params))
            data = cursor.fetchall()
            current_app.logger.debug(f"Fetched monthly data for {school_name}: {data}")

        # Process data and ensure correct month order
        monthly_attendance = {row['month']: (row['monthly_present'] / row['monthly_total'] * 100)
                              if row['monthly_total'] > 0 else 0
                              for row in data}

        # Prepare response data in the correct order, filling gaps with 0
        response_labels = month_order
        response_data = [monthly_attendance.get(month, 0) for month in month_order]

        current_app.logger.info(f"Prepared chart data for {school_name}: Labels={response_labels}, Data Count={len(response_data)}")
        return jsonify({"labels": response_labels, "data": response_data})

    except pymysql.Error as e:
        current_app.logger.error(f"Database error fetching monthly attendance for {school_name}: {e}", exc_info=True)
        return jsonify({"error": f"Database error: {e}"}), 500
    except Exception as e:
        current_app.logger.error(f"Error fetching monthly attendance for {school_name}: {e}", exc_info=True)
        return jsonify({"error": f"An internal error occurred: {e}"}), 500
    finally:
        if connection:
            connection.close()
            current_app.logger.debug(f"DB connection closed for /get_school_monthly_attendance request for {school_name}.")


# ------------------------------------------------------
# Grade-specific attendance routes

@demographics_bp.route('/get_grade_specific_monthly_attendance', methods=['GET'])
def get_grade_specific_monthly_attendance():
    """API endpoint to get monthly average student attendance for a specific school and grade."""
    school_name = request.args.get('school_name')
    grade_name = request.args.get('grade_name')
    academic_year = request.args.get('academic_year')
    gender = request.args.get('gender')

    # Handle case conversion for "Nursery" -> "NURSERY"
    if grade_name and grade_name.lower() == 'nursery':
        grade_name = 'NURSERY'
        current_app.logger.debug(f"Converted grade name: 'Nursery' -> 'NURSERY'")

    current_app.logger.info(f"Received request for /get_grade_specific_monthly_attendance for school: {school_name}, grade: {grade_name}")
    current_app.logger.info(f"Filters received: Academic Year='{academic_year}', Gender='{gender}'")

    if not school_name or not grade_name:
        return jsonify({"error": "Missing 'school_name' or 'grade_name' parameter"}), 400

    connection = None
    try:
        from app import get_db_connection
        connection = get_db_connection()
        if connection is None:
            return jsonify({"error": "Database connection failed"}), 500

        # Define the correct order of months for the academic year
        month_order = [
            'June', 'July', 'August', 'September', 'October', 'November',
            'December', 'January', 'February', 'March', 'April', 'May'
        ]

        # Build the WHERE clause dynamically
        where_clauses = ["school_name = %s", "grade_name = %s", "no_of_working_days > 0"]
        params = [school_name, grade_name]

        if academic_year and academic_year != 'All':
            where_clauses.append("academic_year = %s")
            params.append(academic_year)
            current_app.logger.debug(f"Adding Academic Year filter: {academic_year}")

        if gender and gender != 'All':
            where_clauses.append("gender = %s")
            params.append(gender)
            current_app.logger.debug(f"Adding Gender filter: {gender}")

        # Query to get monthly sums for the specific school and grade
        sql = f"""
            SELECT
                month,
                SUM(no_of_present_days) AS monthly_present,
                SUM(no_of_working_days) AS monthly_total
            FROM student_attendance_data
            WHERE {" AND ".join(where_clauses)}
            GROUP BY month
            ORDER BY FIELD(month, 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'January', 'February', 'March', 'April', 'May');
        """

        current_app.logger.debug(f"Executing SQL for grade-specific monthly attendance: {sql} with params: {params}")
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, tuple(params))
            data = cursor.fetchall()
            current_app.logger.debug(f"Fetched monthly data for {school_name}, grade {grade_name}: {data}")

        # Process data and ensure correct month order
        monthly_attendance = {row['month']: (row['monthly_present'] / row['monthly_total'] * 100)
                              if row['monthly_total'] > 0 else 0
                              for row in data}

        # Prepare response data in the correct order, filling gaps with 0
        response_labels = month_order
        response_data = [monthly_attendance.get(month, 0) for month in month_order]

        current_app.logger.info(f"Prepared chart data for {school_name}, grade {grade_name}: Labels={response_labels}, Data Count={len(response_data)}")
        return jsonify({"labels": response_labels, "data": response_data})

    except pymysql.Error as e:
        current_app.logger.error(f"Database error fetching grade-specific monthly attendance for {school_name}, grade {grade_name}: {e}", exc_info=True)
        return jsonify({"error": f"Database error: {e}"}), 500
    except Exception as e:
        current_app.logger.error(f"Error fetching grade-specific monthly attendance for {school_name}, grade {grade_name}: {e}", exc_info=True)
        return jsonify({"error": f"An internal error occurred: {e}"}), 500
    finally:
        if connection:
            connection.close()
            current_app.logger.debug(f"DB connection closed for /get_grade_specific_monthly_attendance request for {school_name}, grade {grade_name}.")

@demographics_bp.route('/get_grade_specific_parent_monthly', methods=['GET'])
def get_grade_specific_parent_monthly():
    """API endpoint to get monthly average parent attendance for a specific school and grade."""
    school_name = request.args.get('school_name')
    grade_name = request.args.get('grade_name')
    academic_year = request.args.get('academic_year')
    gender = request.args.get('gender')

    # Handle case conversion for "Nursery" -> "NURSERY"
    if grade_name and grade_name.lower() == 'nursery':
        grade_name = 'NURSERY'
        current_app.logger.debug(f"Converted grade name: 'Nursery' -> 'NURSERY'")

    current_app.logger.info(f"Received request for /get_grade_specific_parent_monthly for school: {school_name}, grade: {grade_name}")
    current_app.logger.info(f"Filters received: Academic Year='{academic_year}', Gender='{gender}'")

    if not school_name or not grade_name:
        return jsonify({"error": "Missing 'school_name' or 'grade_name' parameter"}), 400

    connection = None
    try:
        from app import get_db_connection
        connection = get_db_connection()
        if connection is None:
            return jsonify({"error": "Database connection failed"}), 500

        # Define the correct order of months for the academic year
        month_order = [
            'June', 'July', 'August', 'September', 'October', 'November',
            'December', 'January', 'February', 'March', 'April', 'May'
        ]

        # Build the WHERE clause dynamically
        where_clauses = ["school_name = %s", "grade_name = %s", "total_no_of_ptm > 0"]
        params = [school_name, grade_name]

        if academic_year and academic_year != 'All':
            where_clauses.append("academic_year = %s")
            params.append(academic_year)
            current_app.logger.debug(f"Adding Academic Year filter: {academic_year}")

        if gender and gender != 'All':
            where_clauses.append("gender = %s")
            params.append(gender)
            current_app.logger.debug(f"Adding Gender filter: {gender}")

        # Query to get monthly sums for the specific school and grade
        sql = f"""
            SELECT
                month,
                SUM(present_ptm) AS monthly_present,
                SUM(total_no_of_ptm) AS monthly_total
            FROM ptm_attendance_data
            WHERE {" AND ".join(where_clauses)}
            GROUP BY month
            ORDER BY FIELD(month, 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'January', 'February', 'March', 'April', 'May');
        """

        current_app.logger.debug(f"Executing SQL for grade-specific parent monthly attendance: {sql} with params: {params}")
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, tuple(params))
            data = cursor.fetchall()
            current_app.logger.debug(f"Fetched monthly parent data for {school_name}, grade {grade_name}: {data}")

        # Process data and ensure correct month order
        monthly_attendance = {row['month']: (row['monthly_present'] / row['monthly_total'] * 100)
                              if row['monthly_total'] > 0 else 0
                              for row in data}

        # Prepare response data in the correct order, filling gaps with 0
        response_labels = month_order
        response_data = [monthly_attendance.get(month, 0) for month in month_order]

        current_app.logger.info(f"Prepared parent chart data for {school_name}, grade {grade_name}: Labels={response_labels}, Data Count={len(response_data)}")
        return jsonify({"labels": response_labels, "data": response_data})

    except pymysql.Error as e:
        current_app.logger.error(f"Database error fetching grade-specific parent monthly attendance for {school_name}, grade {grade_name}: {e}", exc_info=True)
        return jsonify({"error": f"Database error: {e}"}), 500
    except Exception as e:
        current_app.logger.error(f"Error fetching grade-specific parent monthly attendance for {school_name}, grade {grade_name}: {e}", exc_info=True)
        return jsonify({"error": f"An internal error occurred: {e}"}), 500
    finally:
        if connection:
            connection.close()
            current_app.logger.debug(f"DB connection closed for /get_grade_specific_parent_monthly request for {school_name}, grade {grade_name}.")

@demographics_bp.route('/get_grade_specific_swparent_monthly', methods=['GET'])
def get_grade_specific_swparent_monthly():
    """API endpoint to get monthly average SW-Parent attendance for a specific school and grade."""
    school_name = request.args.get('school_name')
    grade_name = request.args.get('grade_name')
    academic_year = request.args.get('academic_year')
    gender = request.args.get('gender')

    # Handle case conversion for "Nursery" -> "NURSERY"
    if grade_name and grade_name.lower() == 'nursery':
        grade_name = 'NURSERY'
        current_app.logger.debug(f"Converted grade name: 'Nursery' -> 'NURSERY'")

    current_app.logger.info(f"Received request for /get_grade_specific_swparent_monthly for school: {school_name}, grade: {grade_name}")
    current_app.logger.info(f"Filters received: Academic Year='{academic_year}', Gender='{gender}'")

    if not school_name or not grade_name:
        return jsonify({"error": "Missing 'school_name' or 'grade_name' parameter"}), 400

    connection = None
    try:
        from app import get_db_connection
        connection = get_db_connection()
        if connection is None:
            return jsonify({"error": "Database connection failed"}), 500

        # Define the correct order of months for the academic year
        month_order = [
            'June', 'July', 'August', 'September', 'October', 'November',
            'December', 'January', 'February', 'March', 'April', 'May'
        ]

        # Build the WHERE clause dynamically
        where_clauses = ["school_name = %s", "grade_name = %s", "total_no_of_swptm > 0"]
        params = [school_name, grade_name]

        if academic_year and academic_year != 'All':
            where_clauses.append("academic_year = %s")
            params.append(academic_year)
            current_app.logger.debug(f"Adding Academic Year filter: {academic_year}")

        if gender and gender != 'All':
            where_clauses.append("gender = %s")
            params.append(gender)
            current_app.logger.debug(f"Adding Gender filter: {gender}")

        # Query to get monthly sums for the specific school and grade
        sql = f"""
            SELECT
                month,
                SUM(present_swptm) AS monthly_present,
                SUM(total_no_of_swptm) AS monthly_total
            FROM swptm_attendance_data
            WHERE {" AND ".join(where_clauses)}
            GROUP BY month
            ORDER BY FIELD(month, 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'January', 'February', 'March', 'April', 'May');
        """

        current_app.logger.debug(f"Executing SQL for grade-specific SW-Parent monthly attendance: {sql} with params: {params}")
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, tuple(params))
            data = cursor.fetchall()
            current_app.logger.debug(f"Fetched monthly SW-Parent data for {school_name}, grade {grade_name}: {data}")

        # Process data and ensure correct month order
        monthly_attendance = {row['month']: (row['monthly_present'] / row['monthly_total'] * 100)
                              if row['monthly_total'] > 0 else 0
                              for row in data}

        # Prepare response data in the correct order, filling gaps with 0
        response_labels = month_order
        response_data = [monthly_attendance.get(month, 0) for month in month_order]

        current_app.logger.info(f"Prepared SW-Parent chart data for {school_name}, grade {grade_name}: Labels={response_labels}, Data Count={len(response_data)}")
        return jsonify({"labels": response_labels, "data": response_data})

    except pymysql.Error as e:
        current_app.logger.error(f"Database error fetching grade-specific SW-Parent monthly attendance for {school_name}, grade {grade_name}: {e}", exc_info=True)
        return jsonify({"error": f"Database error: {e}"}), 500
    except Exception as e:
        current_app.logger.error(f"Error fetching grade-specific SW-Parent monthly attendance for {school_name}, grade {grade_name}: {e}", exc_info=True)
        return jsonify({"error": f"An internal error occurred: {e}"}), 500
    finally:
        if connection:
            connection.close()
            current_app.logger.debug(f"DB connection closed for /get_grade_specific_swparent_monthly request for {school_name}, grade {grade_name}.")

# Add other routes and helper functions below if needed
# --- Route: Get Parent Attendance Details for a Specific School (for Modal) --- #
# --- Route: Get Monthly Parent Attendance for a Specific School (for Modal Chart) --- #
@demographics_bp.route('/get_school_parent_monthly_attendance', methods=['GET'])
def get_school_parent_monthly_attendance():
    """API endpoint to get monthly average parent attendance for a specific school."""
    school_name = request.args.get('school_name')
    academic_year = request.args.get('academic_year')
    gender = request.args.get('gender')
    current_app.logger.info(f"Received request for /get_school_parent_monthly_attendance for school: {school_name}")
    current_app.logger.info(f"Filters received: Academic Year='{academic_year}', Gender='{gender}'")

    if not school_name:
        return jsonify({"error": "Missing 'school_name' parameter"}), 400

    connection = None
    try:
        from app import get_db_connection
        connection = get_db_connection()
        if connection is None:
            return jsonify({"error": "Database connection failed"}), 500

        # Define the correct order of months for the academic year
        month_order = [
            'June', 'July', 'August', 'September', 'October', 'November',
            'December', 'January', 'February', 'March', 'April', 'May'
        ]

        # Build the WHERE clause dynamically
        where_clauses = ["school_name = %s", "total_no_of_ptm > 0"]
        params = [school_name]

        if academic_year and academic_year != 'All':
            where_clauses.append("academic_year = %s")
            params.append(academic_year)
            current_app.logger.debug(f"Adding Academic Year filter: {academic_year}")

        if gender and gender != 'All':
            where_clauses.append("gender = %s")
            params.append(gender)
            current_app.logger.debug(f"Adding Gender filter: {gender}")

        # Query to get monthly sums for the specific school
        sql = f"""
            SELECT
                month,
                SUM(present_ptm) AS monthly_present,
                SUM(total_no_of_ptm) AS monthly_total
            FROM ptm_attendance_data
            WHERE {" AND ".join(where_clauses)}
            GROUP BY month
            ORDER BY FIELD(month, 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'January', 'February', 'March', 'April', 'May');
        """

        current_app.logger.debug(f"Executing SQL for school parent monthly attendance: {sql} with params: {params}")
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, tuple(params))
            data = cursor.fetchall()
            current_app.logger.debug(f"Fetched monthly parent data for {school_name}: {data}")

        # Process data and ensure correct month order
        monthly_attendance = {row['month']: (row['monthly_present'] / row['monthly_total'] * 100)
                              if row['monthly_total'] > 0 else 0
                              for row in data}

        # Prepare response data in the correct order, filling gaps with 0
        response_labels = month_order
        response_data = [monthly_attendance.get(month, 0) for month in month_order]

        current_app.logger.info(f"Prepared parent chart data for {school_name}: Labels={response_labels}, Data Count={len(response_data)}")
        return jsonify({"labels": response_labels, "data": response_data})

    except pymysql.Error as e:
        current_app.logger.error(f"Database error fetching monthly parent attendance for {school_name}: {e}", exc_info=True)
        return jsonify({"error": f"Database error: {e}"}), 500
    except Exception as e:
        current_app.logger.error(f"Error fetching monthly parent attendance for {school_name}: {e}", exc_info=True)
        return jsonify({"error": f"An internal error occurred: {e}"}), 500
    finally:
        if connection:
            connection.close()
            current_app.logger.debug(f"DB connection closed for /get_school_parent_monthly_attendance request for {school_name}.")

@demographics_bp.route('/get_school_sw_parent_monthly', methods=['GET'])
def get_school_sw_parent_monthly():
    """API endpoint to get monthly SW-Parent attendance for a specific school."""
    school_name = request.args.get('school_name')
    academic_year = request.args.get('academic_year')
    gender = request.args.get('gender')
    current_app.logger.info(f"Received request for /get_school_sw_parent_monthly for school: {school_name}")
    current_app.logger.info(f"Filters received: Academic Year='{academic_year}', Gender='{gender}'")

    if not school_name:
        return jsonify({"error": "Missing 'school_name' parameter"}), 400

    connection = None
    try:
        from app import get_db_connection
        connection = get_db_connection()
        if connection is None:
            return jsonify({"error": "Database connection failed"}), 500

        # Define the correct order of months for the academic year
        month_order = [
            'June', 'July', 'August', 'September', 'October', 'November',
            'December', 'January', 'February', 'March', 'April', 'May'
        ]

        # Build the WHERE clause dynamically
        where_clauses = ["school_name = %s", "total_no_of_swptm > 0"]
        params = [school_name]

        if academic_year and academic_year != 'All':
            where_clauses.append("academic_year = %s")
            params.append(academic_year)
            current_app.logger.debug(f"Adding Academic Year filter: {academic_year}")

        if gender and gender != 'All':
            where_clauses.append("gender = %s")
            params.append(gender)
            current_app.logger.debug(f"Adding Gender filter: {gender}")

        # Query to get monthly sums for the specific school
        sql = f"""
            SELECT
                month,
                SUM(present_swptm) AS monthly_present,
                SUM(total_no_of_swptm) AS monthly_total
            FROM swptm_attendance_data
            WHERE {" AND ".join(where_clauses)}
            GROUP BY month
            ORDER BY FIELD(month, 'June', 'July', 'August', 'September', 'October', 'November', 'December', 'January', 'February', 'March', 'April', 'May');
        """

        current_app.logger.debug(f"Executing SQL for school SW-Parent monthly attendance: {sql} with params: {params}")
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, tuple(params))
            data = cursor.fetchall()
            current_app.logger.debug(f"Fetched monthly SW-Parent data for {school_name}: {data}")

        # Process data and ensure correct month order
        monthly_attendance = {row['month']: (row['monthly_present'] / row['monthly_total'] * 100)
                            if row['monthly_total'] > 0 else 0
                            for row in data}

        # Prepare response data in the correct order, filling gaps with 0
        response_labels = month_order
        response_data = [monthly_attendance.get(month, 0) for month in month_order]

        current_app.logger.info(f"Prepared SW-Parent chart data for {school_name}: Labels={response_labels}, Data Count={len(response_data)}")
        return jsonify({"labels": response_labels, "data": response_data})

    except pymysql.Error as e:
        current_app.logger.error(f"Database error fetching monthly SW-Parent attendance for {school_name}: {e}", exc_info=True)
        return jsonify({"error": f"Database error: {e}"}), 500
    except Exception as e:
        current_app.logger.error(f"Error fetching monthly SW-Parent attendance for {school_name}: {e}", exc_info=True)
        return jsonify({"error": f"An internal error occurred: {e}"}), 500
    finally:
        if connection:
            connection.close()
            current_app.logger.debug(f"DB connection closed for /get_school_sw_parent_monthly request for {school_name}.")