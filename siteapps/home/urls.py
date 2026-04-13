from django.urls import path

from .views import HomeView, InstructionsView

app_name = "home"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("instructions/", InstructionsView.as_view(), name="instructions"),
]
