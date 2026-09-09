from collections import defaultdict

from django.conf import settings
from django.db.models import prefetch_related_objects
from django.shortcuts import get_object_or_404, render

from lex.models import Relation, Sense, Synset, Wordnet


def _guess_princeton_id(id_code):
    if id_code and id_code.startswith("ENG20-"):
        return id_code[6:]
    return id_code


def _guess_source_synset(synset_obj):
    guessed_id = _guess_princeton_id(synset_obj.princeton_id)
    if guessed_id:
        source_synset = (
            Synset.objects.filter(
                princeton_id=guessed_id,
                wordnet_id=settings.SOURCE_WORDNET_ID,  # TODO: make source wordnet configurable
            )
            .exclude(pk=synset_obj.pk)
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


def synset_detail(request, ss_pk):

    synset_obj = get_object_or_404(
        Synset.objects.select_related("pos", "wordnet"), pk=ss_pk
    )
    senses = (
        Sense.objects.filter(synset=ss_pk)
        .select_related("word")
        .prefetch_related("senseexample_set")
    )

    outgoing_relations = Relation.objects.filter(synset_from=ss_pk).select_related(
        "type", "synset_to"
    )
    incoming_relations = Relation.objects.filter(synset_to=ss_pk).select_related(
        "type", "synset_from"
    )

    relations = defaultdict(lambda: {"outgoing": [], "incoming": []})
    for rel in outgoing_relations:
        relations[rel.type.name]["outgoing"].append(rel)

    for rel in incoming_relations:
        relations[rel.type.name]["incoming"].append(rel)

    if synset_obj.copied_from_id:
        source_synset = Synset.objects.select_related("wordnet").get(
            pk=synset_obj.copied_from_id
        )
        explicit_source = True
    else:
        source_synset = _guess_source_synset(synset_obj)
        explicit_source = False

    if source_synset:
        prefetch_related_objects(
            [source_synset], "sense_set__word", "sense_set__senseexample_set"
        )

    context = {
        "synset": synset_obj,
        "senses": senses,
        "relations": dict(relations),
        "source_synset": source_synset,
        "explicit_source": explicit_source,
    }

    return render(
        request,
        "editor/synset_detail.html",
        context,
    )
