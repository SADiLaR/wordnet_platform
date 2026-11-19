import django.db.models.deletion
import django.utils.timezone
import simple_history.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("editor", "0001_initial"),
        ("lex", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name="assignment",
            name="status",
        ),
        # No default: assignments made before this migration have no record of
        # who assigned them, so there is no true value to fill in. Where any
        # exist, this migration fails, and they need deleting first.
        migrations.AddField(
            model_name="assignment",
            name="assigner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assignments_made",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="assignment",
            name="goal",
            field=models.CharField(
                choices=[("complete", "To complete"), ("review", "To review")],
                default="complete",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="assignment",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="assignment",
            name="done_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="assignment",
            name="source_synset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="source_assignments",
                to="lex.synset",
            ),
        ),
        migrations.AlterField(
            model_name="assignment",
            name="target_synset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="target_assignments",
                to="lex.synset",
            ),
        ),
        migrations.AddConstraint(
            model_name="assignment",
            constraint=models.UniqueConstraint(
                fields=("user", "target_synset"),
                name="assignment_one_per_user_target",
                violation_error_message=(
                    "This person already has an assignment on this synset."
                ),
            ),
        ),
        migrations.AddConstraint(
            model_name="assignment",
            constraint=models.UniqueConstraint(
                fields=("user", "source_synset", "target_wordnet"),
                name="assignment_one_per_user_source",
                violation_error_message=(
                    "This person already has an assignment to copy this synset "
                    "into this wordnet."
                ),
            ),
        ),
        migrations.CreateModel(
            name="HistoricalAssignment",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        auto_created=True, blank=True, db_index=True, verbose_name="ID"
                    ),
                ),
                (
                    "goal",
                    models.CharField(
                        choices=[("complete", "To complete"), ("review", "To review")],
                        default="complete",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(blank=True, editable=False)),
                ("done_at", models.DateTimeField(blank=True, null=True)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                (
                    "history_change_reason",
                    models.CharField(max_length=100, null=True),
                ),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "assigner",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source_synset",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="lex.synset",
                    ),
                ),
                (
                    "target_synset",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="lex.synset",
                    ),
                ),
                (
                    "target_wordnet",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="lex.wordnet",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "historical assignment",
                "verbose_name_plural": "historical assignments",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
    ]
