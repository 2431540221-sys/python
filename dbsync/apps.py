from django.apps import AppConfig


class DbSyncConfig(AppConfig):
    name = "dbsync"
    verbose_name = "Database synchronization"

    def ready(self):
        from . import signals

        signals.register()
