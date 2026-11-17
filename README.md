# Movie Ticket Booking System

## Group members

- ATUMANYIRE ASHELLY (223-063061-37676)
- KAJJUBI RAMATHAN (223-063061-37670)
- NALYANYA ARON (225-063061-37815)

## About

A Django application for managing movie theaters, halls, seats, movies, showtimes, clients, and ticket bookings. It includes a dashboard, reports, user profiles, and role management.

## Run locally

From the project root on Windows:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Create an account from the signup page or sign in to Django Admin at `/admin/`.

The local development database has a superuser with username `admin` and password `admin123`. This password is weak and must not be reused for a public deployment.

## Tests

```powershell
python manage.py test
```

## Deploy to Render

Create a new Blueprint from this repository and use the included `render.yaml`. Render provisions the web service and PostgreSQL database. The service runs database migrations on startup and collects static assets during the build.

Set a strong, unique superuser password in the deployed database; the local SQLite superuser is not included in the repository. Uploaded media is stored on the service filesystem and may not persist across redeploys, so configure durable media storage before relying on uploads in production.
