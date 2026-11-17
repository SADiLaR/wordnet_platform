import pytest
from django.conf import settings

# Playwright tests need these overrides to run in Django. To avoid affecting
# other tests, the Playwright tests run separately with pytest, in
# playwright.yml


# settings.py uses manifest storage when DEBUG=False, tests need plain storage:
# https://docs.djangoproject.com/en/5.2/ref/contrib/staticfiles/#manifeststaticfilesstorage
@pytest.fixture(autouse=True)
def plain_static_storage(settings):
    settings.STORAGES = {
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        }
    }


# The test database starts empty, so a test's first wordnet gets pk 1, the default
# source wordnet, whose synsets are read-only. No wordnet has pk 0, so none is the
# source unless a test makes it one.
@pytest.fixture(autouse=True)
def no_source_wordnet(settings):
    settings.SOURCE_WORDNET_ID = 0


# Tests create test data in the database. Playwright's sync API runs an asyncio
# event loop in the test thread, and Django blocks database access from such a
# thread: https://docs.djangoproject.com/en/5.2/topics/async/#async-safety
@pytest.fixture(scope="session", autouse=True)
def allow_async_unsafe():
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
        yield


# Lets tests call page.goto() with a path, relative to the live server:
# https://playwright.dev/python/docs/test-runners#configure-base-url
@pytest.fixture(scope="session")
def base_url(live_server):
    return live_server.url


# Editor pages need login. Logging in through the login form in every test would be
# slow, so the test client logs in and the browser gets its session cookie. Use with
# @pytest.mark.usefixtures("logged_in").
@pytest.fixture
def logged_in(page, client, django_user_model, live_server):
    user = django_user_model.objects.create_user(username="tester")
    client.force_login(user)
    session_cookie = client.cookies[settings.SESSION_COOKIE_NAME]
    page.context.add_cookies(
        [
            {
                "name": session_cookie.key,
                "value": session_cookie.value,
                "url": live_server.url,
            }
        ]
    )
    return user
