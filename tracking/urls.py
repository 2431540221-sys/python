from django.urls import path

from . import views

urlpatterns = [
    path("checkin/", views.checkin, name="checkin"),
    path("history/", views.history, name="history"),
    path("checkin/<int:pk>/delete/", views.checkin_delete, name="checkin_delete"),
    path("journal/", views.journal_list, name="journal_list"),
    path("journal/new/", views.journal_create, name="journal_create"),
    path("journal/<int:pk>/", views.journal_detail, name="journal_detail"),
    path("journal/<int:pk>/edit/", views.journal_update, name="journal_update"),
    path("journal/<int:pk>/delete/", views.journal_delete, name="journal_delete"),
]
