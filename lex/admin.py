from django.contrib import admin

from lex.models import (
    Example,
    Language,
    Lemma,
    PartOfSpeech,
    Relation,
    RelationType,
    Synset,
    Wordnet,
)


class LanguageAdmin(admin.ModelAdmin):
    list_display = ["iso_code", "name"]
    ordering = ["iso_code", "name"]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("iso_code",)
        return super().get_readonly_fields(request, obj)


class SynsetAdmin(admin.ModelAdmin):
    list_filter = ["wordnet", "status"]
    list_display = ["__str__", "pos"]
    search_fields = ["lemma__text"]
    exclude = ["display_name"]

    class LemmaInline(admin.TabularInline):
        model = Lemma
        extra = 1

    class ExampleInline(admin.StackedInline):
        model = Example
        extra = 0

    inlines = [LemmaInline, ExampleInline]


class WordnetAdmin(admin.ModelAdmin):
    list_display = ["name", "language"]


class RelationAdmin(admin.ModelAdmin):
    list_display = ["type", "synset_from", "synset_to"]


admin.site.register(Language, LanguageAdmin)
admin.site.register(Wordnet, WordnetAdmin)
admin.site.register(Synset, SynsetAdmin)
admin.site.register(PartOfSpeech)
admin.site.register(RelationType)
admin.site.register(Relation, RelationAdmin)
