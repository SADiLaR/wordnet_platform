from django.shortcuts import render

from lex.models import Synset, Wordnet


def landing(request):
    wordnets = Wordnet.objects.all()
    context = {"wordnets": wordnets}
    return render(request, "editor/landing.html", context)


def browse_synsets(request):
    wordnets = Wordnet.objects.all()
    if wordnet_name := request.GET.get("wordnet", None):
        if wordnet_obj := next((w for w in wordnets if w.name == wordnet_name), None):
            synsets = Synset.objects.filter(wordnet=wordnet_obj).select_related(
                "copied_from"
            )
            context = {
                "wordnet_found": True,
                "wordnet": wordnet_obj,
                "synsets": synsets,
                "wordnets": wordnets,
            }
        else:
            # no such wordnet
            context = {
                "wordnet_found": False,
                "wordnet_name": wordnet_name,
                "wordnets": wordnets,
            }
    else:
        context = {"wordnet_found": False, "wordnets": wordnets}
    return render(
        request,
        "editor/browse/synsets.html",
        context,
    )
