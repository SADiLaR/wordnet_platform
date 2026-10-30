import pytest
from django.urls import reverse
from playwright.sync_api import Page, expect

from lex.models import Language, PartOfSpeech, Synset, Wordnet

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
