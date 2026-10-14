import html
import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def html_escape(s):
    return html.escape(s)


@register.filter()
def highlight(text, q):
    if not text or not q:
        return text
    text = str(text or "")
    q_re = re.compile(re.escape(q), re.IGNORECASE)
    q = html_escape(q)
    return mark_safe(q_re.sub(f"<strong>{q}</strong>", text))
