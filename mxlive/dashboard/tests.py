from datetime import timedelta
from unittest.mock import MagicMock, patch
from django.apps import apps
from django.test import SimpleTestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string
from django.template import Template, Context
from django.urls import reverse, resolve
from django.utils import timezone

from .registry import DashboardCard, CardRegistry, register_card, card_registry
from . import cards
from .views import BaseDashboardView, UserDashboardView, StaffDashboardView, DashboardIndexView


class TestCardA(DashboardCard):
    name = 'test_card_a'
    title = 'Card A'
    order = 20
    roles = ('user',)
    column = 'left'


class TestCardB(DashboardCard):
    name = 'test_card_b'
    title = 'Card B'
    order = 10
    roles = ('staff',)
    column = 'right'


class TestCardC(DashboardCard):
    name = 'test_card_c'
    title = 'Card C'
    order = 15
    roles = ('user', 'staff')
    column = 'center'


class DashboardRegistryTests(SimpleTestCase):

    def setUp(self):
        self.registry = CardRegistry()
        self.factory = RequestFactory()

        User = get_user_model()
        self.regular_user = User(username='testuser', is_superuser=False)
        self.staff_user = User(username='staffuser', is_superuser=True)

    def test_app_is_installed(self):
        app_config = apps.get_app_config('dashboard')
        self.assertEqual(app_config.name, 'mxlive.dashboard')

    def test_register_and_get_card(self):
        self.registry.register(TestCardA)
        card = self.registry.get_card('test_card_a')
        self.assertIsNotNone(card)
        self.assertIsInstance(card, TestCardA)
        self.assertEqual(card.title, 'Card A')

    def test_register_instance(self):
        instance = TestCardB()
        self.registry.register(instance)
        card = self.registry.get_card('test_card_b')
        self.assertEqual(card, instance)

    def test_register_invalid_type_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.registry.register(object)

    def test_unregister(self):
        self.registry.register(TestCardA)
        self.assertIsNotNone(self.registry.get_card('test_card_a'))
        self.registry.unregister('test_card_a')
        self.assertIsNone(self.registry.get_card('test_card_a'))

    def test_get_cards_ordering(self):
        self.registry.register(TestCardA)  # order=20
        self.registry.register(TestCardB)  # order=10
        self.registry.register(TestCardC)  # order=15

        cards_list = self.registry.get_cards()
        self.assertEqual([c.name for c in cards_list], ['test_card_b', 'test_card_c', 'test_card_a'])

    def test_get_cards_role_filter(self):
        self.registry.register(TestCardA)  # user
        self.registry.register(TestCardB)  # staff
        self.registry.register(TestCardC)  # user, staff

        user_cards = self.registry.get_cards(role='user')
        self.assertEqual([c.name for c in user_cards], ['test_card_c', 'test_card_a'])

        staff_cards = self.registry.get_cards(role='staff')
        self.assertEqual([c.name for c in staff_cards], ['test_card_b', 'test_card_c'])

    def test_get_cards_column_filter(self):
        self.registry.register(TestCardA)  # left
        self.registry.register(TestCardB)  # right
        self.registry.register(TestCardC)  # center

        left_cards = self.registry.get_cards(column='left')
        self.assertEqual([c.name for c in left_cards], ['test_card_a'])

        right_cards = self.registry.get_cards(column='right')
        self.assertEqual([c.name for c in right_cards], ['test_card_b'])

    def test_visibility_with_authenticated_users(self):
        self.registry.register(TestCardA)  # user
        self.registry.register(TestCardB)  # staff
        self.registry.register(TestCardC)  # user, staff

        # Regular user request (can only see non-staff-only cards)
        request = self.factory.get('/')
        request.user = self.regular_user
        cards_list = self.registry.get_cards(request=request)
        self.assertEqual([c.name for c in cards_list], ['test_card_c', 'test_card_a'])

        # Staff user request (can see all cards, or filtered by role)
        request = self.factory.get('/')
        request.user = self.staff_user
        cards_list = self.registry.get_cards(request=request)
        self.assertEqual([c.name for c in cards_list], ['test_card_b', 'test_card_c', 'test_card_a'])

        staff_cards = self.registry.get_cards(request=request, role='staff')
        self.assertEqual([c.name for c in staff_cards], ['test_card_b', 'test_card_c'])

        user_cards = self.registry.get_cards(request=request, role='user')
        self.assertEqual([c.name for c in user_cards], ['test_card_c', 'test_card_a'])

    def test_visibility_with_anonymous_user(self):
        self.registry.register(TestCardA)
        request = self.factory.get('/')
        request.user = MagicMock(is_authenticated=False)
        cards_list = self.registry.get_cards(request=request)
        self.assertEqual(len(cards_list), 0)

    def test_card_context_data(self):
        card = TestCardA()
        request = self.factory.get('/')
        request.user = self.regular_user
        context = card.get_context_data(request, extra_key='extra_value')

        self.assertEqual(context['name'], 'test_card_a')
        self.assertEqual(context['title'], 'Card A')
        self.assertEqual(context['card'], card)
        self.assertEqual(context['extra_key'], 'extra_value')

    def test_render_empty_template_name_returns_empty_string(self):
        card = TestCardA()
        rendered = card.render()
        self.assertEqual(rendered, '')


class CoreCardsTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.regular_user = User(username='testuser', is_superuser=False)
        self.staff_user = User(username='staffuser', is_superuser=True)

    def test_all_core_cards_registered(self):
        expected_cards = {
            'upcoming_beamtime',
            'recent_shipments',
            'recent_sessions',
            'user_guide',
            'beamlines',
            'adaptors',
            'active_connections',
            'staff_shipments',
            'local_contact',
        }
        for card_name in expected_cards:
            self.assertIsNotNone(card_registry.get_card(card_name), f"Missing card: {card_name}")

    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_upcoming_beamtime_card_context(self, mock_get_beamtimes):
        mock_get_beamtimes.return_value = ['bt1', 'bt2']
        card = card_registry.get_card('upcoming_beamtime')
        request = self.factory.get('/')
        request.user = self.regular_user

        self.assertTrue(card.is_visible(request))
        context = card.get_context_data(request)
        self.assertEqual(context['beamtimes'], ['bt1', 'bt2'])

    @patch('mxlive.dashboard.services.get_user_shipments')
    def test_recent_shipments_card_context(self, mock_get_shipments):
        mock_get_shipments.return_value = ['shipment1']
        card = card_registry.get_card('recent_shipments')
        request = self.factory.get('/')
        request.user = self.regular_user

        self.assertTrue(card.is_visible(request))
        context = card.get_context_data(request)
        self.assertEqual(context['shipments'], ['shipment1'])

    @patch('mxlive.dashboard.services.get_user_sessions')
    def test_recent_sessions_card_context(self, mock_get_sessions):
        mock_get_sessions.return_value = ['session1']
        card = card_registry.get_card('recent_sessions')
        request = self.factory.get('/')
        request.user = self.regular_user

        self.assertTrue(card.is_visible(request))
        context = card.get_context_data(request)
        self.assertEqual(context['sessions'], ['session1'])

    @patch('mxlive.dashboard.services.get_staff_beamlines')
    def test_beamlines_card_context(self, mock_get_beamlines):
        mock_get_beamlines.return_value = ['bl1']
        card = card_registry.get_card('beamlines')
        request = self.factory.get('/')
        request.user = self.staff_user

        self.assertTrue(card.is_visible(request))
        context = card.get_context_data(request)
        self.assertEqual(context['beamlines'], ['bl1'])

    @patch('mxlive.dashboard.services.get_staff_adaptors')
    def test_adaptors_card_context(self, mock_get_adaptors):
        mock_get_adaptors.return_value = ['adaptor1']
        card = card_registry.get_card('adaptors')
        request = self.factory.get('/')
        request.user = self.staff_user

        self.assertTrue(card.is_visible(request))
        context = card.get_context_data(request)
        self.assertEqual(context['adaptors'], ['adaptor1'])

    @patch('mxlive.dashboard.services.get_staff_active_connections')
    def test_active_connections_card_context(self, mock_get_conns):
        mock_get_conns.return_value = [{'user': 'u1'}]
        card = card_registry.get_card('active_connections')
        request = self.factory.get('/')
        request.user = self.staff_user

        self.assertTrue(card.is_visible(request))
        context = card.get_context_data(request)
        self.assertEqual(context['connections'], [{'user': 'u1'}])

    @patch('mxlive.dashboard.services.get_staff_shipments')
    def test_staff_shipments_card_context(self, mock_get_shipments):
        mock_get_shipments.return_value = ['s1', 's2']
        card = card_registry.get_card('staff_shipments')
        request = self.factory.get('/')
        request.user = self.staff_user

        self.assertTrue(card.is_visible(request))
        context = card.get_context_data(request)
        self.assertEqual(context['shipments'], ['s1', 's2'])

    @patch('mxlive.dashboard.services.get_today_beamline_support')
    def test_local_contact_card_context(self, mock_get_support):
        mock_get_support.return_value = 'staff_member'
        card = card_registry.get_card('local_contact')
        request = self.factory.get('/')
        request.user = self.staff_user

        self.assertTrue(card.is_visible(request))
        context = card.get_context_data(request)
        self.assertEqual(context['support'], 'staff_member')

    @patch('mxlive.dashboard.services.get_today_beamline_support')
    @patch('mxlive.dashboard.services.get_user_sessions')
    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_user_and_staff_cards_filtering(self, mock_bt, mock_sess, mock_sup):
        mock_bt.return_value = [MagicMock()]
        mock_sess.return_value = [MagicMock()]
        mock_sup.return_value = MagicMock()
        request_user = self.factory.get('/')
        request_user.user = self.regular_user

        request_staff = self.factory.get('/')
        request_staff.user = self.staff_user

        user_cards = card_registry.get_cards(request=request_user, role='user')
        staff_cards = card_registry.get_cards(request=request_staff, role='staff')

        user_card_names = [c.name for c in user_cards]
        staff_card_names = [c.name for c in staff_cards]

        self.assertIn('upcoming_beamtime', user_card_names)
        self.assertIn('recent_shipments', user_card_names)
        self.assertIn('recent_sessions', user_card_names)
        self.assertIn('user_guide', user_card_names)
        self.assertNotIn('beamlines', user_card_names)

        self.assertIn('beamlines', staff_card_names)
        self.assertIn('adaptors', staff_card_names)
        self.assertIn('active_connections', staff_card_names)
        self.assertIn('staff_shipments', staff_card_names)
        self.assertIn('local_contact', staff_card_names)
        self.assertIn('user_guide', staff_card_names)
        self.assertNotIn('upcoming_beamtime', staff_card_names)


class DashboardViewsTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.regular_user = User(username='testuser', is_superuser=False)
        self.staff_user = User(username='staffuser', is_superuser=True)
        self.support_patcher = patch('mxlive.dashboard.services.get_today_beamline_support', return_value=None)
        self.support_patcher.start()
        self.addCleanup(self.support_patcher.stop)

    def test_user_dashboard_view_context(self):
        view = UserDashboardView()
        request = self.factory.get('/')
        request.user = self.regular_user
        view.request = request

        context = view.get_context_data()
        self.assertIn('cards', context)
        self.assertIn('left_cards', context)
        self.assertIn('center_cards', context)
        self.assertIn('right_cards', context)
        self.assertIn('access_types', context)

    def test_staff_dashboard_view_context(self):
        view = StaffDashboardView()
        request = self.factory.get('/')
        request.user = self.staff_user
        view.request = request

        context = view.get_context_data()
        self.assertIn('cards', context)
        self.assertIn('left_cards', context)
        self.assertIn('center_cards', context)
        self.assertIn('right_cards', context)

    def test_staff_dashboard_test_func(self):
        view = StaffDashboardView()

        # Regular user fails
        request = self.factory.get('/')
        request.user = self.regular_user
        view.request = request
        self.assertFalse(view.test_func())

        # Staff user passes
        request.user = self.staff_user
        self.assertTrue(view.test_func())

    @patch.object(UserDashboardView, 'render_to_response')
    def test_dashboard_index_dispatches_user(self, mock_render):
        mock_render.return_value = 'user_response'
        request = self.factory.get('/')
        request.user = self.regular_user

        response = DashboardIndexView.as_view()(request)
        mock_render.assert_called_once()

    @patch.object(StaffDashboardView, 'render_to_response')
    def test_dashboard_index_dispatches_staff(self, mock_render):
        mock_render.return_value = 'staff_response'
        request = self.factory.get('/')
        request.user = self.staff_user

        response = DashboardIndexView.as_view()(request)
        mock_render.assert_called_once()


class TemplateRenderingTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.regular_user = User(username='testuser', is_superuser=False)
        self.staff_user = User(username='staffuser', is_superuser=True)

    def test_render_base_card(self):
        rendered = render_to_string('dashboard/cards/base_card.html', {'title': 'Base Title'})
        self.assertIn('Base Title', rendered)

    @patch('basiclive.core.lims.models.Guide.objects.all')
    def test_render_user_guide_card(self, mock_guides):
        mock_guides.return_value = []
        card = card_registry.get_card('user_guide')
        rendered = card.render()
        self.assertIsInstance(rendered, str)

    @patch('mxlive.dashboard.services.get_user_shipments')
    def test_render_recent_shipments_card(self, mock_shipments):
        mock_shipments.return_value = []
        card = card_registry.get_card('recent_shipments')
        request = self.factory.get('/')
        request.user = self.regular_user
        rendered = card.render(request=request)
        self.assertIn('RECENT SHIPMENTS', rendered)

    @patch('mxlive.dashboard.services.get_user_sessions')
    def test_render_recent_sessions_card_empty(self, mock_sessions):
        mock_sessions.return_value = []
        card = card_registry.get_card('recent_sessions')
        request = self.factory.get('/')
        request.user = self.regular_user
        rendered = card.render(request=request)
        self.assertEqual(rendered.strip(), '')

    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_render_upcoming_beamtime_card_empty(self, mock_beamtimes):
        mock_beamtimes.return_value = []
        card = card_registry.get_card('upcoming_beamtime')
        request = self.factory.get('/')
        request.user = self.regular_user
        rendered = card.render(request=request)
        self.assertEqual(rendered.strip(), '')

    @patch('mxlive.dashboard.services.get_staff_active_connections')
    def test_render_active_connections_card_empty(self, mock_conns):
        mock_conns.return_value = []
        card = card_registry.get_card('active_connections')
        request = self.factory.get('/')
        request.user = self.staff_user
        rendered = card.render(request=request)
        self.assertIn('ACTIVE CONNECTIONS', rendered)
        self.assertIn('No active connections at the moment.', rendered)

    @patch('mxlive.dashboard.services.get_staff_shipments')
    def test_render_staff_shipments_card(self, mock_shipments):
        mock_shipments.return_value = []
        card = card_registry.get_card('staff_shipments')
        request = self.factory.get('/')
        request.user = self.staff_user
        rendered = card.render(request=request)
        self.assertIn('SHIPMENTS', rendered)

    @patch('mxlive.dashboard.services.get_staff_adaptors')
    def test_render_adaptors_card(self, mock_adaptors):
        mock_adaptors.return_value = []
        card = card_registry.get_card('adaptors')
        request = self.factory.get('/')
        request.user = self.staff_user
        rendered = card.render(request=request)
        self.assertIn('ADAPTORS', rendered)

    @patch('mxlive.dashboard.services.get_staff_beamlines')
    def test_render_beamlines_card(self, mock_beamlines):
        mock_beamlines.return_value = []
        card = card_registry.get_card('beamlines')
        request = self.factory.get('/')
        request.user = self.staff_user
        rendered = card.render(request=request)
        self.assertIn('BEAMLINES', rendered)

    @patch('mxlive.dashboard.services.get_user_sessions')
    def test_render_recent_sessions_card_with_sessions(self, mock_sessions):
        class FakeSession:
            pk = 1
            name = 'Session-001'
            start = timezone.now()
            beamline = MagicMock(acronym='BL-1')
            total_time = 3600
            last_record_time = timezone.now()
            data_count = 5
            report_count = 2
            is_recent = False
            feedback = MagicMock(all=lambda: [])

        mock_sessions.return_value = [FakeSession()]
        card = card_registry.get_card('recent_sessions')
        request = self.factory.get('/')
        request.user = self.regular_user
        rendered = card.render(request=request)
        self.assertIn('RECENT SESSIONS', rendered)
        self.assertIn('Session-001', rendered)

    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_render_upcoming_beamtime_card_with_beamtimes(self, mock_bt):
        class FakeBeamtime:
            pk = 1
            duration = timedelta(seconds=28800)
            current = False
            beamline = MagicMock(acronym='08B1-1')
            access = MagicMock()
            start = timezone.now()
            local_contact = None

        mock_bt.return_value = [FakeBeamtime()]
        card = card_registry.get_card('upcoming_beamtime')
        request = self.factory.get('/')
        request.user = self.regular_user
        rendered = card.render(request=request)
        self.assertIn('UPCOMING BEAMTIME', rendered)

    @patch('mxlive.dashboard.services.get_today_beamline_support')
    def test_render_local_contact_card_empty(self, mock_sup):
        mock_sup.return_value = None
        card = card_registry.get_card('local_contact')
        request = self.factory.get('/')
        request.user = self.staff_user
        rendered = card.render(request=request)
        self.assertEqual(rendered.strip(), '')

    @patch('mxlive.dashboard.services.get_today_beamline_support')
    def test_render_local_contact_card_with_support(self, mock_sup):
        class FakeSupport:
            class staff:
                contact_email = 'alice@example.com'
                contact_phone = '555-0100'
            def __str__(self):
                return 'Alice Doe'

        mock_sup.return_value = FakeSupport()
        card = card_registry.get_card('local_contact')
        request = self.factory.get('/')
        request.user = self.staff_user
        rendered = card.render(request=request)
        self.assertIn('LOCAL CONTACT', rendered)
        self.assertIn('ALICE DOE', rendered)
        self.assertIn('555-0100', rendered)

    @patch('mxlive.dashboard.services.get_user_shipments')
    def test_render_card_templatetag(self, mock_shipments):
        mock_shipments.return_value = []
        card = card_registry.get_card('recent_shipments')
        request = self.factory.get('/')
        request.user = self.regular_user
        t = Template('{% load dashboard_tags %}{% render_card card %}')
        rendered = t.render(Context({'card': card, 'request': request}))
        self.assertIn('RECENT SHIPMENTS', rendered)

    def test_render_user_dashboard_template(self):
        context = {
            'user': self.regular_user,
            'left_cards': [],
            'center_cards': [],
            'right_cards': [],
            'full_cards': [],
        }
        rendered = render_to_string('dashboard/user_dashboard.html', context)
        self.assertIn('User', rendered)

    def test_render_staff_dashboard_template(self):
        context = {
            'user': self.staff_user,
            'access_types': [],
            'left_cards': [],
            'center_cards': [],
            'right_cards': [],
            'full_cards': [],
        }
        rendered = render_to_string('dashboard/staff_dashboard.html', context)
        self.assertIn('Staff', rendered)


