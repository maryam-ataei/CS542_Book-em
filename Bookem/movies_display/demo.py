# Store this code in '.py' file
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import cx_Oracle
import re
from datetime import datetime, timedelta
from flask import flash
import uuid
import random
import string
from jinja2 import Environment, FileSystemLoader, select_autoescape
# Create Flask application instance
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Enable the 'do' extension in Jinja2 and add 'set' as a global function
app.jinja_env.add_extension('jinja2.ext.do')
app.jinja_env.globals['set'] = set  # This makes the 'set' function available in Jinja2 templates

# Define Oracle DB connection
dsn_tns = cx_Oracle.makedsn('oracle.wpi.edu', '1521', sid='ORCL')
oracle_connection = cx_Oracle.connect(user='mataeikachooei', password='MR15975346', dsn=dsn_tns)

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    user_info = None

    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()

        cursor = oracle_connection.cursor()

        # Check if the user email exists in the Client table
        query1_corrected = """SELECT C.CID, U.UName, U.UPhoneNum, U.UAddr, U.UGender, U.UDoB 
                              FROM CLIENT C 
                              LEFT JOIN USERS U ON C.CID = U.USSN 
                              WHERE U.UEMAIL = :e AND U.UPASSWORD = :p """  # Assuming the columns are named 'EMAIL' and 'PASSWORD'
        cursor.execute(query1_corrected, {'e': email, 'p': password})
        client_account = cursor.fetchall()

        # Check if the user exists in the EventCreator table
        query2 = """SELECT E.ECID, U.UName, U.UPhoneNum, U.UAddr, U.UGender, U.UDoB 
                    FROM EventCreator E 
                    LEFT JOIN USERS U ON E.ECID = U.USSN 
                    WHERE U.UEMAIL = :e AND U.UPASSWORD = :p """
        cursor.execute(query2, {'e': email, 'p': password})
        event_creator_account = cursor.fetchall()

        # SH
        query3="""SELECT AID, AName FROM Admin WHERE AEmail = :aemail AND Apassword= :Apassword"""
        cursor.execute(query3, {'aemail': email, 'Apassword': password})
        admin_account = cursor.fetchall()


        if client_account:
            session['loggedin'] = True
            session['id'] = client_account[0][0]  # Fetch the correct user ID from the result
            session['password'] = password
            session['user_info'] = client_account[0][1:]  # Store user info
            msg = 'Logged in successfully as Client!'
            # return render_template('client_page.html', msg=msg, user_info= user_info)  # Redirect to client page
            return redirect(url_for('display_movies_by_client', cid=session['id']))  # Redirect to client page
        elif event_creator_account:
            session['loggedin'] = True
            session['id'] = event_creator_account[0][0]  # Fetch the correct user ID from the result
            session['password'] = password
            session['user_info'] = event_creator_account[0][1:]  # Store user info
            msg = 'Logged in successfully as Event Creator!'
            return redirect(url_for('event_creator_page'))  # Redirect to event creator page
        elif admin_account:
            session['loggedin'] = True
            session['id'] = admin_account[0][0]  # Fetch the correct user ID from the result
            session['password'] = password
            user_info = admin_account[0][1:]  # Store user info
            msg = 'Logged in successfully as Admin!'
            return render_template('admin_add_ons.html', msg=msg, user_info=user_info)  # Redirect to event creator page
        else:
            msg = 'Incorrect email / password !'

        return render_template('login.html', msg='Invalid email or password')

    return render_template('login.html', msg=msg, user_info= user_info)


@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('email', None)
    session.clear()
    return redirect(url_for('display_movies_by_client'))



@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        user_type = request.form.get('user_type')  # Get the user type selection
        interest = request.form.get('interest', '')  # Get the interest information

        # First, validate the inputs
        if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address !'
        elif not email or not password:
            msg = 'Please fill out the form !'
        else:
            try:
                # Check if email already exists in the database
                cursor = oracle_connection.cursor()
                cursor.execute("SELECT * FROM Users WHERE UEmail = :email", {'email': email})
                existing_user = cursor.fetchone()

                if existing_user:
                    msg = 'An account with this email already exists!'
                else:
                    # Proceed with registration if email is not already registered
                    cursor.execute(
                        'INSERT INTO USERS (USSN, UName, UEmail, UPhoneNum, UAddr, UPassword, UGender, UDoB)   VALUES (sequence_ussn.NEXTVAL, NULL, :1, NULL, NULL, :2, NULL, NULL)',
                        (email, password))
                    oracle_connection.commit()

                    # Fetch the user's newly inserted data
                    cursor.execute("SELECT * FROM Users WHERE UEmail = :email", {'email': email})
                    user_data = cursor.fetchone()
                    user_id = user_data[0]  # Get the user's ID

                    # Insert user data into appropriate table based on user type
                    if user_type == 'client':
                        cursor.execute('INSERT INTO Client (CID, CInterest) VALUES (:1, :2)', (user_id, interest))
                    elif user_type == 'event_creator':
                        cursor.execute('INSERT INTO EventCreator (ECID) VALUES (:1)', (user_id,))

                    oracle_connection.commit()

                    # Store user data in session for later use
                    session['loggedin'] = True
                    session['id'] = user_id
                    session['email'] = email
                    session['password'] = password


                    return redirect(url_for('index'))
            except Exception as e:
                msg = f"Error: {str(e)}"
                oracle_connection.rollback()  # Rollback the transaction in case of an error
                print(f"Error occurred: {str(e)}")

    elif request.method == 'POST':
        msg = 'Please fill out the form !'

    return render_template('register.html', msg=msg)

# Combined Route to display movies by CID (if provided) or all movies
@app.route('/movies', defaults={'cid': None})
@app.route('/movies/<cid>')
def display_movies_by_client(cid):
    today = datetime.now().date()
    upcoming_threshold = today + timedelta(days=30)
    if 'loggedin' in session and session['loggedin']:
        # If logged in, check if CID is in session or passed as parameter
        cid = session.get('id', cid)
    else:
        cid = None  # Ensure no user ID is used if not logged in

    cursor = oracle_connection.cursor()
    cursor.execute("SELECT * FROM Movie_Create")
    all_movies = cursor.fetchall()

    # Fetch movies specifically for the "Popular Movies" section, sorted by Mrating
    cursor.execute("SELECT * FROM Movie_Create WHERE Mrating IS NOT NULL ORDER BY Mrating DESC")
    popular_movies = cursor.fetchall()

    upcoming_movies = []
    currently_playing_movies = []

    for movie in all_movies:
        # Check if the date fields are already datetime objects
        if isinstance(movie[3], datetime):
            release_date = movie[3].date()
        else:
            release_date = datetime.strptime(movie[3], '%Y-%m-%d').date()  # Use this only if the date is a string

        if isinstance(movie[4], datetime):
            end_date = movie[4].date()
        else:
            end_date = datetime.strptime(movie[4], '%Y-%m-%d').date()  # Use this only if the date is a string

        if release_date > today:
            upcoming_movies.append(movie)
        elif today >= release_date and today <= end_date:
            currently_playing_movies.append(movie)

    recommended_movies = []
    if cid:
        # Assuming you have a logic to select recommendations based on user preferences
        cursor.execute("SELECT CInterest FROM Client WHERE CID = :cid", {'cid': cid})
        interest_row = cursor.fetchone()
        if interest_row:
            interest = interest_row[0]
            cursor.execute("SELECT * FROM Movie_Create WHERE Mgenre = :genre", {'genre': interest})
            recommended_movies = cursor.fetchall()

    cursor.close()

    all_movies_dict = [
        {"ECID": movie[0], "MID": movie[1], "Mproduction": movie[2], "MReleaseDate": movie[3],
         "MEndDate": movie[4], "MURL": movie[5], "Mname": movie[6], "AgeLimit": movie[7],
         "Mduration": movie[8], "Mdescription": movie[9], "Mrating": movie[10],
         "Mprice": movie[11], "Mgenre": movie[12], "Mlanguage": movie[13], "Mformat": movie[14]}
        for movie in all_movies
    ]
    recommended_movies_dict = [
        {"ECID": movie[0], "MID": movie[1], "Mproduction": movie[2], "MReleaseDate": movie[3],
         "MEndDate": movie[4], "MURL": movie[5], "Mname": movie[6], "AgeLimit": movie[7],
         "Mduration": movie[8], "Mdescription": movie[9], "Mrating": movie[10],
         "Mprice": movie[11], "Mgenre": movie[12], "Mlanguage": movie[13], "Mformat": movie[14]}
        for movie in recommended_movies
    ]

    upcoming_movies_dict = [
        {"ECID": movie[0], "MID": movie[1], "Mproduction": movie[2], "MReleaseDate": movie[3],
         "MEndDate": movie[4], "MURL": movie[5], "Mname": movie[6], "AgeLimit": movie[7],
         "Mduration": movie[8], "Mdescription": movie[9], "Mrating": movie[10],
         "Mprice": movie[11], "Mgenre": movie[12], "Mlanguage": movie[13], "Mformat": movie[14]}
        for movie in upcoming_movies
    ]


    currently_playing_movies_dict = [
        {"ECID": movie[0], "MID": movie[1], "Mproduction": movie[2], "MReleaseDate": movie[3],
         "MEndDate": movie[4], "MURL": movie[5], "Mname": movie[6], "AgeLimit": movie[7],
         "Mduration": movie[8], "Mdescription": movie[9], "Mrating": movie[10],
         "Mprice": movie[11], "Mgenre": movie[12], "Mlanguage": movie[13], "Mformat": movie[14]}
    for movie in currently_playing_movies
    ]

    popular_movies_dict = [
        {"ECID": movie[0], "MID": movie[1], "Mproduction": movie[2], "MReleaseDate": movie[3],
         "MEndDate": movie[4], "MURL": movie[5], "Mname": movie[6], "AgeLimit": movie[7],
         "Mduration": movie[8], "Mdescription": movie[9], "Mrating": movie[10],
         "Mprice": movie[11], "Mgenre": movie[12], "Mlanguage": movie[13], "Mformat": movie[14]}
    for movie in popular_movies
    ]

    return render_template('movies_home.html', movies=all_movies_dict, recommended_movies=recommended_movies_dict,
                           upcoming_movies=upcoming_movies_dict,popular_movies = popular_movies_dict, currently_playing_movies=currently_playing_movies_dict,
                           cid=cid)


