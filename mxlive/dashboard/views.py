from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, View
from basiclive.core.lims.conf import settings as lims_cfg
from .registry import card_registry


class BaseDashboardView(LoginRequiredMixin, TemplateView):
    """
    Base view for rendering modular dashboard cards.
    """
    role = 'user'

    def get_cards(self):
        return card_registry.get_cards(request=self.request, role=self.role)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cards = self.get_cards()
        context.update({
            'cards': cards,
            'left_cards': [c for c in cards if c.column == 'left'],
            'center_cards': [c for c in cards if c.column == 'center'],
            'right_cards': [c for c in cards if c.column == 'right'],
            'full_cards': [c for c in cards if c.column == 'full'],
        })

        if lims_cfg.USE_SCHEDULE:
            try:
                from basiclive.core.schedule.models import AccessType
                context['access_types'] = AccessType.objects.all()
            except ImportError:
                context['access_types'] = []

        return context


class UserDashboardView(BaseDashboardView):
    """
    User dashboard displaying user shipments, recent sessions, beamtime, and guides.
    """
    template_name = 'dashboard/user_dashboard.html'
    role = 'user'


class StaffDashboardView(UserPassesTestMixin, BaseDashboardView):
    """
    Staff dashboard displaying beamline controls, automounters, connections, and staff shipments.
    """
    template_name = 'dashboard/staff_dashboard.html'
    role = 'staff'

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or user.is_staff)


class DashboardIndexView(LoginRequiredMixin, View):
    """
    Role-dispatching root dashboard view.
    Dispatches staff/superusers to StaffDashboardView and regular users to UserDashboardView.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.is_superuser or request.user.is_staff:
            return StaffDashboardView.as_view()(request, *args, **kwargs)
        return UserDashboardView.as_view()(request, *args, **kwargs)
