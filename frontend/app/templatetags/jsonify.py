from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.filter
def jsonify(obj):
    return mark_safe(json.dumps(obj))
