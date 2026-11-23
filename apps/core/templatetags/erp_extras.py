from decimal import Decimal

from django import template

from apps.core.permissions import user_can

register = template.Library()


@register.filter
def money(value):
    """Affiche un montant avec séparateur de milliers (affichage arrondi à l'unité)."""
    if value in (None, ""):
        return "0"
    value = Decimal(value).quantize(Decimal("1"))
    return f"{value:,}".replace(",", " ")


@register.filter
def qty(value):
    if value in (None, ""):
        return "0"
    value = Decimal(value).normalize()
    text = format(value, "f")
    return text.replace(".", ",")


@register.simple_tag(takes_context=True)
def can(context, module, action="view"):
    return user_can(context["request"].user, module, action)
