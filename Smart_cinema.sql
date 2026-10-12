-- Remove the old database so we can start fresh during testing.
-- Be careful because this deletes all existing data.
DROP DATABASE smart_cinema;

-- Create the database for the cinema booking project.
CREATE DATABASE smart_cinema;

-- Select the database before creating tables.
USE smart_cinema;


-- Stores customer and admin account details.
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(15),
    role ENUM('customer', 'admin') DEFAULT 'customer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Check the tables created in the database.
SHOW TABLES;

-- Check the structure of the users table.
DESCRIBE users;

-- Add a sample user for testing.
INSERT INTO users (
    full_name,
    email,
    password_hash,
    phone,
    role
)
VALUES (
    'Test User',
    'test@example.com',
    'temporary_password',
    '9876543210',
    'customer'
);

-- Verify that the user was inserted correctly.
SELECT * FROM users;


-- Stores movie details.
CREATE TABLE movies (
    movie_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    language VARCHAR(50) NOT NULL,
    duration_minutes INT NOT NULL,
    release_date DATE,
    age_rating VARCHAR(10),
    poster_url VARCHAR(500),
    status ENUM('upcoming', 'now_showing', 'ended')
        DEFAULT 'upcoming',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Check the structure of the movies table.
DESCRIBE movies;

-- Add a sample movie.
INSERT INTO movies (
    title,
    description,
    language,
    duration_minutes,
    release_date,
    age_rating,
    status
)
VALUES (
    'Interstellar',
    'A science fiction movie about space exploration.',
    'English',
    169,
    '2014-11-07',
    'UA',
    'now_showing'
);

-- View the movies stored in the database.
SELECT * FROM movies;


-- Stores theatre details such as name, city and address.
CREATE TABLE theatres (
    theatre_id INT AUTO_INCREMENT PRIMARY KEY,
    theatre_name VARCHAR(150) NOT NULL,
    city VARCHAR(100) NOT NULL,
    address VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add a sample theatre.
INSERT INTO theatres (
    theatre_name,
    city,
    address
)
VALUES (
    'CineMax Central',
    'Pune',
    'MG Road, Pune'
);

-- Verify the theatre data.
SELECT * FROM theatres;


-- Stores screens inside each theatre.
-- A theatre can have multiple screens.
CREATE TABLE screens (
    screen_id INT AUTO_INCREMENT PRIMARY KEY,
    theatre_id INT NOT NULL,
    screen_name VARCHAR(50) NOT NULL,
    total_seats INT NOT NULL,

    FOREIGN KEY (theatre_id)
        REFERENCES theatres(theatre_id)
        ON DELETE CASCADE
);

-- Add one sample screen.
INSERT INTO screens (
    theatre_id,
    screen_name,
    total_seats
)
VALUES (
    1,
    'Screen 1',
    100
);

-- Verify the screen data.
SELECT * FROM screens;


-- Stores movie genres separately to keep the database normalized.
CREATE TABLE genres (
    genre_id INT AUTO_INCREMENT PRIMARY KEY,
    genre_name VARCHAR(50) NOT NULL UNIQUE
);

-- Add some common movie genres.
INSERT INTO genres (genre_name)
VALUES
('Action'),
('Comedy'),
('Drama'),
('Sci-Fi'),
('Thriller'),
('Romance');

-- Check the genre IDs before using them.
SELECT * FROM genres;


-- Junction table for the many-to-many relationship
-- between movies and genres.
CREATE TABLE movie_genres (
    movie_id INT NOT NULL,
    genre_id INT NOT NULL,

    PRIMARY KEY (movie_id, genre_id),

    FOREIGN KEY (movie_id)
        REFERENCES movies(movie_id)
        ON DELETE CASCADE,

    FOREIGN KEY (genre_id)
        REFERENCES genres(genre_id)
        ON DELETE CASCADE
);

-- Link the sample movie to a genre.
-- The movie_id and genre_id must already exist.
INSERT INTO movie_genres (
    movie_id,
    genre_id
)
VALUES (
    1,
    4
);

-- Check the movie-genre relationship.
SELECT * FROM movie_genres;

-- Display each movie together with its genre.
SELECT
    m.title,
    g.genre_name
FROM movies m
JOIN movie_genres mg
    ON m.movie_id = mg.movie_id
JOIN genres g
    ON mg.genre_id = g.genre_id;


-- Stores scheduled movie shows.
-- Each show belongs to one movie and one screen.
CREATE TABLE shows (
    show_id INT AUTO_INCREMENT PRIMARY KEY,
    movie_id INT NOT NULL,
    screen_id INT NOT NULL,
    show_date DATE NOT NULL,
    show_time TIME NOT NULL,
    base_price DECIMAL(10,2) NOT NULL,
    status ENUM('scheduled', 'cancelled', 'completed')
        DEFAULT 'scheduled',

    FOREIGN KEY (movie_id)
        REFERENCES movies(movie_id)
        ON DELETE CASCADE,

    FOREIGN KEY (screen_id)
        REFERENCES screens(screen_id)
        ON DELETE CASCADE
);

-- Check available movie IDs.
SELECT movie_id, title FROM movies;

-- Check available screen IDs.
SELECT screen_id, screen_name FROM screens;

-- Schedule a sample show.
INSERT INTO shows (
    movie_id,
    screen_id,
    show_date,
    show_time,
    base_price
)
VALUES (
    1,
    1,
    '2026-10-10',
    '18:30:00',
    200.00
);

-- Verify the show details.
SELECT * FROM shows;


-- Stores the physical seats available in each screen.
CREATE TABLE seats (
    seat_id INT AUTO_INCREMENT PRIMARY KEY,
    screen_id INT NOT NULL,
    seat_number VARCHAR(10) NOT NULL,
    seat_type ENUM('regular', 'premium', 'recliner')
        DEFAULT 'regular',

    FOREIGN KEY (screen_id)
        REFERENCES screens(screen_id)
        ON DELETE CASCADE,

    UNIQUE (screen_id, seat_number)
);

-- Add sample seats for Screen 1.
INSERT INTO seats (screen_id, seat_number, seat_type)
VALUES
(1, 'A1', 'regular'),
(1, 'A2', 'regular'),
(1, 'A3', 'regular'),
(1, 'A4', 'regular'),
(1, 'B1', 'premium'),
(1, 'B2', 'premium'),
(1, 'B3', 'premium'),
(1, 'B4', 'premium'),
(1, 'C1', 'recliner'),
(1, 'C2', 'recliner');

-- Verify the seat layout.
SELECT * FROM seats;


-- Stores the main booking record for a user and a show.
CREATE TABLE bookings (
    booking_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    show_id INT NOT NULL,
    booking_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10,2) NOT NULL,
    booking_status ENUM(
        'pending',
        'confirmed',
        'cancelled'
    ) DEFAULT 'pending',

    FOREIGN KEY (user_id)
        REFERENCES users(user_id),

    FOREIGN KEY (show_id)
        REFERENCES shows(show_id)
);


-- Stores the seats included in each booking.
CREATE TABLE booking_seats (
    booking_seat_id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    seat_id INT NOT NULL,
    ticket_price DECIMAL(10,2) NOT NULL,

    FOREIGN KEY (booking_id)
        REFERENCES bookings(booking_id)
        ON DELETE CASCADE,

    FOREIGN KEY (seat_id)
        REFERENCES seats(seat_id),

    UNIQUE (booking_id, seat_id)
);


-- Stores payment information for each booking.
CREATE TABLE payments (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL UNIQUE,
    amount DECIMAL(10,2) NOT NULL,
    payment_method ENUM(
        'upi',
        'card',
        'cash',
        'net_banking'
    ) NOT NULL,
    payment_status ENUM(
        'pending',
        'successful',
        'failed',
        'refunded'
    ) DEFAULT 'pending',
    payment_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (booking_id)
        REFERENCES bookings(booking_id)
        ON DELETE CASCADE
);

-- Check all tables created so far.
SHOW TABLES;

-- Check sample data before creating a booking.
SELECT * FROM users;
SELECT * FROM shows;
SELECT * FROM seats;


-- Create a sample booking.
INSERT INTO bookings (
    user_id,
    show_id,
    total_amount,
    booking_status
)
VALUES (
    1,
    1,
    400.00,
    'confirmed'
);

-- Verify the booking.
SELECT * FROM bookings;


-- Add two seats to the booking.
INSERT INTO booking_seats (
    booking_id,
    seat_id,
    ticket_price
)
VALUES
(1, 1, 200.00),
(1, 2, 200.00);

-- Verify the booked seats.
SELECT * FROM booking_seats;


-- Add a successful payment for the booking.
INSERT INTO payments (
    booking_id,
    amount,
    payment_method,
    payment_status
)
VALUES (
    1,
    400.00,
    'upi',
    'successful'
);

-- Verify the payment.
SELECT * FROM payments;


-- Display a complete booking summary using joins.
SELECT
    b.booking_id,
    u.full_name,
    m.title,
    t.theatre_name,
    s.screen_name,
    sh.show_date,
    sh.show_time,
    se.seat_number,
    bs.ticket_price,
    p.payment_status
FROM bookings b
JOIN users u
    ON b.user_id = u.user_id
JOIN shows sh
    ON b.show_id = sh.show_id
JOIN movies m
    ON sh.movie_id = m.movie_id
JOIN screens s
    ON sh.screen_id = s.screen_id
JOIN theatres t
    ON s.theatre_id = t.theatre_id
JOIN booking_seats bs
    ON b.booking_id = bs.booking_id
JOIN seats se
    ON bs.seat_id = se.seat_id
LEFT JOIN payments p
    ON b.booking_id = p.booking_id;


-- Add show_id to booking_seats so each booked seat
-- can be tied directly to a particular show.
ALTER TABLE booking_seats
ADD COLUMN show_id INT;


-- Temporarily disable safe update mode.
SET SQL_SAFE_UPDATES = 0;

-- Copy the show_id from bookings into existing booking_seats rows.
UPDATE booking_seats bs
JOIN bookings b
ON bs.booking_id = b.booking_id
SET bs.show_id = b.show_id;

-- Turn safe update mode back on.
SET SQL_SAFE_UPDATES = 1;


-- Make show_id compulsory for every booked seat.
ALTER TABLE booking_seats
MODIFY show_id INT NOT NULL;


-- Add a foreign key for show_id.
ALTER TABLE booking_seats
ADD CONSTRAINT fk_booking_seat_show
FOREIGN KEY (show_id)
REFERENCES shows(show_id)
ON DELETE CASCADE;


-- Prevent the same seat from being booked twice for the same show.
ALTER TABLE booking_seats
ADD CONSTRAINT unique_show_seat
UNIQUE (show_id, seat_id);


-- Test double-booking protection.
-- This query is intentionally commented because running it should fail.
-- It proves that the same seat cannot be booked again for the same show.

-- INSERT INTO booking_seats (
--     booking_id,
--     show_id,
--     seat_id,
--     ticket_price
-- )
-- VALUES (
--     1,
--     1,
--     1,
--     200.00
-- );


-- Stores cancellation and refund details.
CREATE TABLE cancellations (
    cancellation_id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL UNIQUE,
    cancellation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    refund_amount DECIMAL(10,2) DEFAULT 0.00,
    refund_status ENUM(
        'pending',
        'processed',
        'rejected'
    ) DEFAULT 'pending',

    FOREIGN KEY (booking_id)
        REFERENCES bookings(booking_id)
        ON DELETE CASCADE
);

-- Check the cancellation table structure.
DESCRIBE cancellations;


-- Stores user ratings and reviews for movies.
CREATE TABLE reviews (
    review_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    movie_id INT NOT NULL,
    rating INT NOT NULL,
    review_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE,

    FOREIGN KEY (movie_id)
        REFERENCES movies(movie_id)
        ON DELETE CASCADE,

    UNIQUE (user_id, movie_id),

    CHECK (rating BETWEEN 1 AND 5)
);


-- Add a sample review.
INSERT INTO reviews (
    user_id,
    movie_id,
    rating,
    review_text
)
VALUES (
    1,
    1,
    5,
    'Excellent movie'
);

-- Verify the review data.
SELECT * FROM reviews;


-- Calculate the average rating for each movie.
SELECT
    m.title,
    ROUND(AVG(r.rating), 2) AS average_rating
FROM movies m
LEFT JOIN reviews r
ON m.movie_id = r.movie_id
GROUP BY m.movie_id, m.title;


-- Create a reusable view containing movie rating statistics.
CREATE VIEW movie_ratings_view AS
SELECT
    m.movie_id,
    m.title,
    ROUND(AVG(r.rating), 2) AS average_rating,
    COUNT(r.review_id) AS total_reviews
FROM movies m
LEFT JOIN reviews r
ON m.movie_id = r.movie_id
GROUP BY m.movie_id, m.title;


-- Test the ratings view.
SELECT * FROM movie_ratings_view;

-- Show all tables and views.
SHOW TABLES;

-- Display only database views.
SHOW FULL TABLES
WHERE Table_type = 'VIEW';


-- Calculate the occupancy percentage for a particular show.
SELECT
    sh.show_id,
    sc.total_seats,
    COUNT(bs.seat_id) AS booked_seats,
    ROUND(
        COUNT(bs.seat_id) * 100.0 / sc.total_seats,
        2
    ) AS occupancy_percentage
FROM shows sh
JOIN screens sc
    ON sh.screen_id = sc.screen_id
LEFT JOIN booking_seats bs
    ON sh.show_id = bs.show_id
WHERE sh.show_id = 1
GROUP BY sh.show_id, sc.total_seats;


-- Change the delimiter so MySQL can read the function correctly.
DELIMITER $$

-- Calculates ticket price based on show occupancy.
CREATE FUNCTION calculate_ticket_price(
    p_show_id INT
)
RETURNS DECIMAL(10,2)
DETERMINISTIC
BEGIN
    DECLARE v_base_price DECIMAL(10,2);
    DECLARE v_total_seats INT;
    DECLARE v_booked_seats INT;
    DECLARE v_occupancy DECIMAL(5,2);
    DECLARE v_final_price DECIMAL(10,2);

    -- Get the base price and screen capacity for the show.
    SELECT
        sh.base_price,
        sc.total_seats
    INTO
        v_base_price,
        v_total_seats
    FROM shows sh
    JOIN screens sc
        ON sh.screen_id = sc.screen_id
    WHERE sh.show_id = p_show_id;

    -- Count how many seats are already booked.
    SELECT COUNT(*)
    INTO v_booked_seats
    FROM booking_seats
    WHERE show_id = p_show_id;

    -- Calculate occupancy percentage.
    SET v_occupancy =
        (v_booked_seats * 100.0) / v_total_seats;

    -- Increase the price when occupancy becomes higher.
    IF v_occupancy <= 30 THEN
        SET v_final_price = v_base_price;
    ELSEIF v_occupancy <= 60 THEN
        SET v_final_price = v_base_price * 1.10;
    ELSEIF v_occupancy <= 80 THEN
        SET v_final_price = v_base_price * 1.20;
    ELSE
        SET v_final_price = v_base_price * 1.30;
    END IF;

    RETURN v_final_price;
END$$

DELIMITER ;

-- Test the dynamic pricing function.
SELECT calculate_ticket_price(1);


DELIMITER $$

-- Stored procedure to create a confirmed booking.
CREATE PROCEDURE create_booking(
    IN p_user_id INT,
    IN p_show_id INT,
    IN p_total_amount DECIMAL(10,2)
)
BEGIN
    INSERT INTO bookings (
        user_id,
        show_id,
        total_amount,
        booking_status
    )
    VALUES (
        p_user_id,
        p_show_id,
        p_total_amount,
        'confirmed'
    );
END$$

DELIMITER ;

-- Test the stored procedure.
CALL create_booking(1, 1, 200.00);

-- Verify the new booking.
SELECT * FROM bookings;


DELIMITER $$

-- Automatically confirms a booking after a successful payment.
CREATE TRIGGER trg_payment_success
AFTER INSERT ON payments
FOR EACH ROW
BEGIN
    IF NEW.payment_status = 'successful' THEN
        UPDATE bookings
        SET booking_status = 'confirmed'
        WHERE booking_id = NEW.booking_id;
    END IF;
END$$

DELIMITER ;


-- Create a pending booking to test the trigger.
INSERT INTO bookings (
    user_id,
    show_id,
    total_amount,
    booking_status
)
VALUES (
    1,
    1,
    200.00,
    'pending'
);


-- Get the newest booking so we can check its booking_id.
SELECT * FROM bookings
ORDER BY booking_id DESC
LIMIT 1;


-- Add a successful payment for the pending booking.
INSERT INTO payments (
    booking_id,
    amount,
    payment_method,
    payment_status
)
VALUES (
    3,
    200.00,
    'upi',
    'successful'
);


-- Check whether the trigger changed the status to confirmed.
SELECT booking_id, booking_status
FROM bookings
WHERE booking_id = 3;


-- View user details after testing registration from Flask.
SELECT
    user_id,
    full_name,
    email,
    password_hash,
    phone,
    role
FROM users;

SELECT * FROM bookings;

SELECT * FROM booking_seats;

SELECT * FROM payments;

SELECT
    booking_id,
    booking_status
FROM bookings;

SELECT
    booking_id,
    user_id,
    total_amount,
    booking_status,
    booking_time
FROM bookings;

SELECT * FROM cancellations;

SELECT
    booking_id,
    booking_status
FROM bookings;

SELECT
    booking_id,
    payment_status
FROM payments;

-- Admin Panel
UPDATE users
SET role = 'admin'
WHERE user_id = 2;

SELECT
    user_id,
    full_name,
    email,
    role
FROM users;

SELECT * FROM movies;

SELECT * FROM theatres;

SELECT * FROM screens;

SELECT
    sh.show_id,
    m.title,
    t.theatre_name,
    sc.screen_name,
    sh.show_date,
    sh.show_time,
    sh.base_price,
    sh.status
FROM shows sh
JOIN movies m
    ON sh.movie_id = m.movie_id
JOIN screens sc
    ON sh.screen_id = sc.screen_id
JOIN theatres t
    ON sc.theatre_id = t.theatre_id
ORDER BY sh.show_id;

SELECT
    b.booking_id,
    u.full_name,
    m.title,
    b.total_amount,
    b.booking_status,
    p.payment_status,
    c.refund_status
FROM bookings b
JOIN users u
    ON b.user_id = u.user_id
JOIN shows sh
    ON b.show_id = sh.show_id
JOIN movies m
    ON sh.movie_id = m.movie_id
LEFT JOIN payments p
    ON b.booking_id = p.booking_id
LEFT JOIN cancellations c
    ON b.booking_id = c.booking_id
ORDER BY b.booking_id DESC;

SELECT * FROM movies;
SELECT * FROM genres;
SELECT * FROM movie_genres;

SELECT
    m.movie_id,
    m.title,
    GROUP_CONCAT(g.genre_name) AS genres
FROM movies m
LEFT JOIN movie_genres mg
    ON m.movie_id = mg.movie_id
LEFT JOIN genres g
    ON mg.genre_id = g.genre_id
GROUP BY
    m.movie_id,
    m.title;
    
-- Add sample movies for recommendation testing

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
VALUES

(
    'Inception',
    'A skilled thief enters dreams to steal secrets and is given a chance to erase his past by planting an idea.',
    'English',
    148,
    '2010-07-16',
    'UA',
    '',
    'now_showing'
),

(
    'The Matrix',
    'A computer hacker discovers that reality is a simulated world and joins a rebellion against intelligent machines.',
    'English',
    136,
    '1999-03-31',
    'UA',
    '',
    'now_showing'
),

(
    'Dune',
    'A young noble travels to a dangerous desert planet where powerful families fight over a valuable resource.',
    'English',
    155,
    '2021-10-22',
    'UA',
    '',
    'now_showing'
),

(
    'The Dark Knight',
    'Batman faces a criminal mastermind who spreads chaos across Gotham City and challenges his sense of justice.',
    'English',
    152,
    '2008-07-18',
    'UA',
    '',
    'now_showing'
),

(
    'Avengers: Endgame',
    'The surviving heroes unite for one final mission to reverse the destruction caused by a powerful enemy.',
    'English',
    181,
    '2019-04-26',
    'UA',
    '',
    'now_showing'
),

(
    'Titanic',
    'Two passengers from different social backgrounds fall in love aboard the famous ocean liner during its tragic voyage.',
    'English',
    195,
    '1997-12-19',
    'UA',
    '',
    'now_showing'
),

(
    'Joker',
    'A struggling man in Gotham City descends into violence and becomes a symbol of chaos.',
    'English',
    122,
    '2019-10-04',
    'A',
    '',
    'now_showing'
),

(
    '3 Idiots',
    'Three engineering students navigate friendship, academic pressure and their search for a meaningful life.',
    'Hindi',
    170,
    '2009-12-25',
    'UA',
    '',
    'now_showing'
);

SELECT
    user_id,
    full_name,
    email,
    role
FROM users;

UPDATE users
SET role = 'admin'
WHERE email = 'satakshiwh@gmail.com';

DROP FUNCTION IF EXISTS calculate_ticket_price;

DELIMITER $$

CREATE FUNCTION calculate_ticket_price(p_show_id INT)
RETURNS DECIMAL(10,2)
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_base_price DECIMAL(10,2);
    DECLARE v_screen_id INT;
    DECLARE v_total_seats INT DEFAULT 0;
    DECLARE v_booked_seats INT DEFAULT 0;
    DECLARE v_occupancy DECIMAL(5,2) DEFAULT 0;
    DECLARE v_final_price DECIMAL(10,2);

    -- Get the show's base price and screen
    SELECT base_price, screen_id
    INTO v_base_price, v_screen_id
    FROM shows
    WHERE show_id = p_show_id;

    -- Count the actual seat records created for this screen
    SELECT COUNT(*)
    INTO v_total_seats
    FROM seats
    WHERE screen_id = v_screen_id;

    -- Count seats already reserved for this show
    SELECT COUNT(*)
    INTO v_booked_seats
    FROM booking_seats
    WHERE show_id = p_show_id;

    -- Avoid division by zero
    IF v_total_seats = 0 THEN
        RETURN v_base_price;
    END IF;
    SET v_occupancy = (v_booked_seats / v_total_seats) * 100;

    -- Dynamic pricing rules
    IF v_occupancy <= 30 THEN
        SET v_final_price = v_base_price;
    ELSEIF v_occupancy <= 60 THEN
        SET v_final_price = v_base_price * 1.10;
    ELSEIF v_occupancy <= 80 THEN
        SET v_final_price = v_base_price * 1.20;
    ELSE
        SET v_final_price = v_base_price * 1.30;
    END IF;
    RETURN ROUND(v_final_price, 2);
END$$
DELIMITER ;

SELECT
    show_id,
    movie_id,
    screen_id,
    base_price
FROM shows;

SELECT calculate_ticket_price(1) AS current_ticket_price;
SELECT
    s.show_id,
    s.base_price,
    COUNT(DISTINCT st.seat_id) AS total_actual_seats,
    COUNT(DISTINCT bs.seat_id) AS booked_seats,
    ROUND(
        COUNT(DISTINCT bs.seat_id)
        / NULLIF(COUNT(DISTINCT st.seat_id), 0)
        * 100,
        2
    ) AS occupancy_percentage,
    calculate_ticket_price(s.show_id) AS dynamic_price
FROM shows s
JOIN seats st
    ON st.screen_id = s.screen_id
LEFT JOIN booking_seats bs
    ON bs.show_id = s.show_id
GROUP BY
    s.show_id,
    s.base_price;
    
SELECT show_id, status
FROM shows
WHERE show_id = 1;

SELECT
    booking_id,
    show_id,
    booking_status
FROM bookings
WHERE show_id = 1;

SELECT
    booking_id,
    payment_status,
    amount
FROM payments
WHERE booking_id IN (
    SELECT booking_id
    FROM bookings
    WHERE show_id = 1
);

SELECT *
FROM cancellations
WHERE booking_id IN (
    SELECT booking_id
    FROM bookings
    WHERE show_id = 1
);

SELECT *
FROM booking_seats
WHERE show_id = 1;