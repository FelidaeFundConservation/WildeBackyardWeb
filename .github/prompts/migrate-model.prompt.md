---
description: "Add a new Django model to a siteapps app: model class, migrations, tests, and optional BackendAPIClient wiring"
argument-hint: "Describe the model: name, app, and fields (e.g. 'WildlifeAlert in socialmedia with title, body, severity')"
agent: "agent"
---

Add a new Django model to this project following all project conventions.

**Model specification:** {{model description from user}}

## Step 1 — Define the model

In `siteapps/<app>/models.py`, add a class that:
- Extends `TimeStampedModel` (from `model_utils.models`)
- Uses a `UUIDField` as primary key (`default=uuid.uuid4, editable=False`)
- Adds `HistoricalRecords` if the model holds sensitive or user-generated data
- Uses `settings.PRIVACY_SETTING_*` constants for any privacy-related choice fields

## Step 2 — Register in admin (if appropriate)

Add `@admin.register(MyModel)` in `siteapps/<app>/admin.py`.

## Step 3 — Create migrations

```bash
uv run python manage.py makemigrations --settings=config.settings.local
```

Review the generated file, then apply:
```bash
uv run python manage.py migrate --settings=config.settings.local
```

Do **not** lint migration files.

## Step 4 — Write tests

In `siteapps/<app>/tests.py` (or `test_<model>.py`), add test cases that:
- Create model instances and verify `created`/`modified` are set
- Test any custom `save()` logic or model methods
- Use `rest_framework.test.APIClient` for endpoint tests

Run: `pytest siteapps/<app>/`

## Step 5 — Expose via API (if needed)

- Add an `APIView` in `views.py`
- Register the URL with a `name` in `urls.py`
- Include the URL under the app's namespace in `config/urls.py`
- If the data originates from WildeBackyardBackend, fetch it via `BackendAPIClient`

## Step 6 — Verify

```bash
pytest                              # all tests pass
uv run pre-commit run --all-files   # no linting errors
```
