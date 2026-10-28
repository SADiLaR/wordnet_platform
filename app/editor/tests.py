from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.html import escape

from editor.filters import SynsetFilter
from editor.models import Assignment
from editor.views import _copied_synsets, _guess_source_synset
from lex.models import (
    Language,
    PartOfSpeech,
    Relation,
    RelationType,
    Sense,
    SenseExample,
    Synset,
    SynsetExample,
    Word,
    Wordnet,
)


class FrontPageTest(SimpleTestCase):
    def test_front_page(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "editor/front_page.html")
        self.assertContains(response, f'href="{reverse("editor:browse_synsets")}"')


class AboutPageTest(SimpleTestCase):
    def test_about_page(self):
        response = self.client.get(reverse("editor:about"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "editor/about.html")
        self.assertContains(response, "<title>About — AfWN Editor</title>")
        self.assertContains(response, "About the African Wordnet Project")
        self.assertContains(response, "https://africanwordnet.wordpress.com/")
        self.assertContains(response, "https://sadilar.org/en/unisa/")
        self.assertContains(response, "About SADiLaR")
        self.assertContains(response, "https://github.com/SADiLaR/wordnet_platform/")
        self.assertContains(response, "Marissa Griesel")
        self.assertContains(response, 'let name = "Marissa.Griesel";')
        self.assertContains(response, 'let domain = "nwu.ac.za";')
        self.assertContains(response, 'id="contact-email"', count=1)
        self.assertContains(response, 'document.getElementById("contact-email")')
        self.assertContains(
            response, "emailElt.href = `mailto:${email}?subject=African+Wordnet+query`;"
        )
        self.assertNotContains(response, "SADiLaR conducted an audit")

    def test_about_url(self):
        self.assertEqual(reverse("editor:about"), "/about/")


class FooterTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")

    def test_authentication_urls(self):
        self.assertEqual(reverse("login"), "/login/")
        self.assertEqual(reverse("logout"), "/logout/")

    def test_footer_for_logged_out_user(self):
        response = self.client.get(reverse("editor:front_page"))

        self.assertContains(response, f'href="{reverse("editor:about")}"')
        self.assertContains(response, f'href="{reverse("login")}"')
        self.assertNotContains(response, f'href="{reverse("admin:index")}"')
        self.assertNotContains(response, f'action="{reverse("logout")}"')

    def test_footer_for_logged_in_user(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("editor:front_page"))

        self.assertContains(response, f'href="{reverse("editor:about")}"')
        self.assertContains(response, f'href="{reverse("admin:index")}"')
        self.assertContains(response, f'action="{reverse("logout")}"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, '<button type="submit"')
        self.assertNotContains(response, f'<a href="{reverse("logout")}"')
        self.assertNotContains(response, f'href="{reverse("login")}"')

    def test_logout_does_not_accept_get(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("logout"))

        self.assertEqual(response.status_code, 405)

    def test_logout_accepts_post(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("editor:front_page"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_page(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")


class EditorViewTest(TestCase):
    def setUp(self):

        language = Language.objects.create(iso_code="afr", name="Afrikaans")
        self.wordnet = Wordnet.objects.create(name="Toets Wordnet", language=language)
        self.wordnet_2 = Wordnet.objects.create(
            name="'n Ander Toets Wordnet", language=language
        )
        self.pos_noun = PartOfSpeech.objects.create(name="noun")
        self.pos_verb = PartOfSpeech.objects.create(name="verb")

        self.synset_a = Synset.objects.create(
            display_name="Toets",
            definition="'n Toets synset",
            wordnet=self.wordnet,
            pos=self.pos_noun,
        )
        self.synset_b = Synset.objects.create(
            definition="Nog 'n toets synset",
            wordnet=self.wordnet,
            pos=self.pos_verb,
            princeton_id="12345678-a",
            status=Synset.Status.DRAFT,
        )
        self.synset_c = Synset.objects.create(
            definition="'n Addisionele toets synset",
            wordnet=self.wordnet,
            pos=self.pos_noun,
        )

        self.synset_d = Synset.objects.create(
            display_name="Toets Twee",
            definition="'n Synset in die tweede wordnet",
            wordnet=self.wordnet_2,
            pos=self.pos_verb,
            princeton_id="12345678-n",
            status=Synset.Status.COMPLETE,
        )

        self.synset_e = Synset.objects.create(
            definition="'n Synset met 'n kopie van 'n ander woordnet",
            wordnet=self.wordnet,
            pos=self.pos_noun,
            copied_from=self.synset_d,
        )

        self.synset_f = Synset.objects.create(
            definition="'n Synset met 'n Princeton ID van 'n ander woordnet",
            wordnet=self.wordnet,
            pos=self.pos_noun,
            princeton_id="12345678-n",
        )

        self.word_1 = Word.objects.create(
            text="toets woord", pos=self.pos_noun, language=language
        )

        self.sense_1 = Sense.objects.create(word=self.word_1, synset=self.synset_b)

        self.sense_2 = Sense.objects.create(word=self.word_1, synset=self.synset_c)

        self.sense_example = SenseExample.objects.create(
            text="Hierdie is 'n toets.", sense=self.sense_1
        )

        self.relation_type = RelationType.objects.create(name="hyper")
        self.rel1 = Relation.objects.create(
            synset_from=self.synset_e,
            synset_to=self.synset_f,
            type=self.relation_type,
        )

        self.rel2 = Relation.objects.create(
            synset_from=self.synset_c,
            synset_to=self.synset_b,
            type=self.relation_type,
        )

    def _get_browse_url(self):
        return reverse("editor:browse_synsets")

    def _get_queue_url(self):
        return reverse("editor:assignment_queue")

    def _get_queue_wn_url(self):
        return reverse(
            "editor:assignment_queue_by_wordnet", kwargs={"wn_pk": self.wordnet.pk}
        )

    def _get_synset_detail_url(self, synset_obj):
        return reverse("editor:synset_detail", kwargs={"pk": synset_obj.pk})

    def _get_synset_detail_url_nonexist(self):
        return reverse("editor:synset_detail", kwargs={"pk": 99999})

    def _get_synset_status_htmx_url(self, synset_obj):
        return reverse("editor:synset_status_htmx", kwargs={"pk": synset_obj.pk})

    def _get_synset_status_htmx_url_nonexist(self):
        return reverse("editor:synset_status_htmx", kwargs={"pk": 99999})

    def _get_synset_definition_url(self, synset_obj):
        return reverse("editor:synset_definition", kwargs={"pk": synset_obj.pk})

    def _get_synset_definition_url_nonexist(self):
        return reverse("editor:synset_definition", kwargs={"pk": 99999})

    def _get_delete_synset_example_url(self, synset_obj, example_obj):
        return reverse(
            "editor:delete_synset_example_htmx",
            kwargs={"synset_pk": synset_obj.pk, "pk": example_obj.pk},
        )

    def _get_add_relation_form_url(self, synset_obj):
        return reverse("editor:add_relation_form_htmx", kwargs={"pk": synset_obj.pk})

    def _get_search_synset_url(self, wordnet_id):
        return reverse("editor:search_synsets_htmx", kwargs={"pk": wordnet_id})

    def _get_add_relation_url(self, synset_obj):
        return reverse("editor:add_relation_htmx", kwargs={"pk": synset_obj.pk})

    def _get_clear_url(self):
        return reverse("editor:clear_htmx")

    def test_browse_synsets(self):
        with self.assertNumQueries(4):
            response = self.client.get(self._get_browse_url())
        self.assertEqual(response.status_code, 200)

    def test_synsets_wordnet_filter(self):
        data = {"wordnet": [self.wordnet.id]}
        wn_filter = SynsetFilter(data=data)
        qs = wn_filter.qs
        self.assertEqual(qs.count(), 5)
        self.assertIn(self.synset_a, qs)
        self.assertNotIn(self.synset_d, qs)

    def test_synsets_pos_filter(self):
        data = {"pos": [self.pos_noun.id]}
        pos_filter = SynsetFilter(data=data)
        qs = pos_filter.qs
        self.assertEqual(qs.count(), 4)
        self.assertIn(self.synset_a, qs)
        self.assertNotIn(self.synset_b, qs)

    def test_synsets_status_filter(self):
        data = {"status": [Synset.Status.COMPLETE]}
        status_filter = SynsetFilter(data=data)
        qs = status_filter.qs
        self.assertEqual(qs.count(), 1)
        self.assertIn(self.synset_d, qs)
        self.assertNotIn(self.synset_b, qs)

    def test_combined_filters(self):
        data = {
            "wordnet": [self.wordnet_2.id],
            "pos": [self.pos_verb.id],
            "status": [Synset.Status.COMPLETE],
        }
        synset_filter = SynsetFilter(data=data)
        qs = synset_filter.qs
        self.assertEqual(qs.count(), 1)
        self.assertIn(self.synset_d, qs)
        self.assertNotIn(self.synset_b, qs)

    def test_browse_synsets_search(self):
        with self.assertNumQueries(4):
            response = self.client.get(self._get_browse_url(), {"search": "toets"})
        self.assertEqual(response.status_code, 200)

    def test_search_filter_definition(self):
        data = {"search": "Addisionele"}
        synset_filter = SynsetFilter(data=data)
        qs = synset_filter.qs
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first(), self.synset_c)

    def test_search_synset_by_pk(self):
        data = {"search": self.synset_a.pk}
        synset_filter = SynsetFilter(data=data)
        qs = synset_filter.qs
        self.assertEqual(qs.count(), 1)
        self.assertIn(self.synset_a, qs)
        self.assertNotIn(self.synset_b, qs)

    def test_search_filter_order(self):
        data = {"search": "toets"}
        self.sense_3 = Sense.objects.create(word=self.word_1, synset=self.synset_a)
        synset_filter = SynsetFilter(data=data)
        qs = synset_filter.qs
        self.assertEqual(qs.count(), 4)
        self.assertEqual(qs[0], self.synset_a)
        self.assertEqual(qs[1], self.synset_b)
        self.assertEqual(qs[2], self.synset_c)

    def test_search_filter_combined(self):
        data = {
            "search": "toets",
            "wordnet": [self.wordnet.id],
        }
        synset_filter = SynsetFilter(data=data)
        qs = synset_filter.qs
        self.assertEqual(qs.count(), 3)
        self.assertIn(self.synset_a, qs)
        self.assertNotIn(self.synset_d, qs)
        with self.assertNumQueries(5):
            response = self.client.get(self._get_browse_url(), data)
        self.assertEqual(response.status_code, 200)

    def test_search_unaccent(self):
        self.synset_a.definition = "Die bokkie blêr"
        self.synset_a.save(update_fields=["definition"])
        data = {
            "search": "bler",
        }
        synset_filter = SynsetFilter(data=data)
        qs = synset_filter.qs
        self.assertEqual(qs.count(), 1)
        self.assertIn(self.synset_a, qs)

    def test_queue_by_wordnet_existing(self):
        with self.assertNumQueries(2):
            response = self.client.get(self._get_queue_wn_url())
        self.assertEqual(response.status_code, 200)

    def test_queue_by_wordnet_non_existing(self):
        nonexist_url = reverse(
            "editor:assignment_queue_by_wordnet", kwargs={"wn_pk": 99999}
        )
        response = self.client.get(nonexist_url)
        self.assertEqual(response.status_code, 404)

    def test_queue_existing(self):
        with self.assertNumQueries(1):
            response = self.client.get(self._get_queue_url())
        self.assertEqual(response.status_code, 200)

    def test_synset_detail_existing_no_princeton(self):
        with self.assertNumQueries(12):
            response = self.client.get(self._get_synset_detail_url(self.synset_a))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["synset"], self.synset_a)

    def test_synset_detail_existing_with_princeton(self):
        with self.assertNumQueries(13):
            response = self.client.get(self._get_synset_detail_url(self.synset_f))
        self.assertEqual(response.status_code, 200)

    def test_synset_detail_non_existing(self):
        with self.assertNumQueries(1):
            response = self.client.get(self._get_synset_detail_url_nonexist())
        self.assertEqual(response.status_code, 404)

    def test_synset_detail_senses_excludes_other_synsets(self):
        response = self.client.get(self._get_synset_detail_url(self.synset_b))
        self.assertQuerySetEqual(
            response.context["senses"],
            [self.sense_1],
            ordered=False,
        )

    def test_guess_source_synset(self):
        # A synset with the old tool's form of synset_d's Princeton ID
        old_id_synset = Synset.objects.create(
            definition="'n Gemigreerde synset",
            wordnet=self.wordnet,
            pos=self.pos_verb,
            princeton_id=f"ENG20-{self.synset_d.princeton_id}",
        )
        with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
            existing = _guess_source_synset(self.synset_f)
            no_match = _guess_source_synset(self.synset_b)
            no_princeton_id = _guess_source_synset(self.synset_a)
            not_itself = _guess_source_synset(self.synset_d)
            old_id = _guess_source_synset(old_id_synset)
        self.assertEqual(existing, self.synset_d)
        self.assertEqual(no_match, None)
        self.assertEqual(no_princeton_id, None)
        self.assertEqual(not_itself, None)
        self.assertEqual(old_id, None)

    def test_guess_source_synset_view_existing(self):
        with self.assertNumQueries(16):
            with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
                response = self.client.get(self._get_synset_detail_url(self.synset_f))
            self.assertEqual(response.context["source_synset"], self.synset_d)

    def test_copied_source_synset(self):
        with self.assertNumQueries(15):
            with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
                response = self.client.get(self._get_synset_detail_url(self.synset_e))
            self.assertEqual(response.context["source_synset"], self.synset_d)

    def test_synset_detail_no_relations(self):
        # synset_a has no relations and no source synset (no Princeton ID, not copied)
        self.assertFalse(
            Relation.objects.filter(
                Q(synset_from=self.synset_a) | Q(synset_to=self.synset_a)
            ).exists()
        )
        self.assertIsNone(self.synset_a.copied_from_id)
        self.assertIsNone(self.synset_a.princeton_id)
        # Queries:
        # fetch synset_a (with pos, wordnet, language, and the same for copied_from)
        # 8 concern exists() checks (_synset_context)
        # relations of synset_a (_synset_context)
        # senses of synset_a (none, so no example prefetch)
        # (no source synset: nothing linked, and no Princeton ID to guess from)
        with self.assertNumQueries(12):
            response = self.client.get(self._get_synset_detail_url(self.synset_a))
        self.assertContains(response, "No relations.", count=1)
        # The working card can still add one
        self.assertContains(
            response,
            reverse("editor:add_relation_form_htmx", kwargs={"pk": self.synset_a.pk}),
        )

    def test_synset_detail_source_card_readonly(self):
        # Both cards share _synset_card_body.html; only the working card is editable
        self.assertEqual(self.synset_e.copied_from_id, self.synset_d.pk)
        # synset_e has a relation (rel1); synset_d, its source, has none
        self.assertTrue(Relation.objects.filter(synset_from=self.synset_e).exists())
        self.assertFalse(
            Relation.objects.filter(
                Q(synset_from=self.synset_d) | Q(synset_to=self.synset_d)
            ).exists()
        )
        # Queries:
        # fetch synset_e (with pos, wordnet, language, and the same for copied_from)
        # 8 concern exists() checks (_synset_context)
        # relations of synset_e (_synset_context)
        # relations of synset_d (_source_synset_context)
        # senses of synset_e (none, so no example prefetch)
        # senses of synset_d (none, so no example prefetch)
        with self.assertNumQueries(15):
            with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
                response = self.client.get(self._get_synset_detail_url(self.synset_e))
        self.assertContains(response, escape(self.synset_d.definition))
        # The copied synsets card is only for synsets in the source wordnet
        self.assertTemplateNotUsed(response, "editor/snippets/_copied_synsets.html")
        # One definition form: the working card's
        self.assertContains(response, 'name="definition"', count=1)
        # Only the source card has no relations to show
        self.assertContains(response, "No relations.", count=1)
        # Only a link or unlink highlights the card
        self.assertNotContains(response, "just-saved")
        # No word search or relation form for the source synset
        for url_name in ("search_words_htmx", "add_relation_form_htmx"):
            self.assertNotContains(
                response, reverse(f"editor:{url_name}", kwargs={"pk": self.synset_d.pk})
            )
            self.assertContains(
                response, reverse(f"editor:{url_name}", kwargs={"pk": self.synset_e.pk})
            )

    def _post_link_synset(self, synset_obj, target_pk):
        with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
            return self.client.post(
                reverse("editor:link_synset_htmx", kwargs={"pk": synset_obj.pk}),
                {"target_pk": target_pk},
            )

    def _assert_source_card(self, response, state):
        # The source card's border, header and actions in a state: "linked",
        # "suggested" or "none". For the card snippet only: on the full page, the
        # working card has a border of its own.
        actions = {
            "linked": ["Change", "Unlink"],
            "suggested": ["Link", "Search other"],
            "none": ["Search"],
        }[state]
        for label in ("Change", "Unlink", "Link", "Search other", "Search"):
            expected = 1 if label in actions else 0
            self.assertContains(response, f">{label}</button>", count=expected)
        if state == "linked":
            self.assertContains(response, "border-info", count=1)
        else:
            self.assertContains(response, "border-secondary-subtle", count=1)
        # A linked or suggested source shows its wordnet; only a suggestion is marked
        wordnet_name = f"({escape(str(self.wordnet_2))})"
        self.assertContains(response, wordnet_name, count=int(state != "none"))
        self.assertContains(response, ">Suggested<", count=int(state == "suggested"))
        self.assertContains(
            response, "No source synset linked.", count=int(state == "none")
        )

    def test_link_source_synset(self):
        self.synset_a.refresh_from_db()
        self.assertIsNone(self.synset_a.copied_from)
        self.assertEqual(self.synset_a.status, Synset.Status.STUB)
        # The target is in the source wordnet, as a real source synset would be
        self.assertEqual(self.synset_d.wordnet_id, self.wordnet_2.pk)
        # synset_a is a noun, synset_d a verb. The source wordnet gets its own
        # language, so the warning can name both.
        self.assertNotEqual(self.synset_a.pos_id, self.synset_d.pos_id)
        english = Language.objects.create(iso_code="eng", name="English")
        Wordnet.objects.filter(pk=self.wordnet_2.pk).update(language=english)
        # Queries:
        # fetch synset_a (with pos, wordnet__language)
        # fetch synset_d (target, with pos, wordnet__language)
        # update synset_a
        # insert history record
        # relations of synset_d (_source_synset_context)
        # senses of synset_d (none, so no example prefetch)
        with self.assertNumQueries(7):
            response = self._post_link_synset(self.synset_a, self.synset_d.pk)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "editor/snippets/_source_synset.html")
        self.assertTemplateNotUsed(response, "editor/synset_detail.html")
        self.assertEqual(response.context["source_synset"], self.synset_d)
        self._assert_source_card(response, "linked")
        self.assertContains(response, "just-saved", count=1)
        # A different part of speech warns, but doesn't block the link
        self.assertContains(
            response,
            "Different parts of speech: Afrikaans <strong>(noun)</strong> "
            "vs English <strong>(verb)</strong>.",
        )
        self.synset_a.refresh_from_db()
        self.assertEqual(self.synset_a.copied_from_id, self.synset_d.pk)
        # Linking isn't a change to the synset's content
        self.assertEqual(self.synset_a.status, Synset.Status.STUB)

    def test_link_source_synset_same_pos(self):
        noun_source = Synset.objects.create(
            definition="'n Selfstandige naamwoord in die tweede wordnet",
            wordnet=self.wordnet_2,
            pos=self.pos_noun,
        )
        self.assertEqual(self.synset_a.pos_id, noun_source.pos_id)
        # Queries:
        # fetch synset_a (with pos, wordnet__language)
        # fetch noun_source (target, with pos, wordnet__language)
        # update synset_a
        # insert history record
        # relations of noun_source (_source_synset_context)
        # senses of noun_source (none, so no example prefetch)
        with self.assertNumQueries(7):
            response = self._post_link_synset(self.synset_a, noun_source.pk)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Different parts of speech")

    def test_link_source_synset_not_in_source_wordnet(self):
        # The security test: synset_c is in the working wordnet, not the source one
        self.assertNotEqual(self.synset_c.wordnet_id, self.wordnet_2.pk)
        self.assertIsNone(self.synset_a.copied_from_id)
        # Queries:
        # fetch synset_a (with pos, wordnet__language)
        # fetch synset_c (target, filtered on the source wordnet: no match)
        with self.assertNumQueries(2):
            response = self._post_link_synset(self.synset_a, self.synset_c.pk)
        self.assertEqual(response.status_code, 404)
        self.synset_a.refresh_from_db()
        self.assertIsNone(self.synset_a.copied_from_id)

    def test_link_source_synset_itself(self):
        # synset_d is in the source wordnet, so only the exclude() stops this
        self.assertEqual(self.synset_d.wordnet_id, self.wordnet_2.pk)
        self.assertIsNone(self.synset_d.copied_from_id)
        # Queries:
        # fetch synset_d (with pos, wordnet__language)
        # fetch synset_d as target (excluded: no match)
        with self.assertNumQueries(2):
            response = self._post_link_synset(self.synset_d, self.synset_d.pk)
        self.assertEqual(response.status_code, 404)
        self.synset_d.refresh_from_db()
        self.assertIsNone(self.synset_d.copied_from_id)

    def test_link_source_synset_already_linked(self):
        self.assertEqual(self.synset_e.copied_from_id, self.synset_d.pk)
        history_count = self.synset_e.history.count()
        # Queries:
        # fetch synset_e (with pos, wordnet__language)
        # fetch synset_d (target, with pos, wordnet__language)
        # (no update or history record: nothing changed)
        # relations of synset_d (_source_synset_context)
        # senses of synset_d (none, so no example prefetch)
        # Only this count checks that the card reuses the fetched target, rather than
        # loading synset_e's source, its wordnet, language and POS again
        with self.assertNumQueries(5):
            response = self._post_link_synset(self.synset_e, self.synset_d.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["source_synset"], self.synset_d)
        # Every save adds a history record, so an unchanged count means no save
        self.assertEqual(self.synset_e.history.count(), history_count)
        # Nothing changed, but the card still shows the click was handled
        self._assert_source_card(response, "linked")
        self.assertContains(response, "just-saved", count=1)

    def test_unlink_source_synset(self):
        self.assertEqual(self.synset_e.copied_from_id, self.synset_d.pk)
        self.assertEqual(self.synset_e.status, Synset.Status.STUB)
        # No Princeton ID, so there's no suggestion to fall back to
        self.assertIsNone(self.synset_e.princeton_id)
        history_count = self.synset_e.history.count()
        # Queries:
        # fetch synset_e (with pos, wordnet__language)
        # (an empty target_pk: no target to fetch)
        # update synset_e
        # insert history record
        # (no guess: no Princeton ID)
        with self.assertNumQueries(3):
            response = self._post_link_synset(self.synset_e, "")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "editor/snippets/_source_synset.html")
        self.assertIsNone(response.context["source_synset"])
        self._assert_source_card(response, "none")
        self.assertContains(response, "just-saved", count=1)
        self.synset_e.refresh_from_db()
        self.assertIsNone(self.synset_e.copied_from_id)
        self.assertEqual(self.synset_e.history.count(), history_count + 1)
        # Unlinking isn't a change to the synset's content
        self.assertEqual(self.synset_e.status, Synset.Status.STUB)

    def test_unlink_source_synset_falls_back_to_suggestion(self):
        # synset_f's Princeton ID matches synset_d, but it's linked to another source
        other_source = Synset.objects.create(
            definition="'n Ander bron in die tweede wordnet",
            wordnet=self.wordnet_2,
            pos=self.pos_noun,
        )
        Synset.objects.filter(pk=self.synset_f.pk).update(copied_from=other_source)
        self.synset_f.refresh_from_db()
        self.assertEqual(self.synset_f.copied_from_id, other_source.pk)
        with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
            self.assertEqual(_guess_source_synset(self.synset_f), self.synset_d)
        # Queries:
        # fetch synset_f (with pos, wordnet__language)
        # update synset_f
        # insert history record
        # guess the source synset (finds synset_d, with pos, wordnet__language)
        # relations of synset_d (_source_synset_context)
        # synset examples of synset_d (_synset_card_body.html)
        # senses of synset_d (none, so no example prefetch)
        with self.assertNumQueries(7):
            response = self._post_link_synset(self.synset_f, "")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["source_synset"], self.synset_d)
        self._assert_source_card(response, "suggested")
        self.assertContains(response, "just-saved", count=1)
        self.synset_f.refresh_from_db()
        self.assertIsNone(self.synset_f.copied_from_id)

    def test_unlink_source_synset_not_linked(self):
        self.assertIsNone(self.synset_a.copied_from_id)
        self.assertIsNone(self.synset_a.princeton_id)
        history_count = self.synset_a.history.count()
        # Queries:
        # fetch synset_a (with pos, wordnet__language)
        # (no update or history record: nothing was linked)
        # (no guess: no Princeton ID)
        with self.assertNumQueries(1):
            response = self._post_link_synset(self.synset_a, "")
        self.assertEqual(response.status_code, 200)
        self._assert_source_card(response, "none")
        # Every save adds a history record, so an unchanged count means no save
        self.assertEqual(self.synset_a.history.count(), history_count)

    def test_synset_detail_in_source_wordnet(self):
        # synset_d is in the source wordnet. Its copies are synset_e (linked) and
        # synset_f (same Princeton ID, not linked), both in self.wordnet, the only
        # other wordnet.
        self.assertEqual(self.synset_d.wordnet_id, self.wordnet_2.pk)
        self.assertEqual(self.synset_e.copied_from_id, self.synset_d.pk)
        self.assertIsNone(self.synset_f.copied_from_id)
        self.assertEqual(self.synset_f.princeton_id, self.synset_d.princeton_id)
        self.assertEqual(set(Wordnet.objects.all()), {self.wordnet, self.wordnet_2})
        # Queries:
        # fetch synset_d (with pos, wordnet, language, and the same for copied_from)
        # 8 concern exists() checks (_synset_context)
        # relations of synset_d (_synset_context)
        # copies of synset_d, with their wordnets (_copied_synsets)
        # wordnets for the stub dropdown (_source_synset_context)
        # synset examples of synset_d (template)
        # senses of synset_d (none, so no example prefetch)
        # (no source card: no guess, no source relations or senses)
        with self.assertNumQueries(14):
            with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
                response = self.client.get(self._get_synset_detail_url(self.synset_d))
        # The copied synsets card takes the source card's place
        self.assertTemplateNotUsed(response, "editor/snippets/_source_synset.html")
        self.assertTemplateUsed(response, "editor/snippets/_copied_synsets.html")
        # The source synset context returned early: no source synset was looked up
        self.assertTrue(response.context["in_source_wordnet"])
        self.assertNotIn("source_synset", response.context)
        # Both copies are linked; only synset_f, which isn't linked, is a suggestion
        for copy in (self.synset_e, self.synset_f):
            self.assertContains(response, self._get_synset_detail_url(copy))
        self.assertContains(response, "Suggested", count=1)
        # Every wordnet but the source has a copy, so there's no form to create one
        self.assertNotContains(
            response, reverse("editor:create_stub", kwargs={"pk": self.synset_d.pk})
        )

    def test_copied_synsets(self):
        # synset_d is in the source wordnet. synset_e is linked to it; synset_f only
        # shares its Princeton ID. Both are in self.wordnet.
        self.assertEqual(self.synset_e.copied_from_id, self.synset_d.pk)
        self.assertIsNone(self.synset_f.copied_from_id)
        self.assertEqual(self.synset_f.princeton_id, self.synset_d.princeton_id)
        # A copy in a wordnet whose name sorts before self.wordnet's
        first_wordnet = Wordnet.objects.create(
            name="Eerste Toets Wordnet", language=self.wordnet.language
        )
        self.assertLess(first_wordnet.name, self.wordnet.name)
        first_copy = Synset.objects.create(
            definition="'n Kopie in die eerste wordnet",
            wordnet=first_wordnet,
            pos=self.pos_verb,
            copied_from=self.synset_d,
        )
        # Not copies: another synset in the source wordnet with the same Princeton ID,
        # a synset linked to that one (so it's not a suggestion for synset_d), and a
        # synset with the old tool's form of the ID
        duplicate = Synset.objects.create(
            definition="'n Duplikaat in die bronwordnet",
            wordnet=self.wordnet_2,
            pos=self.pos_verb,
            princeton_id=self.synset_d.princeton_id,
        )
        Synset.objects.create(
            definition="'n Kopie van die duplikaat",
            wordnet=first_wordnet,
            pos=self.pos_verb,
            princeton_id=self.synset_d.princeton_id,
            copied_from=duplicate,
        )
        Synset.objects.create(
            definition="'n Gemigreerde synset",
            wordnet=first_wordnet,
            pos=self.pos_verb,
            princeton_id=f"ENG20-{self.synset_d.princeton_id}",
        )
        # Queries:
        # copies of synset_d, with their wordnets: reading a copy's wordnet, as the
        # card does, takes no query of its own
        with self.assertNumQueries(1):
            with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
                copied_synsets = list(_copied_synsets(self.synset_d))
                wordnet_names = [copy.wordnet.name for copy in copied_synsets]
        # By wordnet name, then display name (all empty here), then pk
        self.assertEqual(copied_synsets, [first_copy, self.synset_e, self.synset_f])
        self.assertEqual(
            wordnet_names, [first_wordnet.name, self.wordnet.name, self.wordnet.name]
        )

    def test_synset_detail_no_copies(self):
        # A source synset without a Princeton ID, so _copied_synsets() looks for linked
        # copies only. Without that check, it would filter on princeton_id=None, which
        # Django turns into IS NULL: every unlinked synset without a Princeton ID, like
        # synset_a, would be listed as a copy.
        synset = Synset.objects.create(
            definition="'n Bronsynset sonder kopieë",
            wordnet=self.wordnet_2,
            pos=self.pos_noun,
        )
        self.assertIsNone(self.synset_a.princeton_id)
        self.assertIsNone(self.synset_a.copied_from_id)
        # The source wordnet and one other, which can have a stub
        self.assertEqual(set(Wordnet.objects.all()), {self.wordnet_2, self.wordnet})
        # Queries:
        # fetch synset (with pos, wordnet, language, and the same for copied_from)
        # 8 concern exists() checks (_synset_context)
        # relations of synset (_synset_context)
        # copies of synset (_copied_synsets)
        # wordnets for the stub dropdown (_source_synset_context)
        # synset examples of synset (template)
        # senses of synset (none, so no example prefetch)
        with self.assertNumQueries(14):
            with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
                response = self.client.get(self._get_synset_detail_url(synset))
        self.assertEqual(response.context["copied_synsets"], [])
        self.assertContains(response, "Not copied to any wordnet yet.")
        # Every wordnet but the source can have a stub
        self.assertEqual(response.context["stub_wordnets"], [self.wordnet])
        self.assertContains(
            response, reverse("editor:create_stub", kwargs={"pk": synset.pk})
        )
        self.assertContains(
            response,
            f'<option value="{self.wordnet.pk}">{self.wordnet}</option>',
            html=True,
        )

    def _post_create_stub(self, synset_obj, wordnet_pk):
        with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
            return self.client.post(
                reverse("editor:create_stub", kwargs={"pk": synset_obj.pk}),
                {"wordnet_pk": wordnet_pk},
            )

    def test_create_stub(self):
        # synset_d is in the source wordnet, and new_wordnet has no copy of it
        self.assertEqual(self.synset_d.wordnet_id, self.wordnet_2.pk)
        new_wordnet = Wordnet.objects.create(
            name="Nuwe Toets Wordnet", language=self.wordnet.language
        )
        self.assertFalse(Synset.objects.filter(wordnet=new_wordnet).exists())
        # Queries:
        # fetch synset_d, checking it's in the source wordnet
        # fetch new_wordnet, checking it's not the source wordnet
        # look for a copy of synset_d in new_wordnet (none)
        # insert the stub
        # insert its history record
        with self.assertNumQueries(5):
            response = self._post_create_stub(self.synset_d, new_wordnet.pk)
        stub = Synset.objects.get(wordnet=new_wordnet)
        self.assertRedirects(
            response, self._get_synset_detail_url(stub), fetch_redirect_response=False
        )
        self.assertEqual(stub.pos_id, self.synset_d.pos_id)
        self.assertEqual(stub.princeton_id, self.synset_d.princeton_id)
        self.assertEqual(stub.copied_from_id, self.synset_d.pk)
        self.assertEqual(stub.status, Synset.Status.STUB)
        self.assertEqual(stub.definition, "")
        self.assertEqual(stub.history.count(), 1)

    def test_create_stub_existing_copy(self):
        # new_wordnet has a migrated synset with synset_d's Princeton ID, never linked.
        # It counts as a copy, so it's opened instead of creating a second one.
        new_wordnet = Wordnet.objects.create(
            name="Nuwe Toets Wordnet", language=self.wordnet.language
        )
        migrated = Synset.objects.create(
            definition="'n Gemigreerde synset",
            wordnet=new_wordnet,
            pos=self.pos_verb,
            princeton_id=self.synset_d.princeton_id,
        )
        synset_count = Synset.objects.count()
        # Queries:
        # fetch synset_d, checking it's in the source wordnet
        # fetch new_wordnet, checking it's not the source wordnet
        # look for a copy of synset_d in new_wordnet (found: migrated)
        with self.assertNumQueries(3):
            response = self._post_create_stub(self.synset_d, new_wordnet.pk)
        self.assertRedirects(
            response,
            self._get_synset_detail_url(migrated),
            fetch_redirect_response=False,
        )
        self.assertEqual(Synset.objects.count(), synset_count)

    def test_create_stub_not_from_source_wordnet(self):
        # synset_a isn't in the source wordnet, so it can't be copied
        self.assertNotEqual(self.synset_a.wordnet_id, self.wordnet_2.pk)
        synset_count = Synset.objects.count()
        # Queries:
        # fetch synset_a in the source wordnet (not found)
        with self.assertNumQueries(1):
            response = self._post_create_stub(self.synset_a, self.wordnet.pk)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Synset.objects.count(), synset_count)

    def test_create_stub_into_source_wordnet(self):
        synset_count = Synset.objects.count()
        # Queries:
        # fetch synset_d, checking it's in the source wordnet
        # fetch the source wordnet, excluded as a target (not found)
        with self.assertNumQueries(2):
            response = self._post_create_stub(self.synset_d, self.wordnet_2.pk)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Synset.objects.count(), synset_count)

    def test_status_htmx_get(self):
        with self.assertNumQueries(1):
            response = self.client.get(self._get_synset_status_htmx_url(self.synset_a))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context.get("warnings"))

    def test_status_htmx_get_nonexist(self):
        with self.assertNumQueries(1):
            response = self.client.get(self._get_synset_status_htmx_url_nonexist())
        self.assertEqual(response.status_code, 404)

    def test_status_htmx_post_non_complete(self):
        with self.assertNumQueries(3):
            response = self.client.post(
                self._get_synset_status_htmx_url(self.synset_a),
                {"new_status": Synset.Status.DRAFT},
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context.get("warnings"))

        self.synset_a.refresh_from_db()
        self.assertEqual(self.synset_a.status, Synset.Status.DRAFT)

    def test_status_htmx_post_complete_triggers_warning(self):
        with self.subTest("no words, no relations"):
            with self.assertNumQueries(3):
                response = self.client.post(
                    self._get_synset_status_htmx_url(self.synset_a),
                    {"new_status": Synset.Status.COMPLETE},
                )
            self.assertTrue(response.context["warnings"])
            self.synset_a.refresh_from_db()
            self.assertEqual(self.synset_a.status, Synset.Status.STUB)

        with self.subTest("missing usage example"):
            with self.assertNumQueries(5):
                response = self.client.post(
                    self._get_synset_status_htmx_url(self.synset_c),
                    {"new_status": Synset.Status.COMPLETE},
                )
            self.assertTrue(response.context["warnings"])
            self.synset_c.refresh_from_db()
            self.assertEqual(self.synset_c.status, Synset.Status.STUB)

    def test_status_htmx_post_complete_force_save(self):
        with self.assertNumQueries(3):
            response = self.client.post(
                self._get_synset_status_htmx_url(self.synset_a),
                {"new_status": Synset.Status.COMPLETE, "force_save": True},
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context.get("warnings"))
        self.synset_a.refresh_from_db()
        self.assertEqual(self.synset_a.status, Synset.Status.COMPLETE)

    def test_status_htmx_post_complete_no_warning_when_complete(self):
        with self.assertNumQueries(7):
            response = self.client.post(
                self._get_synset_status_htmx_url(self.synset_b),
                {"new_status": Synset.Status.COMPLETE},
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context.get("warnings"))
        self.synset_b.refresh_from_db()
        self.assertEqual(self.synset_b.status, Synset.Status.COMPLETE)

    def test_definition_post(self):
        new_def = "a complete new definition"
        with self.assertNumQueries(3):
            response = self.client.post(
                self._get_synset_definition_url(self.synset_a),
                {"definition": new_def},
            )
        self.assertRedirects(response, self._get_synset_detail_url(self.synset_a))
        self.synset_a.refresh_from_db()
        self.assertEqual(self.synset_a.definition, new_def)
        self.assertEqual(self.synset_a.status, Synset.Status.DRAFT)

    def test_definition_post_invalid(self):
        old_def = self.synset_e.definition
        self.assertTrue(old_def)
        # Queries (the same as loading the page):
        # fetch synset_e (with pos, wordnet, language, and the same for copied_from)
        # 8 concern exists() checks (_synset_context)
        # relations of synset_e (_synset_context)
        # relations of synset_d (_source_synset_context)
        # senses of synset_e (none, so no example prefetch)
        # senses of synset_d (none, so no example prefetch)
        with self.assertNumQueries(15):
            response = self.client.post(
                self._get_synset_definition_url(self.synset_e),
                {"definition": ""},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["definition_form"].errors)
        self.assertEqual(response.context["source_synset"], self.synset_d)
        self.synset_e.refresh_from_db()
        self.assertEqual(self.synset_e.definition, old_def)

    def test_definition_post_non_existing(self):
        with self.assertNumQueries(1):
            response = self.client.post(
                self._get_synset_definition_url_nonexist(),
                {"definition": "a new definition"},
            )
        self.assertEqual(response.status_code, 404)

    def test_definition_get_not_allowed(self):
        with self.assertNumQueries(1):
            response = self.client.get(
                self._get_synset_definition_url(self.synset_a),
            )
        self.assertEqual(response.status_code, 405)

    def test_delete_synset_example_htmx(self):
        synset_example = SynsetExample.objects.create(
            synset_id=self.synset_a.pk,
            text="Test synset example",
        )
        # Queries:
        # fetch synset
        # fetch synset example
        # DELETE example
        # INSERT synset example history
        # fetch updated synset example
        with self.assertNumQueries(5):
            response = self.client.post(
                self._get_delete_synset_example_url(self.synset_a, synset_example)
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SynsetExample.objects.filter(pk=synset_example.pk).exists())

    def test_suggest_relation_htmx_get_no_type(self):
        # Queries:
        # fetch synset
        # fetch types (evaluated by _add_relation_new.html)
        with self.assertNumQueries(2):
            response = self.client.get(self._get_add_relation_form_url(self.synset_a))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "editor/snippets/_add_relation_new.html")
        self.assertIn("types", response.context)

    def test_suggest_relation_htmx_get_with_type(self):
        # Queries:
        # fetch synset
        # types not evaluated by _add_relation.html
        with self.assertNumQueries(2):
            response = self.client.get(
                self._get_add_relation_form_url(self.synset_a),
                {"type": self.relation_type.pk, "direction": "outgoing"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "editor/snippets/_add_relation.html")

    def test_search_synset(self):
        # Queries:
        # fetch synset
        # search query
        with self.assertNumQueries(2):
            response = self.client.get(
                self._get_search_synset_url(self.synset_a.wordnet_id),
                {"q": "toets"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "editor/snippets/_synset_results.html")
        self.assertIsNotNone(response.context["synsets"])

    def test_add_relation_htmx_post_outgoing(self):
        # Queries:
        # fetch synset_a
        # fetch synset_b (target)
        # fetch rel_type
        # circular exists()
        # duplicate exists()
        # create relation
        # history (relation)
        # status save
        # history (synset)
        # relations (_synset_context, synset reused from memory)
        with self.assertNumQueries(18):
            response = self.client.post(
                self._get_add_relation_url(self.synset_a),
                {
                    "type": self.relation_type.pk,
                    "direction": "outgoing",
                    "target_pk": self.synset_b.pk,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Relation.objects.filter(
                synset_from=self.synset_a, synset_to=self.synset_b
            ).exists()
        )

    def test_add_relation_htmx_post_incoming(self):
        # Queries:
        # fetch synset_a
        # fetch synset_b (target)
        # fetch rel_type
        # circular exists()
        # duplicate exists()
        # create relation
        # history (relation)
        # status save
        # history (synset)
        # relations (_synset_context, synset reused from memory)
        with self.assertNumQueries(18):
            response = self.client.post(
                self._get_add_relation_url(self.synset_a),
                {
                    "type": self.relation_type.pk,
                    "direction": "incoming",
                    "target_pk": self.synset_b.pk,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Relation.objects.filter(
                synset_from=self.synset_b, synset_to=self.synset_a
            ).exists()
        )

    def test_add_relation_htmx_post_invalid_direction(self):
        # Queries:
        # fetch synset_a
        # fetch synset_b (target)
        # relations (_synset_context, synset reused)
        with self.assertNumQueries(11):
            response = self.client.post(
                self._get_add_relation_url(self.synset_a),
                {
                    "type": self.relation_type.id,
                    "direction": "sideways",
                    "target_pk": self.synset_b.pk,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)

    def test_add_relation_htmx_post_different_wordnet(self):
        # Queries:
        # fetch synset_a
        # fetch synset_d (target)
        # relations (_synset_context, synset reused)
        with self.assertNumQueries(11):
            response = self.client.post(
                self._get_add_relation_url(self.synset_a),
                {
                    "type": self.relation_type.pk,
                    "direction": "outgoing",
                    "target_pk": self.synset_d.pk,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)

    def test_add_relation_htmx_post_self(self):
        # Queries:
        # fetch synset_a
        # fetch synset_a (target, same pk)
        # relations (_synset_context, synset reused)
        with self.assertNumQueries(11):
            response = self.client.post(
                self._get_add_relation_url(self.synset_a),
                {
                    "type": self.relation_type.pk,
                    "direction": "outgoing",
                    "target_pk": self.synset_a.pk,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)

    def test_add_relation_htmx_post_circular(self):
        # synset_c → synset_b (hyper) exists; adding synset_b → synset_c should be caught
        # Queries:
        # fetch synset_b
        # fetch synset_c (target)
        # fetch rel_type
        # circular exists() → True
        # relations (_synset_context, synset reused)
        with self.assertNumQueries(13):
            response = self.client.post(
                self._get_add_relation_url(self.synset_b),
                {
                    "type": self.relation_type.pk,
                    "direction": "outgoing",
                    "target_pk": self.synset_c.pk,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)

    def test_delete_relation(self):
        # rel2 is synset_c's only relation, in either direction
        self.assertQuerySetEqual(
            Relation.objects.filter(
                Q(synset_from=self.synset_c) | Q(synset_to=self.synset_c)
            ),
            [self.rel2],
        )
        # get synset
        # get relation
        # delete relation
        # create historical relation
        # update synset status
        # create historical synset
        # ... full synset info
        with self.assertNumQueries(15):
            response = self.client.post(
                reverse(
                    "editor:delete_relation_htmx",
                    kwargs={"synset_pk": self.synset_c.pk, "rel_pk": self.rel2.pk},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Relation.objects.filter(synset_from=self.synset_c).exists())
        # The last relation is gone, so the re-rendered section says so
        self.assertContains(response, "No relations.", count=1)
        # The response brings its own wrapper, which replaces the old one (outerHTML)
        self.assertContains(response, 'class="relations-section"', count=1)

        # If someone tries again, it should be acceptable as well:
        response = self.client.post(
            reverse(
                "editor:delete_relation_htmx",
                kwargs={"synset_pk": self.synset_c.pk, "rel_pk": self.rel2.pk},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_clear_htmx(self):
        with self.assertNumQueries(0):
            response = self.client.get(self._get_clear_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

    def _get_search_words_url(self, synset_obj):
        return reverse("editor:search_words_htmx", kwargs={"pk": synset_obj.pk})

    def _get_add_sense_url(self, synset_obj):
        return reverse("editor:add_sense_htmx", kwargs={"pk": synset_obj.pk})

    def test_search_words_htmx_no_query(self):
        # Returns empty response when q is missing
        with self.assertNumQueries(0):
            response = self.client.get(self._get_search_words_url(self.synset_a))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

    def test_search_words_htmx_returns_matching_words(self):
        # Queries:
        # fetch synset (with wordnet, language, pos)
        # search words (filtered by language, pos, text)
        with self.assertNumQueries(2):
            response = self.client.get(
                self._get_search_words_url(self.synset_a), {"q": "toets"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "editor/snippets/_word_results.html")
        self.assertContains(response, "<strong>toets</strong> woord", html=True)

    def test_search_words_htmx_excludes_already_linked(self):
        # word_1 is linked to synset_a via a new sense; should not appear in results
        # Queries:
        # fetch synset (with wordnet, language, pos)
        # search words (excluding already-linked senses)
        Sense.objects.create(word=self.word_1, synset=self.synset_a)
        with self.assertNumQueries(2):
            response = self.client.get(
                self._get_search_words_url(self.synset_a), {"q": "toets"}
            )
        self.assertNotContains(response, self.word_1.text)

    def test_add_sense_htmx_success(self):
        # Queries:
        # fetch synset (with wordnet, language, pos)
        # fetch word (with language, pos)
        # get_or_create sense check (SELECT)
        # SAVEPOINT
        # INSERT sense
        # INSERT sense history
        # fetch senses ordered by text (display_name recalculation)
        # UPDATE synset (display_name save)
        # RELEASE SAVEPOINT
        # UPDATE synset (status → draft)
        # INSERT synset history
        # fetch senses with words (context)
        # fetch sense examples (context)
        with self.assertNumQueries(13):
            response = self.client.post(
                self._get_add_sense_url(self.synset_a),
                {"word_pk": self.word_1.pk},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Sense.objects.filter(word=self.word_1, synset=self.synset_a).exists()
        )

    def test_add_sense_htmx_wrong_language(self):
        # Queries:
        # fetch synset (with wordnet, language, pos)
        # fetch word (with language, pos)
        # fetch senses (context — synset_a has no senses so no examples query)
        other_language = Language.objects.create(iso_code="zul", name="isiZulu")
        other_word = Word.objects.create(
            text="ikhaya", pos=self.pos_noun, language=other_language
        )
        with self.assertNumQueries(3):
            response = self.client.post(
                self._get_add_sense_url(self.synset_a),
                {"word_pk": other_word.pk},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)
        self.assertFalse(
            Sense.objects.filter(word=other_word, synset=self.synset_a).exists()
        )

    def test_add_sense_htmx_wrong_pos(self):
        # Queries:
        # fetch synset (with wordnet, language, pos)
        # fetch word (with language, pos)
        # fetch senses (context — synset_a has no senses so no examples query)
        wrong_pos_word = Word.objects.create(
            text="toets verb",
            pos=self.pos_verb,
            language=self.wordnet.language,
        )
        with self.assertNumQueries(3):
            response = self.client.post(
                self._get_add_sense_url(self.synset_a),
                {"word_pk": wrong_pos_word.pk},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)
        self.assertFalse(
            Sense.objects.filter(word=wrong_pos_word, synset=self.synset_a).exists()
        )

    def test_add_sense_htmx_duplicate(self):
        # word_1 is already linked to synset_b; adding it again should not create a new sense
        # Queries:
        # fetch synset (with wordnet, language, pos)
        # fetch word (with language, pos)
        # fetch senses with words (context)
        # fetch sense examples (context)
        with self.assertNumQueries(4):
            response = self.client.post(
                self._get_add_sense_url(self.synset_b),
                {"word_pk": self.word_1.pk},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)
        self.assertEqual(
            Sense.objects.filter(word=self.word_1, synset=self.synset_b).count(), 1
        )

    def _get_delete_sense_url(self, synset_obj, sense_obj):
        return reverse(
            "editor:delete_sense_htmx",
            kwargs={"synset_pk": synset_obj.pk, "sense_pk": sense_obj.pk},
        )

    def test_delete_sense_htmx_success(self):
        # Queries:
        # fetch synset
        # fetch sense
        # fetch sense examples (pre-delete PROTECT check)
        # DELETE sense
        # INSERT sense history
        # fetch senses with words (display_name recalculation)
        # UPDATE synset (display_name)
        # UPDATE synset (status → draft)
        # INSERT synset history
        # fetch senses with words (context)
        with self.assertNumQueries(10):
            response = self.client.post(
                self._get_delete_sense_url(self.synset_c, self.sense_2)
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Sense.objects.filter(pk=self.sense_2.pk).exists())
        self.synset_c.refresh_from_db()
        self.assertEqual(self.synset_c.status, Synset.Status.DRAFT)

    def test_delete_sense_htmx_wrong_synset(self):
        # sense_1 belongs to synset_b, not synset_a
        # Queries:
        # fetch synset
        # fetch sense
        # fetch senses (context — synset_a has no senses so no examples query)
        with self.assertNumQueries(3):
            response = self.client.post(
                self._get_delete_sense_url(self.synset_a, self.sense_1)
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)
        self.assertTrue(Sense.objects.filter(pk=self.sense_1.pk).exists())

    def test_delete_sense_htmx_invalid_synset(self):
        # Queries:
        # fetch synset (not found → 404)
        invalid_url = reverse(
            "editor:delete_sense_htmx",
            kwargs={"synset_pk": 99999, "sense_pk": self.sense_1.pk},
        )
        with self.assertNumQueries(1):
            response = self.client.post(invalid_url)
        self.assertEqual(response.status_code, 404)

    def test_delete_sense_htmx_invalid_sense(self):
        # Queries:
        # fetch synset
        # fetch sense (not found → 404)
        invalid_url = reverse(
            "editor:delete_sense_htmx",
            kwargs={"synset_pk": self.synset_b.pk, "sense_pk": 99999},
        )
        with self.assertNumQueries(2):
            response = self.client.post(invalid_url)
        self.assertEqual(response.status_code, 404)

    def _get_add_sense_example_url(self, synset_obj):
        return reverse(
            "editor:add_sense_example_htmx", kwargs={"synset_pk": synset_obj.pk}
        )

    def _get_edit_sense_example_url(self, synset_obj, example_obj):
        return reverse(
            "editor:edit_sense_example_htmx",
            kwargs={"synset_pk": synset_obj.pk, "example_pk": example_obj.pk},
        )

    def _get_delete_sense_example_url(self, synset_obj, example_obj):
        return reverse(
            "editor:delete_sense_example_htmx",
            kwargs={"synset_pk": synset_obj.pk, "example_pk": example_obj.pk},
        )

    def _sense_example_texts(self, sense_obj):
        # Straight from the database, empty ones included, in creation order
        return list(
            SenseExample.objects.filter(sense=sense_obj)
            .order_by("pk")
            .values_list("text", flat=True)
        )

    def test_add_sense_example_htmx_success(self):
        self.assertEqual(self._sense_example_texts(self.sense_2), [])
        self.assertEqual(self.synset_c.status, Synset.Status.STUB)
        # Queries:
        # fetch sense (with word, synset), scoped to synset
        # INSERT example
        # INSERT example history
        # UPDATE synset (status → draft)
        # INSERT synset history
        # fetch non-empty examples (context)
        with self.assertNumQueries(6):
            response = self.client.post(
                self._get_add_sense_example_url(self.synset_c),
                {"sense_pk": self.sense_2.pk, "text": "Nog 'n toets."},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._sense_example_texts(self.sense_2), ["Nog 'n toets."])
        # In <q>, so the browser adds the quotation marks and they aren't copied
        self.assertContains(
            response,
            '<q class="text-secondary fst-italic small">Nog \'n toets.</q>',
            html=True,
        )
        # The remove-word prompt in the re-rendered sense now counts the new example
        self.assertContains(
            response, "Its <strong>usage example</strong> will also be deleted."
        )
        # The new example is highlighted, and nothing else is
        new_example = SenseExample.objects.get(sense=self.sense_2)
        self.assertEqual(response.context["saved_pk"], new_example.pk)
        self.assertContains(response, "just-saved", count=1)
        self.synset_c.refresh_from_db()
        self.assertEqual(self.synset_c.status, Synset.Status.DRAFT)

    def test_add_sense_example_htmx_empty_text(self):
        self.assertEqual(self._sense_example_texts(self.sense_2), [])
        # Queries:
        # fetch sense (with word, synset), scoped to synset
        # fetch non-empty examples (context)
        with self.assertNumQueries(2):
            response = self.client.post(
                self._get_add_sense_example_url(self.synset_c),
                {"sense_pk": self.sense_2.pk, "text": "   "},
            )
        self.assertEqual(response.status_code, 200)
        failed_form = response.context["sense"].failed_form
        self.assertTrue(failed_form.errors)
        # It's the add form, not an edit form
        self.assertIsNone(failed_form.instance.pk)
        self.assertContains(response, "is-invalid")
        self.assertEqual(self._sense_example_texts(self.sense_2), [])

    def test_add_sense_example_htmx_wrong_synset(self):
        # sense_2 belongs to synset_c, not synset_b
        self.assertNotEqual(self.sense_2.synset_id, self.synset_b.pk)
        self.assertEqual(self._sense_example_texts(self.sense_2), [])
        # Queries:
        # fetch sense scoped to synset (not found → 404)
        with self.assertNumQueries(1):
            response = self.client.post(
                self._get_add_sense_example_url(self.synset_b),
                {"sense_pk": self.sense_2.pk, "text": "Nog 'n toets."},
            )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self._sense_example_texts(self.sense_2), [])

    def test_edit_sense_example_htmx_success(self):
        Synset.objects.filter(pk=self.synset_b.pk).update(status=Synset.Status.COMPLETE)
        self.synset_b.refresh_from_db()
        self.assertEqual(self.synset_b.status, Synset.Status.COMPLETE)
        self.assertEqual(self.sense_example.text, "Hierdie is 'n toets.")
        # Queries:
        # fetch example (with sense, word, synset), scoped to synset
        # UPDATE example
        # INSERT example history
        # UPDATE synset (status → draft)
        # INSERT synset history
        # fetch non-empty examples (context)
        with self.assertNumQueries(6):
            response = self.client.post(
                self._get_edit_sense_example_url(self.synset_b, self.sense_example),
                {"text": "Hierdie is 'n beter toets."},
            )
        self.assertEqual(response.status_code, 200)
        self.sense_example.refresh_from_db()
        self.assertEqual(self.sense_example.text, "Hierdie is 'n beter toets.")
        # The edited example is highlighted, and nothing else is
        self.assertEqual(response.context["saved_pk"], self.sense_example.pk)
        self.assertContains(response, "just-saved", count=1)
        self.synset_b.refresh_from_db()
        self.assertEqual(self.synset_b.status, Synset.Status.DRAFT)

    def test_edit_sense_example_htmx_unchanged(self):
        Synset.objects.filter(pk=self.synset_b.pk).update(status=Synset.Status.REVIEWED)
        self.synset_b.refresh_from_db()
        self.assertEqual(self.synset_b.status, Synset.Status.REVIEWED)
        # Trailing whitespace is stripped by the form, so this counts as unchanged.
        self.assertEqual(self.sense_example.text, "Hierdie is 'n toets.")
        # Queries:
        # fetch example (with sense, word, synset), scoped to synset
        # fetch non-empty examples (context)
        with self.assertNumQueries(2):
            response = self.client.post(
                self._get_edit_sense_example_url(self.synset_b, self.sense_example),
                {"text": "Hierdie is 'n toets.  "},
            )
        self.assertEqual(response.status_code, 200)
        self.sense_example.refresh_from_db()
        self.assertEqual(self.sense_example.text, "Hierdie is 'n toets.")
        # Nothing was saved, so nothing is highlighted
        self.assertNotContains(response, "just-saved")
        self.synset_b.refresh_from_db()
        self.assertEqual(self.synset_b.status, Synset.Status.REVIEWED)

    def test_edit_sense_example_htmx_empty_text(self):
        self.assertEqual(self.sense_example.text, "Hierdie is 'n toets.")
        # Queries:
        # fetch example (with sense, word, synset), scoped to synset
        # fetch non-empty examples (context)
        with self.assertNumQueries(2):
            response = self.client.post(
                self._get_edit_sense_example_url(self.synset_b, self.sense_example),
                {"text": ""},
            )
        self.assertEqual(response.status_code, 200)
        failed_form = response.context["sense"].failed_form
        self.assertTrue(failed_form.errors)
        # It's this example's edit form
        self.assertEqual(failed_form.instance.pk, self.sense_example.pk)
        self.assertContains(response, "is-invalid")
        self.sense_example.refresh_from_db()
        self.assertEqual(self.sense_example.text, "Hierdie is 'n toets.")

    def test_edit_sense_example_htmx_wrong_synset(self):
        # sense_example belongs to synset_b (through sense_1), not synset_c
        self.assertNotEqual(self.sense_example.sense.synset_id, self.synset_c.pk)
        self.assertEqual(self.sense_example.text, "Hierdie is 'n toets.")
        # Queries:
        # fetch example scoped to synset (not found → 404)
        with self.assertNumQueries(1):
            response = self.client.post(
                self._get_edit_sense_example_url(self.synset_c, self.sense_example),
                {"text": "Gekaap."},
            )
        self.assertEqual(response.status_code, 404)
        self.sense_example.refresh_from_db()
        self.assertEqual(self.sense_example.text, "Hierdie is 'n toets.")

    def test_delete_sense_example_htmx_success(self):
        Synset.objects.filter(pk=self.synset_b.pk).update(status=Synset.Status.COMPLETE)
        self.synset_b.refresh_from_db()
        self.assertEqual(self.synset_b.status, Synset.Status.COMPLETE)
        self.assertTrue(SenseExample.objects.filter(pk=self.sense_example.pk).exists())
        # Queries:
        # fetch example (with sense, word, synset), scoped to synset
        # DELETE example
        # INSERT example history
        # UPDATE synset (status → draft)
        # INSERT synset history
        # fetch non-empty examples (context)
        with self.assertNumQueries(6):
            response = self.client.post(
                self._get_delete_sense_example_url(self.synset_b, self.sense_example)
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SenseExample.objects.filter(pk=self.sense_example.pk).exists())
        self.synset_b.refresh_from_db()
        self.assertEqual(self.synset_b.status, Synset.Status.DRAFT)

    def test_delete_sense_example_htmx_wrong_synset(self):
        # sense_example belongs to synset_b (through sense_1), not synset_c
        self.assertNotEqual(self.sense_example.sense.synset_id, self.synset_c.pk)
        self.assertTrue(SenseExample.objects.filter(pk=self.sense_example.pk).exists())
        # Queries:
        # fetch example scoped to synset (not found → 404)
        with self.assertNumQueries(1):
            response = self.client.post(
                self._get_delete_sense_example_url(self.synset_c, self.sense_example)
            )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(SenseExample.objects.filter(pk=self.sense_example.pk).exists())

    def test_synset_detail_source_examples_readonly(self):
        # synset_e is copied from synset_d; give the source synset an example
        source_word = Word.objects.create(
            text="bron woord", pos=self.pos_verb, language=self.wordnet.language
        )
        source_sense = Sense.objects.create(word=source_word, synset=self.synset_d)
        source_example = SenseExample.objects.create(
            text="'n Bronvoorbeeld.", sense=source_sense
        )
        # Left over from the old tool; the source card must hide it, like the working card
        SenseExample.objects.create(text="", sense=source_sense)
        self.assertEqual(
            self._sense_example_texts(source_sense), ["'n Bronvoorbeeld.", ""]
        )
        self.assertEqual(self.synset_e.copied_from_id, self.synset_d.pk)
        # The assertions below rely on synset_e having no words of its own
        self.assertFalse(self.synset_e.sense_set.exists())
        # Queries:
        # fetch synset (with pos, wordnet, copied_from)
        # 7 concern checks (synset and word concerns)
        # fetch relations (working synset)
        # fetch relations (source synset)
        # fetch senses (with words), working synset — none, so no examples query
        # fetch senses (with words), source synset
        # fetch non-empty examples (source senses)
        with self.assertNumQueries(16):
            response = self.client.get(self._get_synset_detail_url(self.synset_e))
        self.assertContains(response, "n Bronvoorbeeld.")
        (shown_sense,) = response.context["source_synset_senses"]
        self.assertEqual(
            [example.text for example in shown_sense.senseexample_set.all()],
            ["'n Bronvoorbeeld."],
        )
        # synset_e itself has no words, so any edit control would be the source's
        self.assertNotContains(response, "Add usage example")
        self.assertNotContains(response, f"del-sense-example-{source_example.pk}")
        self.assertNotContains(
            response,
            reverse(
                "editor:edit_sense_example_htmx",
                kwargs={"synset_pk": self.synset_e.pk, "example_pk": source_example.pk},
            ),
        )

    def test_synset_detail_hides_empty_examples(self):
        SenseExample.objects.create(text="", sense=self.sense_1)
        self.assertEqual(
            self._sense_example_texts(self.sense_1), [self.sense_example.text, ""]
        )
        # Queries:
        # fetch synset (with pos, wordnet, copied_from)
        # 7 concern checks (synset and word concerns)
        # guess source synset by Princeton ID
        # fetch relations
        # fetch senses (with words)
        # fetch non-empty examples
        with self.assertNumQueries(14):
            response = self.client.get(self._get_synset_detail_url(self.synset_b))
        sense = response.context["senses"][0]
        self.assertEqual(
            [example.text for example in sense.senseexample_set.all()],
            [self.sense_example.text],
        )

    def test_synset_detail_examples_sorted_alphabetically(self):
        # Created out of order, so pk order and alphabetical order differ
        SenseExample.objects.create(text="Wortel.", sense=self.sense_1)
        SenseExample.objects.create(text="Appel.", sense=self.sense_1)
        self.assertEqual(
            self._sense_example_texts(self.sense_1),
            ["Hierdie is 'n toets.", "Wortel.", "Appel."],
        )
        # Queries:
        # fetch synset (with pos, wordnet, copied_from)
        # 7 concern checks (synset and word concerns)
        # guess source synset by Princeton ID
        # fetch relations
        # fetch senses (with words)
        # fetch non-empty examples
        with self.assertNumQueries(14):
            response = self.client.get(self._get_synset_detail_url(self.synset_b))
        sense = response.context["senses"][0]
        self.assertEqual(
            [example.text for example in sense.senseexample_set.all()],
            ["Appel.", "Hierdie is 'n toets.", "Wortel."],
        )

    def test_synset_detail_example_forms_from_form_fields(self):
        # sense_1 is synset_b's only sense, with one example: one edit form, one add
        self.assertEqual(list(self.synset_b.sense_set.all()), [self.sense_1])
        self.assertEqual(
            self._sense_example_texts(self.sense_1), ["Hierdie is 'n toets."]
        )
        max_length = SenseExample._meta.get_field("text").max_length
        # Queries (building the forms adds none):
        # fetch synset (with pos, wordnet, copied_from)
        # 7 concern checks (synset and word concerns)
        # guess source synset by Princeton ID
        # fetch relations
        # fetch senses (with words)
        # fetch non-empty examples
        with self.assertNumQueries(14):
            response = self.client.get(self._get_synset_detail_url(self.synset_b))
        self.assertContains(response, f'maxlength="{max_length}"', count=2)
        # A page load highlights nothing; only a save does
        self.assertNotContains(response, "just-saved")
        # The edit textarea is pre-filled with the saved text. Anchored to the
        # textarea's tags, because the same text also appears in the <q>.
        self.assertContains(response, ">Hierdie is &#x27;n toets.</textarea>")

    def test_synset_detail_delete_sense_warns_about_example(self):
        # sense_1 (synset_b) has one example
        self.assertEqual(
            self._sense_example_texts(self.sense_1), ["Hierdie is 'n toets."]
        )
        # Queries:
        # fetch synset (with pos, wordnet, copied_from)
        # 7 concern checks (synset and word concerns)
        # guess source synset by Princeton ID
        # fetch relations
        # fetch senses (with words)
        # fetch non-empty examples
        with self.assertNumQueries(14):
            response = self.client.get(self._get_synset_detail_url(self.synset_b))
        self.assertContains(
            response, "Its <strong>usage example</strong> will also be deleted."
        )

    def test_synset_detail_delete_sense_warns_about_examples(self):
        SenseExample.objects.create(text="'n Tweede toets.", sense=self.sense_1)
        self.assertEqual(len(self._sense_example_texts(self.sense_1)), 2)
        # Queries:
        # fetch synset (with pos, wordnet, copied_from)
        # 7 concern checks (synset and word concerns)
        # guess source synset by Princeton ID
        # fetch relations
        # fetch senses (with words)
        # fetch non-empty examples
        with self.assertNumQueries(14):
            response = self.client.get(self._get_synset_detail_url(self.synset_b))
        self.assertContains(
            response, "Its <strong>2 usage examples</strong> will also be deleted."
        )

    def test_synset_detail_delete_sense_no_warning_without_examples(self):
        # An empty example isn't shown, so it isn't warned about either
        SenseExample.objects.filter(pk=self.sense_example.pk).update(text="")
        # The example still exists; only its text is empty
        self.assertEqual(self._sense_example_texts(self.sense_1), [""])
        # Queries:
        # fetch synset (with pos, wordnet, copied_from)
        # 7 concern checks (synset and word concerns)
        # guess source synset by Princeton ID
        # fetch relations
        # fetch senses (with words)
        # fetch non-empty examples
        with self.assertNumQueries(14):
            response = self.client.get(self._get_synset_detail_url(self.synset_b))
        self.assertContains(response, "Remove this word from the synset?")
        self.assertNotContains(response, "will also be deleted")

    def test_status_htmx_empty_example_counts_as_missing(self):
        SenseExample.objects.filter(pk=self.sense_example.pk).update(text="")
        # The example still exists; only its text is empty
        self.assertEqual(self._sense_example_texts(self.sense_1), [""])
        # The status must stay draft, so it has to start as draft
        self.assertEqual(self.synset_b.status, Synset.Status.DRAFT)
        # Queries:
        # fetch synset
        # fetch senses
        # fetch non-empty examples
        # fetch words
        # check for relations
        with self.assertNumQueries(5):
            response = self.client.post(
                self._get_synset_status_htmx_url(self.synset_b),
                {"new_status": Synset.Status.COMPLETE},
            )
        self.assertIn(
            '"toets woord" has no usage example.', response.context["warnings"]
        )
        self.synset_b.refresh_from_db()
        self.assertEqual(self.synset_b.status, Synset.Status.DRAFT)


class AssignmentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser")
        language = Language.objects.create(iso_code="eng", name="English")
        pos = PartOfSpeech.objects.create(name="noun")
        self.wordnet = Wordnet.objects.create(name="Test Wordnet", language=language)
        self.wordnet_2 = Wordnet.objects.create(
            name="Test Wordnet 2", language=language
        )
        self.synset_a = Synset.objects.create(
            definition="A test synset", wordnet=self.wordnet, pos=pos
        )
        self.synset_b = Synset.objects.create(
            definition="Another test synset", wordnet=self.wordnet, pos=pos
        )

    def test_clean_on_assignment(self):
        no_target_synset = Assignment(
            user=self.user, source_synset=self.synset_a, target_wordnet=self.wordnet
        )
        no_target_synset.full_clean()

        no_target_wordnet = Assignment(
            user=self.user, source_synset=self.synset_a, target_synset=self.synset_b
        )
        no_target_wordnet.full_clean()
        self.assertEqual(no_target_wordnet.target_wordnet, self.wordnet)

        no_target_synset_or_wordnet = Assignment(
            user=self.user, source_synset=self.synset_a
        )
        with self.assertRaises(ValidationError):
            no_target_synset_or_wordnet.full_clean()

        incompatible_wordnet_and_synset = Assignment(
            user=self.user,
            source_synset=self.synset_a,
            target_synset=self.synset_b,
            target_wordnet=self.wordnet_2,
        )
        with self.assertRaises(ValidationError):
            incompatible_wordnet_and_synset.full_clean()
