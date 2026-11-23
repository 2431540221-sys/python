from django.urls import path

from . import views

urlpatterns = [
    path("accounts/register/", views.register_view, name="register"),
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/logout/", views.logout_view, name="logout"),
    path("privacy/", views.privacy_view, name="privacy"),
    path("privacy/export/", views.export_view, name="export_data"),
    path("privacy/delete-data/", views.delete_data_view, name="delete_data"),
    path("privacy/delete-account/", views.delete_account_view, name="delete_account"),
    path("privacy/sample-data/", views.sample_data_view, name="sample_data"),
    path("admin-stats/", views.admin_stats_view, name="admin_stats"),
]
