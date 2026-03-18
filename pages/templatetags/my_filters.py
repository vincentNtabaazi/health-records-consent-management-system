from django import template

register = template.Library()

@register.filter
def replace_chars(value, arg):
    """
    Replaces all occurrences of a substring with another substring.
    Usage: {{ value|replace_chars:"old_char,new_char" }}
    """
    if isinstance(value, str) and isinstance(arg, str):
        try:
            old_char, new_char = arg.split(',')
            return value.replace(old_char, new_char)
        except ValueError:
            # Handle cases where arg is not in 'old,new' format
            return value
    return value