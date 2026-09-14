from django.contrib import admin

from editor.models import Assignment


class AssignmentAdmin(admin.ModelAdmin):
    list_filter = ["target_wordnet", "user"]
    list_display = [
        "__str__",
        "user",
        "target_wordnet",
        "source_synset",
        "target_synset",
    ]
    raw_id_fields = [
        "source_synset",
        "target_synset",
    ]


admin.site.register(Assignment, AssignmentAdmin)
