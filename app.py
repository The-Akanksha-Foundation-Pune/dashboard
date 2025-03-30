from flask import Flask, render_template, request, flash
import mysql.connector

app = Flask(__name__)
app.secret_key = "your_secret_key"  # For flash messages

# Database connection configuration
db_config = {
    'user': 'my_app_user',
    'password': 'MyNewPass1!',
    'host': 'localhost',
    'database': 'my_app'
}

# Route for Contact Form
@app.route("/", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        subject = request.form["subject"]
        message = request.form["message"]

        if not name or not email or not subject or not message:
            flash("All fields are required!", "danger")
        else:
            try:
                # Connect to the database
                connection = mysql.connector.connect(**db_config)
                cursor = connection.cursor()

                # Insert data into the database
                query = """
                INSERT INTO contact_messages (name, email, subject, message)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query, (name, email, subject, message))
                connection.commit()

                # Close the connection
                cursor.close()
                connection.close()

                flash("Message sent and saved successfully!", "success")
            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")

    return render_template("contact.html")


# Route to display table of entries
@app.route("/entries")
def show_entries():
    try:
        # Connect to the database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # Fetch data from the contact_messages table
        cursor.execute("SELECT name, email, subject, message FROM contact_messages")
        entries = cursor.fetchall()

        # Close the connection
        cursor.close()
        connection.close()

        return render_template("entries.html", entries=entries)

    except mysql.connector.Error as err:
        flash(f"Error: {err}", "danger")
        return render_template("entries.html", entries=[])


if __name__ == "__main__":
    app.run(debug=True)
