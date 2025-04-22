from django.apps import AppConfig

class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'course_analytics'

    def ready(self):
        import course_analytics.signals  # Load signals