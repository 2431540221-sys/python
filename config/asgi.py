import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django_application = get_asgi_application()

from coach_service.api import api_app as fastapi_application

fastapi_application.mount("/", django_application)
application = fastapi_application
