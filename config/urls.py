from django.urls import include, path

from accounts import views as account_views

urlpatterns = [
    path("", account_views.home, name="home"),
    path("api/", include("config.api_urls")),
    path("", include("accounts.urls")),
    path("", include("habits.urls")),
    path("", include("tracking.urls")),
    path("", include("insights.urls")),
    path("", include("coach.urls")),
]
