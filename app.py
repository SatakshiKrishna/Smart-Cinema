from flask import Flask, render_template, request, redirect, url_for, session, flash
from math import radians, sin, cos, asin, sqrt, isfinite
import os
import mysql.connector

from config import DB_CONFIG

from werkzeug.security import generate_password_hash, check_password_hash

# Import both recommendation functions
from recommendation.recommendation_engine import (
    recommend_movies,
    recommend_for_user
)


app = Flask(__name__)

# Flask uses this key for login sessions and flash messages
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "development-only-change-me")


# Creates a connection to MySQL
def get_db_connection():

    return mysql.connector.connect(
        **DB_CONFIG
    )


# Checks whether current user is an administrator
def is_admin():

    return (
        "user_id" in session
        and session.get("role") == "admin"
    )


# Home page
@app.route("/")
def home():

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    # Load currently showing movies and their ratings
    cursor.execute("""
        SELECT
            m.*,

            COALESCE(
                ROUND(
                    AVG(r.rating),
                    1
                ),
                0
            ) AS average_rating,

            COUNT(r.review_id)
            AS review_count

        FROM movies m

        LEFT JOIN reviews r
            ON m.movie_id = r.movie_id

        WHERE m.status = 'now_showing'

        GROUP BY
            m.movie_id,
            m.title,
            m.description,
            m.language,
            m.duration_minutes,
            m.release_date,
            m.age_rating,
            m.poster_url,
            m.status,
            m.created_at

        ORDER BY m.title
    """)

    movies = cursor.fetchall()

    cursor.close()
    connection.close()

    personalized_recommendations = []

    # Generate personalized recommendations
    # only for logged-in customer accounts
    if (
        "user_id" in session
        and session.get("role") == "customer"
    ):

        personalized_recommendations = (
            recommend_for_user(
                session["user_id"],
                limit=5
            )
        )

    return render_template(
        "index.html",
        movies=movies,
        personalized_recommendations=personalized_recommendations
    )


# Dedicated recommendation hub, also accessible to guests for similar-movie discovery.
@app.route("/recommendations")
def personal_recommendations():
    recommendations = []
    if "user_id" in session and session.get("role") == "customer":
        recommendations = recommend_for_user(session["user_id"], limit=8)

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT movie_id, title, description, language, duration_minutes,
                   age_rating, poster_url, status
            FROM movies
            WHERE status = 'now_showing'
            ORDER BY title
        """)
        movies = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    # Add display fields without changing the engine's ranking or scores.
    catalogue = {movie["movie_id"]: movie for movie in movies}
    recommendations = [
        {**catalogue.get(item["movie_id"], {}), **item}
        for item in recommendations
    ]
    return render_template(
        "personal_recommendations.html",
        recommendations=recommendations,
        movies=movies
    )


# Registration page
@app.route("/register", methods=["GET", "POST"])
def register():
    """Accept the existing website form and JSON from Postman."""
    if request.method == "POST":
        data = request.get_json(silent=True) if request.is_json else request.form
        if not isinstance(data, dict) and request.is_json:
            return {"error": "Invalid JSON body"}, 400
        data = data or {}
        full_name = str(data.get("full_name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        phone = str(data.get("phone", "")).strip()
        password = str(data.get("password", ""))
        if not full_name or not email or not password:
            if request.is_json:
                return {"error": "full_name, email and password are required"}, 400
            flash("Please fill name, email and password.")
            return render_template("register.html"), 400

        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (full_name, email, password_hash, phone, role)
                VALUES (%s, %s, %s, %s, 'customer')
            """, (full_name, email, generate_password_hash(password), phone or None))
            connection.commit()
            if request.is_json:
                return {"message": "Registration successful", "email": email,
                        "role": "customer"}, 201
            flash("Registration successful. Please login.")
            return redirect(url_for("login"))
        except mysql.connector.IntegrityError:
            connection.rollback()
            if request.is_json:
                return {"error": "Email is already registered"}, 409
            flash("Email is already registered.")
        finally:
            cursor.close()
            connection.close()
    return render_template("register.html")


# Login page
@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form[
            "email"
        ]

        password = request.form[
            "password"
        ]

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        cursor.execute("""
            SELECT *
            FROM users
            WHERE email = %s
        """, (
            email,
        ))

        user = cursor.fetchone()

        cursor.close()
        connection.close()

        # Compare password with the stored hash
        if (
            user
            and check_password_hash(
                user["password_hash"],
                password
            )
        ):

            session["user_id"] = user[
                "user_id"
            ]

            session["user_name"] = user[
                "full_name"
            ]

            session["role"] = user[
                "role"
            ]

            flash(
                "Login successful."
            )

            if user["role"] == "admin":

                return redirect(
                    url_for(
                        "admin_dashboard"
                    )
                )

            return redirect(
                url_for("home")
            )

        flash(
            "Invalid email or password."
        )

    return render_template(
        "login.html"
    )


# Logs user out
@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out."
    )

    return redirect(
        url_for("home")
    )


# Nearby shows: browser location is optional, and is never stored.
def _distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in kilometres (Haversine)."""
    rlat1, rlon1, rlat2, rlon2 = map(radians, (lat1, lon1, lat2, lon2))
    delta_lat = rlat2 - rlat1
    delta_lon = rlon2 - rlon1
    a = sin(delta_lat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(delta_lon / 2) ** 2
    return 6371.0 * 2 * asin(min(1.0, sqrt(a)))


@app.route("/nearby")
def nearby_shows():
    """Browse future showtimes, theatre locations and live seat counts."""
    city = request.args.get("city", "").strip()[:100]
    latitude = request.args.get("lat", "").strip()
    longitude = request.args.get("lon", "").strip()
    user_lat = user_lon = None
    if latitude or longitude:
        try:
            user_lat, user_lon = float(latitude), float(longitude)
            if not (isfinite(user_lat) and isfinite(user_lon) and -90 <= user_lat <= 90 and -180 <= user_lon <= 180):
                raise ValueError("invalid coordinates")
        except (ValueError, TypeError):
            user_lat = user_lon = None
            flash("Location coordinates were invalid. Use a city search instead.")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT DISTINCT city FROM theatres ORDER BY city")
        cities = [r["city"] for r in cursor.fetchall()]
        query = """
            SELECT sh.show_id, sh.show_date, sh.show_time,
                   sh.base_price, m.title AS movie_title, m.language,
                   t.theatre_name, t.city, t.address, t.latitude, t.longitude,
                   sc.screen_name,
                   (SELECT COUNT(*) FROM seats st WHERE st.screen_id = sc.screen_id) AS total_seats,
                   (SELECT COUNT(*) FROM booking_seats bs WHERE bs.show_id = sh.show_id) AS booked_seats
            FROM shows sh
            JOIN movies m ON m.movie_id = sh.movie_id
            JOIN screens sc ON sc.screen_id = sh.screen_id
            JOIN theatres t ON t.theatre_id = sc.theatre_id
            WHERE sh.status = 'scheduled'
              AND (sh.show_date > CURRENT_DATE()
                   OR (sh.show_date = CURRENT_DATE() AND sh.show_time >= CURRENT_TIME()))
        """
        params = []
        if city:
            query += " AND t.city LIKE %s"
            params.append("%" + city + "%")
        query += " ORDER BY sh.show_date, sh.show_time, t.theatre_name"
        cursor.execute(query, tuple(params))
        shows = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    for show in shows:
        show["available_seats"] = max(0, show["total_seats"] - show["booked_seats"])
        show["distance_km"] = None
        if user_lat is not None and show["latitude"] is not None and show["longitude"] is not None:
            show["distance_km"] = round(_distance_km(user_lat, user_lon,
                            float(show["latitude"]), float(show["longitude"])), 1)
    if user_lat is not None:
        # Known coordinates first (nearest first); unknown coordinates last.
        shows.sort(key=lambda x: (x["distance_km"] is None,
                                  x["distance_km"] if x["distance_km"] is not None else float("inf"),
                                  x["show_date"], x["show_time"]))
    return render_template("nearby.html", shows=shows, cities=cities,
                           selected_city=city, latitude=latitude if user_lat is not None else "",
                           longitude=longitude if user_lon is not None else "")


# Shows scheduled shows for a movie
@app.route(
    "/movie/<int:movie_id>/shows"
)
def movie_shows(movie_id):

    if "user_id" not in session:

        flash(
            "Please login to book tickets."
        )

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT *
        FROM movies
        WHERE movie_id = %s
    """, (
        movie_id,
    ))

    movie = cursor.fetchone()

    if not movie:

        cursor.close()
        connection.close()

        flash(
            "Movie not found."
        )

        return redirect(
            url_for("home")
        )

    cursor.execute("""
        SELECT
            sh.show_id,
            sh.show_date,
            sh.show_time,
            sh.base_price,
            sh.status,

            sc.screen_name,

            t.theatre_name,
            t.city,
            t.address

        FROM shows sh

        JOIN screens sc
            ON sh.screen_id = sc.screen_id

        JOIN theatres t
            ON sc.theatre_id = t.theatre_id

        WHERE sh.movie_id = %s
        AND sh.status = 'scheduled'

        ORDER BY
            sh.show_date,
            sh.show_time
    """, (
        movie_id,
    ))

    shows = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "shows.html",
        movie=movie,
        shows=shows
    )


