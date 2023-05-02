import os
from flask import jsonify, session
from datetime import datetime
from flask import flash
from flask import Flask, render_template, request, redirect, url_for
from database import get_connection

app = Flask(__name__)

# Set the secret key
app.config['SECRET_KEY'] = os.urandom(24)

# Route for the home page
@app.route('/')
def home():
    message = 'Welcome to my Private Coaching!'
    return render_template('home.html', message=message)

# Route for the coach page
@app.route('/coach')
def coach():
    if 'user_id' in session and session['role'] == 'coach':
        # Fetch the coach's information from the database
        connection = get_connection()
        cursor = connection.cursor()
        query = "SELECT first_name, last_name FROM users WHERE id = %s"
        cursor.execute(query, (session['user_id'],))
        coach = cursor.fetchone()
        cursor.close()
        connection.close()

        return render_template('coach.html', coach_name=coach, coach_id=session['user_id'], calendar=True)
    else:
        return redirect(url_for('login'))

# Route for the client page
@app.route('/client')
def client():
    if 'user_id' in session:
        # Get the list of available sessions from the database
        connection = get_connection()
        cursor = connection.cursor()
        query = "SELECT * FROM sessions WHERE is_available = true AND client_id = %s"  # Add the client_id filter
        cursor.execute(query, (session['user_id'],))
        sessions = cursor.fetchall()

        query = "SELECT first_name, last_name FROM users WHERE id = %s"
        cursor.execute(query, (session['user_id'],))
        client_name = cursor.fetchone()
        cursor.close()
        connection.close()

        # Get the first coach_id from the sessions or set a default value
        first_coach_id = sessions[0]['coach_id'] if sessions else -1

        return render_template('client.html', client_name=client_name, sessions=sessions, calendar=True, first_coach_id=first_coach_id)
    else:
        return redirect(url_for('login'))

# Route for the sessions page
@app.route('/sessions')
def sessions():
    search_query = request.args.get('search_query', '')

    with get_connection().cursor() as cursor:
        if search_query:
            query = '''
                SELECT sessions.*, users.first_name, users.last_name
                FROM sessions
                INNER JOIN users ON sessions.coach_id = users.id
                WHERE LOWER(users.first_name) LIKE %s
                OR LOWER(users.last_name) LIKE %s
                OR users.id = %s
            '''
            cursor.execute(query, (f'%{search_query.lower()}%', f'%{search_query.lower()}%', search_query))
        else:
            query = '''
                SELECT sessions.*, users.first_name, users.last_name
                FROM sessions
                INNER JOIN users ON sessions.coach_id = users.id
            '''
            cursor.execute(query)

        results = cursor.fetchall()

    return render_template('session.html', sessions=results)

# Route adding sessions
@app.route('/add_session', methods=['POST'])
def add_session():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    date_time = request.form['date_time']
    location = request.form['location']
    price = request.form['price']

    connection = get_connection()
    with connection.cursor() as cursor:
        query = """
        INSERT INTO sessions (date_time, location, price, is_available, coach_id)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (date_time, location, price, True, session['user_id']))
    connection.commit()
    
    return jsonify({"success": True})


# Route to book a session
@app.route('/book_session', methods=['POST'])
def book_session():
    if 'user_id' not in session or session['role'] != 'client':
        return jsonify({"error": "Not authorized"}), 401

    session_id = request.form['session_id']

    with get_connection() as connection:
        with connection.cursor() as cursor:
            print("User ID:", session['user_id'])
            print("Session ID:", session_id)

            get_client_id_query = "SELECT id FROM users WHERE id = %s AND role = 'client';"
            cursor.execute(get_client_id_query, (session['user_id'],))
            result = cursor.fetchone()
            
            if result is None:
                return jsonify({"error": "Client not found"}), 404

            client_id = result['id']
            print("Client ID:", client_id)

            query = "UPDATE sessions SET client_id = %s, is_available = 0 WHERE id = %s;"
            cursor.execute(query, (client_id, session_id))
            rows_affected = connection.affected_rows()  # Check the number of rows affected

            if rows_affected == 0:
                return jsonify({"error": "Session not found or already booked"}), 404

            connection.commit()

            # Add this print statement
            print(f"Session {session_id} booked for client {client_id}")

    return jsonify({"success": True})

# Route to fetch sessions and return them as JSON
@app.route('/get_sessions', methods=['GET'])
@app.route('/get_sessions/<int:coach_id>', methods=['GET'])
def get_sessions(coach_id=None):
    if 'user_id' not in session:
        return redirect(url_for('home'))

    if session['role'] == 'coach' and coach_id is None:
        coach_id = session['user_id']
    elif session['role'] == 'client' and coach_id is None:
        return jsonify([])  # Return an empty list if no coach_id is provided for clients

    connection = get_connection()
    cursor = connection.cursor()
    query = "SELECT * FROM sessions WHERE is_available = 1 AND coach_id = %s;"
    cursor.execute(query, (coach_id,))
    result = cursor.fetchall()
    cursor.close()
    connection.close()

    print("Raw result:", result)  # Debug message

    sessions = []
    for sess in result:
        session_dict = {
            'id': sess['id'],
            'date_time': sess['date_time'].strftime("%Y-%m-%dT%H:%M:%S") if isinstance(sess['date_time'], datetime) else sess['date_time'],
            'location': sess['location'],
            'price': float(sess['price']),
            'is_available': sess['is_available'],
            'coach_id': sess['coach_id']
        }
        sessions.append(session_dict)

    print("Sessions:", sessions)  # Debug message

    return jsonify(sessions)


# Route for the login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get the username and password from the form
        username = request.form['username']
        password = request.form['password']

        # Check if the username and password are correct
        connection = get_connection()
        cursor = connection.cursor()
        query = "SELECT * FROM users WHERE username = %s AND password = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if user:
            # If the user exists, store user information in the session
            session['user_id'] = user['id']
            session['first_name'] = user['first_name']
            session['role'] = user['role']

            # Set a welcome message with the username
            flash(f'Welcome, {user["username"]}!')

            # Redirect the user based on their role
            if user['role'] == 'client':
                return redirect(url_for('client'))
            elif user['role'] == 'coach':
                return redirect(url_for('coach'))
        else:
            # If the user does not exist, show an error message
            error_message = 'Invalid email/username or password. Please try again.'
            return render_template('login.html', error_message=error_message)

    # Render the login page for a GET request
    return render_template('login.html')

# Route for the logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_role', None)
    return redirect(url_for('home'))

# Route for the signup page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # Insert the new user into the database
        connection = get_connection()
        cursor = connection.cursor()
        query = """INSERT INTO users (first_name, last_name, username, email, password, role)
           VALUES (%s, %s, %s, %s, %s, %s)"""
        cursor.execute(query, (first_name, last_name, username, email, password, role))
        connection.commit()
        cursor.close()
        connection.close()

        flash(f'Successfully signed up! Please log in.')
        return redirect(url_for('login'))

    return render_template('signup.html')

if __name__ == "__main__":
    app.run(debug=True)