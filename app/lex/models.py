from django.db import models
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords
from simple_history.signals import post_create_historical_record

SYNSET_STR_MAX_LENGTH = 100
MAX_WORDS = 3


@receiver(post_create_historical_record)
def post_create_historical_record_callback(
    sender, instance, history_instance, **kwargs
):
    if hasattr(instance, "_change_details"):
        history_instance.change_details = instance._change_details
        history_instance.save()


class HistoricalChangesMixin(models.Model):
    change_details = models.TextField(blank=True, default="")

    class Meta:
        abstract = True


class Language(models.Model):
    iso_code = models.CharField(
        primary_key=True,
        max_length=10,
        verbose_name=_("ISO code"),
        help_text=_("Language code according to ISO 639-3"),
    )
    name = models.CharField(max_length=50, verbose_name=_("name"))
    history = HistoricalRecords()

    class Meta:
        verbose_name = _("language")
        verbose_name_plural = _("languages")

    def __str__(self):
        return f"{self.name} ({self.iso_code})"


class Wordnet(models.Model):
    name = models.CharField(max_length=50, verbose_name=_("name"))
    language = models.ForeignKey(
        "Language", on_delete=models.PROTECT, blank=False, verbose_name=_("language")
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = _("wordnet")
        verbose_name_plural = _("wordnets")

    def __str__(self):
        return self.name


class Synset(models.Model):
    class Status(models.TextChoices):
        STUB = "stub"
        DRAFT = "draft"
        COMPLETE = "complete"
        REVIEWED = "reviewed"

    wordnet = models.ForeignKey("Wordnet", on_delete=models.PROTECT, blank=False)
    definition = models.CharField(max_length=1000, verbose_name=_("definition"))
    lexicalised = models.BooleanField(default=True, verbose_name=_("lexicalised"))
    princeton_id = models.CharField(
        max_length=30, verbose_name=_("Princeton Wordnet ID"), blank=True, null=True
    )
    pos = models.ForeignKey(
        "PartOfSpeech",
        on_delete=models.PROTECT,
        blank=False,
        verbose_name=_("part of speech"),
    )
    status = models.CharField(choices=Status, default=Status.STUB)
    copied_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_synsets",
    )
    display_name = models.CharField(
        max_length=100, verbose_name=_("display_name"), blank=True
    )
    history = HistoricalRecords(
        bases=[HistoricalChangesMixin, models.Model], excluded_fields=["display_name"]
    )
    # domain = closed list

    class Meta:
        verbose_name = _("synset")
        verbose_name_plural = _("synsets")

    def __str__(self):
        word_part = self.short_display_name()
        definition_part_max_length = SYNSET_STR_MAX_LENGTH - len(word_part) - len(" : ")
        if len(self.definition) <= definition_part_max_length:
            # we can use the whole definition
            return f"{word_part} : {self.definition}"
        else:
            # replace excessive tokens with '...'
            last_wanted_space = self.definition.rfind(
                " ", 0, definition_part_max_length - len(" ...")
            )
            return f"{word_part} : {self.definition[:last_wanted_space]} ..."

    def update_display_name(self):
        """We use display_name to avoid making DB calls in __str__().
        No historical record is kept of this change to the synset."""
        senses = self.sense_set.all().order_by("word__text")[: MAX_WORDS + 1]
        words = [s.word.text for s in senses]

        # we choose at most the first MAX_WORDS words to display
        display_words = words[: min(len(words), MAX_WORDS)]
        display_ellipsis = ", ..." if len(words) > MAX_WORDS else ""
        self.display_name = ", ".join(display_words) + display_ellipsis
        self.save_without_historical_record()

    def short_display_name(self):
        return self.display_name or f"({self.pk})"


