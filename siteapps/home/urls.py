# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.

from django.urls import path

from .views import HomeView, InstructionsView

app_name = "home"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("instructions/", InstructionsView.as_view(), name="instructions"),
]
