import pytest

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
