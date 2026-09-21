import django_filters
from django import forms
from django.utils.translation import gettext_lazy as _
from django_filters import ModelMultipleChoiceFilter, MultipleChoiceFilter

from lex.models import PartOfSpeech, Synset, Wordnet


class SynsetFilter(django_filters.FilterSet):
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
