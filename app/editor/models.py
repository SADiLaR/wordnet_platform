from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from lex.models import Synset, Wordnet


class Assignment(models.Model):
    """A piece of work for one person: complete or review one synset.

    The work is either a source synset to copy into `target_wordnet`, or an
    existing synset in `target_synset`. A copy gets its `target_synset` once
    the copy is created.
    """

    class Goal(models.TextChoices):
        # Translators: An assignment's goal, what to do with the synset.
        TO_COMPLETE = "complete", _("To complete")
        # Translators: An assignment's goal, what to do with the synset.
        TO_REVIEW = "review", _("To review")

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # PROTECT, so that who assigned work is never lost: deactivate users instead.
    assigner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="assignments_made"
    )
    goal = models.CharField(choices=Goal, max_length=20, default=Goal.TO_COMPLETE)
    # CASCADE on both synsets: work on a synset that has been deleted is gone
    # too. The history keeps a record of the assignment.
    source_synset = models.ForeignKey(
        Synset,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="source_assignments",
    )
    target_synset = models.ForeignKey(
        Synset,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="target_assignments",
    )
    target_wordnet = models.ForeignKey(Wordnet, on_delete=models.CASCADE, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    done_at = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        # The work is identified by the target synset where there is one, and
        # by source synset + target wordnet where there is a source, so each
        # rule needs a constraint for both. A copy that has been created has
        # both, and both constraints apply. A row whose synset is empty never
        # clashes on that synset's constraint, because NULLs are never equal in
        # a unique constraint.
        constraints = [
            # One assignment per person per synset, so nobody reviews their own work.
            models.UniqueConstraint(
                fields=["user", "target_synset"],
                name="assignment_one_per_user_target",
                violation_error_message=_(
                    "This person already has an assignment on this synset."
                ),
            ),
            models.UniqueConstraint(
                fields=["user", "source_synset", "target_wordnet"],
                name="assignment_one_per_user_source",
                violation_error_message=_(
                    "This person already has an assignment to copy this synset "
                    "into this wordnet."
                ),
            ),
        ]

    def __str__(self):
        return f"Assignment\xa0{self.pk}"

    def goal_reached(self):
        """Whether the synset's status has reached the goal, so the work can be done.

        A reviewed synset is complete too. A copy that hasn't been created yet
        has reached no goal.
        """
        if self.target_synset is None:
            return False
        if self.goal == self.Goal.TO_REVIEW:
            return self.target_synset.status == Synset.Status.REVIEWED
        return self.target_synset.status in (
            Synset.Status.COMPLETE,
            Synset.Status.REVIEWED,
        )

    def clean(self):
        super().clean()

        if not self.source_synset_id and not self.target_synset_id:
            raise ValidationError(
                _("Choose a source synset to copy, or an existing target synset.")
            )

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
