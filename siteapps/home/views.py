from django.utils import timezone
from django.views.generic import TemplateView

from siteapps.users.models import User


class HomeView(TemplateView):
    def get_template_names(self):
        if not self.request.user.is_authenticated:
            return ["home/landing.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        if user.is_authenticated:
            pass

        return context

    template_name = "home/home.html"


class InstructionsView(TemplateView):
    """Landing page for WildeBackyard instructions and user guide."""

    template_name = "home/instructions.html"
