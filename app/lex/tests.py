from django.test import TestCase

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


class SynsetTestCase(TestCase):
    def setUp(self):
        self.language = Language.objects.create(iso_code="zul", name="isiZulu")
        wordnet = Wordnet.objects.create(name="ZulUnitTest", language=self.language)
        self.nounpos = PartOfSpeech.objects.create(name="noun")

        self.synset = Synset.objects.create(
            definition="a test synset", wordnet=wordnet, pos=self.nounpos
        )

    def test_short_display_name_without_display_name(self):
        self.assertEqual(self.synset.short_display_name(), f"({self.synset.pk})")

    def test_short_display_name_with_display_name(self):
        word = Word.objects.create(
            text="igama", pos=self.nounpos, language=self.language
        )
        Sense.objects.create(word=word, synset=self.synset)
        self.synset.refresh_from_db()
        self.assertEqual(self.synset.short_display_name(), "igama")

    def test_str_one_word_short_definition(self):
        word = Word.objects.create(
            text="igama", pos=self.nounpos, language=self.language
        )
        Sense.objects.create(word=word, synset=self.synset)
        self.synset.refresh_from_db()

        self.synset.definition = "a word"
        self.synset.save()

        self.assertEqual(str(self.synset), "igama : a word")

    def test_str_three_words_short_definition(self):
        w1 = Word.objects.create(text="igama", pos=self.nounpos, language=self.language)
        w2 = Word.objects.create(
            text="amagama", pos=self.nounpos, language=self.language
        )
        w3 = Word.objects.create(text="ibizo", pos=self.nounpos, language=self.language)
        Sense.objects.create(word=w1, synset=self.synset)
        Sense.objects.create(word=w2, synset=self.synset)
        Sense.objects.create(word=w3, synset=self.synset)
        self.synset.refresh_from_db()

        self.synset.definition = "a word"
        self.synset.save()

        self.assertEqual(str(self.synset), "amagama, ibizo, igama : a word")

    def test_str_four_words_short_definition(self):
        w1 = Word.objects.create(text="igama", pos=self.nounpos, language=self.language)
        w2 = Word.objects.create(
            text="amagama", pos=self.nounpos, language=self.language
        )
        w3 = Word.objects.create(text="ibizo", pos=self.nounpos, language=self.language)
        w4 = Word.objects.create(
            text="amabizo", pos=self.nounpos, language=self.language
        )
        Sense.objects.create(word=w1, synset=self.synset)
        Sense.objects.create(word=w2, synset=self.synset)
        Sense.objects.create(word=w3, synset=self.synset)
        Sense.objects.create(word=w4, synset=self.synset)
        self.synset.refresh_from_db()

        self.synset.definition = "a word"
        self.synset.save()

        self.assertEqual(str(self.synset), "amabizo, amagama, ibizo, ... : a word")

    def test_str_one_word_long_definition(self):
        word = Word.objects.create(
            text="igama", pos=self.nounpos, language=self.language
        )
        Sense.objects.create(word=word, synset=self.synset)
        self.synset.refresh_from_db()

        self.synset.definition = (
            "A unit that stands on its own according to the intuition of language users. "
            "The difficulty with this definition is that literate language users don’t"
            "normally have intuitions about wordhood that are separate from their writing system."
        )
        self.synset.save()

        self.assertEqual(
            str(self.synset),
            "igama : A unit that stands on its own according to the intuition of language "
            "users. The ...",
        )

    # a test for when last_wanted_space is at definition[definition_part_max_length - len(" ...")]
    def test_str_one_word_long_definition_2(self):
        word = Word.objects.create(
            text="igama", pos=self.nounpos, language=self.language
        )
        Sense.objects.create(word=word, synset=self.synset)
        self.synset.refresh_from_db()

        self.synset.definition = (
            "A unit that stands on its own according to the intuition of language users. "
            "Some issues with this definition are that literate language users don’t"
            "normally have intuitions about wordhood that are separate from their writing system."
        )
        self.synset.save()

        self.assertEqual(
            str(self.synset),
            "igama : A unit that stands on its own according to the intuition of language "
            "users. Some issues ...",
        )

    def test_str_three_words_long_definition(self):
        w1 = Word.objects.create(text="igama", pos=self.nounpos, language=self.language)
        w2 = Word.objects.create(
            text="amagama", pos=self.nounpos, language=self.language
        )
        w3 = Word.objects.create(text="ibizo", pos=self.nounpos, language=self.language)
        Sense.objects.create(word=w1, synset=self.synset)
        Sense.objects.create(word=w2, synset=self.synset)
        Sense.objects.create(word=w3, synset=self.synset)
        self.synset.refresh_from_db()

        self.synset.definition = (
            "A unit that stands on its own according to the intuition of language users. "
            "The difficulty with this definition is that literate language users don’t "
            "normally have intuitions about wordhood that are separate from their writing system."
        )
        self.synset.save()

        self.assertEqual(
            str(self.synset),
            "amagama, ibizo, igama : A unit that stands on its own according to the intuition "
            "of language ...",
        )

    def test_str_four_words_long_definition(self):
        w1 = Word.objects.create(text="igama", pos=self.nounpos, language=self.language)
        w2 = Word.objects.create(
            text="amagama", pos=self.nounpos, language=self.language
        )
        w3 = Word.objects.create(text="ibizo", pos=self.nounpos, language=self.language)
        w4 = Word.objects.create(
            text="amabizo", pos=self.nounpos, language=self.language
        )
        Sense.objects.create(word=w1, synset=self.synset)
        Sense.objects.create(word=w2, synset=self.synset)
        Sense.objects.create(word=w3, synset=self.synset)
        Sense.objects.create(word=w4, synset=self.synset)
        self.synset.refresh_from_db()

        self.synset.definition = (
            "A unit that stands on its own according to the intuition of language users. "
            "The difficulty with this definition is that literate language users don’t "
            "normally have intuitions about wordhood that are separate from their writing system."
        )
        self.synset.save()

        self.assertEqual(
            str(self.synset),
            "amabizo, amagama, ibizo, ... : A unit that stands on its own according to the "
            "intuition of ...",
        )

    def test_synset_change_details_recorded(self):
        test_change_msg = "Changed synset as a test."
        self.synset._change_details = test_change_msg
        self.synset.save()
        self.assertEqual(self.synset.history.latest().change_details, test_change_msg)


class RelationTestCase(TestCase):
    def setUp(self):
        language = Language.objects.create(iso_code="zul", name="isiZulu")
        wordnet = Wordnet.objects.create(name="ZulUnitTest", language=language)
        pos = PartOfSpeech.objects.create(name="noun")

        self.synset_from = Synset.objects.create(
            definition="a source synset",
            wordnet=wordnet,
            pos=pos,
            display_name="source_synset",
        )
        self.synset_to = Synset.objects.create(
            definition="a target synset",
            wordnet=wordnet,
            pos=pos,
            display_name="target_synset",
        )

        relation_type = RelationType.objects.create(name="some_relation")

        self.relation = Relation.objects.create(
            synset_from=self.synset_from, synset_to=self.synset_to, type=relation_type
        )

    def test_str(self):
        self.assertEqual(
            str(self.relation), "source_synset --some_relation-> target_synset"
        )
