from django.shortcuts import get_object_or_404, render

from lex.models import Synset, Wordnet


def landing(request):
    wordnets = Wordnet.objects.all()
    context = {"wordnet_found": False, "wordnets": wordnets}
    return render(request, "editor/landing.html", context)


def landing_by_wordnet(request, wn_pk):
    wordnets = Wordnet.objects.all()
    wordnet_obj = get_object_or_404(Wordnet, pk=wn_pk)
    context = {
        "wordnet_found": True,
        "wordnet": wordnet_obj,
        "wordnets": wordnets,
    }
    return render(request, "editor/landing.html", context)


def browse_synsets(request):
    wordnets = Wordnet.objects.all()
    context = {"wordnet_found": False, "wordnets": wordnets}
    return render(
        request,
        "editor/browse/synsets.html",
        context,
    )


def browse_synsets_by_wordnet(request, wn_pk):
    wordnets = Wordnet.objects.all()
    wordnet_obj = get_object_or_404(Wordnet, pk=wn_pk)
    synsets = Synset.objects.filter(wordnet=wordnet_obj).select_related("copied_from")
    context = {
        "wordnet_found": True,
        "wordnet": wordnet_obj,
        "synsets": synsets,
        "wordnets": wordnets,
    }

    return render(
        request,
        "editor/browse/synsets.html",
        context,
    )
