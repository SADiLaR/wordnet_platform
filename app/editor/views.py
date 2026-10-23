from collections import defaultdict

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q, prefetch_related_objects
from django.db.models.functions import Length
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from lex.models import (
    Relation,
    RelationType,
    Sense,
    SenseExample,
    Synset,
    Word,
    Wordnet,
)

from .filters import SynsetFilter, make_search_qs
from .forms import DefinitionForm, SenseExampleForm


def about(request):
    return render(request, "editor/about.html")


def front_page(request):
    return render(request, "editor/front_page.html")


def _guess_princeton_id(id_code):
    if id_code and id_code.startswith("ENG20-"):
        return id_code[6:]
    return id_code


def _guess_source_synset(synset):
    guessed_id = _guess_princeton_id(synset.princeton_id)
    if guessed_id:
        source_synset = (
            Synset.objects.select_related("pos", "wordnet__language")
            .filter(
                princeton_id=guessed_id,
                wordnet_id=settings.SOURCE_WORDNET_ID,  # TODO: make source wordnet configurable
            )
            .exclude(pk=synset.pk)
            .first()
        )
    else:
        source_synset = None
    return source_synset


def _save_updated_synset(synset, updated_fields=None):
    updated_fields = [] if not updated_fields else updated_fields
    if synset.status != Synset.Status.DRAFT:
        synset.status = Synset.Status.DRAFT
        updated_fields.append("status")
    synset.save(update_fields=updated_fields)


def _examples_prefetch(lookup="senseexample_set"):
    # Examples with empty text are left over from the old tool; treat them as missing.
    # Alphabetical, by the database's collation; pk only breaks ties between duplicates.
    return Prefetch(
        lookup,
        queryset=SenseExample.objects.exclude(text="").order_by("text", "pk"),
    )


def _senses(synset):
    return (
        synset.sense_set.select_related("word")
        .prefetch_related(_examples_prefetch())
        .order_by("word__text")
    )


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
        Synset.objects.all()
        .select_related("copied_from")
        .order_by("display_name", "pk")
    )
    f = SynsetFilter(request.GET, queryset=synsets)
    url_params = request.GET.copy()
    paginator = Paginator(f.qs, 20)
    page_number = request.GET.get("page")
    url_params.pop("page", None)
    page_obj = paginator.get_page(page_number)

    context["page_obj"] = page_obj
    context["filter"] = f
    context["q"] = f.form.cleaned_data.get("search", "").strip()
    context["url_params"] = url_params.urlencode()

    return render(
        request,
        "editor/browse/synsets.html",
        context,
    )


def _build_relations(pk):
    all_relations = Relation.objects.filter(
        Q(synset_from=pk) | Q(synset_to=pk)
    ).select_related("type", "synset_to", "synset_from")
    relations = {"outgoing": defaultdict(list), "incoming": defaultdict(list)}

    for rel in all_relations:
        type_pk = rel.type_id
        if pk == rel.synset_from_id:
            direction = "outgoing"
        else:
            direction = "incoming"
        if type_pk not in relations[direction]:
            relations[direction][type_pk] = {"relations": [], "name": rel.type.name}
        relations[direction][type_pk]["relations"].append(rel)
    return {direction: dict(groups) for direction, groups in relations.items()}


def _synsets_for_detail_page():
    # Synsets, with the related objects the detail page displays (part of speech,
    # wordnet and its language, and the same for the linked source synset) fetched
    # in the same query. Use it to load a synset that will be rendered on that page.
    return Synset.objects.select_related(
        "pos",
        "wordnet__language",
        "copied_from__pos",
        "copied_from__wordnet__language",
    )


def _synset_context(pk=None, synset=None):
    if synset is None and pk is None:
        raise ValueError("Either pk or synset must be provided")
    if synset is None:
        synset = get_object_or_404(_synsets_for_detail_page(), pk=pk)
    if not pk:
        pk = synset.pk

    concerns = []

    for concern in Synset.objects.concerns():
        if concern["qs"].filter(pk=pk).exists():
            concerns.append(concern)

    for concern in Word.objects.concerns():
        if concern["qs"].filter(sense__synset=synset).exists():
            concerns.append(concern)

    senses = _senses(synset)

    context = {
        "synset": synset,
        "senses": senses,
        "relations": _build_relations(pk),
        "definition_form": DefinitionForm(initial={"definition": synset.definition}),
        "concerns": concerns,
    }
    return context