@app.route('/movie/<mid>')
def movie_details(mid):
    cursor = oracle_connection.cursor()
    cursor.execute("SELECT * FROM Movie_Create WHERE MID = :mid", mid=mid)
    movie = cursor.fetchone()

    if not movie:
        return redirect(url_for('display_movies_by_client'))  # Redirect to general movie display

    user_rating = None

    # Get the average user rating for this movie from the Rate table
    cursor.execute("SELECT ROUND(AVG(UserRating), 0) FROM Rate WHERE MID = :mid", mid=mid)

    average_rating_result = cursor.fetchone()
    average_rating = average_rating_result[0] if average_rating_result[0] is not None else "No ratings yet"



    cursor.execute("SELECT Mrating FROM Movie_Create WHERE MID = :mid", mid=mid)
    movie_rating = cursor.fetchone()
    movie_rating = movie_rating[0] if movie_rating[0] is not None else "No ratings yet"

    if 'loggedin' in session:
        cursor.execute("SELECT UserRating FROM Rate WHERE CID = :cid AND MID = :mid",
                       {'cid': session['id'], 'mid': mid})
        rating_result = cursor.fetchone()
        user_rating = rating_result[0] if rating_result else 0  # If no rating, default to 0

    cursor.close()

    movie_details = {
        "ECID": movie[0], "MID": movie[1], "Production": movie[2], "ReleaseDate": movie[3],
        "EndDate": movie[4], "URL": movie[5], "Name": movie[6], "AgeLimit": movie[7],
        "Duration": movie[8], "Description": movie[9], "Rating": average_rating, "UserRating": movie_rating,
        "Price": movie[11], "Genre": movie[12], "Mlanguage": movie[13], "Mformat": movie[14], "TCODE": movie[15]
    }

    return render_template('movie_details.html', movie=movie_details,user_rating=user_rating)



@app.route('/rate_movie', methods=['POST'])
def rate_movie():
    # First, check if user is logged in and get the client ID from the session
    if 'loggedin' not in session or 'id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    # Now, you can safely use the client_id from the session because you know the user is logged in
    client_id = session['id']
    movie_id = request.json['mid']
    user_rating = int(request.json['rating'])

    cursor = oracle_connection.cursor()

    try:
        # Check if this user has already rated the movie
        cursor.execute("SELECT UserRating FROM Rate WHERE CID = :cid AND MID = :mid", {'cid': client_id, 'mid': movie_id})
        existing_rating = cursor.fetchone()

        if existing_rating:
            # Update existing rating
            cursor.execute("UPDATE Rate SET UserRating = :rating WHERE CID = :cid AND MID = :mid",
                           {'cid': client_id, 'mid': movie_id, 'rating': user_rating})
        else:
            # Insert new rating
            cursor.execute("INSERT INTO Rate (CID, MID, UserRating) VALUES (:cid, :mid, :rating)",
                           {'cid': client_id, 'mid': movie_id, 'rating': user_rating})

        oracle_connection.commit()

        # Recalculate the average rating
        cursor.execute("SELECT AVG(UserRating) FROM Rate WHERE MID = :mid", {'mid': movie_id})
        new_avg_result = cursor.fetchone()
        new_avg = round(new_avg_result[0], 2) if new_avg_result[0] is not None else None

        if new_avg is not None:
            # Update the average rating in the Movie_Create table
            cursor.execute("UPDATE Movie_Create SET Mrating = :avg WHERE MID = :mid",
                           {'avg': new_avg, 'mid': movie_id})
            oracle_connection.commit()

    except cx_Oracle.DatabaseError as e:
        # Rollback in case there is any error
        oracle_connection.rollback()
        error = str(e)
        return jsonify({'error': 'Database error occurred: ' + error}), 500
    finally:
        # Ensure the cursor is closed no matter what
        cursor.close()

    return jsonify({'success': 'Rating updated successfully', 'new_avg': new_avg}), 200


# Filter to format date in Jinja template --------------------------------------------------------------
def format_date(value):
    return value.strftime('%Y-%m-%d')


app.jinja_env.filters['format_date'] = format_date