# Displays seats for selected show
@app.route(
    "/show/<int:show_id>/seats"
)
def select_seats(show_id):

    if "user_id" not in session:

        flash(
            "Please login to book tickets."
        )

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            sh.show_id,
            sh.show_date,
            sh.show_time,
            sh.base_price,
            sh.status,

            m.title,
            m.movie_id,

            sc.screen_id,
            sc.screen_name,

            t.theatre_name

        FROM shows sh

        JOIN movies m
            ON sh.movie_id = m.movie_id

        JOIN screens sc
            ON sh.screen_id = sc.screen_id

        JOIN theatres t
            ON sc.theatre_id = t.theatre_id

        WHERE sh.show_id = %s
    """, (
        show_id,
    ))

    show = cursor.fetchone()

    if not show:

        cursor.close()
        connection.close()

        flash(
            "Show not found."
        )

        return redirect(
            url_for("home")
        )

    if show["status"] != "scheduled":

        cursor.close()
        connection.close()

        flash(
            "This show is not available for booking."
        )

        return redirect(
            url_for("home")
        )

    # Get seats and check whether each seat is booked
    cursor.execute("""
        SELECT
            s.seat_id,
            s.seat_number,
            s.seat_type,

            CASE

                WHEN bs.booking_seat_id IS NULL
                THEN 0

                ELSE 1

            END AS is_booked

        FROM seats s

        LEFT JOIN booking_seats bs
            ON s.seat_id = bs.seat_id
            AND bs.show_id = %s

        WHERE s.screen_id = %s

        ORDER BY s.seat_number
    """, (
        show_id,
        show["screen_id"]
    ))

    seats = cursor.fetchall()

    # Calculate current ticket price
    cursor.execute("""
        SELECT
            calculate_ticket_price(%s)
            AS current_price
    """, (
        show_id,
    ))

    current_price = cursor.fetchone()[
        "current_price"
    ]

    cursor.close()
    connection.close()

    return render_template(
        "seats.html",
        show=show,
        seats=seats,
        current_price=current_price
    )


# Creates booking from selected seats
@app.route(
    "/show/<int:show_id>/book",
    methods=["POST"]
)
def book_show(show_id):

    if "user_id" not in session:

        flash(
            "Please login to book tickets."
        )

        return redirect(
            url_for("login")
        )

    selected_seats_text = request.form.get(
        "selected_seats",
        ""
    )

    if not selected_seats_text:

        flash(
            "Please select at least one seat."
        )

        return redirect(
            url_for(
                "select_seats",
                show_id=show_id
            )
        )

    try:

        selected_seat_ids = [
            int(seat_id)

            for seat_id
            in selected_seats_text.split(",")

            if seat_id.strip()
        ]

        # Remove duplicate IDs
        selected_seat_ids = list(
            dict.fromkeys(
                selected_seat_ids
            )
        )

    except ValueError:

        flash(
            "Invalid seat selection."
        )

        return redirect(
            url_for(
                "select_seats",
                show_id=show_id
            )
        )

    if not selected_seat_ids:

        flash(
            "Please select at least one seat."
        )

        return redirect(
            url_for(
                "select_seats",
                show_id=show_id
            )
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        # Booking is handled as one transaction
        connection.start_transaction()

        cursor.execute("""
            SELECT
                show_id,
                screen_id

            FROM shows

            WHERE show_id = %s
            AND status = 'scheduled'
        """, (
            show_id,
        ))

        show = cursor.fetchone()

        if not show:

            connection.rollback()

            flash(
                "This show is not available."
            )

            return redirect(
                url_for("home")
            )

        placeholders = ",".join(
            ["%s"]
            * len(selected_seat_ids)
        )

        # Validate seat IDs against screen
        seat_query = f"""
            SELECT
                seat_id,
                seat_number

            FROM seats

            WHERE screen_id = %s

            AND seat_id IN (
                {placeholders}
            )
        """

        cursor.execute(
            seat_query,
            [
                show["screen_id"],
                *selected_seat_ids
            ]
        )

        valid_seats = cursor.fetchall()

        if (
            len(valid_seats)
            != len(selected_seat_ids)
        ):

            connection.rollback()

            flash(
                "One or more selected seats are invalid."
            )

            return redirect(
                url_for(
                    "select_seats",
                    show_id=show_id
                )
            )

        # Check again for already-booked seats
        booked_query = f"""
            SELECT
                seat_id

            FROM booking_seats

            WHERE show_id = %s

            AND seat_id IN (
                {placeholders}
            )
        """

        cursor.execute(
            booked_query,
            [
                show_id,
                *selected_seat_ids
            ]
        )

        already_booked = (
            cursor.fetchall()
        )

        if already_booked:

            connection.rollback()

            flash(
                "One of the selected seats was just booked. "
                "Please choose again."
            )

            return redirect(
                url_for(
                    "select_seats",
                    show_id=show_id
                )
            )

        # Always calculate price again on server
        cursor.execute("""
            SELECT
                calculate_ticket_price(%s)
                AS current_price
        """, (
            show_id,
        ))

        ticket_price = cursor.fetchone()[
            "current_price"
        ]

        total_amount = (
            ticket_price
            * len(selected_seat_ids)
        )

        cursor.execute("""
            INSERT INTO bookings (
                user_id,
                show_id,
                total_amount,
                booking_status
            )

            VALUES (
                %s,
                %s,
                %s,
                'pending'
            )
        """, (
            session["user_id"],
            show_id,
            total_amount
        ))

        booking_id = cursor.lastrowid

        # Save every booked seat
        for seat_id in selected_seat_ids:

            cursor.execute("""
                INSERT INTO booking_seats (
                    booking_id,
                    show_id,
                    seat_id,
                    ticket_price
                )

                VALUES (
                    %s,
                    %s,
                    %s,
                    %s
                )
            """, (
                booking_id,
                show_id,
                seat_id,
                ticket_price
            ))

        connection.commit()

        return redirect(
            url_for(
                "booking_success",
                booking_id=booking_id
            )
        )

    except mysql.connector.IntegrityError:

        connection.rollback()

        flash(
            "One of the selected seats is no longer available."
        )

        return redirect(
            url_for(
                "select_seats",
                show_id=show_id
            )
        )

    except mysql.connector.Error as error:

        connection.rollback()

        print(
            "Booking error:",
            error
        )

        flash(
            "Booking could not be completed."
        )

        return redirect(
            url_for(
                "select_seats",
                show_id=show_id
            )
        )

    finally:

        cursor.close()
        connection.close()


# Displays booking details before payment
@app.route(
    "/booking/<int:booking_id>/success"
)
def booking_success(booking_id):

    if "user_id" not in session:

        flash(
            "Please login first."
        )

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            b.booking_id,
            b.total_amount,
            b.booking_status,
            b.booking_time,

            m.title,

            sh.show_date,
            sh.show_time,

            sc.screen_name,

            t.theatre_name

        FROM bookings b

        JOIN shows sh
            ON b.show_id = sh.show_id

        JOIN movies m
            ON sh.movie_id = m.movie_id

        JOIN screens sc
            ON sh.screen_id = sc.screen_id

        JOIN theatres t
            ON sc.theatre_id = t.theatre_id

        WHERE b.booking_id = %s
        AND b.user_id = %s
    """, (
        booking_id,
        session["user_id"]
    ))

    booking = cursor.fetchone()

    if not booking:

        cursor.close()
        connection.close()

        flash(
            "Booking not found."
        )

        return redirect(
            url_for("home")
        )

    cursor.execute("""
        SELECT
            s.seat_number,
            s.seat_type,
            bs.ticket_price

        FROM booking_seats bs

        JOIN seats s
            ON bs.seat_id = s.seat_id

        WHERE bs.booking_id = %s

        ORDER BY s.seat_number
    """, (
        booking_id,
    ))

    booked_seats = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "booking_success.html",
        booking=booking,
        booked_seats=booked_seats
    )


