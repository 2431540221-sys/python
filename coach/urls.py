from django.urls import path

from . import views

urlpatterns = [
    path("coach/", views.coach_page, name="coach"),
    path("coach/generate/", views.coach_generate, name="coach_generate"),
    path("coach/ask/", views.coach_ask, name="coach_ask"),
]
