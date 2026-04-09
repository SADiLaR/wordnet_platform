from django.contrib import admin

from lex.models import (
    Language,
    Wordnet,
    Synset,
    Lemma,
    Example,
    PartOfSpeech,
    RelationType,
    Relation,
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
    search_fields = ["lemma__text"]

    class LemmaInline(admin.TabularInline):
        model = Lemma
        extra = 1

    class ExampleInline(admin.StackedInline):
        model = Example
        extra = 0

    inlines = [LemmaInline, ExampleInline]


admin.site.register(Language, LanguageAdmin)
admin.site.register(Wordnet)
admin.site.register(Synset, SynsetAdmin)
admin.site.register(PartOfSpeech)
admin.site.register(RelationType)
admin.site.register(Relation)