# Displays payment page
@app.route(
    "/booking/<int:booking_id>/payment"
)
def payment(booking_id):

    if "user_id" not in session:

        flash(
            "Please login first."
        )

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            booking_id,
            total_amount,
            booking_status

        FROM bookings

        WHERE booking_id = %s
        AND user_id = %s
    """, (
        booking_id,
        session["user_id"]
    ))

    booking = cursor.fetchone()

    if not booking:

        cursor.close()
        connection.close()

        flash(
            "Booking not found."
        )

        return redirect(
            url_for("home")
        )

    if booking["booking_status"] == "confirmed":

        cursor.close()
        connection.close()

        flash(
            "This booking has already been paid."
        )

        return redirect(
            url_for(
                "payment_success",
                booking_id=booking_id
            )
        )

    if booking["booking_status"] == "cancelled":

        cursor.close()
        connection.close()

        flash(
            "Cancelled bookings cannot be paid."
        )

        return redirect(
            url_for("my_bookings")
        )

    cursor.close()
    connection.close()

    return render_template(
        "payment.html",
        booking=booking
    )


# Processes simulated payment
@app.route(
    "/booking/<int:booking_id>/payment",
    methods=["POST"]
)
def process_payment(booking_id):

    if "user_id" not in session:

        flash(
            "Please login first."
        )

        return redirect(
            url_for("login")
        )

    payment_method = request.form.get(
        "payment_method"
    )

    allowed_methods = [
        "upi",
        "card",
        "cash",
        "net_banking"
    ]

    if payment_method not in allowed_methods:

        flash(
            "Please select a valid payment method."
        )

        return redirect(
            url_for(
                "payment",
                booking_id=booking_id
            )
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute("""
            SELECT
                booking_id,
                total_amount,
                booking_status

            FROM bookings

            WHERE booking_id = %s
            AND user_id = %s
        """, (
            booking_id,
            session["user_id"]
        ))

        booking = cursor.fetchone()

        if not booking:

            flash(
                "Booking not found."
            )

            return redirect(
                url_for("home")
            )

        if booking["booking_status"] == "confirmed":

            flash(
                "Payment has already been completed."
            )

            return redirect(
                url_for(
                    "payment_success",
                    booking_id=booking_id
                )
            )

        if booking["booking_status"] == "cancelled":

            flash(
                "Cancelled bookings cannot be paid."
            )

            return redirect(
                url_for("my_bookings")
            )

        cursor.execute("""
            INSERT INTO payments (
                booking_id,
                amount,
                payment_method,
                payment_status
            )

            VALUES (
                %s,
                %s,
                %s,
                'successful'
            )
        """, (
            booking_id,
            booking["total_amount"],
            payment_method
        ))

        # Database trigger changes booking to confirmed
        connection.commit()

        return redirect(
            url_for(
                "payment_success",
                booking_id=booking_id
            )
        )

    except mysql.connector.IntegrityError:

        connection.rollback()

        flash(
            "Payment has already been recorded."
        )

        return redirect(
            url_for(
                "payment_success",
                booking_id=booking_id
            )
        )

    except mysql.connector.Error as error:

        connection.rollback()

        print(
            "Payment error:",
            error
        )

        flash(
            "Payment could not be completed."
        )

        return redirect(
            url_for(
                "payment",
                booking_id=booking_id
            )
        )

    finally:

        cursor.close()
        connection.close()


# Displays final confirmed ticket
@app.route(
    "/booking/<int:booking_id>/payment-success"
)
def payment_success(booking_id):

    if "user_id" not in session:

        flash(
            "Please login first."
        )

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            b.booking_id,
            b.total_amount,
            b.booking_status,
            b.booking_time,

            m.title,

            sh.show_date,
            sh.show_time,

            sc.screen_name,

            t.theatre_name,

            p.payment_id,
            p.payment_method,
            p.payment_status,
            p.payment_time

        FROM bookings b

        JOIN shows sh
            ON b.show_id = sh.show_id

        JOIN movies m
            ON sh.movie_id = m.movie_id

        JOIN screens sc
            ON sh.screen_id = sc.screen_id

        JOIN theatres t
            ON sc.theatre_id = t.theatre_id

        LEFT JOIN payments p
            ON b.booking_id = p.booking_id

        WHERE b.booking_id = %s
        AND b.user_id = %s
    """, (
        booking_id,
        session["user_id"]
    ))

    booking = cursor.fetchone()

    if not booking:

        cursor.close()
        connection.close()

        flash(
            "Booking not found."
        )

        return redirect(
            url_for("home")
        )

    cursor.execute("""
        SELECT
            s.seat_number,
            s.seat_type

        FROM booking_seats bs

        JOIN seats s
            ON bs.seat_id = s.seat_id

        WHERE bs.booking_id = %s

        ORDER BY s.seat_number
    """, (
        booking_id,
    ))

    booked_seats = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "payment_success.html",
        booking=booking,
        booked_seats=booked_seats
    )


