import unicodedata
from collections import defaultdict

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Prefetch, Q, prefetch_related_objects
from django.db.models.functions import Length
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from lex.models import (
    Relation,
    RelationType,
    Sense,
    SenseExample,
    Synset,
    SynsetExample,
    Word,
    Wordnet,
)

from .filters import SynsetFilter, make_search_qs
from .forms import DefinitionForm, SenseExampleForm


def about(request):
    return render(request, "editor/about.html")


def front_page(request):
    return render(request, "editor/front_page.html")


def _guess_source_synset(synset):
    # Only an exact match
    if synset.princeton_id:
        source_synset = (
            Synset.objects.select_related("pos", "wordnet__language")
            .filter(
                princeton_id=synset.princeton_id,
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


def _render_with_summary(request, template, context, senses=None):
    """render(), plus the synset's heading, title and status as out-of-band swaps.

    After `template`, the response has the synset's heading, tab title and status, so
    that those parts of the page stay up to date. HTMX replaces the matching elements
    wherever they are on the page. Views that change a synset's content respond with
    this.

    The heading lists the synset's words. A view that has just rendered the senses
    passes them in, which saves querying them again.
    """
    response = render(request, template, context)
    synset = context["synset"]
    if senses is None:
        senses = synset.sense_set.select_related("word").order_by("word__text")
    summary_context = {"synset": synset, "senses": senses}
    response.write(
        render_to_string(
            "editor/snippets/_synset_summary_oob.html", summary_context, request
        )
    )
    return response


def _examples_prefetch(lookup="senseexample_set"):
    # Examples with empty text are left over from the old tool; treat them as missing.
    # Alphabetical, by the database's collation; pk only breaks ties between duplicates.
    return Prefetch(
        lookup,
        queryset=SenseExample.objects.exclude(text="").order_by("text", "pk"),
    )


def _senses(synset):
    return (
        synset.sense_set.select_related("word__pos")
        .prefetch_related(_examples_prefetch())
        .order_by("word__text")
    )


WORD_TEXT_MAX_LENGTH = Word._meta.get_field("text").max_length


def _word_too_long_error():
    """The error for word text over the length limit; the search and add views share it."""
    return _("A word can’t be longer than %(max)d characters.") % {
        "max": WORD_TEXT_MAX_LENGTH
    }


def _normalise_word_text(text):
    """Compose characters (NFC) and tidy whitespace, changing nothing else.

    NFC makes, e.g., an e followed by a combining acute accent into one é, so the same
    word typed in different ways is stored and matched the same way. Whitespace: the
    ends are stripped and inner runs become one space.
    """
    return " ".join(unicodedata.normalize("NFC", text).split())


def _find_or_create_word(text, synset):
    """Return (word, None) for the text in the synset's language and POS, or (None, error)."""
    text = _normalise_word_text(text)
    if not text:
        return None, _("A word can’t be empty.")
    if len(text) > WORD_TEXT_MAX_LENGTH:
        return None, _word_too_long_error()
    # With get_or_create, someone creating the same word at the same moment just means
    # that this request links to their word.
    word, _created = Word.objects.get_or_create(
        text=text, language_id=synset.wordnet.language_id, pos_id=synset.pos_id
    )
    return word, None


def _word_mismatch_error(word, synset):
    """Return why this existing word can't be linked to the synset, or None if it can."""
    if word.language_id != synset.wordnet.language_id:
        return _("The word and synset belong to different languages.")
    if word.pos_id != synset.pos_id:
        return _("The word and synset have different parts-of-speech.")
    return None


def _synset_examples(synset):
    # No new synset examples are added. Princeton's are kept for historical reasons;
    # the other languages' are to be converted into sense examples, each linked to the
    # right word. Those with empty text are left over from the old tool, so they're
    # left out.
    return synset.synsetexample_set.exclude(text="").order_by("text", "pk")


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
    all_relations = (
        Relation.objects.filter(Q(synset_from=pk) | Q(synset_to=pk))
        .select_related("type", "synset_to", "synset_from")
        .order_by("synset_to__display_name", "synset_from__display_name")
    )
    relations = {"outgoing": defaultdict(list), "incoming": defaultdict(list)}

    for rel in all_relations:
        type_pk = rel.type_id
        if pk == rel.synset_from_id:
            direction = "outgoing"
        else:
            direction = "incoming"
        if type_pk not in relations[direction]:
            relations[direction][type_pk] = {"relations": [], "type": rel.type}
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


def _synset_context(pk=None, synset=None, **kwargs):
    if synset is None and pk is None:
        raise ValueError("Either pk or synset must be provided")
    if synset is None:
        synset = get_object_or_404(_synsets_for_detail_page(), pk=pk)
    if not pk:
        pk = synset.pk

    # Synsets in the source wordnet can't be edited here. With nothing to fix, they
    # get no QA warnings either, which saves their queries.
    readonly = synset.wordnet_id == settings.SOURCE_WORDNET_ID
    concerns = []
    if not readonly:
        for model in (Synset, Word, Relation):
            for concern in model.objects.concerns():
                if concern["synsets"].filter(pk=pk).exists():
                    concerns.append(concern)

    senses = _senses(synset)

    context = {
        "synset": synset,
        "senses": senses,
        "synset_examples": _synset_examples(synset),
        "relations": _build_relations(pk),
        "definition_form": DefinitionForm(initial={"definition": synset.definition}),
        "concerns": concerns,
        "readonly": readonly,
        **kwargs,
    }
    return context


def _copied_synsets(source_synset):
    """The synsets in other wordnets that were copied from a source synset."""
    # A copy is linked to its source, or, if it was migrated and never linked, has the
    # same Princeton ID: the synsets whose source card suggests this synset as the
    # source. A synset linked to another source isn't one, even with the same
    # Princeton ID.
    is_copy = Q(copied_from=source_synset)
    if source_synset.princeton_id:
        is_copy |= Q(copied_from=None, princeton_id=source_synset.princeton_id)
    return (
        Synset.objects.filter(is_copy)
        .exclude(wordnet_id=settings.SOURCE_WORDNET_ID)
        .select_related("wordnet")
        .order_by("wordnet__name", "display_name", "pk")
    )


def _source_synset_context(synset):
    """Context for the source synset card: the linked source, or else a guess."""
    # Synsets in the source wordnet have no source, so the page shows their copies
    # instead of the source card
    if synset.wordnet_id == settings.SOURCE_WORDNET_ID:
        copied_synsets = list(_copied_synsets(synset))
        # A stub can be created in any other wordnet that doesn't have a copy yet
        stub_wordnets = (
            Wordnet.objects.exclude(pk=settings.SOURCE_WORDNET_ID)
            .exclude(pk__in={copy.wordnet_id for copy in copied_synsets})
            .order_by("name", "pk")
        )
        return {
            "synset": synset,
            "in_source_wordnet": True,
            "copied_synsets": copied_synsets,
            "stub_wordnets": list(stub_wordnets),
        }

    if synset.copied_from_id:
        source_synset = synset.copied_from
    else:
        source_synset = _guess_source_synset(synset)

    source_synset_senses = []
    source_synset_examples = []
    source_relations = None
    if source_synset:
        source_synset_senses = _senses(source_synset)
        source_synset_examples = _synset_examples(source_synset)
        source_relations = _build_relations(source_synset.pk)

    return {
        "synset": synset,
        "in_source_wordnet": False,
        "source_synset": source_synset,
        "source_synset_senses": source_synset_senses,
        "source_synset_examples": source_synset_examples,
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
def create_stub(request, pk):
    """Create a stub in another wordnet, copied from a source synset, and open it."""
    # Only a synset in the source wordnet can be copied, and only into another
    # wordnet. Anything else is a 404.
    source_synset = get_object_or_404(
        Synset, pk=pk, wordnet_id=settings.SOURCE_WORDNET_ID
    )
    wordnet = get_object_or_404(
        Wordnet.objects.exclude(pk=settings.SOURCE_WORDNET_ID),
        pk=request.POST.get("wordnet_pk"),
    )
    # The page leaves out wordnets that have a copy, but one may have been made since
    # it was loaded (another person, another window). Open that one instead.
    stub = _copied_synsets(source_synset).filter(wordnet=wordnet).first()
    if stub is None:
        # The definition stays empty: the linguist writes their own
        stub = Synset.objects.create(
            wordnet=wordnet,
            pos_id=source_synset.pos_id,
            princeton_id=source_synset.princeton_id,
            copied_from=source_synset,
            status=Synset.Status.STUB,
        )
    return redirect(stub)


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
    if not (q := _normalise_word_text(request.GET.get("q", ""))):
        return HttpResponse("", content_type="text/html")

    synset = get_object_or_404(Synset.objects.select_related("wordnet", "pos"), pk=pk)
    same_language_and_pos = Word.objects.filter(
        language=synset.wordnet.language_id, pos=synset.pos_id
    )
    words = (
        same_language_and_pos.filter(text__unaccent__icontains=q)
        .exclude(sense__synset=synset)
        .order_by(Length("text"), "text")
    )
    # A separate query, as `words` leaves out this synset's words and gets cut off.
    # Case and accents count: isiZulu's iSonto and isonto can be different words, and
    # Tshivenda's ṱ and t are different letters. Such a near match is listed in
    # `words`, right above the option to create the new word.
    exact_match = (
        same_language_and_pos.filter(text=q)
        .annotate(
            in_synset=Exists(Sense.objects.filter(synset=synset, word=OuterRef("pk")))
        )
        .first()
    )

    too_long = len(q) > WORD_TEXT_MAX_LENGTH

    context = {
        "q": q,
        "synset": synset,
        "words": words[:6],
        "already_linked": exact_match is not None and exact_match.in_synset,
        "can_create": exact_match is None and not too_long,
        "error": _word_too_long_error() if too_long else None,
    }
    return render(
        request,
        "editor/snippets/_word_results.html",
        context,
    )


@require_POST
def delete_synset_example_htmx(request, synset_pk, pk):
    synset = get_object_or_404(Synset, pk=synset_pk)
    context = {}
    try:
        synsetexample = SynsetExample.objects.get(pk=pk)
        if synset_pk != synsetexample.synset_id:
            context["error"] = _(
                "Attempted to delete a synset example not belonging to this synset."
            )
        else:
            synsetexample.delete()
    except SynsetExample.DoesNotExist:
        # We wanted it gone, so let's not complain. Could be a race condition between
        # different users/windows, or a retry due to an unreceived response.
        pass

    contex = {"synset": synset, "synset_examples": _synset_examples(synset)}
    return render(
        request,
        "editor/snippets/_synsetexample.html",
        contex,
    )


@require_POST
def add_sense_htmx(request, pk):
    """Link a word to the synset: an existing one, or a new one created from its text."""
    synset = get_object_or_404(Synset.objects.select_related("wordnet"), pk=pk)

    if "word_text" in request.POST:
        word, error = _find_or_create_word(request.POST["word_text"], synset)
    else:
        word = get_object_or_404(
            Word.objects.select_related("pos"), pk=request.POST.get("word_pk")
        )
        error = _word_mismatch_error(word, synset)

    already_linked_word = None
    sense = None
    if not error:
        sense, created = Sense.objects.get_or_create(synset=synset, word=word)
        if created:
            _save_updated_synset(synset)
        else:
            # The template words the message, so it can show the word in bold
            already_linked_word = word

    senses = _senses(synset)
    context = {
        "synset": synset,
        "senses": senses,
        "saved_pk": sense.pk if sense else None,
        "already_linked_word": already_linked_word,
    }
    if error:
        context["error"] = error
    return _render_with_summary(
        request, "editor/snippets/_sense_list.html", context, senses=senses
    )


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
        return _render_with_summary(
            request,
            "editor/snippets/_sense_list.html",
            context,
            senses=context["senses"],
        )
    sense.delete()
    _save_updated_synset(synset)
    return _render_with_summary(
        request, "editor/snippets/_sense_list.html", context, senses=context["senses"]
    )


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
    return _render_with_summary(request, "editor/snippets/_sense_item.html", context)


@require_POST
def save_sense_example_htmx(request, synset_pk, example_pk=None):
    # Adds an example without example_pk, edits one with it. Filtering on the synset
    # rejects a sense or example from another synset (404), and select_related
    # brings the synset along, so it needs no query of its own.
    if example_pk is None:
        sense = get_object_or_404(
            Sense.objects.select_related("word__pos", "synset"),
            pk=request.POST.get("sense_pk"),
            synset_id=synset_pk,
        )
        example = SenseExample(sense=sense)
    else:
        example = get_object_or_404(
            SenseExample.objects.select_related("sense__word__pos", "sense__synset"),
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
        SenseExample.objects.select_related("sense__word__pos", "sense__synset"),
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
        rel_type = get_object_or_404(RelationType.objects.active(), pk=r_type)
    else:
        template = "editor/snippets/_add_relation_new.html"

    context = {
        "synset": synset,
        "type_id": rel_type.id if r_type else None,
        "direction": request.GET.get("direction"),
        "types": RelationType.objects.active().order_by("name"),
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
        return _render_with_summary(request, "editor/snippets/_relations.html", context)

    if target_synset.wordnet_id != synset.wordnet_id:
        context = _synset_context(synset=synset)
        context["error"] = _("Synsets belong to different wordnets")
        return _render_with_summary(request, "editor/snippets/_relations.html", context)
    if target_synset.pk == synset.pk:
        context = _synset_context(synset=synset)
        context["error"] = _("A synset cannot be related to itself")
        return _render_with_summary(request, "editor/snippets/_relations.html", context)

    rel_type = get_object_or_404(RelationType.objects.active(), id=type_id)
    if Relation.objects.filter(
        synset_from=synset_to, synset_to=synset_from, type=rel_type
    ).exists():
        context = _synset_context(synset=synset)
        context["error"] = _("This relation already exists in the opposite direction")
        return _render_with_summary(request, "editor/snippets/_relations.html", context)
    elif Relation.objects.filter(
        synset_from=synset_from, synset_to=synset_to, type=rel_type
    ).exists():
        context = _synset_context(synset=synset)
        context["error"] = _("This relation already exists")
        return _render_with_summary(request, "editor/snippets/_relations.html", context)
    rel = Relation.objects.create(
        synset_from=synset_from, synset_to=synset_to, type=rel_type
    )
    if synset.status != Synset.Status.DRAFT:
        synset.status = Synset.Status.DRAFT
        synset.save(update_fields=["status"])
    return _render_with_summary(
        request,
        "editor/snippets/_relations.html",
        context=_synset_context(synset=synset, saved_pk=rel.pk),
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
    return _render_with_summary(
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
    # Links the source synset given by `target_pk`, or unlinks it if that's empty.
    # Neither changes the status: the link isn't part of the synset's content.
    # The card's POS warning names both synsets' languages and parts of speech.
    synset = get_object_or_404(
        Synset.objects.select_related("pos", "wordnet__language"), pk=pk
    )
    target_synset = None
    if target_pk := request.POST.get("target_pk"):
        # Only a synset in the source wordnet can be linked, and never the synset
        # itself. Anything else is a 404, as if the target didn't exist.
        target_synset = get_object_or_404(
            Synset.objects.select_related("pos", "wordnet__language")
            .filter(wordnet_id=settings.SOURCE_WORDNET_ID)
            .exclude(pk=synset.pk),
            pk=target_pk,
        )
    # Linking the synset that's already linked, or unlinking when nothing is linked,
    # saves nothing. Assigning it anyway gives the card the target's wordnet, language
    # and POS without another query.
    changed = synset.copied_from_id != (target_synset.pk if target_synset else None)
    synset.copied_from = target_synset
    if changed:
        synset.save(update_fields=["copied_from"])
    context = _source_synset_context(synset)
    # Briefly highlights the card, so the user sees the result of their click
    context["just_saved"] = True
    return render(request, "editor/snippets/_source_synset.html", context)


@require_GET
def clear_htmx(request):
    return HttpResponse("", content_type="text/html")
