import html
import re

from django import template
from django.utils.safestring import mark_safe

from editor.forms import SenseExampleForm

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


# The sense example form: for editing `example`, or for adding one to the sense when
# there's no `example`. Building it here, when a template needs one, keeps the senses
# querysets lazy in views that don't render them. A view re-rendering a form that
# failed validation attaches it to the sense, and it replaces the form it came from:
# an edit form's instance is its example, an add form's is unsaved, with no pk.
@register.filter()
def example_form(sense, example=None):
    failed_form = getattr(sense, "failed_form", None)
    pk = example.pk if example is not None else None
    if failed_form is not None and failed_form.instance.pk == pk:
        return failed_form
    return SenseExampleForm(instance=example)
