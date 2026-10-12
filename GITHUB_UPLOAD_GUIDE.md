# Upload Smart Cinema to GitHub — Beginner Guide

**Before starting:** Use the updated ZIP. Do not upload your old 13,000-file ZIP because it includes `venv/`.

## 1. Open the updated project

Extract the updated ZIP. Open the resulting `SmartCinema` folder in VS Code.

## 2. Set up secrets locally

Copy `.env.example` to `.env` and enter your own MySQL password and a long random Flask secret. `.env` is intentionally excluded from Git. Never add passwords or real user data to a repository.

## 3. Set up the database

Open MySQL Workbench. If you already have `smart_cinema` with your bookings, **BACK UP FIRST**, then run `database/migrate_nearby.sql` **once**, not `schema.sql`. `schema.sql` is for a fresh database and contains no live personal records.

**Sample data:** After the schema/location columns are ready, run `database/add_demo_movies_theatres_showtimes.sql` in Workbench to load 16 movies and multiple sample theatres/showtimes. Full steps: `ADD_MORE_DEMO_CONTENT.md`.

## 4. Check it locally

```powershell
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `/nearby` and confirm your city search and seat availability. If using a fresh database, first register and promote your own account to admin from MySQL Workbench: `UPDATE users SET role = 'admin' WHERE email = 'your_email@example.com';` Then sign out and sign in again. Log in as admin to add real theatre coordinates.

## 5. Create repository

Sign in at https://github.com. Choose **New repository**. Name it `SmartCinema-DBMS`. Pick Private while reviewing, then optionally change visibility later. Do not initialize with a README (this folder already has one). Click Create repository.

## 6. Push from VS Code terminal

Run these commands *inside the SmartCinema folder* (replace placeholders):

```bash
git init
git add .
git status
git commit -m "Smart Cinema DBMS project with nearby show finder"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/SmartCinema-DBMS.git
git push -u origin main
```

If prompted, sign in using Git Credential Manager/browser. GitHub no longer accepts your normal account password for command-line HTTPS authentication.

## 7. Verify carefully

Open the repository in your browser. Make sure `app.py`, `templates/`, `static/`, `database/`, `README.md` are visible. Verify there is **no `.env`**, **no `venv/`**, and no real password. If sensitive information was ever pushed, rotate that password and remove it from Git history (deleting it in a later commit is not enough).

## 8. Updates later

```bash
git add .
git commit -m "Improve nearby shows"
git push
```

Share the finished repository URL with your teammate and paste it in the report's GitHub placeholder.
