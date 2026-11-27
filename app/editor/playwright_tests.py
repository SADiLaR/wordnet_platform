import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from playwright.sync_api import Page, expect

from lex.models import Language, PartOfSpeech, Sense, Synset, Word, Wordnet

# This file is called playwright_tests.py to avoid manage.py test (test*.py)
# picking it up and executing it.

VIEWPORTS = {
    "mobile": {"width": 360, "height": 800},
    "small_screen": {"width": 1024, "height": 768},
    "desktop": {"width": 1280, "height": 720},
}


def test_front_page_title(page: Page):
    page.goto("/")

    expect(page).to_have_title("AfWN Editor")


@pytest.mark.usefixtures("logged_in")
def test_status_warning(page: Page):
    language = Language.objects.create(iso_code="afr", name="Afrikaans")
    wordnet = Wordnet.objects.create(name="Toets Woordnet", language=language)
    pos = PartOfSpeech.objects.create(name="noun")
    synset = Synset.objects.create(
        definition="'n Toets synset", wordnet=wordnet, pos=pos
    )
    page.goto(reverse("editor:synset_detail", kwargs={"pk": synset.pk}))

    status = page.get_by_role("group", name="Synset status")
    status.get_by_text("Complete", exact=True).click()

    expect(page.get_by_text("This synset may not be complete:")).to_be_visible()


@pytest.fixture
def status_request(page: Page, logged_in):
    language = Language.objects.create(iso_code="afr", name="Afrikaans")
    wordnet = Wordnet.objects.create(name="Toets Woordnet", language=language)
    pos = PartOfSpeech.objects.create(name="noun")
    synset = Synset.objects.create(wordnet=wordnet, pos=pos, status=Synset.Status.DRAFT)
    page.goto(reverse("editor:synset_detail", kwargs={"pk": synset.pk}))
    return (
        page.locator(".status-control"),
        reverse("editor:synset_status_htmx", kwargs={"pk": synset.pk}),
    )


@pytest.mark.parametrize("failure", ["500", "404", "proxy", "network"])
def test_status_request_failure(page: Page, status_request, failure):
    control, url = status_request
    error = page.get_by_role("alert")
    title = page.title()
    # Roll back to a newly confirmed value, not just the page's initial status.
    control.get_by_text("Stub", exact=True).click()
    expect(control.get_by_role("radio", name="Stub", exact=True)).to_have_js_property(
        "defaultChecked", True
    )

    def fail_request(route):
        if failure == "404":
            # Exercise Django's real missing-object response and error template.
            missing_url = reverse("editor:synset_status_htmx", kwargs={"pk": 0})
            route.fulfill(
                response=route.fetch(url=route.request.url.replace(url, missing_url))
            )
        elif failure == "500":
            route.fulfill(
                status=500,
                content_type="text/html",
                body=render_to_string("500.html"),
            )
        elif failure == "network":
            route.abort("failed")
        else:
            route.fulfill(
                status=502,
                content_type="text/html",
                body="<h1>Private proxy details</h1>",
            )

    expect(error).to_be_hidden()
    page.route(f"**{url}", fail_request, times=1)
    control.get_by_text("Complete", exact=True).click()
    expect(error).to_be_visible()
    if failure in ("500", "404"):
        expect(error).to_contain_text(f"({failure})")
        if failure == "404":
            expect(error).to_contain_text(
                "This content may have been deleted or changed since you opened "
                "the page. Please reload the page."
            )
            reload_link = error.get_by_role("link", name="Reload page")
            expect(reload_link).to_be_visible()
            expect(reload_link).to_have_attribute("href", "")
    elif failure == "network":
        expect(error).to_contain_text("Network error")
    else:
        expect(error).to_have_text("Request failed. Please try again.")
        expect(page.get_by_text("Private proxy details")).to_have_count(0)
    expect(control.get_by_role("radio", name="Stub", exact=True)).to_be_checked()
    expect(page).to_have_title(title)


@pytest.mark.parametrize("success_status", [200, 204])
def test_request_error_transitions(page: Page, status_request, success_status):
    control, url = status_request
    error = page.get_by_role("alert")
    page.route(f"**{url}", lambda route: route.abort("failed"), times=1)
    control.get_by_text("Complete", exact=True).click()
    expect(error).to_contain_text("Network error")

    message = "You can't create this while X."
    page.route(
        f"**{url}",
        lambda route: route.fulfill(
            status=409,
            content_type="text/html",
            body=render_to_string(
                "base_error.html",
                {"error_title": "Cannot create", "error_message": message},
            ),
        ),
        times=1,
    )
    control.get_by_text("Complete", exact=True).click()
    expect(error).to_have_text(f"Cannot create {message}")
    expect(error).to_have_count(1)
    expect(control.get_by_role("radio", name="Draft", exact=True)).to_be_checked()

    if success_status == 204:
        # No swap: clearing the error must not depend on replacing the control.
        page.route(f"**{url}", lambda route: route.fulfill(status=204), times=1)
    control.get_by_text("Complete", exact=True).click()
    expect(error).to_be_hidden()
    if success_status == 200:
        # Real success retains the status warning and force-save behaviour.
        expect(page.get_by_text("This synset may not be complete:")).to_be_visible()
        control.get_by_role("button", name="Set to Complete anyway").click()
        expect(
            control.get_by_role("radio", name="Complete", exact=True)
        ).to_be_checked()
        expect(page.get_by_text("This synset may not be complete:")).to_have_count(0)


@pytest.mark.usefixtures("logged_in")
def test_add_usage_example_focuses_textarea(page: Page):
    # The add form starts with a hidden input, which can't take focus
    language = Language.objects.create(iso_code="afr", name="Afrikaans")
    wordnet = Wordnet.objects.create(name="Toets Woordnet", language=language)
    pos = PartOfSpeech.objects.create(name="noun")
    synset = Synset.objects.create(
        definition="'n Toets synset", wordnet=wordnet, pos=pos
    )
    word = Word.objects.create(text="toets", pos=pos, language=language)
    Sense.objects.create(word=word, synset=synset)
    page.goto(reverse("editor:synset_detail", kwargs={"pk": synset.pk}))

    page.get_by_role("button", name="Add usage example").click()

    expect(page.get_by_role("textbox", name="Example for “toets”")).to_be_focused()


@pytest.mark.usefixtures("logged_in")
@pytest.mark.parametrize(
    "viewport, visible",
    [("mobile", True), ("small_screen", False), ("desktop", False)],
)
def test_filter_link_by_viewport(page: Page, viewport, visible):
    page.set_viewport_size(VIEWPORTS[viewport])
    page.goto(reverse("editor:browse_synsets"))

    link = page.get_by_role("link", name="Filter results below", include_hidden=True)
    expect(link).to_be_attached()
    expect(link).to_be_visible(visible=visible)
