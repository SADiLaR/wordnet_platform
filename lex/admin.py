from django.contrib import admin
from django.utils.translation import gettext_lazy as _

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


class NoRelatedWidgetsInlineMixin:
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        for field_name, field in formset.form.base_fields.items():
            if hasattr(field.widget, "can_add_related"):
                field.widget.can_add_related = False
                field.widget.can_change_related = False
                field.widget.can_delete_related = False
                if field_name == "type":
                    field.widget.can_view_related = False
        return formset


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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for field_name, field in form.base_fields.items():
            if hasattr(field.widget, "can_add_related"):
                field.widget.can_add_related = False
                field.widget.can_change_related = False
                field.widget.can_delete_related = False
                if field_name in ("wordnet", "pos"):
                    field.widget.can_view_related = False
        return form

    class LemmaInline(admin.TabularInline):
        model = Lemma
        extra = 1

    class ExampleInline(admin.StackedInline):
        model = Example
        extra = 0

    class RelationInlineFrom(NoRelatedWidgetsInlineMixin, admin.TabularInline):
        model = Relation
        exclude = ["display_name"]
        fk_name = "synset_from"
        extra = 1
        verbose_name = _("Relation from this synset")
        verbose_name_plural = _("Relations from this synset")

    class RelationInlineTo(NoRelatedWidgetsInlineMixin, admin.TabularInline):
        model = Relation
        exclude = ["display_name"]
        fk_name = "synset_to"
        extra = 1
        verbose_name = _("Relation to this synset")
        verbose_name_plural = _("Relations to this synset")

    inlines = [LemmaInline, ExampleInline, RelationInlineFrom, RelationInlineTo]


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
