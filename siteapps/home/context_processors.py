# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.

from django.conf import settings


def backend_admin_url(request):
    return {"BACKEND_ADMIN_URL": f"{settings.BACKEND_API_URL}/admin/"}


def fundraiseup(request):
    return {
        "fundraiseup_account_key": settings.FUNDRAISEUP_ACCOUNT_KEY,
        "fundraiseup_form": settings.FUNDRAISEUP_FORM,
    }