# Displays customer's bookings
@app.route("/my-bookings")
def my_bookings():

    if "user_id" not in session:

        flash(
            "Please login to view your bookings."
        )

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            b.booking_id,
            b.booking_time,
            b.total_amount,
            b.booking_status,

            m.movie_id,
            m.title,

            sh.show_date,
            sh.show_time,

            sc.screen_name,

            t.theatre_name,

            GROUP_CONCAT(
                s.seat_number
                ORDER BY s.seat_number
                SEPARATOR ', '
            ) AS seats,

            p.payment_method,
            p.payment_status,

            c.cancellation_time,
            c.refund_amount,
            c.refund_status

        FROM bookings b

        JOIN shows sh
            ON b.show_id = sh.show_id

        JOIN movies m
            ON sh.movie_id = m.movie_id

        JOIN screens sc
            ON sh.screen_id = sc.screen_id

        JOIN theatres t
            ON sc.theatre_id = t.theatre_id

        LEFT JOIN booking_seats bs
            ON b.booking_id = bs.booking_id

        LEFT JOIN seats s
            ON bs.seat_id = s.seat_id

        LEFT JOIN payments p
            ON b.booking_id = p.booking_id

        LEFT JOIN cancellations c
            ON b.booking_id = c.booking_id

        WHERE b.user_id = %s

        GROUP BY
            b.booking_id,
            b.booking_time,
            b.total_amount,
            b.booking_status,
            m.movie_id,
            m.title,
            sh.show_date,
            sh.show_time,
            sc.screen_name,
            t.theatre_name,
            p.payment_method,
            p.payment_status,
            c.cancellation_time,
            c.refund_amount,
            c.refund_status

        ORDER BY b.booking_time DESC
    """, (
        session["user_id"],
    ))

    bookings = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "my_bookings.html",
        bookings=bookings
    )


# Cancels confirmed booking
@app.route(
    "/booking/<int:booking_id>/cancel",
    methods=["POST"]
)
def cancel_booking(booking_id):

    if "user_id" not in session:

        flash(
            "Please login first."
        )

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        connection.start_transaction()

        cursor.execute("""
            SELECT
                booking_id,
                total_amount,
                booking_status

            FROM bookings

            WHERE booking_id = %s
            AND user_id = %s

            FOR UPDATE
        """, (
            booking_id,
            session["user_id"]
        ))

        booking = cursor.fetchone()

        if not booking:

            connection.rollback()

            flash(
                "Booking not found."
            )

            return redirect(
                url_for("my_bookings")
            )

        if booking["booking_status"] != "confirmed":

            connection.rollback()

            flash(
                "Only confirmed bookings can be cancelled."
            )

            return redirect(
                url_for("my_bookings")
            )

        cursor.execute("""
            SELECT
                cancellation_id

            FROM cancellations

            WHERE booking_id = %s
        """, (
            booking_id,
        ))

        existing_cancellation = (
            cursor.fetchone()
        )

        if existing_cancellation:

            connection.rollback()

            flash(
                "This booking has already been cancelled."
            )

            return redirect(
                url_for("my_bookings")
            )

        cursor.execute("""
            INSERT INTO cancellations (
                booking_id,
                refund_amount,
                refund_status
            )

            VALUES (
                %s,
                %s,
                'processed'
            )
        """, (
            booking_id,
            booking["total_amount"]
        ))

        cursor.execute("""
            UPDATE bookings

            SET booking_status = 'cancelled'

            WHERE booking_id = %s
        """, (
            booking_id,
        ))

        cursor.execute("""
            UPDATE payments

            SET payment_status = 'refunded'

            WHERE booking_id = %s
            AND payment_status = 'successful'
        """, (
            booking_id,
        ))

        # Remove seat reservations so seats are available again
        cursor.execute("""
            DELETE FROM booking_seats
            WHERE booking_id = %s
        """, (
            booking_id,
        ))

        connection.commit()

        flash(
            "Booking cancelled successfully. "
            "Your refund has been processed."
        )

    except mysql.connector.Error as error:

        connection.rollback()

        print(
            "Cancellation error:",
            error
        )

        flash(
            "Booking cancellation could not be completed."
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for("my_bookings")
    )


# Displays movie reviews
@app.route(
    "/movie/<int:movie_id>/reviews"
)
def movie_reviews(movie_id):

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            m.movie_id,
            m.title,
            m.description,
            m.language,
            m.duration_minutes,

            COALESCE(
                ROUND(
                    AVG(r.rating),
                    1
                ),
                0
            ) AS average_rating,

            COUNT(r.review_id)
            AS review_count

        FROM movies m

        LEFT JOIN reviews r
            ON m.movie_id = r.movie_id

        WHERE m.movie_id = %s

        GROUP BY
            m.movie_id,
            m.title,
            m.description,
            m.language,
            m.duration_minutes
    """, (
        movie_id,
    ))

    movie = cursor.fetchone()

    if not movie:

        cursor.close()
        connection.close()

        flash(
            "Movie not found."
        )

        return redirect(
            url_for("home")
        )

    cursor.execute("""
        SELECT
            r.review_id,
            r.user_id,
            r.rating,
            r.review_text,
            r.created_at,

            u.full_name

        FROM reviews r

        JOIN users u
            ON r.user_id = u.user_id

        WHERE r.movie_id = %s

        ORDER BY r.created_at DESC
    """, (
        movie_id,
    ))

    reviews = cursor.fetchall()

    can_review = False
    existing_review = None

    # Check whether logged-in customer can review movie
    if (
        "user_id" in session
        and session.get("role") == "customer"
    ):

        cursor.execute("""
            SELECT
                b.booking_id

            FROM bookings b

            JOIN shows sh
                ON b.show_id = sh.show_id

            WHERE b.user_id = %s
            AND sh.movie_id = %s
            AND b.booking_status = 'confirmed'

            LIMIT 1
        """, (
            session["user_id"],
            movie_id
        ))

        confirmed_booking = (
            cursor.fetchone()
        )

        if confirmed_booking:
            can_review = True

        cursor.execute("""
            SELECT
                review_id,
                rating,
                review_text

            FROM reviews

            WHERE user_id = %s
            AND movie_id = %s
        """, (
            session["user_id"],
            movie_id
        ))

        existing_review = (
            cursor.fetchone()
        )

    cursor.close()
    connection.close()

    return render_template(
        "movie_reviews.html",
        movie=movie,
        reviews=reviews,
        can_review=can_review,
        existing_review=existing_review
    )


# Creates or updates movie review
@app.route(
    "/movie/<int:movie_id>/review",
    methods=["POST"]
)
def submit_review(movie_id):

    if "user_id" not in session:

        flash(
            "Please login to submit a review."
        )

        return redirect(
            url_for("login")
        )

    if session.get("role") != "customer":

        flash(
            "Only customer accounts can submit reviews."
        )

        return redirect(
            url_for(
                "movie_reviews",
                movie_id=movie_id
            )
        )

    rating_text = request.form.get(
        "rating",
        ""
    )

    review_text = request.form.get(
        "review_text",
        ""
    ).strip()

    try:

        rating = int(
            rating_text
        )

    except ValueError:

        flash(
            "Please select a valid rating."
        )

        return redirect(
            url_for(
                "movie_reviews",
                movie_id=movie_id
            )
        )

    if rating < 1 or rating > 5:

        flash(
            "Rating must be between 1 and 5."
        )

        return redirect(
            url_for(
                "movie_reviews",
                movie_id=movie_id
            )
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute("""
            SELECT movie_id
            FROM movies
            WHERE movie_id = %s
        """, (
            movie_id,
        ))

        movie = cursor.fetchone()

        if not movie:

            flash(
                "Movie not found."
            )

            return redirect(
                url_for("home")
            )

        # Confirm the customer has booked this movie
        cursor.execute("""
            SELECT
                b.booking_id

            FROM bookings b

            JOIN shows sh
                ON b.show_id = sh.show_id

            WHERE b.user_id = %s
            AND sh.movie_id = %s
            AND b.booking_status = 'confirmed'

            LIMIT 1
        """, (
            session["user_id"],
            movie_id
        ))

        confirmed_booking = (
            cursor.fetchone()
        )

        if not confirmed_booking:

            flash(
                "You can review this movie only after "
                "having a confirmed booking."
            )

            return redirect(
                url_for(
                    "movie_reviews",
                    movie_id=movie_id
                )
            )

        cursor.execute("""
            SELECT
                review_id

            FROM reviews

            WHERE user_id = %s
            AND movie_id = %s
        """, (
            session["user_id"],
            movie_id
        ))

        existing_review = (
            cursor.fetchone()
        )

        if existing_review:

            cursor.execute("""
                UPDATE reviews

                SET
                    rating = %s,
                    review_text = %s,
                    created_at = CURRENT_TIMESTAMP

                WHERE review_id = %s
            """, (
                rating,
                review_text,
                existing_review[
                    "review_id"
                ]
            ))

            flash(
                "Your review has been updated."
            )

        else:

            cursor.execute("""
                INSERT INTO reviews (
                    user_id,
                    movie_id,
                    rating,
                    review_text
                )

                VALUES (
                    %s,
                    %s,
                    %s,
                    %s
                )
            """, (
                session["user_id"],
                movie_id,
                rating,
                review_text
            ))

            flash(
                "Review submitted successfully."
            )

        connection.commit()

    except mysql.connector.Error as error:

        connection.rollback()

        print(
            "Review error:",
            error
        )

        flash(
            "Your review could not be saved."
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for(
            "movie_reviews",
            movie_id=movie_id
        )
    )


# Deletes customer's own review
@app.route(
    "/review/<int:review_id>/delete",
    methods=["POST"]
)
def delete_review(review_id):

    if "user_id" not in session:

        flash(
            "Please login first."
        )

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            review_id,
            movie_id,
            user_id

        FROM reviews

        WHERE review_id = %s
    """, (
        review_id,
    ))

    review = cursor.fetchone()

    if not review:

        cursor.close()
        connection.close()

        flash(
            "Review not found."
        )

        return redirect(
            url_for("home")
        )

    movie_id = review[
        "movie_id"
    ]

    if (
        review["user_id"]
        != session["user_id"]
    ):

        cursor.close()
        connection.close()

        flash(
            "You cannot delete another user's review."
        )

        return redirect(
            url_for(
                "movie_reviews",
                movie_id=movie_id
            )
        )

    try:

        cursor.execute("""
            DELETE FROM reviews
            WHERE review_id = %s
        """, (
            review_id,
        ))

        connection.commit()

        flash(
            "Review deleted successfully."
        )

    except mysql.connector.Error as error:

        connection.rollback()

        print(
            "Delete review error:",
            error
        )

        flash(
            "Review could not be deleted."
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for(
            "movie_reviews",
            movie_id=movie_id
        )
    )


# Displays similar movies using recommendation engine
@app.route(
    "/movie/<int:movie_id>/recommendations"
)
def movie_recommendations(movie_id):

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            movie_id,
            title,
            description,
            language,
            poster_url,
            status

        FROM movies

        WHERE movie_id = %s
    """, (
        movie_id,
    ))

    selected_movie = cursor.fetchone()

    cursor.close()
    connection.close()

    if not selected_movie:

        flash(
            "Movie not found."
        )

        return redirect(
            url_for("home")
        )

    # Generate top five similar movies
    recommendations = recommend_movies(
        movie_id,
        limit=5
    )

    return render_template(
        "movie_recommendations.html",
        selected_movie=selected_movie,
        recommendations=recommendations
    )