class DashboardURLRoutingTests(SimpleTestCase):

    def test_named_url_reversing(self):
        self.assertEqual(reverse('dashboard'), '/')
        self.assertEqual(reverse('user-dashboard'), '/user/')
        self.assertEqual(reverse('staff-dashboard'), '/staff/')

    def test_url_resolving_root(self):
        resolver_match = resolve('/')
        self.assertEqual(resolver_match.func.view_class, DashboardIndexView)

    def test_url_resolving_user(self):
        resolver_match = resolve('/user/')
        self.assertEqual(resolver_match.func.view_class, UserDashboardView)

    def test_url_resolving_staff(self):
        resolver_match = resolve('/staff/')
        self.assertEqual(resolver_match.func.view_class, StaffDashboardView)


class DashboardSecurityAndRoutingTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.anonymous_user = AnonymousUser()
        self.regular_user = User(username='testuser', is_superuser=False, is_staff=False, pk=1)
        self.staff_user = User(username='staffuser', is_superuser=True, is_staff=True, pk=2)
        self.non_su_staff = User(username='staff_scientist', is_superuser=False, is_staff=True, pk=3)

    def test_anonymous_user_on_root_redirects_to_login(self):
        request = self.factory.get('/')
        request.user = self.anonymous_user
        response = DashboardIndexView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_anonymous_user_on_user_dashboard_redirects_to_login(self):
        request = self.factory.get('/user/')
        request.user = self.anonymous_user
        response = UserDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_anonymous_user_on_staff_dashboard_redirects_to_login(self):
        request = self.factory.get('/staff/')
        request.user = self.anonymous_user
        response = StaffDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    @patch('mxlive.dashboard.services.get_user_shipments')
    @patch('mxlive.dashboard.services.get_user_sessions')
    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_regular_user_on_root_renders_user_dashboard(self, mock_bt, mock_sess, mock_ship):
        mock_bt.return_value = []
        mock_sess.return_value = [MagicMock()]
        mock_ship.return_value = []

        request = self.factory.get('/')
        request.user = self.regular_user
        response = DashboardIndexView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('dashboard/user_dashboard.html', response.template_name)
        card_names = [c.name for c in response.context_data['cards']]
        self.assertIn('recent_shipments', card_names)
        self.assertIn('recent_sessions', card_names)
        self.assertNotIn('beamlines', card_names)

    @patch('mxlive.dashboard.services.get_user_shipments')
    @patch('mxlive.dashboard.services.get_user_sessions')
    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_regular_user_on_user_url_renders_user_dashboard(self, mock_bt, mock_sess, mock_ship):
        mock_bt.return_value = []
        mock_sess.return_value = []
        mock_ship.return_value = []

        request = self.factory.get('/user/')
        request.user = self.regular_user
        response = UserDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('dashboard/user_dashboard.html', response.template_name)

    def test_regular_user_on_staff_dashboard_denied(self):
        request = self.factory.get('/staff/')
        request.user = self.regular_user
        with self.assertRaises(PermissionDenied):
            StaffDashboardView.as_view()(request)

    @patch('mxlive.dashboard.services.get_staff_beamlines')
    @patch('mxlive.dashboard.services.get_staff_adaptors')
    @patch('mxlive.dashboard.services.get_staff_active_connections')
    @patch('mxlive.dashboard.services.get_staff_shipments')
    @patch('mxlive.dashboard.services.get_today_beamline_support')
    def test_staff_user_on_root_renders_staff_dashboard(self, mock_sup, mock_ship, mock_conn, mock_adapt, mock_bl):
        mock_sup.return_value = None
        mock_ship.return_value = []
        mock_conn.return_value = []
        mock_adapt.return_value = []
        mock_bl.return_value = []

        request = self.factory.get('/')
        request.user = self.staff_user
        response = DashboardIndexView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('dashboard/staff_dashboard.html', response.template_name)
        card_names = [c.name for c in response.context_data['cards']]
        self.assertIn('beamlines', card_names)
        self.assertIn('adaptors', card_names)
        self.assertIn('active_connections', card_names)
        self.assertIn('staff_shipments', card_names)
        self.assertNotIn('upcoming_beamtime', card_names)

    @patch('mxlive.dashboard.services.get_staff_beamlines')
    @patch('mxlive.dashboard.services.get_staff_adaptors')
    @patch('mxlive.dashboard.services.get_staff_active_connections')
    @patch('mxlive.dashboard.services.get_staff_shipments')
    @patch('mxlive.dashboard.services.get_today_beamline_support')
    def test_staff_user_on_staff_url_renders_staff_dashboard(self, mock_sup, mock_ship, mock_conn, mock_adapt, mock_bl):
        mock_sup.return_value = None
        mock_ship.return_value = []
        mock_conn.return_value = []
        mock_adapt.return_value = []
        mock_bl.return_value = []

        request = self.factory.get('/staff/')
        request.user = self.staff_user
        response = StaffDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('dashboard/staff_dashboard.html', response.template_name)

    @patch('mxlive.dashboard.services.get_user_shipments')
    @patch('mxlive.dashboard.services.get_user_sessions')
    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_non_su_staff_on_root_dispatches_to_user_dashboard(self, mock_bt, mock_sess, mock_ship):
        """
        Users with is_staff=True but is_superuser=False (such as beamline scientists)
        should be dispatched to UserDashboardView on root '/', showing user cards.
        """
        mock_bt.return_value = []
        mock_sess.return_value = [MagicMock()]
        mock_ship.return_value = []

        request = self.factory.get('/')
        request.user = self.non_su_staff
        response = DashboardIndexView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('dashboard/user_dashboard.html', response.template_name)
        card_names = [c.name for c in response.context_data['cards']]
        self.assertIn('recent_shipments', card_names)
        self.assertIn('recent_sessions', card_names)
        self.assertIn('user_guide', card_names)
        self.assertNotIn('beamlines', card_names)

    @patch('mxlive.dashboard.services.get_user_shipments')
    @patch('mxlive.dashboard.services.get_user_sessions')
    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_superuser_on_user_url_renders_user_cards(self, mock_bt, mock_sess, mock_ship):
        """
        Superusers navigating to '/user/' must see user dashboard cards
        (recent shipments, recent sessions, user guide), not just user guide.
        """
        mock_bt.return_value = []
        mock_sess.return_value = [MagicMock()]
        mock_ship.return_value = []

        request = self.factory.get('/user/')
        request.user = self.staff_user
        response = UserDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('dashboard/user_dashboard.html', response.template_name)
        card_names = [c.name for c in response.context_data['cards']]
        self.assertIn('recent_shipments', card_names)
        self.assertIn('recent_sessions', card_names)
        self.assertIn('user_guide', card_names)

    @patch('mxlive.dashboard.services.get_staff_beamlines')
    @patch('mxlive.dashboard.services.get_staff_adaptors')
    @patch('mxlive.dashboard.services.get_staff_active_connections')
    @patch('mxlive.dashboard.services.get_staff_shipments')
    @patch('mxlive.dashboard.services.get_today_beamline_support')
    def test_non_su_staff_on_staff_url_renders_staff_dashboard(self, mock_sup, mock_ship, mock_conn, mock_adapt, mock_bl):
        """
        Users with is_staff=True are allowed to view the Staff dashboard on '/staff/'.
        """
        mock_sup.return_value = None
        mock_ship.return_value = []
        mock_conn.return_value = []
        mock_adapt.return_value = []
        mock_bl.return_value = []

        request = self.factory.get('/staff/')
        request.user = self.non_su_staff
        response = StaffDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('dashboard/staff_dashboard.html', response.template_name)
        card_names = [c.name for c in response.context_data['cards']]
        self.assertIn('beamlines', card_names)
        self.assertIn('adaptors', card_names)
        self.assertIn('active_connections', card_names)
        self.assertIn('staff_shipments', card_names)

    @patch('mxlive.dashboard.services.get_user_shipments')
    @patch('mxlive.dashboard.services.get_user_sessions')
    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_beamtime_card_visible_only_when_has_beamtime(self, mock_bt, mock_sess, mock_ship):
        """
        UpcomingBeamtimeCard is only visible when the user has upcoming beamtime,
        preventing an empty 3-column whitespace on the left of user dashboard.
        """
        mock_sess.return_value = []
        mock_ship.return_value = []

        # When beamtimes is empty
        mock_bt.return_value = []
        request = self.factory.get('/user/')
        request.user = self.regular_user
        response = UserDashboardView.as_view()(request)
        self.assertNotIn('upcoming_beamtime', [c.name for c in response.context_data['cards']])
        self.assertEqual(len(response.context_data['left_cards']), 0)

        # When user has beamtimes
        mock_bt.return_value = [MagicMock()]
        request2 = self.factory.get('/user/')
        request2.user = self.regular_user
        response2 = UserDashboardView.as_view()(request2)
        self.assertIn('upcoming_beamtime', [c.name for c in response2.context_data['cards']])
        self.assertEqual(len(response2.context_data['left_cards']), 1)


class CardQueryDeduplicationTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.regular_user = User(username='testuser', is_superuser=False, pk=1)
        self.staff_user = User(username='staffuser', is_superuser=True, pk=2)

    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_upcoming_beamtime_query_deduplication(self, mock_get_beamtimes):
        class FakeBeamtime:
            pk = 1
            duration = timedelta(seconds=28800)
            current = False
            beamline = MagicMock(acronym='08B1-1')
            access = MagicMock()
            start = timezone.now()
            local_contact = None

        mock_get_beamtimes.return_value = [FakeBeamtime()]
        card = card_registry.get_card('upcoming_beamtime')
        request = self.factory.get('/')
        request.user = self.regular_user

        self.assertTrue(card.is_visible(request))
        rendered = card.render(request=request)
        self.assertIn('UPCOMING BEAMTIME', rendered)
        self.assertEqual(mock_get_beamtimes.call_count, 1)

        # Subsequent get_context_data call on the same request is cached
        ctx = card.get_context_data(request)
        self.assertEqual(mock_get_beamtimes.call_count, 1)
        self.assertEqual(len(ctx['beamtimes']), 1)

    @patch('mxlive.dashboard.services.get_user_sessions')
    def test_recent_sessions_query_deduplication(self, mock_get_sessions):
        class FakeSession:
            pk = 1
            name = 'Session-001'
            start = timezone.now()
            beamline = MagicMock(acronym='BL-1')
            total_time = 3600
            last_record_time = timezone.now()
            data_count = 5
            report_count = 2
            is_recent = False
            feedback = MagicMock(all=lambda: [])

        mock_get_sessions.return_value = [FakeSession()]
        card = card_registry.get_card('recent_sessions')
        request = self.factory.get('/')
        request.user = self.regular_user

        self.assertTrue(card.is_visible(request))
        rendered = card.render(request=request)
        self.assertIn('RECENT SESSIONS', rendered)
        self.assertEqual(mock_get_sessions.call_count, 1)

        # Subsequent get_context_data call on the same request is cached
        ctx = card.get_context_data(request)
        self.assertEqual(mock_get_sessions.call_count, 1)
        self.assertEqual(len(ctx['sessions']), 1)

    @patch('mxlive.dashboard.services.get_today_beamline_support')
    def test_local_contact_query_deduplication(self, mock_get_support):
        class FakeSupport:
            class staff:
                contact_email = 'alice@example.com'
                contact_phone = '555-0100'
            def __str__(self):
                return 'Alice Doe'

        mock_get_support.return_value = FakeSupport()
        card = card_registry.get_card('local_contact')
        request = self.factory.get('/')
        request.user = self.staff_user

        self.assertTrue(card.is_visible(request))
        rendered = card.render(request=request)
        self.assertIn('LOCAL CONTACT', rendered)
        self.assertEqual(mock_get_support.call_count, 1)

        # Subsequent get_context_data call on the same request is cached
        ctx = card.get_context_data(request)
        self.assertEqual(mock_get_support.call_count, 1)
        self.assertIsNotNone(ctx['support'])

    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_cache_is_request_scoped_not_shared_across_requests(self, mock_get_beamtimes):
        mock_get_beamtimes.return_value = [MagicMock()]
        card = card_registry.get_card('upcoming_beamtime')

        request1 = self.factory.get('/')
        request1.user = self.regular_user

        request2 = self.factory.get('/')
        request2.user = self.regular_user

        card.is_visible(request1)
        self.assertEqual(mock_get_beamtimes.call_count, 1)

        card.is_visible(request1)
        self.assertEqual(mock_get_beamtimes.call_count, 1)

        card.is_visible(request2)
        self.assertEqual(mock_get_beamtimes.call_count, 2)

    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_empty_content_suppressed_and_queried_once(self, mock_get_beamtimes):
        mock_get_beamtimes.return_value = []
        card = card_registry.get_card('upcoming_beamtime')
        request = self.factory.get('/')
        request.user = self.regular_user

        self.assertFalse(card.is_visible(request))
        rendered = card.render(request=request)
        self.assertEqual(rendered, '')
        self.assertEqual(mock_get_beamtimes.call_count, 1)


