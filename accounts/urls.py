from django.urls import path

from . import views

urlpatterns = [
    path("accounts/register/", views.register_view, name="register"),
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/logout/", views.logout_view, name="logout"),
    path("accounts/profile/", views.profile_view, name="user_profile"),
    path("privacy/", views.privacy_redirect, name="privacy"),
    path("accounts/profile/delete-data/", views.delete_data_view, name="delete_data"),
    path("accounts/profile/delete-account/", views.delete_account_view, name="delete_account"),
    path("admin-stats/", views.admin_stats_view, name="admin_stats"),
]
