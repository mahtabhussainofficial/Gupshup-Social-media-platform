# Gupshup

### A production-minded social media platform built with FastAPI and PostgreSQL

Gupshup is a full-stack social media application that combines a clean, server-rendered web experience with a documented JSON API. Users can create accounts, publish posts, manage drafts, interact through likes and comments, maintain their profiles, upload profile pictures, and recover access through password-reset emails.

The project is intentionally designed as a practical, maintainable reference application: the web interface and API share the same authentication, validation, authorization, and database layers, so business rules are not duplicated across clients.

> **Project status:** Gupshup is a working learning and portfolio project with local Docker support, PostgreSQL-backed tests, database migrations, and an Azure deployment guide. Review the production limitations before using it for a public, high-traffic deployment.

---

## Contents

- [Highlights](#highlights)
- [Technology stack](#technology-stack)
- [How the application works](#how-the-application-works)
- [Feature overview](#feature-overview)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Docker development](#docker-development)
- [Testing](#testing)
- [API overview](#api-overview)
- [Web pages](#web-pages)
- [Project structure](#project-structure)
- [Data model](#data-model)
- [Security and privacy](#security-and-privacy)
- [Database migrations](#database-migrations)
- [Azure deployment](#azure-deployment)
- [Production considerations](#production-considerations)
- [Development workflow](#development-workflow)
- [Roadmap ideas](#roadmap-ideas)
- [License](#license)

---

## Highlights

- **Full-stack FastAPI application** with one codebase for frontend pages and REST-style JSON endpoints.
- **JWT bearer authentication** with login by either email address or username.
- **Post publishing workflow** with published posts and owner-only drafts.
- **Social interactions** including likes, comments, post search, sorting, and pagination.
- **Profile management** with bios, case-insensitive unique usernames, and validated profile pictures.
- **Password recovery** with expiring, single-use reset links and pluggable email delivery.
- **PostgreSQL-first persistence** using SQLAlchemy and Alembic.
- **Secure media handling** with image format validation, size limits, pixel limits, resizing, and randomized filenames.
- **Responsive server-rendered UI** using Jinja2 templates, CSS, and vanilla JavaScript.
- **Operational health endpoint** for Docker, Azure App Service, and monitoring integrations.
- **Real PostgreSQL test suite** instead of SQLite substitutes, ensuring database-specific behavior is exercised.
- **Containerized local environment** with PostgreSQL, persistent volumes, automatic migrations, and one-command startup.

## Technology stack

| Layer | Technology |
| --- | --- |
| Backend framework | FastAPI |
| ASGI server | Uvicorn |
| Database | PostgreSQL 16 |
| ORM and database access | SQLAlchemy 2 |
| Schema migrations | Alembic |
| Validation and settings | Pydantic 2, Pydantic Settings |
| Authentication | JWT via `python-jose`, bcrypt password hashing |
| HTML rendering | Jinja2 |
| Frontend | HTML, CSS, vanilla JavaScript |
| Image processing | Pillow |
| Email | Console backend for development or SMTP |
| Testing | Pytest, HTTPX, FastAPI `TestClient` |
| Local orchestration | Docker Compose |
| Cloud deployment | Microsoft Azure App Service and Azure Database for PostgreSQL |

---

## How the application works

Gupshup follows a simple layered architecture:

1. **Browser or API client** sends a request.
2. **FastAPI router** authenticates the request and applies endpoint-level authorization.
3. **Pydantic schema** validates incoming data and shapes outgoing responses.
4. **SQLAlchemy session** reads or writes PostgreSQL data.
5. **Response layer** returns JSON to API clients or renders a Jinja2 page for the browser.

The HTML pages are intentionally thin. The browser JavaScript calls the same API exposed to external clients, which keeps permissions, visibility rules, validation, and response behavior consistent.

### Request flow

```text
Browser / API client
        |
        v
FastAPI application
        |
        +--> Authentication and shared dependencies
        |
        +--> Pydantic validation
        |
        +--> Router business rules
        |
        +--> SQLAlchemy session
                    |
                    v
              PostgreSQL
```

---

## Feature overview

### Accounts and authentication

- Register with an email address, username, and password.
- Log in using either username or email.
- Receive a short-lived JWT access token.
- Change the current password after confirming the old password.
- Request a password-reset link without revealing whether an email is registered.
- Reset a password using a secure, expiring, single-use token.

### Posts

- Create, edit, and delete your own posts.
- Publish immediately or save a draft.
- Drafts remain invisible to other users and behave like not-found resources when accessed by unauthorized users.
- Browse posts with:
  - text search across title and content;
  - filtering by owner;
  - newest, oldest, top-voted, or most-discussed sorting;
  - bounded pagination;
  - total-result information through the `X-Total-Count` response header.

### Likes and comments

- Like a visible post once.
- Remove your own like.
- View and add comments on visible posts.
- A comment can be deleted by its author or by the owner of the related post.
- Post responses include vote count, comment count, and whether the current user has voted.

### Profiles and media

- View a user profile and published-post count.
- Update username and bio.
- Upload, replace, or remove a profile picture.
- Accept JPEG, PNG, and WebP uploads.
- Convert accepted images into normalized 400×400 JPEG files.

---

## Quick start

### Prerequisites

For native Windows development:

- Python 3.12 or newer
- PostgreSQL 16 running locally
- PowerShell

For the containerized workflow:

- Docker Desktop with Docker Compose

### 1. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation for the current session, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 3. Configure environment variables

Create a `.env` file in the repository root. At minimum, configure:

```dotenv
DATABASE_HOSTNAME=localhost
DATABASE_PORT=5432
DATABASE_NAME=socialdb
DATABASE_USERNAME=postgres
DATABASE_PASSWORD=your-postgres-password
SECRET_KEY=replace-with-a-long-random-secret
```

For a development password-reset flow, the default `EMAIL_BACKEND=console` is convenient: the reset link is printed in the terminal running Uvicorn. See [Configuration](#configuration) for all supported settings.

### 4. Apply database migrations

```powershell
alembic upgrade head
```

### 5. Start the development server

```powershell
uvicorn app.main:app --reload
```

Open:

- Website: <http://localhost:8000>
- Interactive Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health check: <http://localhost:8000/health>

The health endpoint returns a successful response only when the application can reach PostgreSQL:

```json
{
  "status": "ok",
  "database": "ok"
}
```

---

## Configuration

Settings are loaded from environment variables and `.env` through `pydantic-settings`. Environment variable names are case-insensitive.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | — | Full PostgreSQL URL; useful for Azure and hosted environments |
| `DATABASE_HOSTNAME` | empty | Local PostgreSQL host |
| `DATABASE_PORT` | `5432` | Local PostgreSQL port |
| `DATABASE_NAME` | empty | Local database name |
| `DATABASE_USERNAME` | empty | Local database username |
| `DATABASE_PASSWORD` | empty | Local database password |
| `SECRET_KEY` | required | Secret used to sign JWTs |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT lifetime |
| `APP_NAME` | `Gupshup` | Application/API title |
| `ENVIRONMENT` | `development` | Runtime environment label |
| `APP_BASE_URL` | `http://localhost:8000` | Base URL used in reset links |
| `CORS_ORIGINS` | local URLs | Comma-separated origins allowed for external browser clients |
| `RESET_TOKEN_EXPIRE_MINUTES` | `30` | Password-reset token lifetime |
| `MEDIA_DIR` | `media` | Directory used for profile pictures |
| `MAX_UPLOAD_MB` | `5` | Maximum profile-picture upload size |
| `EMAIL_BACKEND` | `console` | `console` for terminal output or `smtp` for real email |
| `EMAIL_FROM` | `no-reply@gupshup.local` | Sender address |
| `SMTP_HOST` | empty | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USERNAME` | empty | SMTP username |
| `SMTP_PASSWORD` | empty | SMTP password |
| `SMTP_USE_TLS` | `true` | Enable SMTP TLS |

### Generating a strong secret key

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Never commit `.env`, passwords, SMTP credentials, or production secrets to source control.

### Email backends

The console backend requires no setup and prints reset messages to the server log:

```dotenv
EMAIL_BACKEND=console
```

To send real messages, configure SMTP:

```dotenv
EMAIL_BACKEND=smtp
EMAIL_FROM=no-reply@example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_USE_TLS=true
```

---

## Docker development

Docker Compose starts an application container and a PostgreSQL 16 container. Database and media data are stored in named volumes.

1. Install Docker Desktop.
2. Ensure `.env` contains `DATABASE_PASSWORD` and `SECRET_KEY`.
3. Start the stack:

```powershell
docker compose up --build
```

4. Open <http://localhost:8000>.
5. Stop the stack:

```powershell
docker compose down
```

The web container waits for PostgreSQL to become healthy, runs `alembic upgrade head`, and then starts Uvicorn. To remove the persisted local database and media volumes as well:

```powershell
docker compose down -v
```

The `-v` option is destructive for local development data; do not use it when you need to preserve the database.

---

## Testing

Install development dependencies and run:

```powershell
pytest
```

The test suite uses a real PostgreSQL database because this project relies on PostgreSQL-specific behavior such as timezone-aware timestamps, database functions, and case-insensitive indexes. By default, tests target a separate database whose name ends with `_test`.

To point tests at a dedicated database explicitly:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://postgres:password@localhost:5432/socialdb_test"
pytest
```

### Test coverage areas

- Account registration, login, and user profile behavior
- Password changes and password-reset lifecycle
- Post visibility, drafts, ownership, editing, and deletion
- Search, sorting, pagination, and count headers
- Voting and duplicate-vote handling
- Comment creation, visibility, and deletion permissions
- HTML pages, static assets, and health checks
- Profile-picture validation and storage behavior

---

## API overview

All JSON API routes are documented automatically at `/docs` and `/redoc`. Protected routes require:

```http
Authorization: Bearer <access-token>
```

### Authentication

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/login` | Authenticate with username/email and password; returns a JWT |
| `POST` | `/forgot-password` | Request a password-reset email |
| `POST` | `/reset-password` | Set a new password using a reset token |

`/login` uses the OAuth2 form format with `username` and `password`. The `username` field accepts either a username or an email address.

### Users and profiles

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/users/` | Register a new user |
| `GET` | `/users/me` | Read the authenticated user |
| `PATCH` | `/users/me` | Update the authenticated user's username or bio |
| `POST` | `/users/me/password` | Change the authenticated user's password |
| `POST` | `/users/me/picture` | Upload or replace a profile picture |
| `DELETE` | `/users/me/picture` | Remove the profile picture |
| `GET` | `/users/{username}` | Read a public user profile |

### Posts

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/posts/` | Create a post or draft |
| `GET` | `/posts/` | List visible posts |
| `GET` | `/posts/{id}` | Read one visible post |
| `PUT` | `/posts/{id}` | Update an owned post |
| `DELETE` | `/posts/{id}` | Delete an owned post |

`GET /posts/` supports `limit`, `skip`, `search`, `owner`, and `sort` query parameters. Supported sort values are `newest`, `oldest`, `top`, and `discussed`. The endpoint returns `X-Total-Count`.

### Votes and comments

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/vote/` | Add or remove a vote using the request direction |
| `GET` | `/posts/{post_id}/comments` | List comments for a visible post |
| `POST` | `/posts/{post_id}/comments` | Add a comment |
| `DELETE` | `/comments/{comment_id}` | Delete a comment as its author or post owner |

### System

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Verify application and database availability |

---

## Web pages

The same FastAPI process serves the browser experience:

| URL | Page |
| --- | --- |
| `/` | Feed |
| `/login` | Login |
| `/register` | Registration |
| `/forgot-password` | Password-reset request |
| `/reset-password` | Password-reset form |
| `/account` | Account settings |
| `/post/{post_id}` | Post detail |
| `/u/{username}` | User profile |

Static assets are served under `/static`, and uploaded profile media is served under `/media`.

---

## Project structure

```text
.
├── app/
│   ├── main.py                 # FastAPI app, middleware, static mounts, health check
│   ├── config.py               # Environment-backed settings
│   ├── database.py             # SQLAlchemy engine, session, and declarative base
│   ├── models.py               # Users, posts, votes, comments, reset-token tables
│   ├── schemas.py              # Pydantic request and response models
│   ├── oauth2.py               # JWT creation and authenticated-user dependency
│   ├── dependencies.py         # Shared visibility and authorization dependencies
│   ├── mailer.py               # Console and SMTP email delivery
│   ├── images.py               # Image validation and normalization
│   ├── storage.py              # Profile-picture filesystem storage
│   ├── utils.py                # Password hashing and normalization helpers
│   ├── routers/
│   │   ├── auth.py             # Login and password reset
│   │   ├── users.py            # Registration and profile management
│   │   ├── posts.py            # Post CRUD, search, sorting, pagination
│   │   ├── comments.py         # Comment operations
│   │   ├── vote.py             # Like/unlike operations
│   │   └── pages.py            # Jinja2 page routes
│   ├── templates/              # Jinja2 HTML templates
│   └── static/
│       ├── css/style.css       # Application styles
│       ├── js/app.js           # Browser API integration
│       └── img/                # Default avatar and image assets
├── alembic/
│   └── versions/               # Versioned database migrations
├── tests/                      # PostgreSQL-backed Pytest suite
├── media/                      # Local uploaded profile pictures
├── Dockerfile                  # Application image
├── docker-compose.yml          # Local app + PostgreSQL stack
├── docker-entrypoint.sh        # Container migration/startup entrypoint
├── startup.sh                  # Azure App Service startup command
├── DEPLOY_AZURE.md             # Step-by-step Azure deployment guide
├── requirements.txt            # Runtime dependencies
├── requirements-dev.txt        # Runtime plus test dependencies
├── alembic.ini                 # Alembic configuration
└── pytest.ini                  # Pytest configuration
```

The local `venv/` directory is an environment artifact and should not be treated as application source code.

---

## Data model

The relational model is intentionally small and focused:

```text
Users
  ├──< Posts
  ├──< Comments
  ├──< Votes >── Posts
  └──< PasswordResetToken
```

### Main tables

- **`users`** — email, case-insensitive unique username, password hash, bio, profile-picture filename, and creation timestamp.
- **`posts`** — title, content, publication state, owner, and creation timestamp.
- **`votes`** — composite user/post key so a user can vote on a post only once.
- **`comments`** — comment content, post, author, and creation timestamp.
- **`password_reset_tokens`** — hashed reset token, owner, expiry time, and creation timestamp.

Posts, comments, votes, and reset tokens use cascading foreign keys where appropriate so deleted users and posts do not leave orphaned interaction records.

---

## Security and privacy

The project includes several defensive measures:

- Passwords are stored as bcrypt hashes, never as plaintext.
- Login uses the same generic error for an unknown account and a wrong password.
- User emails are not exposed in post responses.
- Password-reset requests return the same response whether or not an account exists.
- Reset tokens are generated from the operating system's secure random source.
- Only a SHA-256 hash of a reset token is stored in PostgreSQL.
- Reset tokens expire and are invalidated after use; requesting a new link removes older unused links.
- Profile uploads are checked by their decoded image format rather than their filename.
- Upload size and pixel-count limits reduce memory and decompression-bomb risk.
- Stored profile images use generated filenames and are re-encoded as clean JPEG files.
- Draft visibility is enforced at the API layer.
- Security response headers include Content Security Policy, `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy`.
- User-provided text is rendered without unsafe `innerHTML` usage in the browser client.

### Important production note

The browser currently keeps the JWT in `localStorage` for simplicity. For a higher-security public deployment, consider HttpOnly, Secure, SameSite cookies, CSRF protection, rate limiting, centralized media storage, stronger observability, and a token revocation strategy.

---

## Database migrations

Apply all migrations:

```powershell
alembic upgrade head
```

Create a new migration after changing SQLAlchemy models:

```powershell
alembic revision --autogenerate -m "describe the schema change"
```

Review autogenerated migrations carefully before applying them. To inspect the current migration:

```powershell
alembic current
```

To see migration history:

```powershell
alembic history
```

---

## Azure deployment

The repository includes a detailed guide in [`DEPLOY_AZURE.md`](./DEPLOY_AZURE.md). It documents two supported approaches:

1. **Code deployment to Linux App Service** — suitable for a low-cost learning/demo deployment.
2. **Container deployment** — uses the repository's Docker image and requires a paid App Service tier that supports custom containers.

The Azure deployment flow uses:

- Azure Database for PostgreSQL Flexible Server
- Azure App Service
- Environment variables for database, JWT, media, and SMTP configuration
- `startup.sh` to run migrations and start Uvicorn
- `/health` for post-deployment verification

Before deploying, set a production `SECRET_KEY`, use `ENVIRONMENT=production`, configure `APP_BASE_URL` with the real HTTPS URL, and never package `.env`, `.git`, `venv`, test data, or local media into a deployment archive.

---

## Production considerations

Before treating this project as a public production service, address the following:

- Add login and password-reset rate limiting.
- Use HttpOnly secure cookies or another hardened token-storage strategy.
- Move profile pictures to durable object storage such as Azure Blob Storage.
- Add structured logs, metrics, tracing, and alerting.
- Add background processing for email and other slow tasks.
- Add automated backups and a tested restore procedure.
- Add a reverse proxy or managed TLS termination appropriate to the hosting platform.
- Review CORS origins and do not use wildcard origins with credentials.
- Add pagination and indexing review for expected production data volumes.
- Rotate secrets through a managed secret store rather than checked-in configuration.
- Add CI checks for tests, migrations, dependency vulnerabilities, and container builds.

---

## Development workflow

1. Create or activate the virtual environment.
2. Install `requirements-dev.txt`.
3. Configure `.env`.
4. Start PostgreSQL, or use `docker compose up --build`.
5. Apply migrations with `alembic upgrade head`.
6. Make focused changes in the relevant router, schema, model, or template.
7. Run the targeted tests, then the full suite with `pytest`.
8. Review generated migrations and API behavior before opening a pull request.

When adding an endpoint:

- define request and response schemas;
- enforce authentication and ownership rules explicitly;
- add a route-level test for success and authorization failures;
- document the endpoint in this README if it changes the public API;
- update migrations when the data model changes.

---

## Roadmap ideas

Potential future improvements include:

- Follow/follower relationships and personalized feeds
- Notifications for likes, comments, and password events
- Refresh tokens and server-side token revocation
- Moderation, reporting, and content-management tools
- Real-time notifications with WebSockets
- Object storage for media and CDN delivery
- Search indexing for larger datasets
- CI/CD automation and preview deployments
- Accessibility and internationalization improvements

These are ideas, not promises of currently implemented functionality.

---

## License

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
