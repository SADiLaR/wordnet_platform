import django_filters
from django import forms
from django.db.models import Case, IntegerField, Q, Value, When
from django.db.models.functions import Length
from django.utils.translation import gettext_lazy as _
from django_filters import ModelMultipleChoiceFilter, MultipleChoiceFilter

from lex.models import PartOfSpeech, Synset, Wordnet


class SynsetFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="ignore", label=_("Search"))

    pos = ModelMultipleChoiceFilter(
        label=_("Part of speech"),
        queryset=PartOfSpeech.objects.all().order_by("name"),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
    )

    wordnet = ModelMultipleChoiceFilter(
        label=_("Wordnet"),
        queryset=Wordnet.objects.all().order_by("name"),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
    )

    status = MultipleChoiceFilter(
        label=_("Status"),
        choices=Synset.Status.choices,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Synset
        fields = ["pos", "wordnet", "status"]

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        search = self.form.cleaned_data.get("search", "").strip()

        if search:
            queryset = (
                queryset.filter(
                    Q(display_name__icontains=search) | Q(definition__icontains=search)
                )
                .annotate(
                    match_priority=Case(
                        When(display_name__icontains=search, then=Value(0)),
                        When(definition__icontains=search, then=Value(1)),
                        output_field=IntegerField(),
                    )
                )
                .order_by(
                    "match_priority",
                    Length("display_name"),
                    "display_name",
                )
            )
        return queryset

    def ignore(self, queryset, name, value):
        return queryset
