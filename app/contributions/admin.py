from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import reverse
from django.urls import path

from contributions.models import ContributionsHistory
from contributions.views import contribution_history, synset_contribution_history


class ContributionsAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse("admin:contributions_view"))

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "contributions/",
                self.admin_site.admin_view(self.contributions_view),
                name="contributions_view",
            ),
            path(
                "synset-contributions/<int:synset_id>/",
                self.admin_site.admin_view(self.synset_contributions_view),
                name="synset_contributions_view",
            ),
        ]
        return custom_urls + urls

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request):
        return False

    def contributions_view(self, request):
        extra_context = self.admin_site.each_context(request)
        return contribution_history(request, self.list_per_page, extra_context)

    def synset_contributions_view(self, request, synset_id):
        extra_context = self.admin_site.each_context(request)
        return synset_contribution_history(request, synset_id, extra_context)


admin.site.register(ContributionsHistory, ContributionsAdmin)
