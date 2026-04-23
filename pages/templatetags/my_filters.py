from django import template

register = template.Library()


@register.filter
def lookup(dictionary, key):
    """Allow {{ dict|lookup:key }} in templates."""
    if isinstance(dictionary, dict):
        return dictionary.get(key, set())
    return set()