# Create client page shows the client information and the tickets that the client has booked ---------------------------------------------------------------
@app.route('/client_page')
def client_page():
    if 'loggedin' in session and 'id' in session:
        client_id = session.get('id')
        if client_id:
            cursor = oracle_connection.cursor()
            try:
                # Directly retrieve the client's points from the database to ensure they are current
                cursor.execute("""
                    SELECT ClientPoints
                    FROM HaveClientHistory
                    WHERE CID = :client_id
                """, {'client_id': client_id})
                client_points_result = cursor.fetchone()
                client_points = client_points_result[0] if client_points_result else 0

                # Retrieve client's points and booked tickets information
                cursor.execute("""
                    SELECT HC.ClientPoints, TKI.TID, MC.Mname, C.CinemaName, MTS.TimeValue, TKI.MSeatNum, CT.TicketStatus
                    FROM HaveClientHistory HC
                    JOIN TicketKeptIn TKI ON HC.CID = TKI.CID
                    JOIN BeShownIn BSI ON TKI.MID = BSI.MID AND TKI.CinemaID = BSI.CinemaID AND TKI.TimeID = BSI.TimeID AND TKI.MSeatNum = BSI.MSeatNum
                    JOIN Cinema C ON BSI.CinemaID = C.CinemaID
                    JOIN MovieTimeShow MTS ON BSI.CinemaID = MTS.CinemaID AND BSI.TimeID = MTS.TimeID
                    JOIN Movie_Create MC ON BSI.MID = MC.MID
                    JOIN CreateTicket CT ON TKI.TID = CT.TID
                    WHERE HC.CID = :client_id
                """, {'client_id': client_id})

                booked_tickets = cursor.fetchall()
                cursor.close()

                # Initialize ticket_dict
                ticket_dict = {}

                # Aggregate seat numbers for each TID using a set to avoid duplicates
                for points, tid, mname, cinema_name, time_value, seat_num, ticket_status in booked_tickets:
                    if tid not in ticket_dict:
                        ticket_dict[tid] = {
                            'ClientPoints': points,
                            'TID': tid,
                            'Mname': mname,
                            'CinemaName': cinema_name,
                            'TimeValue': time_value,
                            'MSeatNum': set(),  # Initialize seat numbers as a set
                            'TicketStatus': ticket_status
                        }
                    ticket_dict[tid]['MSeatNum'].add(
                        seat_num)  # Add seat number to the set, automatically handling duplicates

                # Convert each set of seat numbers to a sorted, comma-separated string
                for ticket in ticket_dict.values():
                    ticket['MSeatNum'] = ', '.join(
                        sorted(ticket['MSeatNum'], key=lambda x: int(x)))  # Assuming seat numbers are sortable integers

                # print("Ticket dicts:", ticket_dict)
                # Retrieve user information
                user_info = session.get('user_info') or {}
                # client_points = session.get('client_points', 0)

                # Debugging print statements
                print("User info:", user_info)
                print("Client points:", client_points)
                # print("Booked tickets:", ticket_dict)

                return render_template('client_page.html', user_info=user_info, client_points=client_points,
                                       booked_tickets=list(ticket_dict.values()))
            except Exception as e:
                print("Error retrieving booking information:", e)
                return render_template('error_page.html'), 500
    else:
        return redirect(url_for('login'))


# Update user information ------------------------------------------------------------------------------------------------
@app.route('/update_user_info', methods=['POST'])
def update_user_info():
    if 'loggedin' in session and 'id' in session:
        client_id = session.get('id')
        if client_id:
            name = request.form.get('name')
            phone = request.form.get('phone')
            address = request.form.get('address')
            gender = request.form.get('gender')
            dob = request.form.get('dob')

            # Debugging: Print received data
            print("Received data:", name, phone, address, gender, dob, client_id)

            # Update user information in the USER table
            cursor = oracle_connection.cursor()
            try:
                cursor.execute("""
                    UPDATE USERS
                    SET UName = :name, UPhoneNum = :phone, UAddr = :address, UGender = :gender, UDoB = TO_DATE(:dob, 'YYYY-MM-DD')
                    WHERE USSN = :client_id
                """, {'name': name, 'phone': phone, 'address': address, 'gender': gender, 'dob': dob,
                      'client_id': client_id})
                oracle_connection.commit()
                cursor.close()

                # Redirect to client page after updating information
                return redirect(url_for('login'))

            except Exception as e:
                # Debugging: Print any exceptions that occur
                print("An error occurred:", e)
                oracle_connection.rollback()  # Rollback changes if an error occurs
                cursor.close()
                return "An error occurred while updating user information."

        else:
            return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))


# Add movie by event creator ------------------------------------------------------------------------------------------------
@app.route('/event_creator_page', methods=['GET', 'POST'])
def event_creator_page():
    if request.method == 'POST':
        # Process form submission
        # Retrieve user id from session
        ecid = session.get('id')
        print("ECID:", ecid)
        if ecid:
            # Retrieve form data
            event_name = request.form['Moviename']
            event_description = request.form['Moviedescp']
            event_price = request.form['mprice']
            event_production = request.form['Mproduction']
            event_release = request.form['releasedate']
            event_end = request.form['enddate']
            event_agelimit = request.form['magelimit']
            event_duration = request.form['mduration']
            event_rating = request.form['mrating']
            event_genre = request.form['moviegenre']
            event_MURL = request.form['MURL']
            event_TCODE = request.form['TCODE']
            event_language = request.form['mlanguage']
            event_format = request.form['mformat']
            event_release = datetime.strptime(event_release, '%Y-%m-%d').date() if event_release else None
            event_end = datetime.strptime(event_end, '%Y-%m-%d').date() if event_end else None

            # Insert data into the database
            cursor = oracle_connection.cursor()

            # Insert into Movie_Create table
            query1 = """
                INSERT INTO Movie_Create (
                ECID,
                MID,
                Mproduction,
                MReleaseDate,
                MEndDate,
                MURL,
                TCODE,
                Mname,
                AgeLimit,
                Mduration,
                Mdescription,
                Mrating,
                Mprice,
                Mgenre,
                Mlanguage,
                Mformat
                ) VALUES (
                :ecid,
                sequence_movie.NEXTVAL,
                :event_production,
                :event_release,
                :event_end,
                :event_MURL,
                :event_TCODE,
                :event_name,
                :event_agelimit,
                :event_duration,
                :event_description,
                :event_rating,
                :event_price,
                :event_genre,
                :event_language,
                :event_format
                )"""
            params = {
                'ecid': ecid,
                'event_production': event_production,
                'event_release': event_release,
                'event_end': event_end,
                'event_name': event_name,
                'event_agelimit': event_agelimit,
                'event_duration': event_duration,
                'event_description': event_description,
                'event_rating': event_rating,
                'event_price': event_price,
                'event_genre': event_genre,
                'event_MURL': event_MURL,
                'event_TCODE': event_TCODE,
                'event_language': event_language,
                'event_format': event_format
            }
            cursor.execute(query1, params)

            # Get the MID of the inserted movie
            cursor.execute("SELECT sequence_movie.CURRVAL FROM dual")
            movie_id = cursor.fetchone()[0]

            # Insert into Movie_AreIn table
            query2 = """
                INSERT INTO Movie_AreIn (ECID, MID, CreatedMovies, MRating)
                VALUES (:ecid, :movie_id, :event_name, :event_rating)
            """
            params2 = {
                'ecid': ecid,
                'movie_id': movie_id,
                'event_name': event_name,
                'event_rating': event_rating
            }
            print("params2:", params2)
            cursor.execute(query2, params2)

            # Insert or update HaveECHistory table
            query3 = """
                INSERT INTO HaveECHistory (ECID, MID, ECRating)
                VALUES (:ecid, :movie_id, :event_rating)
            """
            params3 = {'ecid': ecid, 'movie_id': str(movie_id), 'event_rating': event_rating}
            cursor.execute(query3, params3)

            oracle_connection.commit()
            cursor.close()

            return redirect(url_for('success'))
        else:
            return "User ID not found in session!"

    elif request.method == 'GET':
        # Render the form for GET requests
        return render_template('event_creator_page.html')


# Next page after adding movie ------------------------------------------------------------------------------------------------
@app.route('/success')
def success():
    success_message = "Movie added successfully!"  # Add your success message here
    return render_template('success.html', success_message=success_message)


# View movie history and user information for event creator ------------------------------------------------------------------------------------------------
@app.route('/event_creator_his')
def event_creator_his():
    ecid = session.get('id')
    user_info = session.get('user_info')
    if ecid:
        cursor = oracle_connection.cursor()

        # Retrieve movie history for the event creator
        cursor.execute("""
            SELECT Movie_AreIn.MID, Movie_Create.Mname, Movie_AreIn.MRating
            FROM Movie_AreIn
            JOIN Movie_Create ON Movie_AreIn.MID = Movie_Create.MID
            WHERE Movie_AreIn.ECID = :ecid
        """, {'ecid': ecid})

        movie_history = cursor.fetchall()
        cursor.close()

        # Pass movie history data to the template
        return render_template('event_creator_history.html', movie_history=movie_history, user_info=user_info)
    else:
        return "User ID not found in session!"


