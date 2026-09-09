import threading
from django.template.loader import render_to_string
from django.utils.module_loading import autodiscover_modules
from django.utils.safestring import mark_safe


class DashboardCard:
    """
    Base class for modular dashboard cards/panels.
    """
    name = ''
    title = ''
    template_name = ''
    order = 100
    roles = ('user', 'staff')  # Roles that can see this card
    column = 'center'  # Layout placement hint: 'left', 'center', 'right', 'full'

    def __init__(self):
        if not self.name:
            self.name = self.__class__.__name__.lower()
        self.request = None

    def is_visible(self, request):
        """
        Determine if the card should be displayed for the given request.
        Override to implement custom permissions or configuration checks.
        """
        req = request or self.request
        if not req or not getattr(req, 'user', None) or not req.user.is_authenticated:
            return False

        user = req.user
        is_staff_or_superuser = getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False)
        if 'staff' in self.roles and 'user' not in self.roles:
            return is_staff_or_superuser
        return True

    def get_context_data(self, request=None, **kwargs):
        """
        Return the context data required to render this card.
        """
        req = request or self.request
        context = {
            'card': self,
            'name': self.name,
            'title': self.title,
            'request': req,
        }
        context.update(kwargs)
        return context

    def render(self, context=None, request=None):
        """
        Render the card HTML using its template and context data.
        """
        if not self.template_name:
            return mark_safe('')

        req = request or self.request
        card_context = self.get_context_data(req)
        if context:
            card_context.update(context)

        return mark_safe(render_to_string(self.template_name, card_context, request=req))

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name} (order={self.order})>"


class CardRegistry:
    """
    Thread-safe registry of dashboard cards.
    """

    def __init__(self):
        self._cards = {}
        self._lock = threading.RLock()
        self._discovered = False

    def register(self, card_or_class):
        """
        Register a DashboardCard class or instance. Can be used as a decorator.
        """
        with self._lock:
            if isinstance(card_or_class, type) and issubclass(card_or_class, DashboardCard):
                card_instance = card_or_class()
            elif isinstance(card_or_class, DashboardCard):
                card_instance = card_or_class
            else:
                raise TypeError(f"Expected DashboardCard subclass or instance, got {type(card_or_class)}")

            self._cards[card_instance.name] = card_instance
            return card_or_class

    def unregister(self, name):
        """
        Unregister a card by name.
        """
        with self._lock:
            if name in self._cards:
                del self._cards[name]

    def get_card(self, name):
        """
        Retrieve a registered card instance by name.
        """
        with self._lock:
            return self._cards.get(name)

    def get_cards(self, request=None, role=None, column=None):
        """
        Get all matching cards, optionally filtered by request visibility,
        role ('user' or 'staff'), and column placement, sorted by order.
        """
        with self._lock:
            cards = list(self._cards.values())

        if role:
            cards = [c for c in cards if role in c.roles]

        if column:
            cards = [c for c in cards if c.column == column]

        if request is not None:
            cards = [c for c in cards if c.is_visible(request)]
            for c in cards:
                c.request = request

        cards.sort(key=lambda c: (c.order, c.name))
        return cards

    def clear(self):
        """
        Clear all registered cards.
        """
        with self._lock:
            self._cards.clear()

    def autodiscover(self):
        """
        Autodiscover 'cards.py' modules across installed apps.
        """
        with self._lock:
            if not self._discovered:
                autodiscover_modules('cards')
                self._discovered = True


# Global registry singleton and helper decorator
card_registry = CardRegistry()
register_card = card_registry.register
