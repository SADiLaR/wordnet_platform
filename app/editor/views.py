from collections import defaultdict

from django.conf import settings
from django.db.models import Q, prefetch_related_objects
from django.shortcuts import get_object_or_404, render

from lex.models import Relation, Synset, Wordnet


def _guess_princeton_id(id_code):
    if id_code and id_code.startswith("ENG20-"):
        return id_code[6:]
    return id_code


def _guess_source_synset(synset):
    guessed_id = _guess_princeton_id(synset.princeton_id)
    if guessed_id:
        source_synset = (
            Synset.objects.filter(
                princeton_id=guessed_id,
                wordnet_id=settings.SOURCE_WORDNET_ID,  # TODO: make source wordnet configurable
            )
            .exclude(pk=synset.pk)
            .first()
        )
    else:
        source_synset = None
    return source_synset


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


def synset_detail(request, pk):

    synset = get_object_or_404(
        Synset.objects.select_related("pos", "wordnet", "copied_from__wordnet"), pk=pk
    )
    senses = synset.sense_set.select_related("word").prefetch_related(
        "senseexample_set"
    )

    all_relations = Relation.objects.filter(
        Q(synset_from=pk) | Q(synset_to=pk)
    ).select_related("type", "synset_to", "synset_from")
    relations = defaultdict(lambda: {"outgoing": [], "incoming": []})

    for rel in all_relations:
        if synset == rel.synset_from:
            relations[rel.type.name]["outgoing"].append(rel)
        else:
            relations[rel.type.name]["incoming"].append(rel)

    if synset.copied_from_id:
        source_synset = synset.copied_from
    else:
        source_synset = _guess_source_synset(synset)

    if source_synset:
        prefetch_related_objects(
            [source_synset], "sense_set__word", "sense_set__senseexample_set"
        )

    context = {
        "synset": synset,
        "senses": senses,
        "relations": dict(relations),
        "source_synset": source_synset,
    }

    return render(
        request,
        "editor/synset_detail.html",
        context,
    )
