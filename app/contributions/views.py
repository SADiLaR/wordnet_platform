from types import SimpleNamespace

from dateutil.relativedelta import relativedelta
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render, reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _

from contributions.forms import ContributionsForm
from contributions.models import ContributionsHistory
from lex.models import HistoricalSynset, Synset, Wordnet

FALLBACK_PAGE_SIZE = 25


def default_date_filters():
    time_now = timezone.now()
    time_one_month_ago = time_now - relativedelta(months=1)

    today = time_now.date()
    one_month_ago = time_one_month_ago.date()

    return {"start_date": one_month_ago, "end_date": today}


def build_filter_choices(objects, param_key, active_pk, base_params):
    object_choices = [
        {
            "selected": None,
            "query_string": "?" + urlencode(base_params),
            "display": _("All"),
        }
    ]
    for obj in objects:
        object_choices.append(
            {
                "selected": str(obj.pk) == active_pk,
                "query_string": "?" + urlencode({**base_params, param_key: obj.pk}),
                "display": str(obj),
            }
        )
    return object_choices


def build_pagination(request, queryset, page_size=FALLBACK_PAGE_SIZE):
    # pagination
    paginator = Paginator(queryset, page_size)
    page_num = int(request.GET.get("p", 1))
    page = paginator.get_page(page_num)

    def get_query_string(new_params=None, remove=None):
        params = {k: v for k, v in request.GET.items()}
        if new_params:
            params.update(new_params)
        if remove:
            for r in remove:
                params.pop(r, None)
        if new_params and "p" in new_params and new_params["p"] == 1:
            params.pop("p", None)
        return "?" + urlencode(params)

    fake_cl_attrs = {
        "formset": None,
        "can_show_all": False,
        "paginator": paginator,
        "page_num": page_num,
        "result_count": paginator.count,
        "multi_page": paginator.num_pages > 1,
        "get_query_string": get_query_string,
    }
    return (page, fake_cl_attrs)


def contribution_history(request, page_size=FALLBACK_PAGE_SIZE, extra_context=None):
    """
    We display a form that lists all synsets that have been affected by an edit.
    This includes changes to synset fields, but also changes in inline forms.

    This can be filtered by user and time frame (default: last month).

    Each table entry is clickable, which directs to a page with more details
    about the changes on that synset.
    """
    form = ContributionsForm(request.GET)
    skip_pagination = "all" in request.GET
    context = {
        "form": form,
        **(extra_context or {}),
    }
    request.current_app = admin.site.name

    if form.is_valid():
        # Prepare queryset of records for synset edits.
        # This works because a save on the Synset admin form triggers
        # the creation of a HistoricalSynset record, irrespective of
        # whether the change was to the synset itself or to an object
        # in one of the inline forms.
        synset_edits = HistoricalSynset.objects.values_list("id", flat=True)

        # prepare filters
        filters = {}
        if user_pk := request.GET.get("user"):
            filters["history_user_id"] = user_pk
        if wordnet_pk := request.GET.get("wordnet"):
            filters["wordnet_id"] = wordnet_pk
        default_dates = default_date_filters()
        start_date = form.cleaned_data["start_date"] or default_dates["start_date"]
        end_date = form.cleaned_data["end_date"] or default_dates["end_date"]
        filters.update(
            {
                "history_date__date__gte": start_date,
                "history_date__date__lte": end_date,
            }
        )

        # filter queryset and obtain edited synsets
        synset_edits = synset_edits.filter(**filters)
        edited_synsets = Synset.objects.filter(id__in=synset_edits).select_related(
            "wordnet"
        )

        params = {"start_date": start_date, "end_date": end_date}
        form = ContributionsForm(
            data={
                **request.GET,
                **params,
            }
        )
        form.is_valid()

        users = User.objects.all()
        if wordnet_pk:
            params["wordnet"] = wordnet_pk
        user_choices = build_filter_choices(users, "user", user_pk, params)

        wordnets = Wordnet.objects.all()
        if user_pk:
            params["user"] = user_pk
        wordnet_choices = build_filter_choices(wordnets, "wordnet", wordnet_pk, params)

        page, fake_cl_attrs = build_pagination(request, edited_synsets, page_size)
        fake_cl = SimpleNamespace(show_all=skip_pagination, **fake_cl_attrs)
        synsets_to_show = edited_synsets if skip_pagination else page.object_list

        context.update(
            {
                "form": form,
                "edited_synsets": synsets_to_show,
                "user_choices": user_choices,
                "wordnet_choices": wordnet_choices,
                "title": _("Contributions History"),
                "opts": ContributionsHistory._meta,
                "has_filters": True,
            }
        )
    else:
        # SimpleNamespace required: Django's {% pagination %} tag uses attribute access on cl;
        # Omitting cl from context causes an AttributeError
        fake_cl = SimpleNamespace(
            formset=None,
            show_all=skip_pagination,
            can_show_all=False,
        )
    context["cl"] = fake_cl

    return render(
        request,
        "contributions/contribution_history.html",
        context,
    )


def synset_contribution_history(request, synset_id, extra_context=None):

    synset = get_object_or_404(Synset, pk=synset_id)
    data = dict(
        user=request.GET.get("user"),
        wordnet=request.GET.get("wordnet"),
        start_date=request.GET.get("start_date"),
        end_date=request.GET.get("end_date"),
    )

    # prepare filters
    # We require that change_details be non-empty. Empty change_details
    # occur typically when a user saves the synset form, but changes
    # were only made in inline forms. In such a case, a historical
    # record is still created, because the synset itself is saved,
    # but nothing about the synset changed.
    filters = {"change_details__gt": ""}
    if user := data["user"]:
        filters["history_user_id"] = user
        user_obj = User.objects.get(pk=user)
    else:
        user_obj = None

    if start_date := data["start_date"]:
        filters["history_date__date__gte"] = start_date
    if end_date := data["end_date"]:
        filters["history_date__date__lte"] = end_date

    # get synset edits
    synset_edits = (
        HistoricalSynset.objects.filter(id=synset_id, **filters)
        .order_by("-history_date")
        .select_related("history_user")
    )

    # some ux
    source = request.GET.get("source")
    if source == "synset":
        back_url = reverse("admin:lex_synset_change", args=[synset_id])
        back_label = _("Back to synset")
    else:
        params = {k: v for k, v in data.items() if v}
        back_url = reverse("admin:contributions_view") + (
            "?" + urlencode(params) if params else ""
        )
        back_label = _("Back to contributions")

    return render(
        request,
        "contributions/synset_contribution_history.html",
        {
            "edits": synset_edits,
            "synset": synset,
            "user_obj": user_obj,
            "back_url": back_url,
            "back_label": back_label,
            **data,
            **(extra_context or {}),
        },
    )