# Admin dashboard
@app.route("/admin")
def admin_dashboard():

    if "user_id" not in session:

        flash(
            "Please login first."
        )

        return redirect(
            url_for("login")
        )

    if not is_admin():

        flash(
            "You are not authorized to access "
            "the admin dashboard."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            COUNT(*) AS total_users

        FROM users

        WHERE role = 'customer'
    """)

    total_users = cursor.fetchone()[
        "total_users"
    ]

    cursor.execute("""
        SELECT
            COUNT(*) AS total_movies

        FROM movies
    """)

    total_movies = cursor.fetchone()[
        "total_movies"
    ]

    cursor.execute("""
        SELECT
            COUNT(*) AS total_bookings

        FROM bookings
    """)

    total_bookings = cursor.fetchone()[
        "total_bookings"
    ]

    cursor.execute("""
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS total_revenue

        FROM payments

        WHERE payment_status = 'successful'
    """)

    total_revenue = cursor.fetchone()[
        "total_revenue"
    ]

    cursor.execute("""
        SELECT
            COUNT(*) AS total_shows

        FROM shows

        WHERE status = 'scheduled'
    """)

    total_shows = cursor.fetchone()[
        "total_shows"
    ]

    cursor.close()
    connection.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_movies=total_movies,
        total_bookings=total_bookings,
        total_revenue=total_revenue,
        total_shows=total_shows
    )


# Displays movies for admin
@app.route("/admin/movies")
def admin_movies():

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT *
        FROM movies
        ORDER BY created_at DESC
    """)

    movies = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_movies.html",
        movies=movies
    )


# Adds a movie
@app.route(
    "/admin/movies/add",
    methods=["GET", "POST"]
)
def admin_add_movie():

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    if request.method == "POST":

        title = request.form[
            "title"
        ]

        description = request.form[
            "description"
        ]

        language = request.form[
            "language"
        ]

        duration_minutes = request.form[
            "duration_minutes"
        ]

        release_date = request.form[
            "release_date"
        ]

        age_rating = request.form[
            "age_rating"
        ]

        poster_url = request.form[
            "poster_url"
        ]

        status = request.form[
            "status"
        ]

        connection = get_db_connection()
        cursor = connection.cursor()

        try:

            cursor.execute("""
                INSERT INTO movies (
                    title,
                    description,
                    language,
                    duration_minutes,
                    release_date,
                    age_rating,
                    poster_url,
                    status
                )

                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
            """, (
                title,
                description,
                language,
                duration_minutes,

                release_date
                if release_date
                else None,

                age_rating,
                poster_url,
                status
            ))

            connection.commit()

            flash(
                "Movie added successfully."
            )

            return redirect(
                url_for(
                    "admin_movies"
                )
            )

        except mysql.connector.Error as error:

            connection.rollback()

            print(
                "Add movie error:",
                error
            )

            flash(
                "Movie could not be added."
            )

        finally:

            cursor.close()
            connection.close()

    return render_template(
        "admin_add_movie.html"
    )


# Edits movie
@app.route(
    "/admin/movies/<int:movie_id>/edit",
    methods=["GET", "POST"]
)
def admin_edit_movie(movie_id):

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT *
        FROM movies
        WHERE movie_id = %s
    """, (
        movie_id,
    ))

    movie = cursor.fetchone()

    if not movie:

        cursor.close()
        connection.close()

        flash(
            "Movie not found."
        )

        return redirect(
            url_for(
                "admin_movies"
            )
        )

    if request.method == "POST":

        title = request.form[
            "title"
        ]

        description = request.form[
            "description"
        ]

        language = request.form[
            "language"
        ]

        duration_minutes = request.form[
            "duration_minutes"
        ]

        release_date = request.form[
            "release_date"
        ]

        age_rating = request.form[
            "age_rating"
        ]

        poster_url = request.form[
            "poster_url"
        ]

        status = request.form[
            "status"
        ]

        try:

            cursor.execute("""
                UPDATE movies

                SET
                    title = %s,
                    description = %s,
                    language = %s,
                    duration_minutes = %s,
                    release_date = %s,
                    age_rating = %s,
                    poster_url = %s,
                    status = %s

                WHERE movie_id = %s
            """, (
                title,
                description,
                language,
                duration_minutes,

                release_date
                if release_date
                else None,

                age_rating,
                poster_url,
                status,
                movie_id
            ))

            connection.commit()

            flash(
                "Movie updated successfully."
            )

            return redirect(
                url_for(
                    "admin_movies"
                )
            )

        except mysql.connector.Error as error:

            connection.rollback()

            print(
                "Edit movie error:",
                error
            )

            flash(
                "Movie could not be updated."
            )

    cursor.close()
    connection.close()

    return render_template(
        "admin_edit_movie.html",
        movie=movie
    )


# Deletes movie
@app.route(
    "/admin/movies/<int:movie_id>/delete",
    methods=["POST"]
)
def admin_delete_movie(movie_id):

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            DELETE FROM movies
            WHERE movie_id = %s
        """, (
            movie_id,
        ))

        connection.commit()

        flash(
            "Movie deleted successfully."
        )

    except mysql.connector.Error as error:

        connection.rollback()

        print(
            "Delete movie error:",
            error
        )

        flash(
            "Movie could not be deleted."
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for(
            "admin_movies"
        )
    )


