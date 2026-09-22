# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.

"""
WSGI config for project_restoration project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os
from pathlib import Path

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.staging")

application = get_wsgi_application()

# Wrap with Whitenoise to serve static files
from whitenoise import WhiteNoise
BASE_DIR = Path(__file__).resolve().parent.parent.parent
application = WhiteNoise(application, root=str(BASE_DIR / "staticfiles"))
