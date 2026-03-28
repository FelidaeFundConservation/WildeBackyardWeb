# Wilde Backyard Web — Copilot Instructions

## Overview

Django 5.0 **server-side-rendered web frontend** for the Wilde Backyard wildlife conservation platform. This app communicates with **WildeBackyardBackend** (separate Django REST API) for data and authentication — it is not a standalone backend.

**Stack:** Python 3.10+, Django 5.0.1, PostgreSQL (prod) / SQLite (local), Django REST Framework, `uv` package manager, GCP App Engine

## Project Layout

```
config/           # Django settings (base/local/prod/staging), urls.py, wsgi/
siteapps/
  home/           # Landing page and authenticated home views
  users/          # Auth, profiles, registration, password resets
  species/        # Wildlife species data (fetched from Backend API)
  sightings/      # Sighting submission forms and reverse geocoding
  socialmedia/    # Feed, posts, comments, likes, moderation
  templates/      # Django HTML templates (jinja-style with slippers components)
  static/         # Source static files
staticfiles/      # Collected static files (do not edit directly)
```

## Build & Run

```bash
# Install dependencies (uses uv lockfile)
uv sync
uv pip install -r requirements-dev.txt  # dev tools

# Run dev server
uv run python manage.py runserver --settings=config.settings.local

# Run migrations
uv run python manage.py migrate --settings=config.settings.local

# Collect static files
uv run python manage.py collectstatic --settings=config.settings.local --noinput
```

Default settings module: `config.settings.local`. Also available: `staging`, `prod`.

## Testing

```bash
pytest                              # all tests (uses config.settings.local)
pytest siteapps/species/            # single app
pytest -v -s                        # verbose
pytest --cov=siteapps --cov=config  # with coverage
```

Config in `pyproject.toml`: runs with `--reuse-db --no-migrations` for speed. Test files: `tests.py`, `test_*.py`, `*_tests.py`. Test class/method names must follow Django convention (`test_*`).

## Code Style

- **Formatter:** `black` — line length **120**, excludes `migrations/`
- **Imports:** `isort` — black profile, line length 120, excludes `migrations/`
- **Unused imports:** `pycln` — applied to `siteapps/` only
- **Pre-commit:** run `uv run pre-commit install` after cloning; hooks enforce all of the above plus JSON/YAML/TOML validation, private key detection, tab/CRLF prevention

Run manually: `uv run pre-commit run --all-files`

## Key Patterns

### BackendAPIClient — all external data goes through here
```python
from siteapps.users.backend_api_client import BackendAPIClient

api = BackendAPIClient(auth_token=request.session.get('backend_api_token'))
result = api.get("/v1/species/api/names/get/")
```

### Custom Authentication Backend
Auth in `siteapps/users/` verifies credentials against the Backend REST API, creates a local `User` record, and stores the token in `request.session['backend_api_token']`. Do **not** create Django passwords locally for normal users.

### DRF APIView for internal endpoints
```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class MyView(APIView):
    def post(self, request):
        return Response({"key": "value"}, status=status.HTTP_200_OK)
```

### Validation mixins
Reusable mixins like `LatLngValidationMixin` return a `Response` on failure or `None` on success. Check the return value before proceeding.

### Privacy settings (sightings/posts)
Three levels defined in `settings.base`:
- `PRIVACY_SETTING_PUBLIC` — full coordinates
- `PRIVACY_SETTING_OBSCURED` — obfuscated bounding box
- `PRIVACY_SETTING_PRIVATE` — no location data

### Models
Use `model_utils.TimeStampedModel` as base (adds `created`/`modified`). UUIDs as primary keys. `django-simple-history` for audit trails on sensitive models.

### URL namespacing
Every app has a `namespace` in `config/urls.py`. Use `reverse("appname:viewname")` and `{% url "appname:viewname" %}` consistently.

## Environment Variables

Copy `.env.example` to `.env`. Key vars:
- `DJANGO_SECRET_KEY`
- `BACKEND_API_URL` — URL of WildeBackyardBackend (default: `http://localhost:8000`)
- `DATABASE_URL_PROD` — PostgreSQL URL (prod only)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — optional OAuth
- `MAILGUN_API_KEY` — email (prod only)

## Deployment

GCP App Engine. Deploy from project root:
```bash
gcloud app deploy app.yaml --quiet
```

## Common Pitfalls

- **Use `uv run` or activate `.venv`** before any `manage.py` command — do not use system Python.
- **Migrations excluded from all linting** — never run black/isort on migration files.
- **Backend API must be running** for auth and data features to work locally; set `BACKEND_API_URL` in `.env`.
- **SQLite in local**, PostgreSQL in staging/prod — don't commit a modified `db.sqlite3`.
- **Static files**: `collectstatic` must be run before deployment; never edit `staticfiles/` directly.