#  Complete user information for client and event creator ------------------------------------------------------------------------------------------------
@app.route('/complete_info', methods=['POST'])
def complete_info():
    if 'loggedin' in session:
        user_id = session['id']
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        gender = request.form.get('gender')
        dob = request.form.get('dob')
        usertype = request.form.get('user_type')
        userinterst = request.form.get('interest')
        cursor = oracle_connection.cursor()
        cursor.execute(
            "UPDATE Users SET UName = :name, UPhoneNum = :phone, UAddr = :address, UGender = :gender, UDoB = TO_DATE(:dob, 'YYYY-MM-DD') WHERE USSN = :user_id",
            {'name': name, 'phone': phone, 'address': address, 'gender': gender, 'dob': dob, 'user_id': user_id})
        oracle_connection.commit()

        if usertype == 'client':
            cursor.execute("INSERT INTO Client (CID, CInterest) VALUES (:user_id, :interest)",
                           {'user_id': user_id, 'interest': userinterst})
            oracle_connection.commit()
        elif usertype == 'event_creator':
            cursor.execute("INSERT INTO EventCreator (ECID) VALUES (:user_id)", {'user_id': user_id})
            oracle_connection.commit()

        # Redirect to the login page after updating user info
        return redirect(url_for('login'))
    else:
        # Redirect to login page if user is not logged in
        return redirect(url_for('login'))


# View index page after logging for client ------------------------------------------------------------------------------------------------
@app.route('/index')
def index():
    if 'loggedin' in session:
        return render_template('index.html', session=session)
    else:
        return redirect(url_for('login'))

'''
# Logout from the session ------------------------------------------------------------------------------------------------
@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('email', None)
    return redirect(url_for('login'))
'''

# Fron page ------------------------------------------------------------------------------------------------
# @app.route('/front_page')
# def front_page():
#     return render_template('front_page.html')


# if signed in as ADMIN goes to a page where admin can add data----------------------------------------------------------------------------
@app.route('/Admin_add_ons')
def add_on():
    return render_template("admin_add_ons.html")


# This creates cinema - done by admin -----------------------------------------------------------------------------------------------------

@app.route('/cinema_create', methods=['GET', 'POST'])
def add_cinema():
    if request.method == 'POST':
        # Retrieve form data
        cinema_name = request.form['Cinemaname']
        cinema_address = request.form['cinemaadd']
        cinema_capacity = request.form['cinemacap']

        # Check if cinema name exists
        cursor = oracle_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM Cinema WHERE CINEMANAME = :cname", {'cname': cinema_name})
        count = cursor.fetchone()[0]

        if count > 0:
            # Cinema name already exists, return a message or redirect to prevent duplicate insertion
            return redirect(url_for('cinemadetails'))

        # Insert data into the database
        query2 = """
            INSERT INTO Cinema (CINEMAID,CINEMAADDR, CINEMACAPACITY, CINEMANAME) 
            VALUES (sequence_cinema.NEXTVAL,:cinemaadd, :cinemacap, :Cinemaname)
        """
        params2 = {
            'cinemaadd': cinema_address,
            'cinemacap': cinema_capacity,
            'Cinemaname': cinema_name
        }

        cursor.execute(query2, params2)
        oracle_connection.commit()

        # Close the cursor
        cursor.close()

        flash('New cinema added successfully!', 'success')
        return redirect(url_for('cinema_create'))

    # This section handles GET request to show the form and existing cinemas
    cursor = oracle_connection.cursor()
    cursor.execute("SELECT CINEMAID, CINEMANAME, CINEMAADDR, CINEMACAPACITY FROM Cinema")
    cinemas = cursor.fetchall()
    cursor.close()

    return render_template('cinema_create.html', cinemas=cinemas)


# Define route to render the admin page -
@app.route('/cinema_create')
def cinema_create():
    return render_template('cinema_create.html')


# This add cinema details - Add timimgs to cinema and seat numbers to the database------------------------------------------------------------

@app.route('/cinema_details', methods=['POST'])
def cinemadetails():
    if request.method == 'POST':
        cinema_name = request.form['Cinemaname']
        dates = request.form.getlist('dates[]')  # List of dates
        times = request.form.getlist('times[]')  # List of times

        # search for cinema ID with cinema name
        cursor = oracle_connection.cursor()
        cursor.execute("SELECT CINEMAID, CINEMACAPACITY from Cinema WHERE CINEMANAME = :cname", {'cname': cinema_name})
        result = cursor.fetchone()
        cinema_id, cinema_capacity = result if result else (None, None)
        oracle_connection.commit()
        print("dates:", dates)
        print("times:", times)
        for date, time in zip(dates, times):
            date_id = f'date_{cinema_id}_{date}'
            time_id = f'time_{cinema_id}_{time}'

            # Insert date and time into MovieTimeShow
            query_cd = """
                INSERT INTO MovieTimeShow (TimeID, CinemaID, TimeValue, DateID, DateValue) 
                VALUES (:timeid, :cinemaid, TO_TIMESTAMP(:timevalue, 'YYYY-MM-DD HH24:MI'), :dateid, TO_DATE(:datevalue, 'YYYY-MM-DD'))
            """
            params_cd = {
                'timeid': time_id,
                'cinemaid': cinema_id,
                'timevalue': f"{date} {time}",
                'dateid': date_id,
                'datevalue': date
            }
            cursor.execute(query_cd, params_cd)
            oracle_connection.commit()

            query_s = """
                INSERT INTO HAVE_MOVIESEAT (CINEMAID,TimeID, MSEATNUM, MSEATSTATUS, DateID) 
                VALUES ( :cinemaid, :timeid,:sn ,'empty', :dateid)
            """
            for seat_num in range(1, int(cinema_capacity) + 1):
                params_s = {
                    'cinemaid': cinema_id,
                    'timeid': time_id,
                    'sn': str(seat_num),
                    'dateid': date_id
                }
                cursor.execute(query_s, params_s)
                oracle_connection.commit()
        cursor.close()

        return redirect(url_for('cinema_details'))


@app.route('/cinema_details')
def cinema_details():
    cinema_name = request.args.get('cinema_name', '')  # Get the cinema name from the URL parameter
    cursor = oracle_connection.cursor()

    # Fetch cinema capacity
    cursor.execute("SELECT CINEMACAPACITY FROM Cinema WHERE CINEMANAME = :cname", {'cname': cinema_name})
    result = cursor.fetchone()
    cinema_capacity = result[0] if result else None
    cursor.close()

    # Pass cinema capacity to the template
    return render_template('cinema_details.html', cinema_name=cinema_name, cinema_capacity=cinema_capacity)



# For adding cinema to a particular movie --------------------------------------------------------------

@app.route('/add_movie_to_cinema', methods=['GET', 'POST'])
def add_movietocinema():
    cursor = oracle_connection.cursor()
    ecid = session.get('id')
    if ecid is None:
        return "Session ID not found", 400

    if request.method == 'POST':
        movie_name = request.form['movie']
        cinema_name = request.form['cinema']
        timing = request.form['timing']
        date_id = request.form['date']

        print(f"Adding movie '{movie_name}' to cinema '{cinema_name}' at timing {timing} on date ID {date_id}")

        try:
            cinema_id = cursor.execute("SELECT CinemaID FROM Cinema WHERE CinemaName = :name",
                                       {'name': cinema_name}).fetchone()
            if cinema_id is None:
                return "Cinema not found", 404
            cinema_id = cinema_id[0]

                    # timing is combination of cinema_id and timing
            timing_id = "time"+"_"+cinema_id+"_"+timing

            movie_id = cursor.execute("SELECT MID,MReleaseDate,MEndDate FROM Movie_Create WHERE Mname = :name",
                                      {'name': movie_name}).fetchone()
            if movie_id is None:
                return "Movie not found", 404
            movie_id = movie_id[0]

            print(f"Fetching seats for Cinema ID: {cinema_id}, Time ID: {timing_id}, Date ID: {date_id}")
            mseats = cursor.execute("""
                SELECT MSEATNUM FROM Have_MovieSeat 
                WHERE CinemaID = :cinema_id AND TimeID = :timing_id AND DateID = :date_id
            """, {'cinema_id': cinema_id, 'timing_id': timing_id, 'date_id': date_id}).fetchall()

            if not mseats:
                return "No seats found for this timing", 404

            movie_release_date = movie_id[1]
            movie_end_date = movie_id[2]

            for mseat in mseats:
                cursor.execute("""
                    INSERT INTO BeShownIn (MID, ECID, CinemaID, TimeID, MSeatNum, M_FROM, M_TO, DateID)
                    VALUES (:movie_id, :ecid, :cinema_id, :timing_id, :mseatnum, :movie_release_date, :movie_end_date, :date_id)
                """, {'movie_id': movie_id, 'ecid': ecid, 'cinema_id': cinema_id,'movie_release_date':movie_release_date,'movie_end_date' :movie_end_date,'timing_id': timing_id,
                      'mseatnum': mseat[0], 'date_id': date_id})

            oracle_connection.commit()
            return redirect(url_for('success'))
        except Exception as e:
            oracle_connection.rollback()
            print("Failed to insert data:", e)
            return str(e), 500
        finally:
            cursor.close()

    else:
        movie_names = cursor.execute("SELECT Mname FROM Movie_Create").fetchall()
        cinema_names = cursor.execute("SELECT CinemaName FROM Cinema").fetchall()
        return render_template('add_movie_to_cinema.html', movie_names=movie_names, cinema_names=cinema_names)


