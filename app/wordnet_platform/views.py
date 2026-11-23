from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from django.views import defaults


@login_not_required
def health(request):
    """A very basic (minimal dependency) health endpoint."""
    # If we want/need a health check for DB, cache, files, etc. that should
    # probably be separate.
    return HttpResponse("OK", content_type="text/plain")


# Error handlers, for the whole site (handler400 etc. in urls.py). HTMX requests update
# part of a page, so a full error page would have nowhere to go. Instead they get
# `_request_failed.html`, which HTMX shows at the top of the page (see `htmx-config` in
# the editor's base.html). Other requests, including the admin's, get Django's default
# error pages.


def _request_failed(message, status):
    # Rendered without the request, as Django's own server error page is: the
    # context processors could fail too.
    html = render_to_string(
        "editor/snippets/_request_failed.html", {"message": message}
    )
    return HttpResponse(html, status=status)


def _refused(status):
    return _request_failed(
        _(
            "That didn’t work. Something on this page may have changed since you "
            "opened it. Reload the page and try again."
        ),
        status,
    )


def _is_htmx(request):
    # The middleware that sets request.htmx may not have run if the error happened
    # before it.
    return bool(getattr(request, "htmx", False))


def bad_request(request, exception):
    if _is_htmx(request):
        return _refused(400)
    return defaults.bad_request(request, exception)


def permission_denied(request, exception):
    if _is_htmx(request):
        return _refused(403)
    return defaults.permission_denied(request, exception)


def page_not_found(request, exception):
    if _is_htmx(request):
        return _refused(404)
    return defaults.page_not_found(request, exception)


def server_error(request):
    if _is_htmx(request):
        return _request_failed(
            _("Something went wrong. Reload the page and try again."), 500
        )
    return defaults.server_error(request)
