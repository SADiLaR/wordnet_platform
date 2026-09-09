from django.test import TestCase
from django.urls import reverse

from editor.views import _guess_princeton_id, _guess_source_synset
from lex.models import (
    Language,
    PartOfSpeech,
    Relation,
    RelationType,
    Sense,
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
        pos = PartOfSpeech.objects.create(name="noun")

        self.synset_a = Synset.objects.create(
            definition="'n Toets synset", wordnet=self.wordnet, pos=pos
        )
        self.synset_b = Synset.objects.create(
            definition="Nog 'n toets synset",
            wordnet=self.wordnet,
            pos=pos,
            princeton_id="12345678-a",
        )
        self.synset_c = Synset.objects.create(
            definition="'n Addisionele toets synset", wordnet=self.wordnet, pos=pos
        )

        self.synset_d = Synset.objects.create(
            definition="'n Synset in die tweede wordnet",
            wordnet=self.wordnet_2,
            pos=pos,
            princeton_id="12345678-n",
        )

        self.synset_e = Synset.objects.create(
            definition="'n Synset met 'n kopie van 'n ander woordnet",
            wordnet=self.wordnet,
            pos=pos,
            copied_from=self.synset_d,
        )

        self.synset_f = Synset.objects.create(
            definition="'n Synset met 'n Princeton ID van 'n ander woordnet",
            wordnet=self.wordnet,
            pos=pos,
            princeton_id="12345678-n",
        )

        self.word_1 = Word.objects.create(text="toets", pos=pos, language=language)

        self.sense_1 = Sense.objects.create(word=self.word_1, synset=self.synset_b)

        self.sense_2 = Sense.objects.create(word=self.word_1, synset=self.synset_c)

        relation_type = RelationType.objects.create(name="hyper")
        Relation.objects.create(
            synset_from=self.synset_e,
            synset_to=self.synset_f,
            type=relation_type,
        )

    def _get_browse_url(self):
        return reverse("editor:browse_synsets")

    def _get_browse_wn_url(self):
        return reverse(
            "editor:browse_synsets_by_wordnet", kwargs={"wn_pk": self.wordnet.pk}
        )

    def _get_queue_url(self):
        return reverse("editor:assignment_queue")

    def _get_queue_wn_url(self):
        return reverse(
            "editor:assignment_queue_by_wordnet", kwargs={"wn_pk": self.wordnet.pk}
        )

    def _get_synset_detail_url(self, synset_obj):
        return reverse("editor:synset_detail", kwargs={"ss_pk": synset_obj.pk})

    def _get_synset_detail_url_nonexist(self):
        return reverse("editor:synset_detail", kwargs={"ss_pk": 99})

    def test_browse_synsets_by_wordnet_existing(self):
        with self.assertNumQueries(3):
            response = self.client.get(self._get_browse_wn_url())
        self.assertEqual(response.status_code, 200)

    def test_browse_synsets_by_wordnet_existing_excludes_other_synsets(self):
        response = self.client.get(self._get_browse_wn_url())
        self.assertQuerySetEqual(
            response.context["synsets"],
            [self.synset_a, self.synset_b, self.synset_c, self.synset_e, self.synset_f],
            ordered=False,
        )

    def test_browse_synsets_by_wordnet_non_existing(self):
        nonexist_url = reverse("editor:browse_synsets_by_wordnet", kwargs={"wn_pk": 99})
        response = self.client.get(nonexist_url)
        self.assertEqual(response.status_code, 404)

    def test_browse_synsets_existing(self):
        with self.assertNumQueries(1):
            response = self.client.get(self._get_browse_url())
        self.assertEqual(response.status_code, 200)

    def test_queue_by_wordnet_existing(self):
        with self.assertNumQueries(2):
            response = self.client.get(self._get_queue_wn_url())
        self.assertEqual(response.status_code, 200)

    def test_queue_by_wordnet_non_existing(self):
        nonexist_url = reverse(
            "editor:assignment_queue_by_wordnet", kwargs={"wn_pk": 99}
        )
        response = self.client.get(nonexist_url)
        self.assertEqual(response.status_code, 404)

    def test_queue_existing(self):
        with self.assertNumQueries(1):
            response = self.client.get(self._get_queue_url())
        self.assertEqual(response.status_code, 200)

    def test_synset_detail_existing_no_princeton(self):
        with self.assertNumQueries(4):
            response = self.client.get(self._get_synset_detail_url(self.synset_a))
        self.assertEqual(response.status_code, 200)

    def test_synset_detail_existing_with_princeton(self):
        with self.assertNumQueries(5):
            response = self.client.get(self._get_synset_detail_url(self.synset_f))
        self.assertEqual(response.status_code, 200)

    def test_synset_detail_non_existing(self):
        with self.assertNumQueries(1):
            response = self.client.get(self._get_synset_detail_url_nonexist())
        self.assertEqual(response.status_code, 404)

    def test_synset_detail_correct_synset_in_context(self):
        response = self.client.get(self._get_synset_detail_url(self.synset_a))
        self.assertEqual(response.context["synset"], self.synset_a)

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

    def test_guess_source_synset_existing(self):
        with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
            result = _guess_source_synset(self.synset_f)
        self.assertEqual(result, self.synset_d)

    def test_guess_source_synset_no_match(self):
        with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
            result = _guess_source_synset(self.synset_b)
        self.assertEqual(result, None)

    def test_guess_source_synset_no_princeton_id(self):
        with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
            result = _guess_source_synset(self.synset_a)
        self.assertEqual(result, None)

    def test_guess_source_synset_not_itself(self):
        with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
            result = _guess_source_synset(self.synset_d)
        self.assertEqual(result, None)

    def test_guess_source_synset_view_existing(self):
        with self.assertNumQueries(6):
            with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
                response = self.client.get(self._get_synset_detail_url(self.synset_f))
            self.assertEqual(response.context["source_synset"], self.synset_d)
            self.assertEqual(response.context["explicit_source"], False)

    def test_copied_source_synset(self):
        with self.assertNumQueries(6):
            with self.settings(SOURCE_WORDNET_ID=self.wordnet_2.pk):
                response = self.client.get(self._get_synset_detail_url(self.synset_e))
            self.assertEqual(response.context["source_synset"], self.synset_d)
            self.assertEqual(response.context["explicit_source"], True)
