from django.test import TestCase
from django.urls import reverse

from lex.models import (
    Language,
    PartOfSpeech,
    Synset,
    Wordnet,
)


class BrowseSynsetsByWordnetViewTest(TestCase):
    def setUp(self):

        language = Language.objects.create(iso_code="afr", name="Afrikaans")
        self.wordnet = Wordnet.objects.create(name="Toets Wordnet", language=language)
        self.url = reverse("editor:browse_synsets_by_wordnet")
        self.wn_url = reverse(
            "editor:browse_synsets_by_wordnet", kwargs={"wn_pk": self.wordnet.pk}
        )
        pos = PartOfSpeech.objects.create(name="noun")

        self.synset_a = Synset.objects.create(
            definition="'n Toets synset",
            wordnet=self.wordnet,
            pos=pos,
        )
        self.synset_b = Synset.objects.create(
            definition="Nog 'n toets synset",
            wordnet=self.wordnet,
            pos=pos,
        )
        self.synset_c = Synset.objects.create(
            definition="'n Addisionele toets synset",
            wordnet=self.wordnet,
            pos=pos,
        )

    def test_browse_synsets_by_wordnet_existing(self):
        response = self.client.get(self.wn_url)
        self.assertEqual(response.status_code, 200)

    def test_browse_synsets_by_wordnet_non_existing(self):
        nonexist_url = reverse("editor:browse_synsets_by_wordnet", kwargs={"wn_pk": 99})
        response = self.client.get(nonexist_url)
        self.assertEqual(response.status_code, 404)

    def test_browse_synsets_by_wordnet_num_queries(self):
        self.assertNumQueries(3, lambda: self.client.get(self.wn_url))

    def test_browse_synsets_existing(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_browse_synsets_num_queries(self):
        self.assertNumQueries(1, lambda: self.client.get(self.url))
