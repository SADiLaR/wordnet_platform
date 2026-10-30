from django.apps import apps
from django.db import models
from django.db.models import Count, Exists, OuterRef, Q
from django.db.models.expressions import Value
from django.db.models.fields import IntegerField
from django.db.models.functions import Greatest, Least
from django.db.models.lookups import Func
from django.utils.translation import gettext_lazy as _


class RegexpCount(Func):
    """Return the number of occurrences of the given regex expression."""

    function = "REGEXP_COUNT"
    output_field = IntegerField()

    def __init__(self, expression, regex, **extra):
        # This takes `regex` as a literal regular expression, instead of a
        # reference that could (e.g.) refer to a column:
        if isinstance(regex, str):
            regex = Value(regex)
        super().__init__(expression, regex, **extra)


class WordManager(models.Manager):
    def _language_mismatch(self):
        Sense = apps.get_model("lex", "Sense")
        mismatching_senses = Sense.objects.filter(word_id=OuterRef("pk")).exclude(
            synset__wordnet__language_id=OuterRef("language_id")
        )

        return {
            "key": "language-mismatch",
            "name": _("Language mismatch"),
            "description": _("Word and wordnet have different languages"),
            "qs": (
                self.get_queryset()
                .annotate(has_language_mismatch=Exists(mismatching_senses))
                .filter(has_language_mismatch=True)
            ),
        }

    def _suspicious_characters(self):
        return {
            "key": "suspicious-characters",
            "name": _("Suspicious characters"),
            "description": _("Word contains suspicious characters"),
            "qs": self.get_queryset().filter(text__regex=r"[/;,]"),
        }

    def _suspicious_brackets(self):
        return {
            "key": "suspicious-bracket",
            "name": _("Suspicious bracket"),
            "description": _("Suspicious brackets or spacing in word"),
            "qs": (
                self.get_queryset()
                .annotate(
                    bracket_difference=(
                        RegexpCount("text", r"\(") - RegexpCount("text", r"\)")
                    )
                )
                .filter(
                    Q(text__regex=r"[^ ]\(")  # bracket not at start and without space
                    | Q(text__regex=r"\)[^ ]")  # bracket not and end and without space
                    | ~Q(bracket_difference=0),  # unequal number of brackets "(", ")"
                )
            ),
        }

    def concerns(self):
        return [
            self._language_mismatch(),
            self._suspicious_characters(),
            self._suspicious_brackets(),
        ]


class SynsetManager(models.Manager):
    def _missing_definition(self):
        return {
            "key": "missing-definition",
            "name": _("Missing definition"),
            "description": _("Synset without definition"),
            "qs": self.get_queryset().filter(
                Q(definition__isnull=True) | Q(definition="")
            ),
        }

    def _without_words(self):
        return {
            "key": "without-words",
            "name": _("Synset without words"),
            "description": _("Synset without words"),
            "qs": (
                self.get_queryset()
                .annotate(sense_count=Count("sense"))
                .filter(sense_count=0)
            ),
        }

    def _mixed_pos(self):
        return {
            "key": "mixed-word-pos",
            "name": _("Mixed word parts of speech"),
            "description": _("Words in synset have different parts of speech"),
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
            "name": _("Part of speech mismatch"),
            "description": _("Synset has a different part of speech than its words"),
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
            "name": _("Synset example present"),
            "description": _("Synset has a synset example"),
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


class RelationManager(models.Manager):
    pair_order = (
        Least("synset_from_id", "synset_to_id"),
        Greatest("synset_from_id", "synset_to_id"),
        "pk",
    )
    symmetric_relation_types = [
        "similar_to",
        "ant",
        "also_see",
        "near_antonym",
        "attr",
        "verb_group",
    ]

    def _both_directions(self):
        Relation = apps.get_model("lex", "Relation")

        reverse = Relation.objects.filter(
            synset_from_id=OuterRef("synset_to_id"),
            synset_to_id=OuterRef("synset_from_id"),
            type_id=OuterRef("type_id"),
        )

        return {
            "key": "relation-both-directions",
            "name": _("Relation in both directions"),
            "description": _(
                "A one-directional relation type links two synsets both ways"
            ),
            "qs": (
                self.get_queryset()
                .annotate(has_reverse=Exists(reverse))
                .filter(has_reverse=True)
                .exclude(type__name__in=self.symmetric_relation_types)
                .order_by(*self.pair_order)
            ),
        }

    def concerns(self):
        return [
            self._both_directions(),
        ]
