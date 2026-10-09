from django.apps import apps
from django.db import models
from django.db.models import Count, Exists, OuterRef, Q
from django.utils.translation import gettext_lazy as _


class WordManager(models.Manager):
    def _language_mismatch(self):
        Sense = apps.get_model("lex", "Sense")
        mismatching_senses = Sense.objects.filter(word_id=OuterRef("pk")).exclude(
            synset__wordnet__language_id=OuterRef("language_id")
        )

        return {
            "key": "language-mismatch",
            "name": _("Word and wordnet have different languages"),
            "qs": (
                self.get_queryset()
                .annotate(has_language_mismatch=Exists(mismatching_senses))
                .filter(has_language_mismatch=True)
            ),
        }

    def _suspicious_characters(self):
        return {
            "key": "suspicious-characters",
            "name": _("Word contains suspicious characters"),
            "qs": self.get_queryset().filter(text__regex=r"[/;,]"),
        }

    def _suspicious_opening_bracket(self):
        return {
            "key": "suspicious-opening-bracket",
            "name": _("Suspicious opening bracket in word"),
            "qs": (
                self.get_queryset()
                .filter(text__contains="(")
                .exclude(text__contains=" (")
            ),
        }

    def concerns(self):
        return [
            self._language_mismatch(),
            self._suspicious_characters(),
            self._suspicious_opening_bracket(),
        ]


class SynsetManager(models.Manager):
    def _missing_definition(self):
        return {
            "key": "missing-definition",
            "name": _("Synset without definition"),
            "qs": self.get_queryset().filter(
                Q(definition__isnull=True) | Q(definition="")
            ),
        }

    def _without_words(self):
        return {
            "key": "without-words",
            "name": _("Synset without words"),
            "qs": (
                self.get_queryset()
                .annotate(sense_count=Count("sense"))
                .filter(sense_count=0)
            ),
        }

    def _mixed_pos(self):
        return {
            "key": "mixed-word-pos",
            "name": _("Words in synset have different parts of speech"),
            "qs": (
                self.get_queryset()
                .annotate(
                    word_pos_count=Count(
                        "sense__word__pos",
                        distinct=True,
                    )
                )
                .filter(word_pos_count__gt=1)
            ),
        }

    def _pos_mismatch(self):
        Sense = apps.get_model("lex", "Sense")
        mismatching_word_pos = Sense.objects.filter(synset_id=OuterRef("pk")).exclude(
            word__pos_id=OuterRef("pos_id")
        )

        return {
            "key": "word-pos-mismatch",
            "name": _("Synset has a different part of speech than its words"),
            "qs": (
                self.get_queryset()
                .exclude(pos__name__iexact="multiple")
                .annotate(has_pos_mismatch=Exists(mismatching_word_pos))
                .filter(has_pos_mismatch=True)
            ),
        }

    def _sense_example(self):
        SynsetExample = apps.get_model("lex", "SynsetExample")
        synset_examples = SynsetExample.objects.filter(synset_id=OuterRef("pk"))

        return {
            "key": "synset-example",
            "name": _("Synset has a synset example"),
            "qs": (
                self.get_queryset()
                .annotate(has_synset_example=Exists(synset_examples))
                .filter(has_synset_example=True)
            ),
        }

    def concerns(self):
        return [
            self._missing_definition(),
            self._without_words(),
            self._mixed_pos(),
            self._pos_mismatch(),
            self._sense_example(),
        ]
