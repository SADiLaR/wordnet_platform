import django_filters
from django import forms
from django.db.models import OuterRef, Q, Subquery
from django.db.models.functions import Length
from django.utils.translation import gettext_lazy as _
from django_filters import ModelMultipleChoiceFilter, MultipleChoiceFilter

from lex.models import PartOfSpeech, Sense, Synset, Wordnet


class SynsetFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="ignore", label=_("Search"))

    pos = ModelMultipleChoiceFilter(
        label=_("Part of speech"),
        queryset=PartOfSpeech.objects.all().order_by("name"),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        distinct=False,
    )

    wordnet = ModelMultipleChoiceFilter(
        label=_("Wordnet"),
        queryset=Wordnet.objects.all().order_by("name"),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        distinct=False,
    )

    status = MultipleChoiceFilter(
        label=_("Status"),
        choices=Synset.Status.choices,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        distinct=False,
    )

    class Meta:
        model = Synset
        fields = ["pos", "wordnet", "status"]

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        search = self.form.cleaned_data.get("search", "").strip()
        MIN_DEFINITION_SEARCH_LENGTH = 4

        if search:
            search_filter = Q(display_name__unaccent__icontains=search)
            # Only search definitions for longer search terms.
            if len(search) >= MIN_DEFINITION_SEARCH_LENGTH:
                search_filter |= Q(definition__unaccent__icontains=search)

            # Find Sense rows that belong to the current Synset and whose linked
            # Word matches the search text, so we can rank using the actual
            # matching word rather than the full display_name.
            matching_senses = (
                Sense.objects.filter(
                    synset_id=OuterRef("pk"),
                    word__text__unaccent__icontains=search,
                )
                .annotate(
                    word_score=Length("word__text"),
                )
                .order_by(
                    "word_score",
                )
            )

            queryset = (
                queryset.filter(search_filter)
                .annotate(
                    match_score=Subquery(matching_senses.values("word_score")[:1]),
                )
                .order_by(
                    "match_score",
                    "display_name",
                    "pk",
                )
            )

        return queryset

    def ignore(self, queryset, name, value):
        return queryset
