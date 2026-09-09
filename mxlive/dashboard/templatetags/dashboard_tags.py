from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def render_card(context, card):
    """
    Render a DashboardCard using the current template context.
    """
    request = getattr(context, 'request', None)
    return card.render(context=context.flatten(), request=request)