# @app.route('/success')
# def success():
#     return 'Movie successfully added to cinema!'



@app.route('/fetch_timings')
def fetch_timings():
    cinema_name = request.args.get('cinema_name')
    cursor = oracle_connection.cursor()

    # Since the request may just include the cinema name and you want all timings related to it:
    try:
        # Fetching CinemaID from Cinema table
        cinema_id = cursor.execute("""
            SELECT CinemaID FROM Cinema WHERE CinemaName = :name
        """, {'name': cinema_name}).fetchone()

        # If cinema is not found, return an appropriate response
        if not cinema_id:
            return jsonify({'error': 'Cinema not found'}), 404
        
        cinema_id = cinema_id[0]

        timings = cursor.execute("""
            SELECT TimeID, TO_CHAR(TimeValue, 'HH24:MI') AS TimeLabel, DateID, TO_CHAR(DateValue, 'YYYY-MM-DD') AS DateLabel
            FROM MovieTimeShow
            WHERE CinemaID = (SELECT CinemaID FROM Cinema WHERE CinemaName = :name)
            ORDER BY TimeValue
        """, {'name': cinema_name}).fetchall()

        # Return a JSON response containing the timings
        return jsonify({
            'timings': [{
                'TimeID': timing[0],
                'time_label': timing[1],
                'date_id': timing[2],
                'date_label': timing[3]
            } for timing in timings]
        })

    except Exception as e:
        print("Database error:", str(e))
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


# Define route to render the admin page
@app.route('/add_movie_to_cinema')
def add_movie_to_cinema():
    return render_template('add_movie_to_cinema.html')


# Show the Date, cinema and times that the movie is shown ------------------------------------------------------------------------------------------------
@app.route('/locselection/<mid>')  # Use the correct URL with movie ID as a variable part of the URL
def movie_showtimes(mid):
    selected_date = request.args.get('date')
    cursor = oracle_connection.cursor()
    print("Selected date:", selected_date)
    # Fetch all available dates for the movie to allow user selection
    cursor.execute("""
        SELECT DISTINCT DateID
        FROM BeShownIn
        WHERE MID = :mid
        ORDER BY DateID
    """, {'mid': mid})
    available_dates = cursor.fetchall()

    cinemas = {}
    if selected_date:
        # Fetch cinemas and times for the selected movie and date
        cursor.execute("""
            SELECT C.CinemaName, B.TimeID
            FROM BeShownIn B
            JOIN Cinema C ON B.CinemaID = C.CinemaID
            WHERE B.MID = :mid AND B.DateID = :date_id
            GROUP BY C.CinemaName, B.TimeID
            ORDER BY C.CinemaName, B.TimeID
        """, {'mid': mid, 'date_id': selected_date})
        results = cursor.fetchall()
        # print("Results:", results)
        # Organize data by cinema with a list of times
        for cinema_name, time_id in results:
            if cinema_name not in cinemas:
                cinemas[cinema_name] = []
            cinemas[cinema_name].append(time_id)

    cursor.close()
    return render_template('locselection.html', available_dates=available_dates, cinemas=cinemas,
                           selected_date=selected_date, mid=mid)


@app.route('/')
def index2():
    return "Welcome to Movie Showtimes!"


@app.route('/seats', methods=['GET', 'POST'])
def bkseats():
    cid = session.get('id')

    if request.method == 'POST':
        if request.is_json:
            data = request.json
            selected_seats = data.get('selectedSeats')
            total_price = data.get('totalPrice')

            print(data)
            # print("Selected Seats:", selected_seats)
            # print("Total Price:", total_price)

            selected_seats = data.get('selectedSeats')
            total_price = data.get('totalPrice')
            cinema_id = data.get('cinema_id')
            time_id = data.get('time_id')
            date_id = data.get('date_id')
            mid = data.get('mid')

            # print("Received data:", data)
            cursor = oracle_connection.cursor()
            cursor.execute("SELECT MPrice FROM Movie_Create WHERE MID = :mid", {'mid': mid})
            movie_price = cursor.fetchone()
            # print("Movie price:", movie_price)
            # Insert selected seats into the database
            cursor = oracle_connection.cursor()
            try:
                # Assuming 'selected_seats' is a list of seat numbers
                for seat_num in selected_seats:
                    cursor.execute("""
                    INSERT INTO SelectedItems (CID, MID, MSeatNum, CinemaID, TimeID, DateID)
                    VALUES (:cid, :mid, :mseatnum, :cinema_id, :time_id, :date_id)
                    """, {
                        'cid': cid,
                        'mid': mid,
                        'mseatnum': seat_num,
                        'cinema_id': cinema_id,
                        'time_id': time_id,
                        'date_id': date_id
                    })
                oracle_connection.commit()
            except Exception as e:
                oracle_connection.rollback()  # Rollback in case of any error
                print(f"Database Error: {e}")
            finally:
                cursor.close()

            return redirect(url_for('payment'))  # Redirect to the payment page after successful insertion

        else:
            # Handle the error for non-JSON request
            return jsonify({'error': 'Invalid request, JSON expected'}), 400

    else:
        # Retrieve parameters from GET request
        cinema_name = request.args.get('cinema_id')
        time_id = request.args.get('time_id')
        date_id = request.args.get('date_id')
        mid = request.args.get('mid')  # Default ID for testing

        #print(f"cinema_name received: {cinema_name}")
        #print(f"time_id received: {time_id}")
        #print(f"date_id received: {date_id}")
        #print(f"movie_id received: {mid}")

        cursor = oracle_connection.cursor()

        # Fetch cinema ID based on the cinema name
        cursor.execute("SELECT CinemaID FROM Cinema WHERE CinemaName = :cinema_name", {'cinema_name': cinema_name})
        cinema_id = cursor.fetchone()[0]
        #print(f"cinema_id received: {cinema_id}")
        # Fetch seating info from the database
        query = """
        SELECT MC.MName, MC.MPrice, HMS.MSeatNum, HMS.MSeatStatus
        FROM BeShownIn BSI
        JOIN Movie_Create MC ON BSI.MID = MC.MID
        JOIN Have_MovieSeat HMS ON BSI.CinemaID = HMS.CinemaID AND BSI.TimeID = HMS.TimeID AND BSI.DateID = HMS.DateID AND BSI.MSeatNum = HMS.MSeatNum
        WHERE BSI.CinemaID = :cinema_id AND BSI.TimeID = :time_id AND BSI.DateID = :date_id AND BSI.MID = :mid
        ORDER BY TO_NUMBER(HMS.MSeatNum)
        """
        cursor.execute(query, {'cinema_id': cinema_id, 'time_id': time_id, 'date_id': date_id, 'mid': mid})
        movie_info = cursor.fetchall()
        cursor.close()
        #print("movie info", movie_info)

        return render_template('seats.html', movie_info=movie_info, cinema_id=cinema_id, time_id=time_id,
                               date_id=date_id, mid=mid)


