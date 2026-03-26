from django.db import models
from django.utils.translation import gettext_lazy as _


class Language(models.Model):
    iso_code = models.CharField(primary_key=True, max_length=10, verbose_name=_("ISO code"))
    name = models.CharField(max_length=50, verbose_name=_("name"))

    class Meta:
        verbose_name = _("language")
        verbose_name_plural = _("languages")

    def __str__(self):
        return f"{self.name} ({self.iso_code})"


class Wordnet(models.Model):
    name = models.CharField(max_length=50, verbose_name=_("name"))
    language = models.ForeignKey("Language", on_delete=models.PROTECT, blank=False, verbose_name=_("language"))

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
    pos = models.ForeignKey("PartOfSpeech", on_delete=models.PROTECT, blank=False, verbose_name=_("part of speech"))
    status = models.IntegerField(choices=Status, default=Status.UNVERIFIED)
    # domain = closed list

    class Meta:
        verbose_name = _("synset")
        verbose_name_plural = _("synsets")


class Term(models.Model):
    text = models.CharField(max_length=1000, verbose_name=_("term"))
    synset = models.ForeignKey("Synset", on_delete=models.CASCADE, blank=False, verbose_name=_("synset"))
    lexicalised = models.BooleanField(default=True, verbose_name=_("lexicalised"))

    class Meta:
        verbose_name = _("term")
        verbose_name_plural = _("terms")

    def __str__(self):
        return self.text


class Example(models.Model):
    text = models.CharField(max_length=1000, verbose_name=_("example"))
    synset = models.ForeignKey("Synset", on_delete=models.CASCADE, blank=False, verbose_name=_("Synset"))

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
    synset_from = models.ForeignKey("Synset", related_name="+", on_delete=models.CASCADE, blank=False)
    synset_to = models.ForeignKey("Synset", related_name="+", on_delete=models.CASCADE, blank=False)
    type = models.ForeignKey("RelationType", on_delete=models.PROTECT, blank=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("synset_from", "synset_to", "type"),
                name="unique_relation",
                violation_error_message=_("Relation already defined"),
            ),
        ]
