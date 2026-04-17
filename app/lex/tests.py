from django.test import TestCase

from lex.models import (
    Language,
    Lemma,
    PartOfSpeech,
    Relation,
    RelationType,
    Synset,
    Wordnet,
)


class SynsetTestCase(TestCase):
    def setUp(self):
        language = Language.objects.create(iso_code="zul", name="isiZulu")
        wordnet = Wordnet.objects.create(name="ZulUnitTest", language=language)
        pos = PartOfSpeech.objects.create(name="noun")

        self.synset = Synset.objects.create(
            definition="a test synset", wordnet=wordnet, pos=pos
        )

    def test_short_display_name_without_display_name(self):
        self.assertEqual(self.synset.short_display_name(), f"({self.synset.pk})")

    def test_short_display_name_with_display_name(self):
        Lemma.objects.create(text="igama", synset=self.synset)
        self.synset.refresh_from_db()
        self.assertEqual(self.synset.short_display_name(), "igama")

    def test_str_one_lemma_short_definition(self):
        Lemma.objects.create(text="igama", synset=self.synset)
        self.synset.refresh_from_db()

        self.synset.definition = "a word"
        self.synset.save()

        self.assertEqual(str(self.synset), "igama : a word")

    def test_str_three_lemmas_short_definition(self):
        Lemma.objects.create(text="igama", synset=self.synset)
        Lemma.objects.create(text="amagama", synset=self.synset)
        Lemma.objects.create(text="ibizo", synset=self.synset)
        self.synset.refresh_from_db()

        self.synset.definition = "a word"
        self.synset.save()

        self.assertEqual(str(self.synset), "amagama, ibizo, igama : a word")

    def test_str_four_lemmas_short_definition(self):
        Lemma.objects.create(text="igama", synset=self.synset)
        Lemma.objects.create(text="amagama", synset=self.synset)
        Lemma.objects.create(text="ibizo", synset=self.synset)
        Lemma.objects.create(text="amabizo", synset=self.synset)
        self.synset.refresh_from_db()

        self.synset.definition = "a word"
        self.synset.save()

        self.assertEqual(str(self.synset), "amabizo, amagama, ibizo, ... : a word")

    def test_str_one_lemma_long_definition(self):
        Lemma.objects.create(text="igama", synset=self.synset)
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
    def test_str_one_lemma_long_definition_2(self):
        Lemma.objects.create(text="igama", synset=self.synset)
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

    def test_str_three_lemmas_long_definition(self):
        Lemma.objects.create(text="igama", synset=self.synset)
        Lemma.objects.create(text="amagama", synset=self.synset)
        Lemma.objects.create(text="ibizo", synset=self.synset)
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

    def test_str_four_lemmas_long_definition(self):
        Lemma.objects.create(text="igama", synset=self.synset)
        Lemma.objects.create(text="amagama", synset=self.synset)
        Lemma.objects.create(text="ibizo", synset=self.synset)
        Lemma.objects.create(text="amabizo", synset=self.synset)
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
