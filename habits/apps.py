from django.apps import AppConfig


class HabitsConfig(AppConfig):
    name = "habits"
    verbose_name = "Thói quen"

    def ready(self):
        from .scheduler import start_scheduler_if_needed

        start_scheduler_if_needed()
