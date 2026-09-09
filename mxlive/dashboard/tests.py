from unittest.mock import MagicMock
from django.apps import apps
from django.test import SimpleTestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.template import TemplateDoesNotExist

from .registry import DashboardCard, CardRegistry, register_card, card_registry


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

        cards = self.registry.get_cards()
        self.assertEqual([c.name for c in cards], ['test_card_b', 'test_card_c', 'test_card_a'])

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
        cards = self.registry.get_cards(request=request)
        self.assertEqual([c.name for c in cards], ['test_card_c', 'test_card_a'])

        # Staff user request
        request = self.factory.get('/')
        request.user = self.staff_user
        cards = self.registry.get_cards(request=request)
        self.assertEqual([c.name for c in cards], ['test_card_b', 'test_card_c'])

    def test_visibility_with_anonymous_user(self):
        self.registry.register(TestCardA)
        request = self.factory.get('/')
        request.user = MagicMock(is_authenticated=False)
        cards = self.registry.get_cards(request=request)
        self.assertEqual(len(cards), 0)

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
