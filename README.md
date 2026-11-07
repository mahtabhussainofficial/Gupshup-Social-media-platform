# Gupshup: a social media app built with FastAPI and PostgreSQL

A full-stack learning project: JSON API + server-rendered HTML pages in one FastAPI app.

**Features:** registration and login (JWT, bcrypt) · posts with drafts · likes · comments · profile pages ·
profile pictures (validated and resized) · password reset by email · search, sorting and pagination ·
Alembic migrations · 50+ Pytest tests against real PostgreSQL · Docker · Azure deployment guide.

## Run it locally (Windows 11, PowerShell)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env          # then edit .env: your Postgres password and a SECRET_KEY
alembic upgrade head            # creates/updates the tables
uvicorn app.main:app --reload
```

Open http://localhost:8000 (the website) or http://localhost:8000/docs (interactive API docs).
With the default `EMAIL_BACKEND=console`, password-reset emails are **printed in the terminal** where uvicorn runs.

## Run the tests

```powershell
pytest
```

Tests use a separate database named `<DATABASE_NAME>_test`, created automatically, so your real data is never touched.

## Run with Docker

Install Docker Desktop (free for personal and educational use), make sure `.env` has `DATABASE_PASSWORD` and
`SECRET_KEY`, then:

```powershell
docker compose up --build
```

The stack contains the app and its own PostgreSQL. Migrations run automatically on start.

## Project layout

```
app/
  main.py          app setup, middleware, /health
  config.py        all settings, read from environment variables / .env
  database.py      engine and session
  models.py        tables: users, posts, votes, comments, password_reset_tokens
  schemas.py       request/response shapes and validation (Pydantic)
  oauth2.py        JWT creation and checking
  mailer.py        sending email (console or SMTP)
  images.py        validating/resizing uploaded pictures
  storage.py       where uploaded files are saved (swap this file for cloud storage later)
  dependencies.py  shared checks (e.g. "is this post visible to me?")
  routers/         auth, users, posts, comments, vote, pages
  templates/       Jinja2 HTML pages        static/  CSS, JS, default avatar
alembic/versions/  database migrations      tests/   Pytest suite
Dockerfile, docker-compose.yml, docker-entrypoint.sh, startup.sh, DEPLOY_AZURE.md
```

## Design decisions worth knowing

- **One source of truth:** the HTML pages call the same JSON API as any other client; permissions and validation live only in the routers.
- **Privacy:** other users never see your email; drafts are invisible (404) to everyone but the owner.
- **Passwords:** bcrypt hashes, 8–72 byte limit; reset tokens are random, expire in 30 minutes, work once, and only their SHA-256 hash is stored.
- **Uploads:** the real image format is checked with Pillow (not the file name), size and pixel limits apply, and the image is re-encoded as a clean 400×400 JPEG under a random name.
- **Counts:** likes and comments are separate subqueries so a post with 3 likes and 4 comments never shows 12.
- **Tokens in the browser:** the login token is kept in `localStorage` (simple and fine for learning). The pages never use `innerHTML` for user text, which is what protects against XSS. A production site might prefer HttpOnly cookies.

## Breaking changes compared with the original API

- Registration now requires a `username`; emails are stored lowercase; passwords need 8–72 bytes.
- `owner.email` was removed from post responses (replaced by `owner.username` and `owner.image_url`).
- Posts default to `published: true` (before, an omitted value created a draft).
- Wrong login returns **401** instead of 403. `GET /` now returns the website; use `/health` for a JSON check.
- `GET /posts/` also returns `comments` and `voted`, and the `X-Total-Count` header.
