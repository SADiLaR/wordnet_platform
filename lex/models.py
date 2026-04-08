from django.db import models
from django.utils.translation import gettext_lazy as _

SYNSET_STR_MAX_LENGTH = 100
MAX_LEMMAS = 3


class Language(models.Model):
    iso_code = models.CharField(
        primary_key=True,
        max_length=10,
        verbose_name=_("ISO code"),
        help_text=_("Language code according to ISO 639-3"),
    )
    name = models.CharField(max_length=50, verbose_name=_("name"))

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

    class Meta:
        verbose_name = _("wordnet")
        verbose_name_plural = _("wordnets")

    def __str__(self):
        return self.name


class Synset(models.Model):
    class Status(models.IntegerChoices):
        UNVERIFIED = 0, _("Unverified")
        REJECTED = -1, _("Rejected")
        ACCEPTED = +1, _("Accepted")

    wordnet = models.ForeignKey("Wordnet", on_delete=models.PROTECT, blank=False)
    definition = models.CharField(max_length=1000, verbose_name=_("definition"))
    pos = models.ForeignKey(
        "PartOfSpeech",
        on_delete=models.PROTECT,
        blank=False,
        verbose_name=_("part of speech"),
    )
    status = models.IntegerField(choices=Status, default=Status.UNVERIFIED)
    display_name = models.CharField(
        max_length=100, verbose_name=_("display_name"), blank=True
    )
    # domain = closed list

    class Meta:
        verbose_name = _("synset")
        verbose_name_plural = _("synsets")

    def update_display_name(self):
        lemmas = self.lemma_set.all().order_by("text")[: MAX_LEMMAS + 1]

        # we choose at most the first MAX_LEMMAS lemmas to display
        display_lemmas = lemmas[: min(len(lemmas), MAX_LEMMAS)]
        display_ellipsis = ", ..." if len(lemmas) > MAX_LEMMAS else ""
        self.display_name = (
            ", ".join([lemma.text for lemma in display_lemmas]) + display_ellipsis
        )
        self.save()

    def short_display_name(self):
        return self.display_name or f"({self.pk})"

    def __str__(self):
        lemma_part = self.short_display_name()
        definition_part_max_length = (
            SYNSET_STR_MAX_LENGTH - len(lemma_part) - len(" : ")
        )
        if len(self.definition) <= definition_part_max_length:
            # we can use the whole definition
            return f"{lemma_part} : {self.definition}"
        else:
            # replace excessive tokens with '...'
            last_wanted_space = self.definition.rfind(
                " ", 0, definition_part_max_length - len(" ...")
            )
            return f"{lemma_part} : {self.definition[:last_wanted_space]} ..."


class Lemma(models.Model):
    text = models.CharField(max_length=100, verbose_name=_("lemma"))
    synset = models.ForeignKey(
        "Synset", on_delete=models.CASCADE, blank=False, verbose_name=_("synset")
    )
    lexicalised = models.BooleanField(default=True, verbose_name=_("lexicalised"))

    class Meta:
        verbose_name = _("lemma")
        verbose_name_plural = _("lemmas")

    def __str__(self):
        return self.text

    # TODO: needs more thought
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.synset.update_display_name()

    def delete(self, *args, **kwargs):
        deletion = super().delete(*args, **kwargs)
        self.synset.update_display_name()
        return deletion


class Example(models.Model):
    text = models.CharField(
        max_length=1000,
        verbose_name=_("example"),
        help_text=_("Example sentence showing typical usage"),
    )
    synset = models.ForeignKey(
        "Synset", on_delete=models.CASCADE, blank=False, verbose_name=_("Synset")
    )

    class Meta:
        verbose_name = _("example")
        verbose_name_plural = _("examples")

    def __str__(self):
        return self.text


class PartOfSpeech(models.Model):
    name = models.CharField(max_length=50, verbose_name=_("name"))

    class Meta:
        verbose_name = _("Part of speech")
        verbose_name_plural = _("Parts of speech")

    def __str__(self):
        return self.name


class RelationType(models.Model):
    name = models.CharField(max_length=50, verbose_name=_("name"))

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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("synset_from", "synset_to", "type"),
                name="unique_relation",
                violation_error_message=_("Relation already defined"),
            ),
        ]
