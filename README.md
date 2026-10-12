# Smart Cinema Management, Dynamic Pricing & Recommendations

Third-year DBMS project using Flask, MySQL, Bootstrap and scikit-learn.

## Modules

- Customer registration/login, show scheduling, seat booking and simulated payments
- Database-based dynamic pricing, cancellation/refund simulation and reviews
- Content-based recommendations and admin analytics
- **Nearby theatres and showtimes:** city search or browser location, show dates/times, seats remaining, distance to theatres with saved coordinates

## Local setup (Windows / VS Code)

1. Install Python 3.11+ and MySQL Server + MySQL Workbench.
2. Open this `SmartCinema` folder in VS Code.
3. Terminal: `py -m venv venv` then `venv\Scripts\activate` (PowerShell: `venv\Scripts\Activate.ps1`).
4. Run: `pip install -r requirements.txt`.
5. Copy `.env.example` to `.env` and set `DB_PASSWORD` and a random `FLASK_SECRET_KEY`. Never commit `.env`.
6. **Existing database:** use Workbench to back up the database, then execute `database/migrate_nearby.sql` **once**. Don't run the old SQL file containing DROP DATABASE. **New database only:** run `database/schema.sql` in Workbench (creates empty tables).
7. Run: `python app.py`. Open http://127.0.0.1:5000/.
8. Admin > Theatres > Edit: enter the real theatre's latitude and longitude (both optional). Add a show for a **future date** using Admin > Shows, and ensure seats were created for its screen.
9. **For a fresh database only:** register a user, then promote it in MySQL Workbench with `UPDATE users SET role = 'admin' WHERE email = 'your_email@example.com';` (replace with your registered email). Sign out and back in to refresh the role.
10. Open http://127.0.0.1:5000/nearby. Search a city, or select **Use my location** (browser permission on localhost). Use the View & choose seats button to continue normal booking.

### Important usage notes
- Nearest ordering uses a Haversine straight-line distance in kilometres, **not driving distance**. Only theatres with coordinates can be ranked by distance; others are listed last.
- City filtering is available even when browser location is denied. Browser coordinates are used for the current search and are not stored in MySQL.
- Only future `scheduled` shows are listed; the older sample show dated `2026-10-10` is not upcoming.
- Seat count comes from physical `seats` minus reserved `booking_seats` records, preserving existing booking logic.
- Payments and refunds are **simulated**; this is an academic demo, not a live payment service.
- Use HTTPS and additional security checks before any production deployment.

## Add 16 movies and 6 sample theatres with showtimes

Run `database/add_demo_movies_theatres_showtimes.sql` in MySQL Workbench **after** setting up the schema and location columns. This adds 16 demo movies, six explicitly fictional demo theatres in Pune, 12 screens, 288 physical seats, and up to 168 shows scheduled across the upcoming seven days. See `ADD_MORE_DEMO_CONTENT.md` for complete instructions, safe reruns and browser verification. Movie/date filters on `/nearby` make the large schedule easier to browse.

## Postman registration test

`POST http://127.0.0.1:5000/register` with Body > raw > JSON:

```json
{ "full_name": "Test Student", "email": "new_student@example.com", "phone": "9876543210", "password": "Test1234" }
```

Expected for a new email: `201 Created`. Existing email: `409 Conflict`. Missing required fields: `400 Bad Request`. Website form submissions continue to work.

## GitHub

The `.gitignore` excludes local secrets, virtual environments and Python caches. Do **not** upload `.env`, `config.py` files containing a real password, SQL data dumps containing personal data, or `venv/`. Follow `GITHUB_UPLOAD_GUIDE.md`.

## Source ownership

Academic project by Satakshi Krishna and Rutu Vaghaisya.
