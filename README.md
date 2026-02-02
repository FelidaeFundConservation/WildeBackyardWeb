# Wilde Backyard Web

Django web application for Wilde Backyard project.

## Setup

This project uses `uv` for package management.

### Installation

```bash
# Install dependencies
uv sync

# Install development dependencies
uv pip install -r requirements-dev.txt

# Install pre-commit hooks
uv run pre-commit install
```

### Running the Application

```bash
# Run development server
uv run python manage.py runserver

# Run with specific settings
uv run python manage.py runserver --settings=config.settings.local
```

### Testing

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=siteapps --cov=config
```

### Pre-commit Hooks

This project uses pre-commit hooks for code quality:

```bash
# Install hooks
uv run pre-commit install

# Run hooks manually
uv run pre-commit run --all-files
```

## Project Structure

- `config/` - Django configuration
- `siteapps/` - Application modules
- `staticfiles/` - Static files

## Development

- Python 3.10+
- Django 5.0+
- PostgreSQL database