def _source_synset_context(synset):
    """Context for the source synset card: the linked source, or else a guess."""
    # Synsets in the source wordnet have no source, so the page leaves the card out
    if synset.wordnet_id == settings.SOURCE_WORDNET_ID:
        return {"synset": synset, "in_source_wordnet": True}

    if synset.copied_from_id:
        source_synset = synset.copied_from
    else:
        source_synset = _guess_source_synset(synset)

    source_synset_senses = []
    source_relations = None
    if source_synset:
        source_synset_senses = _senses(source_synset)
        source_relations = _build_relations(source_synset.pk)

    return {
        "synset": synset,
        "in_source_wordnet": False,
        "source_synset": source_synset,
        "source_synset_senses": source_synset_senses,
        "source_relations": source_relations,
    }


def synset_detail(request, pk):
    context = _synset_context(pk)
    context.update(_source_synset_context(context["synset"]))
    return render(
        request,
        "editor/synset_detail.html",
        context,
    )


@require_POST
def delete_synset(request, pk):
    synset = get_object_or_404(Synset, pk=pk)
    synset.delete()
    url = f"{reverse('editor:browse_synsets')}?wordnet={synset.wordnet_id}"
    return redirect(url)


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
                [synset],
                _examples_prefetch("sense_set__senseexample_set"),
                "sense_set__word",
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
    # An invalid form re-renders the whole detail page
    synset = get_object_or_404(_synsets_for_detail_page(), pk=pk)

    if request.method == "POST":
        form = DefinitionForm(request.POST)
        if form.is_valid():
            synset.definition = form.cleaned_data["definition"]
            updated_fields = ["definition"]
            _save_updated_synset(synset, updated_fields)

            return redirect("editor:synset_detail", pk=pk)
        else:
            context = _synset_context(synset=synset)
            context.update(_source_synset_context(synset))
            context["definition_form"] = form
            return render(request, "editor/synset_detail.html", context)

    return HttpResponseNotAllowed(["POST"])


@require_GET
def search_words_htmx(request, pk):
    if not (q := request.GET.get("q")):
        return HttpResponse("", content_type="text/html")

    synset = get_object_or_404(Synset.objects.select_related("wordnet"), pk=pk)
    words = (
        Word.objects.filter(
            language=synset.wordnet.language_id,
            pos=synset.pos_id,
            text__unaccent__icontains=q,
        )
        .exclude(sense__synset=synset)
        .order_by(Length("text"), "text")
    )

    context = {
        "q": q.strip(),
        "synset": synset,
        "words": words[:6],
    }
    return render(
        request,
        "editor/snippets/_word_results.html",
        context,
    )


@require_POST
def add_sense_htmx(request, pk):
    synset = get_object_or_404(Synset.objects.select_related("wordnet"), pk=pk)

    word_pk = request.POST.get("word_pk")
    word = get_object_or_404(Word, pk=word_pk)

    context = {
        "synset": synset,
        "senses": _senses(synset),
    }

    if word.language_id != synset.wordnet.language_id:
        context["error"] = _("The word and synset belong to different languages.")
        return render(request, "editor/snippets/_sense_list.html", context)
    if word.pos_id != synset.pos_id:
        context["error"] = _("The word and synset have different parts-of-speech.")
        return render(request, "editor/snippets/_sense_list.html", context)
    _sense, created = Sense.objects.get_or_create(synset=synset, word=word)
    if not created:
        context["error"] = _(
            "The word '%(word)s' is already linked to this synset."
        ) % {"word": word.text}
        return render(request, "editor/snippets/_sense_list.html", context)
    _save_updated_synset(synset)
    return render(request, "editor/snippets/_sense_list.html", context=context)


