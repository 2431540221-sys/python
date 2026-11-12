from django.urls import path

from . import views

urlpatterns = [
    path("habits/", views.habit_list, name="habit_list"),
    path("habits/new/", views.habit_create, name="habit_create"),
    path("habits/<int:pk>/", views.habit_detail, name="habit_detail"),
    path("habits/<int:pk>/edit/", views.habit_update, name="habit_update"),
    path("habits/<int:pk>/delete/", views.habit_delete, name="habit_delete"),
    path("habits/<int:pk>/toggle/", views.habit_toggle, name="habit_toggle"),
]