##Payment ------------------------------------------------------------------------------------------------------------
def generate_transaction_num(length=10):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def generate_ticket_id(length=10):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


@app.route('/payment', methods=['GET'])
def payment():
    user_id = session.get('id')
    
    if not user_id:
        flash("User ID not found in session.", "error")
        return redirect(url_for('login'))  # Redirect to login or appropriate route
    
    cursor = oracle_connection.cursor()

    # Check if the selected items need to be fetched again
    if 'recalculate_price' not in session or session['recalculate_price']:
        cursor.execute("""
            SELECT SI.CID, SI.MID, MC.MName, LISTAGG(SI.MSeatNum, ', ') WITHIN GROUP (ORDER BY SI.MSeatNum) AS SeatNumbers, 
            C.CinemaName, TS.TimeID, TS.TimeValue, MC.MPrice, TS.DateID
            FROM SelectedItems SI
            JOIN BeShownIn BSI ON SI.MID = BSI.MID AND SI.CinemaID = BSI.CinemaID AND SI.TimeID = BSI.TimeID AND SI.DateID = BSI.DateID AND SI.MSeatNum = BSI.MSeatNum 
            JOIN Movie_Create MC ON SI.MID = MC.MID
            JOIN Cinema C ON SI.CinemaID = C.CinemaID
            JOIN MovieTimeShow TS ON SI.TimeID = TS.TimeID AND SI.CinemaID = TS.CinemaID AND SI.DateID = TS.DateID
            WHERE SI.CID = :user_id AND SI.IsActive = 'Y'
            GROUP BY SI.CID, SI.MID, MC.MName, C.CinemaName, TS.TimeID, TS.TimeValue, MC.MPrice, TS.DateID
        """, {'user_id': user_id})
        selected_items = cursor.fetchall()
        session['selected_items'] = selected_items  # Store selected items in session

        # Recalculate the total price
        total_price = sum(float(item[7]) * count_seat_numbers(item[3]) for item in selected_items)
        session['total_price'] = total_price
        session['recalculate_price'] = False
    else:
        # Use the stored values from session
        selected_items = session.get('selected_items', [])
        total_price = session.get('total_price', 0)

    # Fetching client points afresh to ensure the latest value is used
    cursor.execute("SELECT ClientPoints FROM HaveClientHistory WHERE CID = :user_id", {'user_id': user_id})
    client_points_result = cursor.fetchone()
    client_points = client_points_result[0] if client_points_result else 0
    session['client_points'] = client_points

    cursor.close()

    return render_template('payment.html', selected_items=selected_items, total_price=total_price, client_points=client_points)


def count_seat_numbers(seat_numbers):
    # Splits the seat numbers string into a list and returns its length
    return len(seat_numbers.split(', '))



@app.route('/process_payment', methods=['POST'])
def process_payment():
    # Retrieve payment information from the form
    card_name = request.form.get('cardname')
    card_number = request.form.get('cardnumber')
    exp_month = request.form.get('expmonth')
    exp_year = request.form.get('expyear')
    cvv = request.form.get('cvv')

    cursor = oracle_connection.cursor()
    user_id = session.get('id')
    cursor.execute("""
        SELECT SI.CID, SI.MID, MC.MName, LISTAGG(SI.MSeatNum, ', ') WITHIN GROUP (ORDER BY SI.MSeatNum) AS SeatNumbers, 
        C.CinemaName, TS.TimeID, TS.TimeValue, MC.MPrice, TS.DateID, SI.CinemaID
        FROM SelectedItems SI
        JOIN BeShownIn BSI ON SI.MID = BSI.MID AND SI.CinemaID = BSI.CinemaID AND SI.TimeID = BSI.TimeID AND SI.DateID = BSI.DateID AND SI.MSeatNum = BSI.MSeatNum 
        JOIN Movie_Create MC ON SI.MID = MC.MID
        JOIN Cinema C ON SI.CinemaID = C.CinemaID
        JOIN MovieTimeShow TS ON SI.TimeID = TS.TimeID AND SI.CinemaID = TS.CinemaID AND SI.DateID = TS.DateID
        WHERE SI.CID = :user_id AND SI.IsActive = 'Y'
        GROUP BY SI.CID, SI.MID, MC.MName, C.CinemaName, TS.TimeID, TS.TimeValue, MC.MPrice, TS.DateID, SI.CinemaID
    """, {'user_id': user_id})
    selected_movies = cursor.fetchall()
    cursor.close()
    # print(selected_movies)
    # Here you would typically perform validation and perhaps interact with a payment gateway
    # For this example, let's assume the payment is successful

    # Generate a unique transaction number
    transaction_num = generate_transaction_num()

    # Save payment information to the session
    user_id = session.get('id')
    movie_time = selected_movies[0][6].strftime("%H:%M:%S")  # Convert datetime to string
    # Split the string by underscores and take the last part for the date
    movie_date_parts = selected_movies[0][8].split('_')
    movie_date = movie_date_parts[-1]  # This will be '2024-05-01'

    session['payment_info'] = {
        'cid': user_id,  # Include the 'cid' key with the user ID
        'pay_card_name': card_name,
        'pay_card_number': card_number,
        'pay_exp_month': exp_month,
        'pay_exp_year': exp_year,
        'cvv': cvv,
        'transaction_num': transaction_num,
        'movie_name': selected_movies[0][2],
        'movie_cinema': selected_movies[0][4],
        'movie_time': movie_time,
        'movie_seat': selected_movies[0][3],
        'id_movie': selected_movies[0][1],
        'id_cinema': selected_movies[0][9],
        'id_time': selected_movies[0][5],
        'id_date': selected_movies[0][8],
        'movie_date': movie_date,
        # 'total_price': selected_movies[0][8]
    }
    # Retrieve total price from session
    total_price = session.get('total_price')
    seats = selected_movies[0][3].split(', ')
    cursor = oracle_connection.cursor()
    try:
        for seat_num in seats:
            cursor.execute("""
            INSERT INTO GoFor_Transaction (TransactionNum, CID, MID, MSeatNum, CinemaID, TimeID, PaymentDate_Time, TransactionStatus, DateID)
            VALUES (:transaction_num, :user_id, :movie_id, :seat_num, :cinema_id, :time_id, :payment_date_time, :transaction_status, :date_id)
            """, {'transaction_num': transaction_num, 'user_id': user_id, 'movie_id': selected_movies[0][1],
                  'seat_num': seat_num,
                  'cinema_id': selected_movies[0][9], 'time_id': selected_movies[0][5],
                  'payment_date_time': datetime.now(), 'transaction_status': 'NO', 'date_id': selected_movies[0][8]})
            oracle_connection.commit()
    except Exception as e:
        flash('An error occurred while processing payment. Please try again later.', 'error')
        print("Error processing payment:", e)
        oracle_connection.rollback()
        cursor.close()
        return redirect(url_for('payment'))

    cursor.close()

    # Redirect to the confirmation page
    return redirect(url_for('confirm_transaction'))


