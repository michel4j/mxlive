from basiclive.core.lims.conf import settings as lims_cfg
from .registry import DashboardCard, register_card
from . import services


@register_card
class UpcomingBeamtimeCard(DashboardCard):
    name = 'upcoming_beamtime'
    title = 'UPCOMING BEAMTIME'
    template_name = 'dashboard/cards/upcoming_beamtime.html'
    order = 10
    roles = ('user',)
    column = 'left'

    def is_visible(self, request):
        if not super().is_visible(request):
            return False
        if not lims_cfg.USE_SCHEDULE:
            return False
        req = request or self.request
        user = getattr(req, 'user', None)
        if not user or not user.is_authenticated:
            return False
        beamtimes = services.get_user_beamtimes(user)
        return beamtimes.exists() if hasattr(beamtimes, 'exists') else bool(beamtimes)

    def get_context_data(self, request=None, **kwargs):
        context = super().get_context_data(request, **kwargs)
        req = request or self.request
        user = getattr(req, 'user', None)
        context['beamtimes'] = services.get_user_beamtimes(user) if user else []
        return context


@register_card
class RecentShipmentsCard(DashboardCard):
    name = 'recent_shipments'
    title = 'RECENT SHIPMENTS'
    template_name = 'dashboard/cards/recent_shipments.html'
    order = 20
    roles = ('user',)
    column = 'center'

    def get_context_data(self, request=None, **kwargs):
        context = super().get_context_data(request, **kwargs)
        req = request or self.request
        user = getattr(req, 'user', None)
        context['shipments'] = services.get_user_shipments(user) if user else []
        return context


@register_card
class RecentSessionsCard(DashboardCard):
    name = 'recent_sessions'
    title = 'RECENT SESSIONS'
    template_name = 'dashboard/cards/recent_sessions.html'
    order = 30
    roles = ('user',)
    column = 'center'

    def get_context_data(self, request=None, **kwargs):
        context = super().get_context_data(request, **kwargs)
        req = request or self.request
        user = getattr(req, 'user', None)
        context['sessions'] = services.get_user_sessions(user) if user else []
        return context


@register_card
class UserGuideCard(DashboardCard):
    name = 'user_guide'
    title = 'GUIDE'
    template_name = 'dashboard/cards/user_guide.html'
    order = 40
    roles = ('user', 'staff')
    column = 'right'


@register_card
class BeamlinesCard(DashboardCard):
    name = 'beamlines'
    title = 'BEAMLINES'
    template_name = 'dashboard/cards/beamlines.html'
    order = 10
    roles = ('staff',)
    column = 'left'

    def get_context_data(self, request=None, **kwargs):
        context = super().get_context_data(request, **kwargs)
        context['beamlines'] = services.get_staff_beamlines()
        return context


@register_card
class AdaptorsCard(DashboardCard):
    name = 'adaptors'
    title = 'ADAPTORS'
    template_name = 'dashboard/cards/adaptors.html'
    order = 20
    roles = ('staff',)
    column = 'left'

    def get_context_data(self, request=None, **kwargs):
        context = super().get_context_data(request, **kwargs)
        context['adaptors'] = services.get_staff_adaptors()
        return context


@register_card
class ActiveConnectionsCard(DashboardCard):
    name = 'active_connections'
    title = 'ACTIVE CONNECTIONS'
    template_name = 'dashboard/cards/active_connections.html'
    order = 30
    roles = ('staff',)
    column = 'center'

    def get_context_data(self, request=None, **kwargs):
        context = super().get_context_data(request, **kwargs)
        context['connections'] = services.get_staff_active_connections()
        return context


@register_card
class StaffShipmentsCard(DashboardCard):
    name = 'staff_shipments'
    title = 'SHIPMENTS'
    template_name = 'dashboard/cards/staff_shipments.html'
    order = 40
    roles = ('staff',)
    column = 'center'

    def get_context_data(self, request=None, **kwargs):
        context = super().get_context_data(request, **kwargs)
        context['shipments'] = services.get_staff_shipments()
        return context


@register_card
class LocalContactCard(DashboardCard):
    name = 'local_contact'
    title = 'LOCAL CONTACT'
    template_name = 'dashboard/cards/local_contact.html'
    order = 10
    roles = ('staff',)
    column = 'right'

    def is_visible(self, request):
        if not super().is_visible(request):
            return False
        return bool(lims_cfg.USE_CRM)

    def get_context_data(self, request=None, **kwargs):
        context = super().get_context_data(request, **kwargs)
        context['support'] = services.get_today_beamline_support()
        return context
