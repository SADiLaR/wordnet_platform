from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from editor.filters import SynsetFilter
from editor.models import Assignment
from editor.views import _guess_princeton_id, _guess_source_synset
from lex.models import (
    Language,
    PartOfSpeech,
    Relation,
    RelationType,
    Sense,
    SenseExample,
    Synset,
    Word,
    Wordnet,
)


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

        relation_type = RelationType.objects.create(name="hyper")
        Relation.objects.create(
            synset_from=self.synset_e,
            synset_to=self.synset_f,
            type=relation_type,
        )

        Relation.objects.create(
            synset_from=self.synset_c,
            synset_to=self.synset_b,
            type=relation_type,
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

    def test_synsets_status_filter(self):
        data = {"status": [Synset.Status.COMPLETE]}
        status_filter = SynsetFilter(data=data)
        qs = status_filter.qs
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

    def test_search_filter_definition(self):
        data = {"search": "Addisionele"}
        synset_filter = SynsetFilter(data=data)
        qs = synset_filter.qs
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first(), self.synset_c)

    def test_search_filter_order(self):
        data = {"search": "toets"}
        synset_filter = SynsetFilter(data=data)
        qs = synset_filter.qs
        self.assertEqual(qs.count(), 4)
        self.assertEqual(qs[0], self.synset_a)
        self.assertEqual(qs[1], self.synset_d)
        self.assertEqual(qs[2], self.synset_b)

    def test_search_filter_combined(self):
        data = {
            "search": "toets",
            "wordnet": [self.wordnet.id],
        }
        synset_filter = SynsetFilter(data=data)
        qs = synset_filter.qs
        self.assertEqual(qs.count(), 3)
        self.assertNotIn(self.synset_d, qs)

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
        with self.assertNumQueries(3):
            response = self.client.get(self._get_synset_detail_url(self.synset_a))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["synset"], self.synset_a)

    def test_synset_detail_existing_with_princeton(self):
        with self.assertNumQueries(4):
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

    def test_guess_princeton_id(self):
        self.assertEqual("12345678-v", _guess_princeton_id("12345678-v"))
        self.assertEqual("", _guess_princeton_id(""))
        self.assertEqual(None, _guess_princeton_id(None))
        self.assertEqual("12345678-v", _guess_princeton_id("ENG20-12345678-v"))

    def test_guess_source_synset(self):
        with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
            existing = _guess_source_synset(self.synset_f)
            no_match = _guess_source_synset(self.synset_b)
            no_princeton_id = _guess_source_synset(self.synset_a)
            not_itself = _guess_source_synset(self.synset_d)
        self.assertEqual(existing, self.synset_d)
        self.assertEqual(no_match, None)
        self.assertEqual(no_princeton_id, None)
        self.assertEqual(not_itself, None)

    def test_guess_source_synset_view_existing(self):
        with self.assertNumQueries(5):
            with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
                response = self.client.get(self._get_synset_detail_url(self.synset_f))
            self.assertEqual(response.context["source_synset"], self.synset_d)

    def test_copied_source_synset(self):
        with self.assertNumQueries(4):
            with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
                response = self.client.get(self._get_synset_detail_url(self.synset_e))
            self.assertEqual(response.context["source_synset"], self.synset_d)

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
