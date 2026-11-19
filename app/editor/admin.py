from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from simple_history.admin import SimpleHistoryAdmin

from editor.models import Assignment


class DoneFilter(admin.SimpleListFilter):
    """Filter assignments by whether they are done, in words rather than by date."""

    title = _("done status")
    parameter_name = "done"

    def lookups(self, request, model_admin):
        return [("yes", _("Done")), ("no", _("Not done"))]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(done_at__isnull=False)
        if self.value() == "no":
            return queryset.filter(done_at__isnull=True)
        return queryset


class AssignmentAdmin(SimpleHistoryAdmin):
    list_filter = [
        "target_wordnet",
        "goal",
        "user",
        "assigner",
        DoneFilter,
    ]
    list_display = [
        "__str__",
        "user",
        "goal",
        "target_wordnet",
        "source_synset",
        "target_synset",
        "assigner",
        "created_at",
        "done_at",
    ]
    ordering = ["-created_at", "-pk"]
    raw_id_fields = [
        "source_synset",
        "target_synset",
    ]
    # The assigner is always whoever added the assignment, so nobody can
    # record someone else as having assigned work.
    readonly_fields = ["assigner", "created_at"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.assigner = request.user
        super().save_model(request, obj, form, change)


admin.site.register(Assignment, AssignmentAdmin)
