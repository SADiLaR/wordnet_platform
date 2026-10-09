from django.test import TestCase

from lex.models import (
    Language,
    PartOfSpeech,
    Sense,
    Synset,
    SynsetExample,
    Word,
    Wordnet,
)


class WordConcernTests(TestCase):
    def setUp(self):
        self.language = Language.objects.create(iso_code="eng", name="English")
        self.pos_noun = PartOfSpeech.objects.create(name="noun")

    def _get_concern(self, key):
        return next(
            concern for concern in Word.objects.concerns() if concern["key"] == key
        )

    def test_language_mismatch(self):
        afrikaans = Language.objects.create(iso_code="afr", name="Afrikaans")
        wordnet = Wordnet.objects.create(name="Afrikaans Wordnet", language=afrikaans)
        word = Word.objects.create(
            text="test", pos=self.pos_noun, language=self.language
        )
        synset = Synset.objects.create(
            display_name="toets",
            definition="toets een",
            wordnet=wordnet,
            pos=self.pos_noun,
        )
        Sense.objects.create(word=word, synset=synset)
        concern = self._get_concern("language-mismatch")
        self.assertTrue(concern["qs"].filter(pk=word.pk).exists())

    def test_suspicious_characters(self):
        word = Word.objects.create(
            text="cat;cats",
            pos=self.pos_noun,
            language=self.language,
        )
        concern = self._get_concern("suspicious-characters")
        self.assertTrue(concern["qs"].filter(pk=word.pk).exists())

    def test_suspicious_opening_bracket(self):
        word = Word.objects.create(
            text="cat(test)",
            pos=self.pos_noun,
            language=self.language,
        )
        concern = self._get_concern("suspicious-opening-bracket")
        self.assertTrue(concern["qs"].filter(pk=word.pk).exists())


class SynsetConcernTests(TestCase):
    def setUp(self):
        self.language = Language.objects.create(iso_code="eng", name="English")
        self.pos_noun = PartOfSpeech.objects.create(name="noun")
        self.pos_verb = PartOfSpeech.objects.create(name="verb")
        self.wordnet = Wordnet.objects.create(
            name="Test Wordnet",
            language=self.language,
        )
        self.synset = Synset.objects.create(
            display_name="test",
            definition="Test synset",
            wordnet=self.wordnet,
            pos=self.pos_noun,
        )

    def _get_concern(self, key):
        return next(
            concern for concern in Synset.objects.concerns() if concern["key"] == key
        )

    def test_missing_definition(self):
        self.synset.definition = ""
        self.synset.save(update_fields=["definition"])
        concern = self._get_concern("missing-definition")
        self.assertTrue(concern["qs"].filter(pk=self.synset.pk).exists())

    def test_without_words(self):
        concern = self._get_concern("without-words")
        self.assertTrue(concern["qs"].filter(pk=self.synset.pk).exists())

    def test_mixed_word_pos(self):
        word_noun = Word.objects.create(
            text="test",
            pos=self.pos_noun,
            language=self.language,
        )
        word_verb = Word.objects.create(
            text="testing",
            pos=self.pos_verb,
            language=self.language,
        )
        Sense.objects.create(word=word_noun, synset=self.synset)
        Sense.objects.create(word=word_verb, synset=self.synset)
        concern = self._get_concern("mixed-word-pos")
        self.assertTrue(concern["qs"].filter(pk=self.synset.pk).exists())

    def test_synset_has_synset_example(self):
        SynsetExample.objects.create(
            text="This is an example.",
            synset_id=self.synset.pk,
        )
        concern = self._get_concern("synset-example")
        self.assertTrue(concern["qs"].filter(pk=self.synset.pk).exists())
