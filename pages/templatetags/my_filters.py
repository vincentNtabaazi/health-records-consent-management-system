from django import template

register = template.Library()


@register.filter
def lookup(dictionary, key):
    """Allow {{ dict|lookup:key }} in templates."""
    if isinstance(dictionary, dict):
        return dictionary.get(key, set())
    return set()

@register.filter
def clean_key(value):
    return value.replace("_", " ").upper()