from django.urls import path

from .views import landing_page

app_name = "marketing"

urlpatterns = [
    path("", landing_page, name="landing"),
]
