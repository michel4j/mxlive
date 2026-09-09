from .registry import DashboardCard, CardRegistry, card_registry, register_card

default_app_config = 'mxlive.dashboard.apps.DashboardConfig'

__all__ = [
    'DashboardCard',
    'CardRegistry',
    'card_registry',
    'register_card',
]