@require_POST
def delete_sense_htmx(request, synset_pk, sense_pk):
    synset = get_object_or_404(Synset, pk=synset_pk)
    sense = get_object_or_404(Sense.objects.select_related("synset"), pk=sense_pk)

    context = {
        "synset": synset,
        "senses": _senses(synset),
    }

    if sense.synset_id != synset_pk:
        context["error"] = _(
            "Attempted to delete a sense not belonging to this synset."
        )
        return render(request, "editor/snippets/_sense_list.html", context)
    sense.delete()
    _save_updated_synset(synset)
    return render(request, "editor/snippets/_sense_list.html", context=context)


def _render_sense_item(request, synset, sense, failed_form=None, saved_pk=None):
    # A form that failed validation is attached to the sense, so the template can
    # re-open that one form with its errors (see the `example_form` filter). It isn't
    # a model field; it only exists on this instance, for this response.
    prefetch_related_objects([sense], _examples_prefetch())
    sense.failed_form = failed_form
    context = {
        "synset": synset,
        "sense": sense,
        # Briefly highlights the example just saved, which sorting may have moved
        "saved_pk": saved_pk,
    }
    return render(request, "editor/snippets/_sense_item.html", context)


@require_POST
def save_sense_example_htmx(request, synset_pk, example_pk=None):
    # Adds an example without example_pk, edits one with it. Filtering on the synset
    # rejects a sense or example from another synset (404), and select_related
    # brings the synset along, so it needs no query of its own.
    if example_pk is None:
        sense = get_object_or_404(
            Sense.objects.select_related("word", "synset"),
            pk=request.POST.get("sense_pk"),
            synset_id=synset_pk,
        )
        example = SenseExample(sense=sense)
    else:
        example = get_object_or_404(
            SenseExample.objects.select_related("sense__word", "sense__synset"),
            pk=example_pk,
            sense__synset_id=synset_pk,
        )
        sense = example.sense
    synset = sense.synset
    form = SenseExampleForm(request.POST, instance=example)
    if not form.is_valid():
        return _render_sense_item(request, synset, sense, failed_form=form)
    # A new example always counts as changed. For an edit, saving unchanged text
    # shouldn't cost a reviewed synset its status.
    if not form.has_changed():
        return _render_sense_item(request, synset, sense)
    form.save()
    _save_updated_synset(synset)
    return _render_sense_item(request, synset, sense, saved_pk=example.pk)


@require_POST
def delete_sense_example_htmx(request, synset_pk, example_pk):
    example = get_object_or_404(
        SenseExample.objects.select_related("sense__word", "sense__synset"),
        pk=example_pk,
        sense__synset_id=synset_pk,
    )
    sense = example.sense
    synset = sense.synset
    example.delete()
    _save_updated_synset(synset)
    return _render_sense_item(request, synset, sense)


@require_GET
def add_relation_form_htmx(request, pk):
    synset = get_object_or_404(Synset, pk=pk)

    if r_type := request.GET.get("type"):
        template = "editor/snippets/_add_relation.html"
        rel_type = get_object_or_404(RelationType, pk=r_type)
    else:
        template = "editor/snippets/_add_relation_new.html"

    context = {
        "synset": synset,
        "type_id": rel_type.id if r_type else None,
        "direction": request.GET.get("direction"),
        "types": RelationType.objects.all().order_by("name"),
    }
    return render(
        request,
        template,
        context,
    )


def search_synsets_htmx(request, pk):
    if not (q := request.GET.get("q")):
        return HttpResponse("", content_type="text/html")

    wordnet = get_object_or_404(Wordnet, pk=pk)
    synsets = Synset.objects.filter(wordnet_id=wordnet.id).only(
        "display_name", "definition"
    )
    synsets = make_search_qs(synsets, q)
    context = {
        "q": q.strip(),
        "synsets": synsets[:6],
    }
    return render(
        request,
        "editor/snippets/_synset_results.html",
        context,
    )


