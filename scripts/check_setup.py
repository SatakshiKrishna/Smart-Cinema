"""Read-only MySQL setup check for the SmartCinema project.

Run from the project root after creating .env and setting up the database:
    python scripts/check_setup.py

It never creates, changes, or deletes user records.
"""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

REQUIRED_TABLES = {
    'users', 'movies', 'theatres', 'screens', 'genres', 'movie_genres',
    'shows', 'seats', 'bookings', 'booking_seats', 'payments',
    'cancellations', 'reviews',
}


def main():
    try:
        import mysql.connector
        from config import DB_CONFIG
    except ImportError as exc:
        print('Missing Python package:', exc)
        print('Install dependencies first: python -m pip install -r requirements.txt')
        return 1

    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        cursor.execute('SHOW TABLES')
        tables = {row[0] for row in cursor.fetchall()}
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            print('ERROR: Missing tables:', ', '.join(missing))
            print('For a fresh database run database/schema.sql.')
            return 1
        print('OK: All 13 cinema tables exist.')

        cursor.execute('SHOW COLUMNS FROM theatres')
        columns = {row[0] for row in cursor.fetchall()}
        if not {'latitude', 'longitude'}.issubset(columns):
            print('ERROR: Theatre location columns are missing.')
            print('Existing database: run database/migrate_nearby.sql once (after backup).')
            return 1
        print('OK: Theatre location columns exist.')

        cursor.execute('SHOW COLUMNS FROM booking_seats')
        b_columns = {row[0] for row in cursor.fetchall()}
        if 'show_id' not in b_columns:
            print('ERROR: booking_seats.show_id is missing; use the final schema.')
            return 1
        print('OK: booking_seats.show_id exists.')

        for name in ('movies', 'theatres', 'screens', 'seats', 'shows'):
            cursor.execute('SELECT COUNT(*) FROM `' + name + '`')
            print(f'{name}: {cursor.fetchone()[0]} records')
        cursor.execute('''
            SELECT COUNT(*) FROM shows
            WHERE status = 'scheduled'
              AND (show_date > CURRENT_DATE()
                   OR (show_date = CURRENT_DATE() AND show_time >= CURRENT_TIME()))
        ''')
        upcoming = cursor.fetchone()[0]
        print('Upcoming scheduled shows:', upcoming)
        if not upcoming:
            print('TIP: Run database/add_demo_movies_theatres_showtimes.sql for sample shows.')

        cursor.execute("SHOW FUNCTION STATUS WHERE Db = DATABASE() AND Name = 'calculate_ticket_price'")
        if not cursor.fetchone():
            print('WARNING: calculate_ticket_price function not found.')
        else:
            print('OK: Dynamic pricing function is available.')
        cursor.execute("SHOW TRIGGERS LIKE 'payments'")
        triggers = {row[0] for row in cursor.fetchall()}
        if 'trg_payment_success' not in triggers:
            print('WARNING: Payment success trigger not found.')
        else:
            print('OK: Payment trigger is available.')
        print('Setup check completed. Open http://127.0.0.1:5000/nearby after starting Flask.')
        return 0
    except mysql.connector.Error as exc:
        print('MySQL check failed:', exc)
        print('Check MySQL Server, .env credentials, and database setup.')
        return 1
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


if __name__ == '__main__':
    raise SystemExit(main())
