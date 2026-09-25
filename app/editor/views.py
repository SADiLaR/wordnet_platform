from collections import defaultdict

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q, prefetch_related_objects
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from lex.models import Relation, Synset, Wordnet

from .filters import SynsetFilter
from .forms import DefinitionForm


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


def browse_synsets(request):
    wordnets = Wordnet.objects.all()
    context = {"wordnets": wordnets}
    synsets = (
        Synset.objects.all().select_related("copied_from").order_by("display_name")
    )
    f = SynsetFilter(request.GET, queryset=synsets)
    url_params = request.GET.copy()
    paginator = Paginator(f.qs, 20)
    page_number = url_params.pop("page", None)
    page_obj = paginator.get_page(page_number)

    context["page_obj"] = page_obj
    context["filter"] = f
    context["url_params"] = url_params.urlencode()

    return render(
        request,
        "editor/browse/synsets.html",
        context,
    )


def _synset_context(pk=None, synset=None):

    if synset is None and pk is None:
        raise ValueError("Either pk or synset must be provided")
    if synset is None:
        synset = get_object_or_404(
            Synset.objects.select_related("pos", "wordnet", "copied_from__wordnet"),
            pk=pk,
        )
    if not pk:
        pk = synset.pk

    senses = synset.sense_set.select_related("word").prefetch_related(
        "senseexample_set"
    )

    all_relations = Relation.objects.filter(
        Q(synset_from=pk) | Q(synset_to=pk)
    ).select_related("type", "synset_to", "synset_from")
    relations = {"outgoing": defaultdict(list), "incoming": defaultdict(list)}

    for rel in all_relations:
        if synset == rel.synset_from:
            relations["outgoing"][rel.type.name].append(rel)
        else:
            relations["incoming"][rel.type.name].append(rel)

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
        "relations": {direction: dict(types) for direction, types in relations.items()},
        "source_synset": source_synset,
        "definition_form": DefinitionForm(initial={"definition": synset.definition}),
    }
    return context


def synset_detail(request, pk):

    context = _synset_context(pk)
    return render(
        request,
        "editor/synset_detail.html",
        context,
    )


def synset_status_htmx(request, pk):
    synset = get_object_or_404(Synset, pk=pk)
    context = {"synset": synset}

    if request.method == "POST":
        status = request.POST["new_status"]
        warnings = []

        if status in (
            Synset.Status.COMPLETE,
            Synset.Status.REVIEWED,
        ) and not request.POST.get("force_save"):
            if not synset.definition:
                warnings.append(_("No definition."))

            prefetch_related_objects(
                [synset], "sense_set__senseexample_set", "sense_set__word"
            )
            if len(synset.sense_set.all()) < 1:
                warnings.append(_("No words."))
            else:
                for sense in synset.sense_set.all():
                    if len(sense.senseexample_set.all()) < 1:
                        warnings.append(
                            _('"%(word)s" has no usage example.')
                            % {"word": sense.word.text}
                        )
            if not Relation.objects.filter(
                Q(synset_from=pk) | Q(synset_to=pk)
            ).exists():
                warnings.append(_("No relations."))

        if warnings:
            context["warnings"] = warnings
            context["new_status"] = status
            context["new_status_label"] = Synset.Status(status).label
        else:
            synset.status = status
            synset.save(update_fields=["status"])

    return render(
        request,
        "editor/snippets/_status_control.html",
        context,
    )


def synset_definition(request, pk):
    synset = get_object_or_404(Synset, pk=pk)

    if request.method == "POST":
        form = DefinitionForm(request.POST)
        if form.is_valid():
            synset.definition = form.cleaned_data["definition"]
            updated_fields = ["definition"]
            if synset.status != Synset.Status.DRAFT:
                synset.status = Synset.Status.DRAFT
                updated_fields.append("status")
            synset.save(update_fields=updated_fields)

            return redirect("editor:synset_detail", pk=pk)
        else:
            context = _synset_context(synset)
            context["definition_form"] = form
            return render(request, "editor/synset_detail.html", context)

    return HttpResponseNotAllowed(["POST"])
