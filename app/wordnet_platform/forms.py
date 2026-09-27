from django.contrib.auth.forms import AuthenticationForm as _AuthenticationForm
from django.forms.renderers import TemplatesSetting


class BootstrapFormMixin:
    """Customise form for Bootstrap styling, as in term_platform."""

    error_css_class = "alert alert-danger"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class AuthenticationForm(BootstrapFormMixin, _AuthenticationForm):
    # Use term_platform's template renderer only for authentication forms.
    default_renderer = TemplatesSetting