@app.route('/confirm_transaction', methods=['GET', 'POST'])
def confirm_transaction():
    # Retrieve payment information from the session
    payment_info = session.get('payment_info')
    # print("Payment info in confirmation:", payment_info)
    if not payment_info:
        flash('Payment information not found. Please complete the payment first.', 'error')
        return redirect(url_for('payment'))

    if request.method == 'GET':
        # Retrieve selected movie information
        selected_items = []
        for key, value in payment_info.items():
            if key.startswith('movie_'):
                movie_info = value.split('_')
                selected_items.append(movie_info)

        # Retrieve total price from session
        total_price = session.get('total_price')
        return render_template('confirm_transaction.html', payment_info=payment_info, selected_items=selected_items,
                               total_price=total_price)

    elif request.method == 'POST':
        # Update the transaction status to 'YES' in the database
        transaction_num = payment_info['transaction_num']
        print("Transaction number:", transaction_num)
        print("Payment info:", payment_info)
        seats = payment_info['movie_seat'].split(', ')
        cursor = oracle_connection.cursor()
        try:
            for seat_num in seats:
                cursor.execute("""
                UPDATE GoFor_Transaction
                SET TransactionStatus = 'YES'
                WHERE TransactionNum = :transaction_num AND MSeatNum = :seat_num
                """, {'transaction_num': transaction_num, 'seat_num': seat_num})
                oracle_connection.commit()
        except Exception as e:
            flash('An error occurred while updating transaction status. Please try again later.', 'error')
            print("Error updating transaction status:", e)
            oracle_connection.rollback()
            return redirect(url_for('confirm_transaction'))
        finally:
            cursor.close()

        # Insert data into TransactionConfirm table
        user_id = payment_info['cid']
        movie_id = payment_info['id_movie']
        cinema_id = payment_info['id_cinema']
        time_id = payment_info['id_time']
        date_id = payment_info['id_date']
        seats = payment_info['movie_seat'].split(', ')

        print("user_id, movie_id, cinema_id, time_id, seat_num, date_id", user_id, movie_id, cinema_id, time_id, seats,
              date_id)
        try:
            cursor = oracle_connection.cursor()
            for seat_num in seats:
                cursor.execute("""
                    INSERT INTO TransactionConfirm (CID, TransactionNum, MID, MSeatNum, CinemaID, TimeID, DateID)
                    VALUES (:user_id, :transaction_num, :movie_id, :seat_num, :cinema_id, :time_id, :date_id)
                """, {
                    'user_id': user_id,
                    'transaction_num': transaction_num,
                    'movie_id': movie_id,
                    'seat_num': seat_num,
                    'cinema_id': cinema_id,
                    'time_id': time_id,
                    'date_id': date_id
                })
            oracle_connection.commit()
        except Exception as e:
            flash('An error occurred while confirming transaction. Please try again later.', 'error')
            print("Error confirming transaction:", e)
            oracle_connection.rollback()
            cursor.close()
            return redirect(url_for('confirm_transaction'))

        # Insert data into CreateTicket table
        ticket_id = generate_ticket_id()  # Generate a unique ticket ID
        try:
            cursor = oracle_connection.cursor()
            for seat_num in seats:  # Assuming seats is a list of seat numbers
                cursor.execute("""
                    INSERT INTO CreateTicket (TID, CID, MID, MSeatNum, CinemaID, TimeID, TransactionNum, TicketStatus, DateID)
                    VALUES (:ticket_id, :user_id, :movie_id, :seat_num, :cinema_id, :time_id, :transaction_num, 'Booked', :date_id)
                """, {
                    'ticket_id': ticket_id,  # Ensure this is unique for each ticket
                    'user_id': user_id,
                    'movie_id': movie_id,
                    'seat_num': seat_num,  # This now refers to a single seat number
                    'cinema_id': cinema_id,
                    'time_id': time_id,
                    'transaction_num': transaction_num,
                    'date_id': date_id
                })
            oracle_connection.commit()
        except Exception as e:
            flash('An error occurred while creating the ticket. Please try again later.', 'error')
            print("Error creating ticket:", e)
            oracle_connection.rollback()
            cursor.close()
            return redirect(url_for('confirm_transaction'))

        # Update the seat status to 'not available' in the Have_MovieSeat table
        try:
            for seat_num in seats:
                cursor.execute("""
                    UPDATE Have_MovieSeat
                    SET MSeatStatus = 'Occupied'
                    WHERE CinemaID = :cinema_id AND TimeID = :time_id AND DateID = :date_id AND MSeatNum = :seat_num
                """, {'cinema_id': cinema_id, 'time_id': time_id, 'date_id': date_id, 'seat_num': seat_num})
            oracle_connection.commit()
        except Exception as e:
            flash('An error occurred while updating seat status. Please try again later.', 'error')
            print("Error updating seat status:", e)
            oracle_connection.rollback()
            cursor.close()
            return redirect(url_for('confirm_transaction'))

            # Insert data into TicketKeptIn table
        try:
            for seat_num in seats:
                print("Seat number:", seat_num)
                cursor.execute("""
                    INSERT INTO TicketKeptIn (CID, TID, MID, MSeatNum, CinemaID, TimeID, TransactionNum, DateID)
                    VALUES (:user_id, :ticket_id, :movie_id, :seat_num, :cinema_id, :time_id, :transaction_num, :date_id)
                    """, {'user_id': user_id, 'ticket_id': ticket_id, 'movie_id': movie_id, 'seat_num': seat_num,
                          'cinema_id': cinema_id, 'time_id': time_id, 'transaction_num': transaction_num,
                          'date_id': date_id})
                oracle_connection.commit()
        except Exception as e:
            flash('An error occurred while inserting into TicketKeptIn. Please try again later.', 'error')
            print("Error inserting into TicketKeptIn:", e)
            oracle_connection.rollback()
            cursor.close()
            return redirect(url_for('confirm_transaction'))

        cursor.close()

        # Delete data from selected items
        cursor = oracle_connection.cursor()
        try:
            # Update the status of selected items to inactive instead of deleting them
            cursor.execute("UPDATE SelectedItems SET IsActive = 'N' WHERE CID = :user_id", {'user_id': user_id})
            oracle_connection.commit()
        except Exception as e:
            flash('An error occurred while updating selected items. Please try again later.', 'error')
            print("Error updating selected items:", e)
            oracle_connection.rollback()
        finally:
            cursor.close()
            # Redirect to the ticket page
            return redirect(url_for('show_ticket', ticket_id=ticket_id))

     


@app.route('/show_ticket/<ticket_id>', methods=['GET'])
def show_ticket(ticket_id):
    # Retrieve payment information from the session
    payment_info = session.get('payment_info')

    if not payment_info:
        flash('Payment information not found. Please complete the payment first.', 'error')
        return redirect(url_for('payment'))

    # Extract relevant information from payment_info
    ticket_info = {
        'TID': ticket_id,
        'user': payment_info['cid'],
        'Movie': payment_info['movie_name'],
        'MSeatNum': payment_info['movie_seat'],
        'Cinema': payment_info['movie_cinema'],
        'Time': payment_info['movie_time'],
        'TransactionNum': payment_info['transaction_num'],
        'Date': payment_info['movie_date'],
        # 'TotalPrice': payment_info['total_price'],
        'TicketStatus': 'Booked'  # Assuming ticket status is always 'Booked' for confirmed transactions
    }

    TotalPrice = session.get('total_price')
    # Update client history and get all ticket IDs associated with the client
    update_client_history(ticket_info['user'], ticket_info['TID'])
    
    # Reset total price and recalculate flag after ticket confirmation
    session.pop('total_price', None)
    session['recalculate_price'] = True

    return render_template('ticket.html', ticket_info=ticket_info, TotalPrice=TotalPrice)


@app.route('/redeem_points', methods=['POST'])
def redeem_points():
    user_id = session.get('payment_info', {}).get('cid')
    total_price = session.get('total_price')
    client_points = session.get('client_points')

    if not user_id or total_price is None or client_points is None:
        flash('Failed to redeem points. Please try again later.', 'error')
        return redirect(url_for('payment'))

    redeem_amount = min(client_points / 100, total_price)
    new_total_price = total_price - redeem_amount

    cursor = oracle_connection.cursor()
    try:
        cursor.execute("""
            UPDATE HaveClientHistory
            SET ClientPoints = ClientPoints - :used_points
            WHERE CID = :user_id
        """, {'used_points': redeem_amount * 100, 'user_id': user_id})
        oracle_connection.commit()
    except Exception as e:
        flash('An error occurred while redeeming points. Please try again later.', 'error')
        oracle_connection.rollback()
        cursor.close()
        return redirect(url_for('payment'))

    session['total_price'] = new_total_price
    session['client_points'] -= redeem_amount * 100
    session['recalculate_price'] = False  # Ensure not to recalculate unless necessary

    try:
        cursor.execute("""
            INSERT INTO Redeem (CID, RedeemAmount, RedeemDate, TransactionNum, MID, CinemaID, TimeID, DateID, MSeatNum)
            VALUES (:user_id, :redeem_amount, CURRENT_TIMESTAMP, :transaction_num, :mid, :cinema_id, :time_id, :date_id, :seat_num)
        """, {
            'user_id': user_id, 'redeem_amount': redeem_amount, 'transaction_num': session['payment_info']['transaction_num'],
            'mid': session['payment_info']['id_movie'], 'cinema_id': session['payment_info']['id_cinema'],
            'time_id': session['payment_info']['id_time'], 'date_id': session['payment_info']['id_date'],
            'seat_num': session['payment_info']['movie_seat']
        })
        oracle_connection.commit()
    except Exception as e:
        flash(f'An error occurred while inserting into Redeem table: {str(e)}', 'error')
        oracle_connection.rollback()
        cursor.close()
        return redirect(url_for('payment'))
    
    flash(f'Points redeemed successfully. ${redeem_amount:.2f} has been deducted from your total.', 'success')
    return redirect(url_for('payment'))



