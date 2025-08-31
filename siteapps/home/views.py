from datetime import timedelta

from django.utils import timezone
from django.views.generic import TemplateView

from siteapps.users.models import User


class HomeView(TemplateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        if user.is_authenticated:
            pass

        return context

    template_name = "home/home.html"
