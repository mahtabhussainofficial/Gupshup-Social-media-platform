# Deploying to Microsoft Azure (student account)

> **Honest status:** the app, Docker files and migrations were tested locally (see README). These Azure steps
> follow Microsoft's documented behaviour but were **not run against a real Azure subscription** by the person
> who wrote them. Expect to hit one or two portal surprises. When you do, copy the exact error text and ask.

## What Azure gives students (checked November 2026)

- **Azure for Students:** a $100 credit valid for 12 months, no credit card, renewable yearly while you are a
  student. Re-check the offer page yourself; Microsoft changes these programs.
- **PostgreSQL Flexible Server, Burstable B1ms:** Microsoft's free-services list includes 750 hours/month, 32 GB
  storage and 32 GB backup for 12 months. The storage meter counts the **provisioned** size, so choose 32 GB, not more.
- **App Service Free (F1):** 60 CPU-minutes/day, 1 GB RAM, 1 GB storage, no SLA, no custom domain or SSL.
  It runs **Python code**, but **not custom Docker containers**. Running a Docker image on App Service needs
  at least the **Basic (B1)** plan, which uses your credit.

## Pick one path

| | Path A: code deploy | Path B: Docker image |
|---|---|---|
| App Service plan | **F1 (free)** | B1 or higher (uses credit, roughly a monthly cost) |
| Uses your Dockerfile | no | yes |
| Good for | learning, a live demo link for your CV | showing real container skills |
| Limitation | stops for the day after 60 CPU-minutes; app sleeps when idle | credit drains while it runs |

Start with **Path A** to get a live URL cheaply. Do **Path B** later, or run the Docker stack locally with
`docker compose up --build` to demonstrate Docker without paying anything.

## Step 0: protect your credit

1. Portal → **Cost Management → Budgets** → create a budget of $20 with an email alert.
2. Put everything in **one resource group** (`gupshup-rg` below). When finished experimenting, deleting the
   resource group deletes everything inside it and stops all charges.
3. Choose a **region** and use it for everything. If the portal says a region is not allowed for your
   subscription or that PostgreSQL is unavailable there, pick another region from the list it offers.

## Step 1: database (both paths)

Azure CLI (install it, then `az login`). Replace the values in `< >`. Use a strong password made of letters and digits
to avoid URL-escaping problems.

```powershell
az group create --name gupshup-rg --location <region>

az postgres flexible server create `
  --resource-group gupshup-rg --name <unique-db-name> --location <region> `
  --tier Burstable --sku-name Standard_B1ms --storage-size 32 --version 16 `
  --admin-user gupshupadmin --admin-password <DB_PASSWORD> `
  --database-name gupshup --public-access 0.0.0.0
```

`--public-access 0.0.0.0` adds the firewall rule that lets *Azure services* (your web app) connect. To also run
migrations or `psql` from your own computer, add your IP: Portal → your server → **Networking → Add current client IP**.

Your connection string (this app converts it to the psycopg driver automatically):

```
postgresql://gupshupadmin:<DB_PASSWORD>@<unique-db-name>.postgres.database.azure.com:5432/gupshup?sslmode=require
```

## Step 2A: web app, code deploy (free F1)

```powershell
az appservice plan create --resource-group gupshup-rg --name gupshup-plan --is-linux --sku F1

az webapp create --resource-group gupshup-rg --plan gupshup-plan `
  --name <unique-app-name> --runtime "PYTHON:3.12"

az webapp config appsettings set --resource-group gupshup-rg --name <unique-app-name> --settings `
  SCM_DO_BUILD_DURING_DEPLOYMENT=true `
  SECRET_KEY=<64-hex-chars> `
  DATABASE_URL="postgresql://gupshupadmin:<DB_PASSWORD>@<unique-db-name>.postgres.database.azure.com:5432/gupshup?sslmode=require" `
  ENVIRONMENT=production `
  APP_BASE_URL=https://<unique-app-name>.azurewebsites.net `
  CORS_ORIGINS=https://<unique-app-name>.azurewebsites.net `
  MEDIA_DIR=/home/media

az webapp config set --resource-group gupshup-rg --name <unique-app-name> --startup-file "startup.sh"
```

Generate `SECRET_KEY` with `python -c "import secrets; print(secrets.token_hex(32))"`. Never reuse your local one.

Deploy: zip the project **contents** (not the parent folder, and without `venv`, `.env`, `.git`, `media`, `tests`),
then:

```powershell
az webapp deploy --resource-group gupshup-rg --name <unique-app-name> --src-path app.zip --type zip
```

Open `https://<unique-app-name>.azurewebsites.net/health`. You want `{"status":"ok","database":"ok"}`.
If not: Portal → your web app → **Log stream** shows the startup errors (`alembic` failures, missing settings).

`/home` is the folder App Service keeps across restarts, so uploaded profile pictures survive restarts there.
Confirm in the portal that your files are still there after a restart before relying on it.

## Step 2B: web app, Docker image (B1 or higher)

1. Build and push an image to a registry. Easiest: a free public repository on Docker Hub or GitHub Container
   Registry (`docker build -t <you>/gupshup:1 .` then `docker push`). Never put secrets inside the image.
2. Create a **B1** plan (`--sku B1`) and a web app with `--deployment-container-image-name <you>/gupshup:1`.
3. Settings: the same as Step 2A (minus `SCM_DO_BUILD_DURING_DEPLOYMENT`), plus `WEBSITES_PORT=8000` and
   `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true` (keeps `/home` persistent), with `MEDIA_DIR=/home/media`.
4. The container's entrypoint already runs `alembic upgrade head` and then starts the server.

## Email on Azure

The default `EMAIL_BACKEND=console` only prints to the logs, so users would never receive a reset link.
For a live demo set `EMAIL_BACKEND=smtp` plus `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
`EMAIL_FROM` as app settings. Any SMTP provider works. Gmail works for learning if you turn on 2-step
verification and create an **App Password** (never your real password).

## HTTPS, Nginx and reverse proxies (concepts, since you asked for them)

- On App Service, Azure's front end already terminates **HTTPS/TLS** for `*.azurewebsites.net` and forwards plain
  HTTP to your container. That is a **reverse proxy**. It is why the start command has `--proxy-headers`:
  the app trusts the `X-Forwarded-*` headers to learn the original request was HTTPS.
- On your own Linux server you would run **Nginx** in front of the app: Nginx holds the TLS certificate
  (free from Let's Encrypt), serves static files, and forwards other requests to `uvicorn` on localhost.
- A custom domain with its own certificate is a paid or higher-tier feature on App Service (not on F1).
  You do not need one for learning.

## Known limits of this setup

- Login tokens last 30 minutes with no refresh, and a password reset does not invalidate tokens already issued.
- No rate limiting on login or password reset yet.
- Profile pictures live on the app's disk, not in blob storage.
