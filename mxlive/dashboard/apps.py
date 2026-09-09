from django.apps import AppConfig


class DashboardConfig(AppConfig):
    name = 'mxlive.dashboard'
    label = 'dashboard'
    verbose_name = 'Dashboard'

    def ready(self):
        from .registry import card_registry
        card_registry.autodiscover()
