from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse


@login_not_required
def health(request):
    """A very basic (minimal dependency) health endpoint."""
    # If we want/need a health check for DB, cache, files, etc. that should
    # probably be separate.
    return HttpResponse("OK", content_type="text/plain")