class BeamtimeCalendarServiceTests(SimpleTestCase):

    def setUp(self):
        User = get_user_model()
        self.user = User(username='scientist', pk=42)
        self.anonymous_user = AnonymousUser()

    def test_calendar_generates_three_consecutive_months_by_default(self):
        from .services import get_user_beamtime_calendar
        from datetime import date

        ref = date(2026, 9, 15)
        months = get_user_beamtime_calendar(self.anonymous_user, reference_date=ref)
        self.assertEqual(len(months), 3)

        self.assertEqual((months[0]['year'], months[0]['month'], months[0]['month_name']), (2026, 9, 'September'))
        self.assertEqual((months[1]['year'], months[1]['month'], months[1]['month_name']), (2026, 10, 'October'))
        self.assertEqual((months[2]['year'], months[2]['month'], months[2]['month_name']), (2026, 11, 'November'))

    def test_calendar_handles_year_boundary_transition(self):
        from .services import get_user_beamtime_calendar
        from datetime import date

        ref = date(2026, 11, 20)
        months = get_user_beamtime_calendar(self.anonymous_user, reference_date=ref)
        self.assertEqual(len(months), 3)

        self.assertEqual((months[0]['year'], months[0]['month']), (2026, 11))
        self.assertEqual((months[1]['year'], months[1]['month']), (2026, 12))
        self.assertEqual((months[2]['year'], months[2]['month']), (2027, 1))

    def test_calendar_weeks_and_weekday_headers(self):
        from .services import get_user_beamtime_calendar
        from datetime import date

        ref = date(2026, 9, 1)
        months = get_user_beamtime_calendar(self.anonymous_user, reference_date=ref)
        september = months[0]

        self.assertEqual(september['weekday_headers'], ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'])
        self.assertGreaterEqual(len(september['weeks']), 4)
        for week in september['weeks']:
            self.assertEqual(len(week), 7)

        # First day of Sep 2026 is Tuesday, so first day of week 1 should be Aug 31 with in_month=False
        first_day = september['weeks'][0][0]
        self.assertFalse(first_day['in_month'])
        self.assertEqual(first_day['date'], date(2026, 8, 31))

        # Second day of week 1 is Sep 1 with in_month=True
        second_day = september['weeks'][0][1]
        self.assertTrue(second_day['in_month'])
        self.assertEqual(second_day['date'], date(2026, 9, 1))

    def test_calendar_maps_beamtimes_to_matching_dates(self):
        from .services import get_user_beamtime_calendar
        from datetime import date, datetime

        tz = timezone.get_current_timezone()
        bt_start = timezone.make_aware(datetime(2026, 9, 10, 8, 0, 0), tz)
        bt_end = timezone.make_aware(datetime(2026, 9, 11, 16, 0, 0), tz)

        mock_bt = MagicMock()
        mock_bt.pk = 101
        mock_bt.start = bt_start
        mock_bt.end = bt_end
        mock_bt.cancelled = False
        mock_bt.beamline.acronym = 'CMCF-ID'
        mock_bt.access.name = 'Remote'
        mock_bt.access.color = '#336699'
        mock_bt.shifts = 4
        mock_bt.start_date_display.return_value = 'Thursday, September 10'
        mock_bt.start_time_display.return_value = '8AM'

        user = MagicMock()
        user.pk = 42
        mock_qs = MagicMock()
        mock_qs.with_duration.return_value.select_related.return_value.order_by.return_value = [mock_bt]
        user.beamtime.filter.return_value = mock_qs

        months = get_user_beamtime_calendar(user, reference_date=date(2026, 9, 1))
        september = months[0]
        self.assertTrue(september['has_beamtimes'])

        # Find day 10 and day 11 in September
        days_by_date = {
            day['date']: day
            for week in september['weeks']
            for day in week
            if day['in_month']
        }

        day_10 = days_by_date[date(2026, 9, 10)]
        self.assertTrue(day_10['has_beamtime'])
        self.assertEqual(day_10['access_color'], '#336699')
        self.assertEqual(len(day_10['beamtimes']), 1)
        self.assertEqual(day_10['beamtimes'][0]['beamline'], 'CMCF-ID')

        day_11 = days_by_date[date(2026, 9, 11)]
        self.assertTrue(day_11['has_beamtime'])

        day_12 = days_by_date[date(2026, 9, 12)]
        self.assertFalse(day_12['has_beamtime'])

    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_upcoming_beamtime_card_calendar_context_structure(self, mock_get_beamtimes):
        class MockBeamtime:
            pk = 10
            start = timezone.now()
            end = timezone.now() + timedelta(hours=8)
            duration = timedelta(hours=8)
            current = True
            cancelled = False
            beamline = MagicMock(acronym='CMCF-BM')
            access = MagicMock(color='#ff5500')
            shifts = 1
            comments = 'Test beamtime'

        mock_get_beamtimes.return_value = [MockBeamtime()]
        card = card_registry.get_card('upcoming_beamtime')
        request = RequestFactory().get('/')
        request.user = self.user

        self.assertTrue(card.is_visible(request))
        context = card.get_context_data(request)
        self.assertIn('calendar_months', context)
        self.assertEqual(len(context['calendar_months']), 3)
        self.assertTrue(context['has_beamtimes'])
        self.assertIn('access_types', context)
        self.assertIn('beamtimes', context)
        self.assertEqual(len(context['beamtimes']), 1)

    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_upcoming_beamtime_card_visibility_when_empty(self, mock_get_beamtimes):
        mock_get_beamtimes.return_value = []
        card = card_registry.get_card('upcoming_beamtime')
        request = RequestFactory().get('/')
        request.user = self.user

        self.assertFalse(card.is_visible(request))
        context = card.get_context_data(request)
        self.assertFalse(context['has_beamtimes'])
        self.assertEqual(context['beamtimes'], [])

    @patch('mxlive.dashboard.cards.lims_cfg')
    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_upcoming_beamtime_card_hidden_when_use_schedule_false(self, mock_get_beamtimes, mock_lims_cfg):
        mock_lims_cfg.USE_SCHEDULE = False
        mock_get_beamtimes.return_value = [MagicMock()]
        card = card_registry.get_card('upcoming_beamtime')
        request = RequestFactory().get('/')
        request.user = self.user

        self.assertFalse(card.is_visible(request))

    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_render_upcoming_beamtime_calendar_html(self, mock_get_beamtimes):
        class MockBeamtime:
            pk = 10
            start = timezone.now()
            end = timezone.now() + timedelta(hours=8)
            duration = timedelta(hours=8)
            current = True
            cancelled = False
            beamline = MagicMock(acronym='CMCF-BM')
            access = MagicMock(color='#ff5500')
            shifts = 1
            comments = 'Test beamtime'

        class MockAccessType:
            name = 'Remote'
            color = '#ff5500'

        mock_get_beamtimes.return_value = [MockBeamtime()]
        card = card_registry.get_card('upcoming_beamtime')
        request = RequestFactory().get('/')
        request.user = self.user

        rendered = card.render(request=request)
        self.assertIn('upcoming-beamtime-calendar', rendered)
        self.assertIn('calendar-mini-month', rendered)
        self.assertIn('calendar-table', rendered)
        self.assertIn('<th>Mo</th>', rendered)
        self.assertIn('has-beamtime', rendered)
        self.assertIn('--beamtime-color: #ff5500', rendered)
        self.assertIn('data-date=', rendered)

    @patch('mxlive.dashboard.services.get_user_beamtimes')
    def test_render_upcoming_beamtime_popover_and_modal_linkages(self, mock_get_beamtimes):
        class MockSession:
            pk = 404
            name = 'session-404'

        class MockLocalContact:
            pk = 55
            first_name = 'Jane'
            last_name = 'Scientist'
            def __str__(self):
                return 'Jane Scientist'

        class MockBeamtime:
            pk = 77
            start = timezone.now()
            end = timezone.now() + timedelta(hours=8)
            duration = timedelta(hours=8)
            current = True
            cancelled = False
            beamline = MagicMock(acronym='CMCF-ID')
            access = MagicMock(color='#0088cc')
            access.name = 'Remote'
            shifts = 2
            comments = 'High resolution dataset'
            local_contact = MockLocalContact()

            def sessions(self):
                return [MockSession()]

        mock_get_beamtimes.return_value = [MockBeamtime()]
        card = card_registry.get_card('upcoming_beamtime')
        request = RequestFactory().get('/')
        request.user = self.user

        rendered = card.render(request=request)
        self.assertIn('data-bs-toggle="popover"', rendered)
        self.assertIn('data-popover-target=', rendered)
        self.assertIn('popover-template', rendered)
        self.assertIn('popover-body-content', rendered)
        self.assertIn('data-modal-url="/calendar/beamtime/77/info/"', rendered)
        self.assertIn('/calendar/support/55/info/?current=True', rendered)
        self.assertIn('/users/sessions/404/', rendered)
        self.assertIn('initCalendarPopovers', rendered)

    def test_calendar_handles_leap_year_february_29(self):
        from .services import get_user_beamtime_calendar
        from datetime import date

        # 2028 is a leap year; reference starting January 2028
        ref = date(2028, 1, 15)
        months = get_user_beamtime_calendar(self.anonymous_user, reference_date=ref)
        self.assertEqual(len(months), 3)

        february = months[1]
        self.assertEqual(february['month_name'], 'February')
        self.assertEqual(february['year'], 2028)

        feb_days = [
            day for week in february['weeks']
            for day in week
            if day['in_month']
        ]
        self.assertEqual(len(feb_days), 29)
        self.assertEqual(feb_days[-1]['day'], 29)
        self.assertEqual(feb_days[-1]['date'], date(2028, 2, 29))

    def test_calendar_handles_non_leap_year_february_28(self):
        from .services import get_user_beamtime_calendar
        from datetime import date

        # 2027 is not a leap year; reference starting February 2027
        ref = date(2027, 2, 1)
        months = get_user_beamtime_calendar(self.anonymous_user, reference_date=ref)
        february = months[0]
        self.assertEqual(february['month_name'], 'February')
        feb_days = [
            day for week in february['weeks']
            for day in week
            if day['in_month']
        ]
        self.assertEqual(len(feb_days), 28)
        self.assertEqual(feb_days[-1]['day'], 28)

    def test_calendar_multi_day_beamtime_spans_multiple_days(self):
        from .services import get_user_beamtime_calendar
        from datetime import date, datetime

        tz = timezone.get_current_timezone()
        # 3-day beamtime from April 14 08:00 to April 16 16:00
        bt_start = timezone.make_aware(datetime(2027, 4, 14, 8, 0, 0), tz)
        bt_end = timezone.make_aware(datetime(2027, 4, 16, 16, 0, 0), tz)

        mock_bt = MagicMock()
        mock_bt.pk = 202
        mock_bt.start = bt_start
        mock_bt.end = bt_end
        mock_bt.duration = timedelta(days=2, hours=8)
        mock_bt.cancelled = False
        mock_bt.beamline.acronym = '08B1-1'
        mock_bt.access.name = 'Mail-in'
        mock_bt.access.color = '#28a745'
        mock_bt.shifts = 7
        mock_bt.start_date_display.return_value = 'Wednesday, April 14'
        mock_bt.start_time_display.return_value = '08:00'

        months = get_user_beamtime_calendar(
            self.anonymous_user,
            reference_date=date(2027, 4, 1),
            beamtimes=[mock_bt]
        )
        april = months[0]
        days_by_date = {
            day['date']: day
            for week in april['weeks']
            for day in week
            if day['in_month']
        }

        # Days 14, 15, 16 should all have beamtime
        self.assertTrue(days_by_date[date(2027, 4, 14)]['has_beamtime'])
        self.assertTrue(days_by_date[date(2027, 4, 15)]['has_beamtime'])
        self.assertTrue(days_by_date[date(2027, 4, 16)]['has_beamtime'])

        # Days 13 and 17 should NOT have beamtime
        self.assertFalse(days_by_date[date(2027, 4, 13)]['has_beamtime'])
        self.assertFalse(days_by_date[date(2027, 4, 17)]['has_beamtime'])

        # Color and beamline check
        day_15 = days_by_date[date(2027, 4, 15)]
        self.assertEqual(day_15['access_color'], '#28a745')
        self.assertEqual(day_15['beamtimes'][0]['beamline'], '08B1-1')

    def test_calendar_excludes_cancelled_beamtimes(self):
        from .services import get_user_beamtime_calendar
        from datetime import date, datetime

        tz = timezone.get_current_timezone()
        bt_start = timezone.make_aware(datetime(2026, 10, 5, 8, 0, 0), tz)
        bt_end = timezone.make_aware(datetime(2026, 10, 5, 16, 0, 0), tz)

        mock_bt = MagicMock()
        mock_bt.pk = 303
        mock_bt.start = bt_start
        mock_bt.end = bt_end
        mock_bt.cancelled = True

        user = MagicMock()
        user.pk = 42
        mock_qs = MagicMock()
        # Non-cancelled filter should return empty list
        mock_qs.with_duration.return_value.select_related.return_value.order_by.return_value = []
        user.beamtime.filter.return_value = mock_qs

        months = get_user_beamtime_calendar(user, reference_date=date(2026, 10, 1))
        october = months[0]
        self.assertFalse(october['has_beamtimes'])
        user.beamtime.filter.assert_called_once()
        filter_kwargs = user.beamtime.filter.call_args[1]
        self.assertFalse(filter_kwargs['cancelled'])