@require_POST
def add_relation_htmx(request, pk):
    synset = get_object_or_404(Synset, pk=pk)

    type_id = request.POST.get("type")
    direction = request.POST.get("direction")
    target_synset_pk = request.POST.get("target_pk")
    target_synset = get_object_or_404(Synset, pk=target_synset_pk)

    if direction == "outgoing":
        synset_from = synset
        synset_to = target_synset
    elif direction == "incoming":
        synset_from = target_synset
        synset_to = synset
    else:
        context = _synset_context(synset=synset)
        context["error"] = _("Invalid relation direction")
        return render(request, "editor/snippets/_relations.html", context)

    if target_synset.wordnet_id != synset.wordnet_id:
        context = _synset_context(synset=synset)
        context["error"] = _("Synsets belong to different wordnets")
        return render(request, "editor/snippets/_relations.html", context)
    if target_synset.pk == synset.pk:
        context = _synset_context(synset=synset)
        context["error"] = _("A synset cannot be related to itself")
        return render(request, "editor/snippets/_relations.html", context)

    rel_type = get_object_or_404(RelationType, id=type_id)
    if Relation.objects.filter(
        synset_from=synset_to, synset_to=synset_from, type=rel_type
    ).exists():
        context = _synset_context(synset=synset)
        context["error"] = _("This relation already exists in the opposite direction")
        return render(request, "editor/snippets/_relations.html", context)
    elif Relation.objects.filter(
        synset_from=synset_from, synset_to=synset_to, type=rel_type
    ).exists():
        context = _synset_context(synset=synset)
        context["error"] = _("This relation already exists")
        return render(request, "editor/snippets/_relations.html", context)
    Relation.objects.create(synset_from=synset_from, synset_to=synset_to, type=rel_type)
    if synset.status != Synset.Status.DRAFT:
        synset.status = Synset.Status.DRAFT
        synset.save(update_fields=["status"])
    return render(
        request,
        "editor/snippets/_relations.html",
        context=_synset_context(synset=synset),
    )


@require_POST
def delete_relation_htmx(request, synset_pk, rel_pk):
    synset = get_object_or_404(Synset, pk=synset_pk)
    context = {}
    try:
        relation = Relation.objects.get(pk=rel_pk)
        if synset_pk not in (relation.synset_from_id, relation.synset_to_id):
            context["error"] = _(
                "Attempted to delete a relation not belonging to this synset."
            )
        else:
            relation.delete()
            _save_updated_synset(synset)
    except Relation.DoesNotExist:
        # We wanted it gone, so let's not complain. Could be a race condition between
        # different users/windows, or a retry due to an unreceived response.
        pass
    context.update(_synset_context(synset=synset))
    return render(
        request,
        "editor/snippets/_relations.html",
        context=context,
    )


@require_GET
def link_synset_form_htmx(request, pk):
    synset = get_object_or_404(Synset, pk=pk)
    context = {"source_wordnet": settings.SOURCE_WORDNET_ID, "synset": synset}
    return render(request, "editor/snippets/_link_synset.html", context)


@require_POST
def link_synset_htmx(request, pk):
    # Linking doesn't change the status: the link isn't part of the synset's content.
    # The card's POS warning names both synsets' languages and parts of speech.
    synset = get_object_or_404(
        Synset.objects.select_related("pos", "wordnet__language"), pk=pk
    )
    # Only a synset in the source wordnet can be linked, and never the synset
    # itself. Anything else is a 404, as if the target didn't exist.
    target_synset = get_object_or_404(
        Synset.objects.select_related("pos", "wordnet__language")
        .filter(wordnet_id=settings.SOURCE_WORDNET_ID)
        .exclude(pk=synset.pk),
        pk=request.POST.get("target_pk"),
    )
    # Linking the synset that's already linked saves nothing. Assigning it anyway
    # gives the card the target's wordnet, language and POS without another query.
    changed = synset.copied_from_id != target_synset.pk
    synset.copied_from = target_synset
    if changed:
        synset.save(update_fields=["copied_from"])
    return render(
        request,
        "editor/snippets/_source_synset.html",
        _source_synset_context(synset),
    )


@require_GET
def clear_htmx(request):
    return HttpResponse("", content_type="text/html")
