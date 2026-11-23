from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/read/", views.notifications_read, name="notifications_read"),
    path("notifications/push-subscription/", views.push_subscription, name="push_subscription"),
    path("service-worker.js", views.service_worker, name="service_worker"),
]
