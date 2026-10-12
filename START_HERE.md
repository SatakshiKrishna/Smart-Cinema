# Smart Cinema — START HERE

This ZIP is the full **Flask + MySQL** DBMS project. You do not need the old 128-MB ZIP or its virtual environment. Open **this `SmartCinema` folder** in VS Code, not the surrounding ZIP extraction folder.

## 1. Install tools

- Python 3.11 or 3.12
- MySQL Server and MySQL Workbench
- VS Code with the Python extension

## 2. Open VS Code terminal inside `SmartCinema`

In Windows PowerShell:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell says execution of scripts is disabled, use **Command Prompt** instead:

```cmd
venv\Scripts\activate.bat
```

On macOS/Linux: `python3 -m venv venv`, `source venv/bin/activate`, then `python -m pip install -r requirements.txt`.

## 3. Make your private environment file

1. In VS Code copy `.env.example` to `.env` (Windows Command Prompt: `copy .env.example .env`).
2. Edit `.env` and put your **actual MySQL password** in `DB_PASSWORD`.
3. Set `DB_USER` and `DB_HOST` if different from `root` and `localhost`.
4. Replace `FLASK_SECRET_KEY` with a long random string.
5. **Never add `.env` to GitHub.** `.gitignore` excludes it.

## 4. Choose exactly ONE database setup path

### A. Existing `smart_cinema` database (you want to KEEP bookings)

1. **Backup** your existing database using Workbench > Server > Data Export.
2. Check columns: `USE smart_cinema; DESCRIBE theatres;`.
3. If latitude and longitude are **missing**, run **`database/migrate_nearby.sql` ONCE** in Workbench.
4. If both columns already exist, **skip** the migration.
5. Run `database/add_demo_movies_theatres_showtimes.sql` to add additional movies, 6 fictional theatres, seats and upcoming showtimes.
6. **NEVER run the old `Smart_cinema.sql`**, which starts with DROP DATABASE and would delete your data.

### B. Fresh installation (you have NO existing bookings to preserve)

1. In Workbench execute `database/schema.sql` to create the schema.
2. Next execute `database/add_demo_movies_theatres_showtimes.sql` to populate movie/theatre/show/seat demonstration data.
3. Do **not** run `migrate_nearby.sql` after the fresh schema; those columns are already present.
4. Run the application, **register an admin account**, then run this SQL in Workbench with your own new email:

   ```sql
   USE smart_cinema;
   UPDATE users SET role='admin' WHERE email='your_email@example.com';
   ```

5. Sign out and sign in again before opening the Admin dashboard.

### Note on demo data

The 6 demo theatres are **fictional**. Movie shows are **sample schedules**, generated for the next 7 days relative to the day you execute the seed script, **not official cinema schedules**. If the show list is empty a week later, rerun the sample script to create new future dates; it avoids duplicate date/time slots on the same screen.

## 5. Check MySQL setup safely

```bash
python scripts/check_setup.py
```

The check is read-only. It reports missing tables or columns, record counts, and future show counts.

## 6. Run the website

```bash
python app.py
```

Open the following URLs in your browser:

- Home / movies: http://127.0.0.1:5000/
- **Nearby theatres, showtimes, remaining seats:** http://127.0.0.1:5000/nearby
- Registration: http://127.0.0.1:5000/register
- Admin: http://127.0.0.1:5000/admin (admin login required)

Search by **Pune** to see the demo theatres. Choose **Use my location** to sort by approximate *straight-line* distance (permission optional). Click **View & choose seats** to continue the existing customer booking process.

## 7. Postman registration demonstration

Set method **POST**, URL `http://127.0.0.1:5000/register`, Body > raw > JSON:

```json
{
  "full_name":"Test Student",
  "email":"unique_student@example.com",
  "phone":"9876543210",
  "password":"Test1234"
}
```

A new unique email should return **201 Created**. Use a different email on each trial.

## 8. Upload to GitHub

Read `GITHUB_UPLOAD_GUIDE.md`. GitHub holds the **source code and SQL scripts**, but not your local live MySQL data. The virtual environment (`venv/`) and secret `.env` are excluded.

## Project folder map

| File/folder | Purpose |
|---|---|
| `app.py` | Flask routes: customers, booking, pricing, payments, reviews, admin, nearby shows |
| `config.py`, `.env.example` | MySQL configuration without real passwords |
| `recommendation/recommendation_engine.py` | TF-IDF and cosine similarity recommendation engine |
| `templates/` | Complete customer/admin HTML templates |
| `static/css`, `static/js` | Styles and interactive UI |
| `database/schema.sql` | Fresh 13-table database schema and MySQL routine definitions |
| `database/migrate_nearby.sql` | Adds coordinates to an existing database; **run only if missing** |
| `database/add_demo_movies_theatres_showtimes.sql` | Additional movies, demo theatres, physical seats, seven days of showtimes |
| `scripts/check_setup.py` | Read-only database status check |
| `docs/` | College report and presentation resources |

Payment/refund operations are simulated; this is an academic project, not a production ticketing service.
