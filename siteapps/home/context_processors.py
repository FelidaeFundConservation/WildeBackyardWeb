from django.conf import settings


def backend_admin_url(request):
    return {"BACKEND_ADMIN_URL": f"{settings.BACKEND_API_URL}/admin/"}
