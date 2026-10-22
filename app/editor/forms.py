from django import forms

from lex.models import SenseExample, Synset


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
