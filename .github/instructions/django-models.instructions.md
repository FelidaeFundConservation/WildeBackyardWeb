---
description: "Use when creating or editing Django models, views, migrations, or tests in this project. Covers model base classes, UUID keys, migrations workflow, uv run requirements, and BackendAPIClient patterns."
applyTo: "siteapps/**/*.py"
---

# Django Development Rules

## Terminal commands
Always prefix Django management commands with `uv run`:
```bash
uv run python manage.py <command> --settings=config.settings.local
```

## New models
Always extend `TimeStampedModel` with a UUID primary key:
```python
import uuid
from model_utils.models import TimeStampedModel

class MyModel(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # created and modified fields are added automatically
```

Use `django-simple-history` (`HistoricalRecords`) on models with sensitive or auditable data.

## After every model change
1. `uv run python manage.py makemigrations --settings=config.settings.local`
2. Review the generated migration file in `siteapps/<app>/migrations/`
3. `uv run python manage.py migrate --settings=config.settings.local`
4. Never hand-edit migration files unless fixing a known bug.

## Migrations are excluded from all linting
Never run `black`, `isort`, or `pycln` on `migrations/` directories.

## Views
- Use `APIView` (DRF) for JSON endpoints; use Django `View` for HTML-rendered pages.
- Validate inputs with reusable mixin methods that return a `Response` on failure or `None` on success.
- Gate HTML views with `@method_decorator(login_required, name="dispatch")`.

## Calling the Backend REST API
All data fetched from WildeBackyardBackend must go through `BackendAPIClient`:
```python
from siteapps.users.backend_api_client import BackendAPIClient

api = BackendAPIClient(auth_token=request.session.get('backend_api_token'))
result = api.get("/v1/some/endpoint/")
```
Never use `requests` directly to call the backend; always use `BackendAPIClient`.

## URL namespacing
Register each new URL with a `name` and ensure the app's `urls.py` is included with its `namespace` in `config/urls.py`. Use `reverse("namespace:name")` in Python and `{% url "namespace:name" %}` in templates.

## Privacy settings
Use the constants from `django.conf.settings`:
- `settings.PRIVACY_SETTING_PUBLIC`
- `settings.PRIVACY_SETTING_OBSCURED`
- `settings.PRIVACY_SETTING_PRIVATE`
Never hard-code the string values `"public"`, `"obscured"`, or `"private"`.
