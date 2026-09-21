from django import forms

from lex.models import Synset


class DefinitionForm(forms.ModelForm):
    class Meta:
        model = Synset
        fields = ["definition"]
