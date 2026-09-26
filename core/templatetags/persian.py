from django import template

register = template.Library()


@register.filter
def price_fa(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return value
    formatted = f"{n:,}".replace(',', '،')
    return formatted.translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))

@register.filter
def to_fa_digits(value):
    return str(value).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))