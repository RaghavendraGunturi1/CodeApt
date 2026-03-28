from django.apps import AppConfig


class AssessmentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assessments'

    def ready(self):
        # Register signals for automatic attempt-counter creation.
        from . import signals  # noqa: F401