# Displays theatres
def _theatre_coordinates(data):
    lat = str(data.get("latitude", "")).strip()
    lon = str(data.get("longitude", "")).strip()
    if not lat and not lon:
        return None, None
    if not lat or not lon:
        raise ValueError("Enter both latitude and longitude, or leave both empty.")
    try:
        latitude, longitude = float(lat), float(lon)
    except ValueError:
        raise ValueError("Coordinates must be numbers.")
    if not (isfinite(latitude) and isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Latitude must be -90 to 90; longitude must be -180 to 180.")
    return latitude, longitude


@app.route("/admin/theatres")
def admin_theatres():

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            t.theatre_id,
            t.theatre_name,
            t.city,
            t.address,
            t.latitude,
            t.longitude,
            t.created_at,

            COUNT(sc.screen_id)
            AS screen_count

        FROM theatres t

        LEFT JOIN screens sc
            ON t.theatre_id = sc.theatre_id

        GROUP BY
            t.theatre_id,
            t.theatre_name,
            t.city,
            t.address,
            t.latitude,
            t.longitude,
            t.created_at

        ORDER BY t.theatre_name
    """)

    theatres = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_theatres.html",
        theatres=theatres
    )


# Adds theatre
@app.route(
    "/admin/theatres/add",
    methods=["GET", "POST"]
)
def admin_add_theatre():

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    if request.method == "POST":

        theatre_name = request.form[
            "theatre_name"
        ]

        city = request.form[
            "city"
        ]

        address = request.form["address"]
        try:
            latitude, longitude = _theatre_coordinates(request.form)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("admin_add_theatre"))

        connection = get_db_connection()
        cursor = connection.cursor()

        try:

            cursor.execute("""
                INSERT INTO theatres (
                    theatre_name, city, address, latitude, longitude
                ) VALUES (%s, %s, %s, %s, %s)
            """, (theatre_name, city, address, latitude, longitude))

            connection.commit()

            flash(
                "Theatre added successfully."
            )

            return redirect(
                url_for(
                    "admin_theatres"
                )
            )

        except mysql.connector.Error as error:

            connection.rollback()

            print(
                "Add theatre error:",
                error
            )

            flash(
                "Theatre could not be added."
            )

        finally:

            cursor.close()
            connection.close()

    return render_template(
        "admin_add_theatre.html"
    )


# Edits theatre
@app.route(
    "/admin/theatres/<int:theatre_id>/edit",
    methods=["GET", "POST"]
)
def admin_edit_theatre(theatre_id):

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT *
        FROM theatres
        WHERE theatre_id = %s
    """, (
        theatre_id,
    ))

    theatre = cursor.fetchone()

    if not theatre:

        cursor.close()
        connection.close()

        flash(
            "Theatre not found."
        )

        return redirect(
            url_for(
                "admin_theatres"
            )
        )

    if request.method == "POST":

        theatre_name = request.form[
            "theatre_name"
        ]

        city = request.form[
            "city"
        ]

        address = request.form["address"]
        try:
            latitude, longitude = _theatre_coordinates(request.form)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("admin_edit_theatre", theatre_id=theatre_id))

        try:

            cursor.execute("""
                UPDATE theatres

                SET
                    theatre_name = %s,
                    city = %s,
                    address = %s,
                    latitude = %s,
                    longitude = %s

                WHERE theatre_id = %s
            """, (
                theatre_name,
                city,
                address,
                latitude,
                longitude,
                theatre_id
            ))

            connection.commit()

            flash(
                "Theatre updated successfully."
            )

            return redirect(
                url_for(
                    "admin_theatres"
                )
            )

        except mysql.connector.Error as error:

            connection.rollback()

            print(
                "Edit theatre error:",
                error
            )

            flash(
                "Theatre could not be updated."
            )

    cursor.close()
    connection.close()

    return render_template(
        "admin_edit_theatre.html",
        theatre=theatre
    )


# Deletes theatre
@app.route(
    "/admin/theatres/<int:theatre_id>/delete",
    methods=["POST"]
)
def admin_delete_theatre(theatre_id):

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            DELETE FROM theatres
            WHERE theatre_id = %s
        """, (
            theatre_id,
        ))

        connection.commit()

        flash(
            "Theatre deleted successfully."
        )

    except mysql.connector.Error as error:

        connection.rollback()

        print(
            "Delete theatre error:",
            error
        )

        flash(
            "Theatre could not be deleted."
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for(
            "admin_theatres"
        )
    )


# Displays screens for a theatre
@app.route(
    "/admin/theatres/<int:theatre_id>/screens"
)
def admin_screens(theatre_id):

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT *
        FROM theatres
        WHERE theatre_id = %s
    """, (
        theatre_id,
    ))

    theatre = cursor.fetchone()

    if not theatre:

        cursor.close()
        connection.close()

        flash(
            "Theatre not found."
        )

        return redirect(
            url_for(
                "admin_theatres"
            )
        )

    cursor.execute("""
        SELECT
            sc.screen_id,
            sc.screen_name,
            sc.total_seats,

            COUNT(s.seat_id)
            AS created_seats

        FROM screens sc

        LEFT JOIN seats s
            ON sc.screen_id = s.screen_id

        WHERE sc.theatre_id = %s

        GROUP BY
            sc.screen_id,
            sc.screen_name,
            sc.total_seats

        ORDER BY sc.screen_name
    """, (
        theatre_id,
    ))

    screens = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_screens.html",
        theatre=theatre,
        screens=screens
    )


# Adds a screen
@app.route(
    "/admin/theatres/<int:theatre_id>/screens/add",
    methods=["GET", "POST"]
)
def admin_add_screen(theatre_id):

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT *
        FROM theatres
        WHERE theatre_id = %s
    """, (
        theatre_id,
    ))

    theatre = cursor.fetchone()

    if not theatre:

        cursor.close()
        connection.close()

        flash(
            "Theatre not found."
        )

        return redirect(
            url_for(
                "admin_theatres"
            )
        )

    if request.method == "POST":

        screen_name = request.form[
            "screen_name"
        ]

        total_seats = request.form[
            "total_seats"
        ]

        try:

            cursor.execute("""
                INSERT INTO screens (
                    theatre_id,
                    screen_name,
                    total_seats
                )

                VALUES (
                    %s,
                    %s,
                    %s
                )
            """, (
                theatre_id,
                screen_name,
                total_seats
            ))

            connection.commit()

            flash(
                "Screen added successfully."
            )

            return redirect(
                url_for(
                    "admin_screens",
                    theatre_id=theatre_id
                )
            )

        except mysql.connector.Error as error:

            connection.rollback()

            print(
                "Add screen error:",
                error
            )

            flash(
                "Screen could not be added."
            )

    cursor.close()
    connection.close()

    return render_template(
        "admin_add_screen.html",
        theatre=theatre
    )


# Edits screen
@app.route(
    "/admin/screens/<int:screen_id>/edit",
    methods=["GET", "POST"]
)
def admin_edit_screen(screen_id):

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            sc.*,
            t.theatre_name

        FROM screens sc

        JOIN theatres t
            ON sc.theatre_id = t.theatre_id

        WHERE sc.screen_id = %s
    """, (
        screen_id,
    ))

    screen = cursor.fetchone()

    if not screen:

        cursor.close()
        connection.close()

        flash(
            "Screen not found."
        )

        return redirect(
            url_for(
                "admin_theatres"
            )
        )

    if request.method == "POST":

        screen_name = request.form[
            "screen_name"
        ]

        total_seats = request.form[
            "total_seats"
        ]

        try:

            cursor.execute("""
                UPDATE screens

                SET
                    screen_name = %s,
                    total_seats = %s

                WHERE screen_id = %s
            """, (
                screen_name,
                total_seats,
                screen_id
            ))

            connection.commit()

            flash(
                "Screen updated successfully."
            )

            return redirect(
                url_for(
                    "admin_screens",
                    theatre_id=screen[
                        "theatre_id"
                    ]
                )
            )

        except mysql.connector.Error as error:

            connection.rollback()

            print(
                "Edit screen error:",
                error
            )

            flash(
                "Screen could not be updated."
            )

    cursor.close()
    connection.close()

    return render_template(
        "admin_edit_screen.html",
        screen=screen
    )


# Deletes screen
@app.route(
    "/admin/screens/<int:screen_id>/delete",
    methods=["POST"]
)
def admin_delete_screen(screen_id):

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            theatre_id

        FROM screens

        WHERE screen_id = %s
    """, (
        screen_id,
    ))

    screen = cursor.fetchone()

    if not screen:

        cursor.close()
        connection.close()

        flash(
            "Screen not found."
        )

        return redirect(
            url_for(
                "admin_theatres"
            )
        )

    theatre_id = screen[
        "theatre_id"
    ]

    try:

        cursor.execute("""
            DELETE FROM screens
            WHERE screen_id = %s
        """, (
            screen_id,
        ))

        connection.commit()

        flash(
            "Screen deleted successfully."
        )

    except mysql.connector.Error as error:

        connection.rollback()

        print(
            "Delete screen error:",
            error
        )

        flash(
            "Screen could not be deleted."
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for(
            "admin_screens",
            theatre_id=theatre_id
        )
    )


# Displays all shows
@app.route("/admin/shows")
def admin_shows():

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            sh.show_id,
            sh.show_date,
            sh.show_time,
            sh.base_price,
            sh.status,

            m.title,

            sc.screen_name,

            t.theatre_name,
            t.city,

            COUNT(
                DISTINCT bs.booking_seat_id
            ) AS booked_seats

        FROM shows sh

        JOIN movies m
            ON sh.movie_id = m.movie_id

        JOIN screens sc
            ON sh.screen_id = sc.screen_id

        JOIN theatres t
            ON sc.theatre_id = t.theatre_id

        LEFT JOIN booking_seats bs
            ON sh.show_id = bs.show_id

        GROUP BY
            sh.show_id,
            sh.show_date,
            sh.show_time,
            sh.base_price,
            sh.status,
            m.title,
            sc.screen_name,
            t.theatre_name,
            t.city

        ORDER BY
            sh.show_date DESC,
            sh.show_time DESC
    """)

    shows = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_shows.html",
        shows=shows
    )


