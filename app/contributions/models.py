from django.db import models
from django.utils.translation import gettext_lazy as _


class ContributionsHistory(models.Model):
    class Meta:
        managed = False
        verbose_name = _("Contribution")
        verbose_name_plural = _("Contributions")

    def __str__(self):
        return super().__str__()
