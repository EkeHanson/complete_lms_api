# groups/apps.py
from django.apps import AppConfig

class GroupsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'groups'

    def ready(self):
        # Import and register signals
        from . import signals