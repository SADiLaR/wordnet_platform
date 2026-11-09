from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from lex.models import PartOfSpeech, SenseExample, Synset, Wordnet


class DefinitionForm(forms.ModelForm):
    class Meta:
        model = Synset
        fields = ["definition"]


class SenseExampleForm(forms.ModelForm):
    class Meta:
        model = SenseExample
        fields = ["text"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The model allows blank text (for admin inlines); the editor doesn't.
        self.fields["text"].required = True


class NewSynsetForm(forms.Form):
    """A new synset's wordnet and part of speech.

    Any wordnet can be chosen except the source wordnet, whose synsets aren't edited
    here.
    """

    # A plain Form, not a ModelForm: a ModelForm would validate the model too, which
    # looks up both foreign keys a second time.
    wordnet = forms.ModelChoiceField(
        queryset=Wordnet.objects.order_by("name", "pk"),
        label=_("Wordnet"),
        empty_label=_("Choose a wordnet…"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    pos = forms.ModelChoiceField(
        queryset=PartOfSpeech.objects.order_by("name", "pk"),
        label=_("Part of speech"),
        empty_label=_("Choose a part of speech…"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Read when the form is made, not when the module is imported, so that a test
        # can override the setting
        wordnet_field = self.fields["wordnet"]
        wordnet_field.queryset = wordnet_field.queryset.exclude(
            pk=settings.SOURCE_WORDNET_ID
        )
