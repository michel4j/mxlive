from unittest.mock import MagicMock, patch
from django.apps import apps
from django.test import SimpleTestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string
from django.template import Template, Context
from django.urls import reverse, resolve

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

        # Regular user request
        request = self.factory.get('/')
        request.user = self.regular_user
        cards_list = self.registry.get_cards(request=request)
        self.assertEqual([c.name for c in cards_list], ['test_card_c', 'test_card_a'])

        # Staff user request
        request = self.factory.get('/')
        request.user = self.staff_user
        cards_list = self.registry.get_cards(request=request)
        self.assertEqual([c.name for c in cards_list], ['test_card_b', 'test_card_c'])

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

    def test_user_and_staff_cards_filtering(self):
        request_user = self.factory.get('/')
        request_user.user = self.regular_user

        request_staff = self.factory.get('/')
        request_staff.user = self.staff_user

        user_cards = card_registry.get_cards(request=request_user)
        staff_cards = card_registry.get_cards(request=request_staff)

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
        self.assertIn('Start Now', rendered)

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
        self.assertIn('Start Now', rendered)

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

    def test_url_resolving_dashboard_prefix(self):
        self.assertEqual(resolve('/dashboard/').func.view_class, DashboardIndexView)
        self.assertEqual(resolve('/dashboard/user/').func.view_class, UserDashboardView)
        self.assertEqual(resolve('/dashboard/staff/').func.view_class, StaffDashboardView)