# Adds show
@app.route(
    "/admin/shows/add",
    methods=["GET", "POST"]
)
def admin_add_show():

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            movie_id,
            title,
            status

        FROM movies

        WHERE status IN (
            'upcoming',
            'now_showing'
        )

        ORDER BY title
    """)

    movies = cursor.fetchall()

    # Only screens with real seat records can be used
    cursor.execute("""
        SELECT
            sc.screen_id,
            sc.screen_name,
            sc.total_seats,

            t.theatre_name,
            t.city,

            COUNT(s.seat_id)
            AS created_seats

        FROM screens sc

        JOIN theatres t
            ON sc.theatre_id = t.theatre_id

        LEFT JOIN seats s
            ON sc.screen_id = s.screen_id

        GROUP BY
            sc.screen_id,
            sc.screen_name,
            sc.total_seats,
            t.theatre_name,
            t.city

        HAVING COUNT(s.seat_id) > 0

        ORDER BY
            t.theatre_name,
            sc.screen_name
    """)

    screens = cursor.fetchall()

    if request.method == "POST":

        movie_id = request.form[
            "movie_id"
        ]

        screen_id = request.form[
            "screen_id"
        ]

        show_date = request.form[
            "show_date"
        ]

        show_time = request.form[
            "show_time"
        ]

        base_price = request.form[
            "base_price"
        ]

        try:

            # Check movie exists
            cursor.execute("""
                SELECT
                    movie_id

                FROM movies

                WHERE movie_id = %s
            """, (
                movie_id,
            ))

            movie_exists = cursor.fetchone()

            if not movie_exists:

                flash(
                    "Selected movie does not exist."
                )

                return redirect(
                    url_for(
                        "admin_add_show"
                    )
                )

            # Check selected screen has seat rows
            cursor.execute("""
                SELECT
                    sc.screen_id,

                    COUNT(s.seat_id)
                    AS seat_count

                FROM screens sc

                LEFT JOIN seats s
                    ON sc.screen_id = s.screen_id

                WHERE sc.screen_id = %s

                GROUP BY sc.screen_id
            """, (
                screen_id,
            ))

            screen = cursor.fetchone()

            if (
                not screen
                or screen["seat_count"] == 0
            ):

                flash(
                    "The selected screen has no seat records. "
                    "Add seats before scheduling a show."
                )

                return redirect(
                    url_for(
                        "admin_add_show"
                    )
                )

            cursor.execute("""
                INSERT INTO shows (
                    movie_id,
                    screen_id,
                    show_date,
                    show_time,
                    base_price,
                    status
                )

                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'scheduled'
                )
            """, (
                movie_id,
                screen_id,
                show_date,
                show_time,
                base_price
            ))

            connection.commit()

            flash(
                "Show scheduled successfully."
            )

            return redirect(
                url_for(
                    "admin_shows"
                )
            )

        except mysql.connector.Error as error:

            connection.rollback()

            print(
                "Add show error:",
                error
            )

            flash(
                "Show could not be created."
            )

    cursor.close()
    connection.close()

    return render_template(
        "admin_add_show.html",
        movies=movies,
        screens=screens
    )


# Edits show
@app.route(
    "/admin/shows/<int:show_id>/edit",
    methods=["GET", "POST"]
)
def admin_edit_show(show_id):

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT *
        FROM shows
        WHERE show_id = %s
    """, (
        show_id,
    ))

    show = cursor.fetchone()

    if not show:

        cursor.close()
        connection.close()

        flash(
            "Show not found."
        )

        return redirect(
            url_for(
                "admin_shows"
            )
        )

    cursor.execute("""
        SELECT
            movie_id,
            title

        FROM movies

        ORDER BY title
    """)

    movies = cursor.fetchall()

    cursor.execute("""
        SELECT
            sc.screen_id,
            sc.screen_name,

            t.theatre_name,
            t.city,

            COUNT(s.seat_id)
            AS created_seats

        FROM screens sc

        JOIN theatres t
            ON sc.theatre_id = t.theatre_id

        LEFT JOIN seats s
            ON sc.screen_id = s.screen_id

        GROUP BY
            sc.screen_id,
            sc.screen_name,
            t.theatre_name,
            t.city

        HAVING COUNT(s.seat_id) > 0

        ORDER BY
            t.theatre_name,
            sc.screen_name
    """)

    screens = cursor.fetchall()

    if request.method == "POST":

        movie_id = request.form[
            "movie_id"
        ]

        screen_id = request.form[
            "screen_id"
        ]

        show_date = request.form[
            "show_date"
        ]

        show_time = request.form[
            "show_time"
        ]

        base_price = request.form[
            "base_price"
        ]

        status = request.form[
            "status"
        ]

        try:

            cursor.execute("""
                SELECT
                    COUNT(*) AS booking_count

                FROM booking_seats

                WHERE show_id = %s
            """, (
                show_id,
            ))

            booking_count = (
                cursor.fetchone()[
                    "booking_count"
                ]
            )

            # Do not allow screen change once seats exist
            if (
                booking_count > 0
                and int(screen_id)
                != show["screen_id"]
            ):

                flash(
                    "The screen cannot be changed because "
                    "seats have already been booked for this show."
                )

                return redirect(
                    url_for(
                        "admin_edit_show",
                        show_id=show_id
                    )
                )

            cursor.execute("""
                UPDATE shows

                SET
                    movie_id = %s,
                    screen_id = %s,
                    show_date = %s,
                    show_time = %s,
                    base_price = %s,
                    status = %s

                WHERE show_id = %s
            """, (
                movie_id,
                screen_id,
                show_date,
                show_time,
                base_price,
                status,
                show_id
            ))

            connection.commit()

            flash(
                "Show updated successfully."
            )

            return redirect(
                url_for(
                    "admin_shows"
                )
            )

        except mysql.connector.Error as error:

            connection.rollback()

            print(
                "Edit show error:",
                error
            )

            flash(
                "Show could not be updated."
            )

    cursor.close()
    connection.close()

    return render_template(
        "admin_edit_show.html",
        show=show,
        movies=movies,
        screens=screens
    )


# Cancels show
@app.route(
    "/admin/shows/<int:show_id>/cancel",
    methods=["POST"]
)
def admin_cancel_show(show_id):

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute("""
            SELECT
                show_id,
                status

            FROM shows

            WHERE show_id = %s
        """, (
            show_id,
        ))

        show = cursor.fetchone()

        if not show:

            flash(
                "Show not found."
            )

            return redirect(
                url_for(
                    "admin_shows"
                )
            )

        if show["status"] == "cancelled":

            flash(
                "This show is already cancelled."
            )

            return redirect(
                url_for(
                    "admin_shows"
                )
            )

        cursor.execute("""
            UPDATE shows

            SET status = 'cancelled'

            WHERE show_id = %s
        """, (
            show_id,
        ))

        connection.commit()

        flash(
            "Show cancelled successfully."
        )

    except mysql.connector.Error as error:

        connection.rollback()

        print(
            "Cancel show error:",
            error
        )

        flash(
            "Show could not be cancelled."
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for(
            "admin_shows"
        )
    )


# Deletes unused show
@app.route(
    "/admin/shows/<int:show_id>/delete",
    methods=["POST"]
)
def admin_delete_show(show_id):

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute("""
            SELECT
                COUNT(*) AS booking_count

            FROM bookings

            WHERE show_id = %s
        """, (
            show_id,
        ))

        booking_count = (
            cursor.fetchone()[
                "booking_count"
            ]
        )

        if booking_count > 0:

            flash(
                "This show cannot be deleted because "
                "booking records already exist. "
                "Cancel the show instead."
            )

            return redirect(
                url_for(
                    "admin_shows"
                )
            )

        cursor.execute("""
            DELETE FROM shows
            WHERE show_id = %s
        """, (
            show_id,
        ))

        if cursor.rowcount == 0:

            connection.rollback()

            flash(
                "Show not found."
            )

            return redirect(
                url_for(
                    "admin_shows"
                )
            )

        connection.commit()

        flash(
            "Show deleted successfully."
        )

    except mysql.connector.Error as error:

        connection.rollback()

        print(
            "Delete show error:",
            error
        )

        flash(
            "Show could not be deleted."
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for(
            "admin_shows"
        )
    )


