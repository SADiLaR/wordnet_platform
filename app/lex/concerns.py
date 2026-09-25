from django.contrib import admin
from django.core.paginator import Paginator
from django.db.models import Count, Exists, F, OuterRef, Subquery
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


def _concern_counts_per_wordnet(queryset, model_name):
    concern_ids = queryset.values("pk")

    if model_name == "synset":
        return (
            Synset.objects.filter(pk__in=Subquery(concern_ids))
            .values("wordnet_id")
            .annotate(count=Count("pk"))
        )

    return (
        Word.objects.filter(
            pk__in=Subquery(concern_ids),
            sense__synset__wordnet_id__isnull=False,
        )
        .annotate(wordnet_id=F("sense__synset__wordnet_id"))
        .values("wordnet_id")
        .annotate(count=Count("pk", distinct=True))
    )


def concerns_report(request):
    selected_wordnet = request.GET.get("wordnet")
    wordnets = list(Wordnet.objects.all().order_by("name"))

    wordnet_concerns = {
        wordnet.pk: {
            "wordnet": wordnet,
            "groups": [],
            "total_count": 0,
        }
        for wordnet in wordnets
    }

    for label, model_name, model in [
        ("Word concerns", "word", Word),
        ("Synset concerns", "synset", Synset),
    ]:
        # Create list of counts per concern per wordnet
        concerns_by_wordnet = {wordnet.pk: [] for wordnet in wordnets}

        for concern in model.objects.concerns():
            counts = _concern_counts_per_wordnet(
                concern["qs"],
                model_name,
            )

            for result in counts:
                wordnet_id = result["wordnet_id"]
                count = result["count"]
                concerns_by_wordnet[wordnet_id].append(
                    {
                        "name": concern["name"],
                        "key": concern["key"],
                        "count": result["count"],
                        "model_name": model_name,
                    }
                )

                wordnet_concerns[wordnet_id]["total_count"] += count

        for wordnet in wordnets:
            concerns = concerns_by_wordnet[wordnet.pk]
            if concerns:
                wordnet_concerns[wordnet.pk]["groups"].append(
                    {
                        "label": label,
                        "concerns": concerns,
                    }
                )
    wordnet_groups = list(wordnet_concerns.values())

    return render(
        request,
        "admin/concerns/summary.html",
        {
            **admin.site.each_context(request),
            "wordnet_groups": wordnet_groups,
            "selected_wordnet": selected_wordnet,
        },
    )


def concerns_detail(request, model_name, concern_key):
    model = CONCERN_MODELS[model_name]
    concern = _get_concern(model, concern_key)
    wordnet_pk = request.GET.get("wordnet")
    wordnet = Wordnet.objects.get(pk=wordnet_pk)

    queryset = _filter_concern_by_wordnet(
        concern["qs"],
        model_name,
        wordnet_pk,
    )

    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_range = paginator.get_elided_page_range(
        page_obj.number,
    )

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
            "wordnet": wordnet,
            "page_range": page_range,
        },
    )
