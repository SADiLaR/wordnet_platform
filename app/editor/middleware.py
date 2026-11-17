from django.contrib.auth.middleware import LoginRequiredMiddleware
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import resolve_url
from django_htmx.http import HttpResponseClientRedirect


class HtmxLoginRequiredMiddleware(LoginRequiredMiddleware):
    """Require login for every view not marked `@login_not_required`, also with HTMX.

    Django's middleware redirects to the login page. An HTMX request would follow
    that redirect and swap the whole login page into part of the page, e.g. the word
    list. Instead, HTMX requests get an `HX-Redirect` header, which makes HTMX load
    the login page as a full page.

    After login, the user should return to the page they were on (HX-Current-URL),
    not to the URL of the HTMX request: that is often a POST-only view.
    """

    def handle_no_permission(self, request, view_func):
        if not request.htmx:
            return super().handle_no_permission(request, view_func)

        login_url = resolve_url(self.get_login_url(view_func))
        # None if the header is missing or names another site, so we can't be
        # used to send someone to another site after login
        next_url = request.htmx.current_url_abs_path
        if next_url:
            redirect_field_name = self.get_redirect_field_name(view_func)
            login_url = redirect_to_login(next_url, login_url, redirect_field_name).url
        return HttpResponseClientRedirect(login_url)