# Update client history and get all ticket IDs associated with the client ----------------------------------------------
def update_client_history(cid, tid):
    cursor = oracle_connection.cursor()

    try:
        # Check if the client already exists in the HaveClientHistory table
        cursor.execute("SELECT * FROM HaveClientHistory WHERE CID = :cid", {'cid': cid})
        client_history = cursor.fetchone()

        if client_history is None:
            # If the client doesn't exist, insert a new record with the TID
            cursor.execute("""
                INSERT INTO HaveClientHistory (CID, BookedTickets, ClientPoints)
                VALUES (:cid, :tid, 5)
            """, {'cid': cid, 'tid': tid})
        else:
            # If the client exists, append the new TID if it's not already there
            booked_tickets = client_history[1].split(',') if client_history[1] else []
            if tid not in booked_tickets:
                booked_tickets.append(tid)
                booked_tickets_str = ','.join(booked_tickets)
                cursor.execute("""
                    UPDATE HaveClientHistory
                    SET BookedTickets = :booked_tickets, ClientPoints = ClientPoints + 5
                    WHERE CID = :cid
                """, {'booked_tickets': booked_tickets_str, 'cid': cid})

        oracle_connection.commit()
    except Exception as e:
        print("Error updating client history:", e)
        oracle_connection.rollback()
    finally:
        cursor.close()


# cancle ticket ------------------------------------------------------------------------------------------------------------
@app.route('/cancel_ticket/<ticket_id>', methods=['POST'])
def cancel_ticket(ticket_id):
    cursor = oracle_connection.cursor()

    try:
        # Retrieve ticket information from the form submission
        ticket_id = request.form['ticket_id']
        print("Ticket ID:", ticket_id)

        # Retrieve ticket information from the database
        cursor.execute("""
            SELECT TID, CID, MID, LISTAGG(MSeatNum, ', ') WITHIN GROUP (ORDER BY MSeatNum) AS Seats, CinemaID, TimeID, TransactionNum, TicketStatus, DateID
            FROM CreateTicket
            WHERE TID = :ticket_id
            GROUP BY TID, CID, MID, CinemaID, TimeID, TransactionNum, TicketStatus, DateID
        """, {'ticket_id': ticket_id})
        ticket_info = cursor.fetchone()
        print("Ticket info:", ticket_info)

        if not ticket_info:
            flash('Ticket not found.', 'error')
            return redirect(url_for('client_page'))

        if ticket_info[1] != session['id']:
            flash('You are not authorized to cancel this ticket.', 'error')
            return redirect(url_for('client_page'))
        else:
            for seat_num in ticket_info[3].split(', '):
                print("Seat number:", seat_num)

                # Insert data into the CancelTicket table
                cursor.execute("""
                    INSERT INTO CancleTicket (TID, CID, MID, MSeatNum, CinemaID, TimeID, TransactionNum, DateID)
                    VALUES (:ticket_id, :cid, :mid, :seat_num, :cinema_id, :time_id, :transaction_num, :date_id)
                """, {
                    'ticket_id': ticket_id,
                    'cid': session['id'],
                    'mid': ticket_info[2],
                    'seat_num': seat_num,
                    'cinema_id': ticket_info[4],
                    'time_id': ticket_info[5],
                    'transaction_num': ticket_info[6],
                    'date_id': ticket_info[8]
                })
                print("Ticket canceled successfully.")

            # Update the ticket status to "Canceled" in the CreateTicket table
            cursor.execute("""
                UPDATE CreateTicket
                SET TicketStatus = 'Canceled'
                WHERE TID = :ticket_id
            """, {'ticket_id': ticket_id})

            # Insert information into the UpdateCanceledMovie table
            for seat_num in ticket_info[3].split(', '):
                cursor.execute("""
                    INSERT INTO UpdateCancledMovie (TID, CID, MID, MSeatNum, CinemaID, TimeID, TransactionNum, DateID)
                    VALUES (:ticket_id, :cid, :mid, :seat_num, :cinema_id, :time_id, :transaction_num, :date_id)
                """, {
                    'ticket_id': ticket_id,
                    'cid': session['id'],
                    'mid': ticket_info[2],
                    'seat_num': seat_num,
                    'cinema_id': ticket_info[4],
                    'time_id': ticket_info[5],
                    'transaction_num': ticket_info[6],
                    'date_id': ticket_info[8]
                })
                print("Ticket canceled successfully.")
            # Update the seat status to 'empty' in the Have_MovieSeat table
            for seat_num in ticket_info[3].split(', '):
                cursor.execute("""
                    UPDATE Have_MovieSeat
                    SET MSeatStatus = 'empty'
                    WHERE CinemaID = :cinema_id AND TimeID = :time_id AND MSeatNum = :seat_num
                """, {
                    'cinema_id': ticket_info[4],
                    'time_id': ticket_info[5],
                    'seat_num': seat_num
                })
                print("Ticket canceled successfully, seat updated.")
            # Commit the transaction
            oracle_connection.commit()

            flash('Ticket canceled successfully.', 'success')

                    # Start transaction by checking client points
            cursor.execute("""
                SELECT ClientPoints FROM HaveClientHistory WHERE CID = :cid
            """, {'cid': session['id']})
            client_points = cursor.fetchone()
            if client_points and client_points[0] >= 5:
                # Deduct 5 points from the client's points
                cursor.execute("""
                    UPDATE HaveClientHistory SET ClientPoints = ClientPoints - 5 WHERE CID = :cid
                """, {'cid': session['id']})
                oracle_connection.commit()
                flash('Ticket canceled successfully, 5 points deducted.', 'success')
            else:
                flash('Not enough points to deduct.', 'error')

            # Delete data from selected items
            for seat_num in ticket_info[3].split(', '):
                cursor.execute("DELETE FROM SelectedItems WHERE CID = :cid AND TimeID = :time_id AND MSeatNum = :seat_num AND MID = : movie_id", 
                           {'cid': session['id'],
                            'time_id': ticket_info[5],
                            'seat_num': seat_num,
                            'movie_id': ticket_info[2]})
                print("Selected item deleted successfully.")
            oracle_connection.commit()

            for seat_num in ticket_info[3].split(', '):
                cursor.execute("DELETE FROM TransactionConfirm WHERE CID = :cid AND TimeID = :time_id AND MSeatNum = :seat_num AND MID = : movie_id AND DateID = :date_id AND TransactionNum = :transaction_num", 
                           {'cid': session['id'],
                            'time_id': ticket_info[5],
                            'seat_num': seat_num,
                            'movie_id': ticket_info[2],
                            'date_id': ticket_info[8],
                            'transaction_num': ticket_info[6]})
                print("Transaction confirm deleted successfully.")
            oracle_connection.commit()


    except Exception as e:
        flash('An error occurred while canceling the ticket. Please try again later.', 'error')
        print("Error canceling ticket:", e)
        oracle_connection.rollback()
    finally:
        cursor.close()



    return redirect(url_for('client_page'))


if __name__ == '__main__':
    app.run(debug=True)
