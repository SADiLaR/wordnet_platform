from django import forms
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from nested_admin import NestedModelAdmin, NestedStackedInline, NestedTabularInline
from simple_history.admin import SimpleHistoryAdmin

from lex.models import (
    Language,
    PartOfSpeech,
    Relation,
    RelationType,
    Sense,
    SenseExample,
    Synset,
    SynsetExample,
    Word,
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


# Only provides add buttons, no change or delete
class OnlyAddWidgetsInlineMixin:
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        for field_name, field in formset.form.base_fields.items():
            if hasattr(field.widget, "can_add_related"):
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


class SynsetAdmin(NestedModelAdmin, SimpleHistoryAdmin):
    list_filter = ["wordnet", "status"]
    list_display = ["__str__", "pos"]
    search_fields = ["sense__word__text", "definition"]
    raw_id_fields = ("copied_from",)
    exclude = ["display_name"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for field_name, field in form.base_fields.items():
            if field_name == "definition":
                field.widget = forms.Textarea(attrs={"rows": 3})

            if hasattr(field.widget, "can_add_related"):
                field.widget.can_add_related = False
                field.widget.can_change_related = False
                field.widget.can_delete_related = False
                if field_name in ("wordnet", "pos"):
                    field.widget.can_view_related = False
        return form

    def get_inlines(self, request, obj):
        if not obj or not obj.display_name:
            return [self.SenseInline, self.SynsetExampleInline]
        else:
            return [
                self.SenseInline,
                self.SynsetExampleInline,
                self.RelationInlineFrom,
                self.RelationInlineTo,
            ]

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        if not obj or not obj.display_name:
            context["show_save"] = False
            context["show_save_as_new"] = False
            context["show_save_and_add_another"] = False
        return super().render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj
        )

    def save_model(self, request, obj, form, change):
        """We override this method to inject change reasons for synset field changes."""
        changes = []
        try:
            old_synset = Synset.objects.get(pk=obj.pk)
        except Synset.DoesNotExist:
            changes.append(("Added synset", f"'{obj.definition}'"))
            old_synset = None

        if old_synset:
            for changed_field in form.changed_data:
                old_value = getattr(old_synset, changed_field)
                new_value = getattr(obj, changed_field)
                changes.append(
                    (f"Changed synset's {changed_field}", f"{old_value} → {new_value}.")
                )

        if changes:
            change_msgs = [": ".join(c) for c in changes]
            change_reason_msg = "; ".join(change_msgs)
            obj._change_details = change_reason_msg

        return super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """We override this method to inject change reasons for inline changes."""

        changes = []
        for f in formset.forms:
            # deletions
            # f.instance._state.adding = False where f has been added to the DB
            # See: https://docs.djangoproject.com/en/6.0/ref/models/instances/#state
            if not f.instance._state.adding and f in formset.deleted_forms:
                old_obj = f.instance
                model_class = type(f.instance)
                changes.append(f"Deleted {model_class._meta.verbose_name}: {old_obj}")
            # changes
            elif f.has_changed() and not f.instance._state.adding:
                new_obj = f.instance
                model_class = type(f.instance)
                old_obj = model_class.objects.get(pk=new_obj.pk)
                for c in f.changed_data:
                    old_value = getattr(old_obj, c)
                    new_value = getattr(new_obj, c)
                    changes.append(
                        f"Changed {c} of {model_class._meta.verbose_name} '{old_obj}': {old_value} → {new_value}"
                    )
            # additions
            elif f.has_changed():
                new_obj = f.instance
                model_class = type(f.instance)
                changes.append(f"Added {model_class._meta.verbose_name}: {new_obj}")

        if changes:
            change_reason_msg = "; ".join(changes)
            formset.instance._change_details = change_reason_msg
            formset.instance.save()

        return super().save_formset(request, form, formset, change)

    # Override Django simple-history to show custom view
    def history_view(self, request, object_id, extra_context=None):
        params = {"source": "synset"}
        return HttpResponseRedirect(
            reverse("admin:synset_contributions_view", args=[object_id])
            + "?"
            + urlencode(params)
        )

    class SenseInline(OnlyAddWidgetsInlineMixin, NestedTabularInline):
        model = Sense
        autocomplete_fields = ["word"]
        extra = 0
        verbose_name = _("Associated word")
        verbose_name_plural = _("Associated words")

        class SenseExampleInline(NestedStackedInline):
            model = SenseExample
            extra = 0
            verbose_name = _("Usage example")
            verbose_name_plural = _("Usage examples")

        inlines = [SenseExampleInline]

    class SynsetExampleInline(NestedStackedInline):
        model = SynsetExample
        extra = 0

    class RelationInlineFrom(NoRelatedWidgetsInlineMixin, NestedTabularInline):
        model = Relation
        exclude = ["display_name"]
        fk_name = "synset_from"
        readonly_fields = ("display_from",)
        fields = ("display_from", "type", "synset_to")
        raw_id_fields = ("synset_to",)
        extra = 0
        verbose_name = _("Relation from this synset to another")
        verbose_name_plural = _("Relations from this synset to another")

        def display_from(self, obj):
            return str(obj.synset_from)

        def get_queryset(self, request):
            return (
                super()
                .get_queryset(request)
                .select_related("synset_from", "synset_to", "type")
            )

        display_from.short_description = _("This synset")

    class RelationInlineTo(NoRelatedWidgetsInlineMixin, NestedTabularInline):
        model = Relation
        exclude = ["display_name"]
        fk_name = "synset_to"
        readonly_fields = ("display_to",)
        fields = ("synset_from", "type", "display_to")
        raw_id_fields = ("synset_from",)
        extra = 0
        verbose_name = _("Relation from another synset to this synset")
        verbose_name_plural = _("Relations from another synset to this synset")

        def display_to(self, obj):
            return str(obj.synset_to)

        def get_queryset(self, request):
            return (
                super()
                .get_queryset(request)
                .select_related("synset_from", "synset_to", "type")
            )

        display_to.short_description = _("This synset")

    inlines = [SenseInline, SynsetExampleInline, RelationInlineFrom, RelationInlineTo]


# TODO : think about changing inheritance to SimpleHistoryAdmin
class WordAdmin(admin.ModelAdmin):
    list_filter = ["language", "pos"]
    list_display = ["text", "pos"]
    search_fields = ["text"]

    class SenseInline(NoRelatedWidgetsInlineMixin, admin.TabularInline):
        model = Sense
        autocomplete_fields = ["synset"]
        extra = 1
        verbose_name = _("Associated synset")
        verbose_name_plural = _("Associated synsets")

    def get_inlines(self, request, obj):
        return [self.SenseInline]


class WordnetAdmin(admin.ModelAdmin):
    list_display = ["name", "language"]


class RelationAdmin(SimpleHistoryAdmin):
    list_display = ["type", "synset_from", "synset_to"]
    raw_id_fields = ("synset_from", "synset_to")


admin.site.register(Language, LanguageAdmin)
admin.site.register(Wordnet, WordnetAdmin)
admin.site.register(Synset, SynsetAdmin)
admin.site.register(Word, WordAdmin)
admin.site.register(PartOfSpeech)
admin.site.register(RelationType)
admin.site.register(Relation, RelationAdmin)
