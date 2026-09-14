from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from lex.models import Synset, Wordnet


class Assignment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active"
        COMPLETED = "completed"
        TARGET_DELETED = "target_deleted"

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    source_synset = models.ForeignKey(
        Synset, on_delete=models.SET_NULL, null=True, related_name="source_assignments"
    )
    target_synset = models.ForeignKey(
        Synset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="target_assignments",
    )
    target_wordnet = models.ForeignKey(Wordnet, on_delete=models.CASCADE, blank=True)
    status = models.CharField(choices=Status, max_length=30, default=Status.ACTIVE)

    def __str__(self):
        return f"Assignment\xa0{self.pk}"

    def clean(self):
        super().clean()

        if self.target_synset_id:
            if self.target_wordnet_id:
                if self.target_synset.wordnet_id != self.target_wordnet_id:
                    raise ValidationError(
                        _("Target synset must belong to target wordnet.")
                    )
            else:
                self.target_wordnet_id = self.target_synset.wordnet_id
        elif not self.target_wordnet_id:
            raise ValidationError(
                _("Specify either a target wordnet or target synset.")
            )