class Word(models.Model):
    text = models.CharField(max_length=100, verbose_name=_("lemma"))
    pos = models.ForeignKey(
        "PartOfSpeech",
        on_delete=models.PROTECT,
        blank=False,
        verbose_name=_("part of speech"),
    )
    language = models.ForeignKey(
        "Language", on_delete=models.PROTECT, blank=False, verbose_name=_("language")
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = _("word")
        verbose_name_plural = _("words")
        constraints = [
            models.UniqueConstraint(
                # For now, we enforce the following. In future, we may
                # want to think about changing this as we gain a better
                # understanding of the use cases we want to support.
                fields=("text", "language", "pos"),
                name="unique_word",
                violation_error_message=_("Word already defined"),
            )
        ]

    def __str__(self):
        return f"{self.text} ({self.pos.short_name})"

    # TODO: needs more thought
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        for sense in self.sense_set.all():
            sense.synset.update_display_name()

    def delete(self, *args, **kwargs):
        synsets_to_update = [s.synset for s in self.sense_set.all()]
        deletion = super().delete(*args, **kwargs)
        for synset in synsets_to_update:
            synset.update_display_name()
        return deletion


class Sense(models.Model):
    # PROTECT here forces the user to unlink all words from a synset or
    # all synsets from a word before deleting. Probably the right route.
    word = models.ForeignKey(
        "Word", on_delete=models.PROTECT, blank=False, verbose_name=_("Word")
    )
    synset = models.ForeignKey(
        "Synset", on_delete=models.PROTECT, blank=False, verbose_name=_("Synset")
    )
    comment = models.CharField(
        max_length=1000,
        verbose_name=_("comment"),
        default="",
        blank=True,
        help_text=_("Additional information on word sense"),
    )
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("word", "synset"), name="unique_sense")
        ]

    def __str__(self):
        # The idea is that user never looks at the representation of a sense. Since
        # the string representation appears in admin.TabularInline, this ensures a
        # less cluttered interface.
        # This might have to change when looking more deeply into the modifications to
        # the Contributions app
        return ""

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.synset.update_display_name()

    def delete(self, *args, **kwargs):
        deletion = super().delete(*args, **kwargs)
        self.synset.update_display_name()
        return deletion


class SenseExample(models.Model):
    text = models.CharField(
        max_length=1000,
        verbose_name=_("example"),
        help_text=_(
            "Example sentence illustrating the meaning of a word in a specific sense"
        ),
        blank=True,  # # stop the empty inline blocking save on the synset
    )
    sense = models.ForeignKey(
        "Sense", on_delete=models.CASCADE, blank=False, verbose_name=_("Sense")
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = _("sense example")
        verbose_name_plural = _("sense examples")

    def __str__(self):
        return self.text


class SynsetExample(models.Model):
    text = models.CharField(
        max_length=1000,
        verbose_name=_("example"),
        help_text=_("Example sentence illustrating synset meaning"),
        blank=True,  # # stop the empty inline blocking save on the synset
    )
    synset = models.ForeignKey(
        "Synset", on_delete=models.CASCADE, blank=False, verbose_name=_("Synset")
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = _("synset example")
        verbose_name_plural = _("synset examples")

    def __str__(self):
        return self.text


class PartOfSpeech(models.Model):
    name = models.CharField(max_length=50, verbose_name=_("name"))
    short_name = models.CharField(max_length=1, verbose_name=_("short name"))
    history = HistoricalRecords()

    class Meta:
        verbose_name = _("Part of speech")
        verbose_name_plural = _("Parts of speech")

    def __str__(self):
        return self.name


class RelationType(models.Model):
    name = models.CharField(max_length=50, verbose_name=_("name"))
    history = HistoricalRecords()

    class Meta:
        verbose_name = _("Relation type")
        verbose_name_plural = _("Relation types")

    def __str__(self):
        return self.name


class Relation(models.Model):
    synset_from = models.ForeignKey(
        "Synset", related_name="+", on_delete=models.CASCADE, blank=False
    )
    synset_to = models.ForeignKey(
        "Synset", related_name="+", on_delete=models.CASCADE, blank=False
    )
    type = models.ForeignKey("RelationType", on_delete=models.PROTECT, blank=False)
    display_name = models.CharField(
        max_length=270, verbose_name=_("display_name"), default="no_display_name"
    )
    history = HistoricalRecords(excluded_fields=["display_name"])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("synset_from", "synset_to", "type"),
                name="unique_relation",
                violation_error_message=_("Relation already defined"),
            ),
        ]

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        self.display_name = f"{self.synset_from.display_name} --{self.type}-> {self.synset_to.display_name}"
        super().save(*args, **kwargs)
