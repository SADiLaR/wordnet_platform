from django.contrib import admin
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.shortcuts import render
from django.urls import reverse

from lex.models import Sense, Synset, Word, Wordnet

CONCERN_MODELS = {
    "word": Word,
    "synset": Synset,
}


def _get_concern(model, concern_key):
    for concern in model.objects.concerns():
        if concern["key"] == concern_key:
            return concern


def _build_admin_url(instance):
    return reverse(
        f"admin:{instance._meta.app_label}_{instance._meta.model_name}_change",
        args=[instance.pk],
    )


def _filter_concern_by_wordnet(queryset, model_name, wordnet_pk):
    if model_name == "synset":
        return queryset.filter(wordnet_id=wordnet_pk).order_by("display_name", "pk")

    if model_name == "word":
        senses_in_wordnet = Sense.objects.filter(
            word_id=OuterRef("pk"),
            synset__wordnet_id=wordnet_pk,
        )

        return (
            queryset.annotate(in_wordnet=Exists(senses_in_wordnet))
            .filter(in_wordnet=True)
            .order_by("text", "pk")
        )


def concerns_report(request):
    selected_wordnet = request.GET.get("wordnet")
    wordnets = list(Wordnet.objects.all().order_by("name"))
    selected_concern = request.GET.get("concern")

    concerns = []

    for model_name, model in [
        ("word", Word),
        ("synset", Synset),
    ]:
        for concern in model.objects.concerns():
            if selected_concern and concern["key"] != selected_concern:
                continue

            queryset = concern["qs"]

            if selected_wordnet:
                queryset = _filter_concern_by_wordnet(
                    queryset,
                    model_name,
                    selected_wordnet,
                )

            concerns.append(
                {
                    "key": concern["key"],
                    "name": concern["name"],
                    "description": concern["description"],
                    "model_name": model_name,
                    "count": queryset.count(),
                }
            )

    return render(
        request,
        "admin/concerns/summary.html",
        {
            **admin.site.each_context(request),
            "concerns": concerns,
            "wordnets": wordnets,
            "selected_wordnet": selected_wordnet,
            "selected_concern": selected_concern,
        },
    )


def concerns_detail(request, model_name, concern_key):
    model = CONCERN_MODELS[model_name]
    concern = _get_concern(model, concern_key)
    wordnets = Wordnet.objects.all().order_by("name")
    wordnet = request.GET.get("wordnet")

    queryset = concern["qs"]

    if wordnet:
        queryset = _filter_concern_by_wordnet(queryset, model_name, wordnet)

    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_range = paginator.get_elided_page_range(page_obj.number)

    items = [
        {
            "obj": obj,
            "admin_url": _build_admin_url(obj),
        }
        for obj in page_obj.object_list
    ]

    return render(
        request,
        "admin/concerns/detail.html",
        {
            **admin.site.each_context(request),
            "concern": concern,
            "items": items,
            "page_obj": page_obj,
            "selected_wordnet": wordnet,
            "wordnets": wordnets,
            "page_range": page_range,
        },
    )