# Displays all bookings to admin
@app.route("/admin/bookings")
def admin_bookings():

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute("""
        SELECT
            b.booking_id,
            b.booking_time,
            b.total_amount,
            b.booking_status,

            u.full_name,
            u.email,

            m.title,

            sh.show_date,
            sh.show_time,

            sc.screen_name,

            t.theatre_name,
            t.city,

            GROUP_CONCAT(
                s.seat_number
                ORDER BY s.seat_number
                SEPARATOR ', '
            ) AS seats,

            p.payment_method,
            p.payment_status,
            p.payment_time,

            c.cancellation_time,
            c.refund_amount,
            c.refund_status

        FROM bookings b

        JOIN users u
            ON b.user_id = u.user_id

        JOIN shows sh
            ON b.show_id = sh.show_id

        JOIN movies m
            ON sh.movie_id = m.movie_id

        JOIN screens sc
            ON sh.screen_id = sc.screen_id

        JOIN theatres t
            ON sc.theatre_id = t.theatre_id

        LEFT JOIN booking_seats bs
            ON b.booking_id = bs.booking_id

        LEFT JOIN seats s
            ON bs.seat_id = s.seat_id

        LEFT JOIN payments p
            ON b.booking_id = p.booking_id

        LEFT JOIN cancellations c
            ON b.booking_id = c.booking_id

        GROUP BY
            b.booking_id,
            b.booking_time,
            b.total_amount,
            b.booking_status,
            u.full_name,
            u.email,
            m.title,
            sh.show_date,
            sh.show_time,
            sc.screen_name,
            t.theatre_name,
            t.city,
            p.payment_method,
            p.payment_status,
            p.payment_time,
            c.cancellation_time,
            c.refund_amount,
            c.refund_status

        ORDER BY b.booking_time DESC
    """)

    bookings = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_bookings.html",
        bookings=bookings
    )


# Admin analytics page
@app.route("/admin/analytics")
def admin_analytics():

    if not is_admin():

        flash(
            "Admin access required."
        )

        return redirect(
            url_for("home")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    # Successful revenue
    cursor.execute("""
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS total_revenue

        FROM payments

        WHERE payment_status = 'successful'
    """)

    total_revenue = cursor.fetchone()[
        "total_revenue"
    ]

    # Confirmed bookings
    cursor.execute("""
        SELECT
            COUNT(*) AS confirmed_bookings

        FROM bookings

        WHERE booking_status = 'confirmed'
    """)

    confirmed_bookings = cursor.fetchone()[
        "confirmed_bookings"
    ]

    # Pending bookings
    cursor.execute("""
        SELECT
            COUNT(*) AS pending_bookings

        FROM bookings

        WHERE booking_status = 'pending'
    """)

    pending_bookings = cursor.fetchone()[
        "pending_bookings"
    ]

    # Cancelled bookings
    cursor.execute("""
        SELECT
            COUNT(*) AS cancelled_bookings

        FROM bookings

        WHERE booking_status = 'cancelled'
    """)

    cancelled_bookings = cursor.fetchone()[
        "cancelled_bookings"
    ]

    # Current reserved seats
    cursor.execute("""
        SELECT
            COUNT(*) AS total_reserved_seats

        FROM booking_seats
    """)

    total_reserved_seats = cursor.fetchone()[
        "total_reserved_seats"
    ]

    # Refund amount
    cursor.execute("""
        SELECT
            COALESCE(
                SUM(refund_amount),
                0
            ) AS total_refunds

        FROM cancellations

        WHERE refund_status = 'processed'
    """)

    total_refunds = cursor.fetchone()[
        "total_refunds"
    ]

    # Most popular movies
    cursor.execute("""
        SELECT
            m.title,

            COUNT(
                DISTINCT b.booking_id
            ) AS booking_count,

            COUNT(
                bs.booking_seat_id
            ) AS tickets_sold

        FROM movies m

        LEFT JOIN shows sh
            ON m.movie_id = sh.movie_id

        LEFT JOIN bookings b
            ON sh.show_id = b.show_id
            AND b.booking_status = 'confirmed'

        LEFT JOIN booking_seats bs
            ON b.booking_id = bs.booking_id

        GROUP BY
            m.movie_id,
            m.title

        ORDER BY
            tickets_sold DESC,
            booking_count DESC,
            m.title

        LIMIT 10
    """)

    popular_movies = cursor.fetchall()

    # Revenue by movie
    cursor.execute("""
        SELECT
            m.title,

            COALESCE(
                SUM(p.amount),
                0
            ) AS revenue

        FROM movies m

        LEFT JOIN shows sh
            ON m.movie_id = sh.movie_id

        LEFT JOIN bookings b
            ON sh.show_id = b.show_id

        LEFT JOIN payments p
            ON b.booking_id = p.booking_id
            AND p.payment_status = 'successful'

        GROUP BY
            m.movie_id,
            m.title

        ORDER BY revenue DESC
    """)

    movie_revenue = cursor.fetchall()

    # Show occupancy
    cursor.execute("""
        SELECT
            sh.show_id,
            m.title,

            t.theatre_name,
            sc.screen_name,

            sh.show_date,
            sh.show_time,
            sh.status,

            COUNT(
                DISTINCT s.seat_id
            ) AS total_seats,

            COUNT(
                DISTINCT bs.seat_id
            ) AS booked_seats,

            CASE

                WHEN COUNT(
                    DISTINCT s.seat_id
                ) = 0

                THEN 0

                ELSE ROUND(
                    (
                        COUNT(
                            DISTINCT bs.seat_id
                        )
                        /
                        COUNT(
                            DISTINCT s.seat_id
                        )
                    ) * 100,
                    2
                )

            END AS occupancy_percentage

        FROM shows sh

        JOIN movies m
            ON sh.movie_id = m.movie_id

        JOIN screens sc
            ON sh.screen_id = sc.screen_id

        JOIN theatres t
            ON sc.theatre_id = t.theatre_id

        LEFT JOIN seats s
            ON sc.screen_id = s.screen_id

        LEFT JOIN booking_seats bs
            ON sh.show_id = bs.show_id
            AND s.seat_id = bs.seat_id

        GROUP BY
            sh.show_id,
            m.title,
            t.theatre_name,
            sc.screen_name,
            sh.show_date,
            sh.show_time,
            sh.status

        ORDER BY
            occupancy_percentage DESC,
            sh.show_date DESC,
            sh.show_time DESC
    """)

    show_occupancy = cursor.fetchall()

    cursor.close()
    connection.close()

    # Prepare Chart.js values
    movie_labels = [
        movie["title"]
        for movie in popular_movies
    ]

    movie_ticket_values = [
        movie["tickets_sold"]
        for movie in popular_movies
    ]

    revenue_movie_labels = [
        movie["title"]
        for movie in movie_revenue
    ]

    revenue_movie_values = [
        float(
            movie["revenue"]
        )
        for movie in movie_revenue
    ]

    return render_template(
        "admin_analytics.html",

        total_revenue=total_revenue,

        confirmed_bookings=confirmed_bookings,

        pending_bookings=pending_bookings,

        cancelled_bookings=cancelled_bookings,

        total_reserved_seats=total_reserved_seats,

        total_refunds=total_refunds,

        popular_movies=popular_movies,

        movie_revenue=movie_revenue,

        show_occupancy=show_occupancy,

        movie_labels=movie_labels,

        movie_ticket_values=movie_ticket_values,

        revenue_movie_labels=revenue_movie_labels,

        revenue_movie_values=revenue_movie_values
    )


# Starts Flask development server
if __name__ == "__main__":

    app.run(
        debug=os.environ.get("FLASK_DEBUG", "0") == "1"
    )