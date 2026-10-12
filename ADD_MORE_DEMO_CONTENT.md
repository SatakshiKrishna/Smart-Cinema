# Add More Movies, Theatres, Showtimes and Seats

The complete starter data file is `database/add_demo_movies_theatres_showtimes.sql`.

This is **fictional demonstration content** for a college DBMS project. Movie titles refer to real films, but the six `SmartCinema Demo - ...` theatres are invented and their dates/timings are **not real-world movie listings**. Their latitude/longitude values are approximate Pune neighbourhood centres.

## What gets added

| Item | Added to an otherwise empty database |
|---|---:|
| Movies | 16 |
| Demo theatres | 6 (Kothrud, Baner, Viman Nagar, Hadapsar, Wakad and Camp) |
| Screens | 12 (2 in each demo theatre) |
| Physical seats | 288 (24 per screen) |
| Scheduled shows | Up to 168 (7 upcoming days × 4 shows × 6 theatres) |

The script checks for matching existing movies, theatres, screens, seats and scheduled slots before inserting. Counts may be lower if some matching records already exist. Running it again on the same day will not create duplicate showtime slots. Running it on another day can extend the future schedule with additional dates.

## Step 1: Back up existing data

In MySQL Workbench, open **Server → Data Export**, select `smart_cinema`, and export a backup before making changes. **Do not run the old `Smart_cinema.sql` file: it contains `DROP DATABASE smart_cinema` and will delete your data.**

## Step 2: Check the nearby-location migration

Run this in Workbench:

```sql
USE smart_cinema;
DESCRIBE theatres;
```

If you already see `latitude` and `longitude`, do **not** rerun `database/migrate_nearby.sql`.

If those two columns are missing, run `database/migrate_nearby.sql` **once**.

For a completely fresh install, run `database/schema.sql` instead of the migration, then continue.

## Step 3: Add movies, demo theatres, physical seats and timings

1. Open `database/add_demo_movies_theatres_showtimes.sql` in MySQL Workbench.
2. Select the full script and press the **Execute** (lightning) button.
3. Wait for the SQL statements to finish. The verification queries at the end will show counts and sample schedules.
4. No changes to `app.py` are needed just to add the sample rows.

## Step 4: Test in the browser

1. Start Flask with `python app.py` from the `SmartCinema` directory.
2. Open `http://127.0.0.1:5000/` and find the additional movie cards.
3. Open `http://127.0.0.1:5000/nearby`, enter **Pune**, and click **Find shows**.
4. Use the **Filter by movie** and **Show date** menus to narrow the displayed results.
5. Click **View & choose seats** on a show. Log in if asked; the chosen screen has 24 physical seat records.
6. Optionally click **Use my location**; browser permission is optional. Distance is straight-line approximation, not driving distance.

## Demo showtimes

Each of the six demo theatres gets these sample times **for each of the next seven days**:

- **Demo Screen 1:** 11:00 AM and 6:30 PM
- **Demo Screen 2:** 2:15 PM and 9:15 PM

The movie is rotated through the 16-film catalogue so users can browse different options. The dynamic ticket price is still calculated by MySQL when the user selects seats.

## Step 5: Upload updated code to GitHub

The SQL seed script and updated `templates/nearby.html` are already inside the ZIP. Upload the **entire new project folder** following `GITHUB_UPLOAD_GUIDE.md`.

Never upload `.env`, `venv/`, database passwords, or database exports containing real user details. **GitHub stores the code and SQL scripts, not the live records inside your MySQL server.** Anyone cloning the project must run the schema and sample data scripts on their own MySQL instance.
