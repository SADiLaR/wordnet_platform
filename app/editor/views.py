from django.shortcuts import get_object_or_404, render

from lex.models import Synset, Wordnet


def assignment_queue(request, wn_pk=None):
    wordnets = Wordnet.objects.all()
    context = {"wordnets": wordnets}
    if wn_pk:
        wordnet_obj = get_object_or_404(Wordnet, pk=wn_pk)
        context["wordnet"] = wordnet_obj
    return render(request, "editor/assignment_queue.html", context)


def browse_synsets(request, wn_pk=None):
    wordnets = Wordnet.objects.all()
    context = {"wordnets": wordnets}
    if wn_pk:
        wordnet_obj = get_object_or_404(Wordnet, pk=wn_pk)
        synsets = Synset.objects.filter(wordnet=wordnet_obj).select_related(
            "copied_from"
        )
        context["wordnet"] = wordnet_obj
        context["synsets"] = synsets

    return render(
        request,
        "editor/browse/synsets.html",
        context,
    )
