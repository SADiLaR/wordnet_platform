from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from lex.models import (
    Language,
    PartOfSpeech,
    Synset,
    Wordnet,
)


class ContributionHistoryViewTest(TestCase):
    def setUp(self):
        now = timezone.now()

        self.admin_user = User.objects.create_superuser(
            username="admin", password="password"
        )
        self.user_a = User.objects.create_user(username="user_a", password="password")
        self.user_b = User.objects.create_user(username="user_b", password="password")
        self.client.login(username="admin", password="password")

        language = Language.objects.create(iso_code="afr", name="Afrikaans")
        wordnet = Wordnet.objects.create(name="Toets Wordnet", language=language)
        pos = PartOfSpeech.objects.create(name="noun")

        self.synset_a = Synset.objects.create(
            definition="'n Toets synset",
            wordnet=wordnet,
            pos=pos,
        )
        self.synset_b = Synset.objects.create(
            definition="Nog 'n toets synset",
            wordnet=wordnet,
            pos=pos,
        )
        self.synset_c = Synset.objects.create(
            definition="'n Addisionele toets synset",
            wordnet=wordnet,
            pos=pos,
        )

        self.synset_a.history.all().delete()
        self.synset_b.history.all().delete()
        self.synset_c.history.all().delete()

        # change_details values are intentionally unique across all records
        # to allow set-based comparison in tests.
        self.all_records = [
            {
                "id": 0,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 60,
                "change_details": "Changed definition of synset: ouer definisie → ou definisie",
            },
            {
                "id": 1,
                "synset": self.synset_c,
                "user": self.user_a,
                "days_ago": 50,
                "change_details": "Changed definition of synset: 'n definisie → nog 'n definisie",
            },
            {
                "id": 2,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 31,
                "change_details": "Changed definition of synset: ou definisie → nuwe definisie",
            },
            {
                "id": 3,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 30,
                "change_details": "Added word: ketel",
            },
            {
                "id": 4,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 24,
                "change_details": "Changed text of word 'ketel': ketel → keteltjie",
            },
            {
                "id": 5,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 15,
                "change_details": "Added example: Die ketel kook.",
            },
            {
                "id": 6,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 13,
                "change_details": "Added relation: synset_a --hypernym-> synset_b",
            },
            {
                "id": 7,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 12,
                "change_details": "Deleted word: keteltjie",
            },
            {
                "id": 8,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 11,
                "change_details": "Changed text of example: Die ketel kook. → Die ketel het gekook.",
            },
            {
                "id": 9,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 9,
                "change_details": "Changed definition of synset: nuwe definisie → nuwer definisie",
            },
            {
                "id": 10,
                "synset": self.synset_a,
                "user": self.user_b,
                "days_ago": 9,
                "change_details": "Added word: waterkoker",
            },
            {
                "id": 11,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 7,
                "change_details": "Changed text of word 'waterkoker': waterkoker → waterkokertjie",
            },
            {
                "id": 12,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 5,
                "change_details": "Added example: Die waterkoker kook.",
            },
            {
                "id": 13,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 3,
                "change_details": "Added relation: synset_b --hypernym-> synset_c",
            },
            {
                "id": 14,
                "synset": self.synset_a,
                "user": self.user_b,
                "days_ago": 3,
                "change_details": "Deleted word: waterkokertjie",
            },
            {
                "id": 15,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 2,
                "change_details": "Changed text of example: Die waterkoker kook. → Die waterkoker het gekook.",
            },
            {
                "id": 16,
                "synset": self.synset_a,
                "user": self.user_a,
                "days_ago": 2,
                "change_details": "Deleted relation: synset_a --hypernym-> synset_b",
            },
        ]

        for r in self.all_records:
            r["synset"]._change_details = r["change_details"]
            r["synset"]._history_user = r["user"]
            r["synset"].save()
            record = r["synset"].history.order_by("history_id").last()
            record.history_date = now - timedelta(days=r["days_ago"])
            record.save()

    def _get_contributions_response(self, params):
        return self.client.get(reverse("admin:contributions_view"), params)

    def _get_synset_contributions_response(self, synset_id, params):
        return self.client.get(
            reverse("admin:synset_contributions_view", args=[synset_id]), params
        )

    # Essentially a copy of views.default_date_filters, but recreated here
    # to ensure the tests are independent.
    def _default_date_filters(self):
        time_now = timezone.now()
        time_one_month_ago = time_now - relativedelta(months=1)

        today = time_now.date()
        one_month_ago = time_one_month_ago.date()

        return one_month_ago, today

    def test_contributions_no_filter_input(self):
        one_month_ago, today = self._default_date_filters()
        one_month_ago_days = (today - one_month_ago).days

        reference_records = [
            r for r in self.all_records if r["days_ago"] <= one_month_ago_days
        ]
        reference_synsets = {r["synset"] for r in reference_records}

        response = self._get_contributions_response({})
        self.assertEqual(response.status_code, 200)
        edited_synsets = response.context["edited_synsets"]
        self.assertEqual(set(edited_synsets), reference_synsets)

    def test_contributions_only_user_filter(self):
        one_month_ago, today = self._default_date_filters()
        one_month_ago_days = (today - one_month_ago).days

        ref_records_a = [
            r
            for r in self.all_records
            if r["user"] == self.user_a and r["days_ago"] <= one_month_ago_days
        ]
        ref_records_b = [
            r
            for r in self.all_records
            if r["user"] == self.user_b and r["days_ago"] <= one_month_ago_days
        ]
        ref_synsets_a = {r["synset"] for r in ref_records_a}
        ref_synsets_b = {r["synset"] for r in ref_records_b}

        params_a = {"user": self.user_a.pk}
        params_b = {"user": self.user_b.pk}

        scenarios = [(ref_synsets_a, params_a), (ref_synsets_b, params_b)]
        for ref_synsets, params in scenarios:
            with self.subTest(params=params):
                response = self._get_contributions_response(params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(response.context["edited_synsets"]), ref_synsets)

    def test_contributions_only_date_filter(self):
        _, date_today = self._default_date_filters()
        date_10_days_ago = date_today - timedelta(days=10)
        date_30_days_ago = date_today - timedelta(days=30)
        date_31_days_ago = date_today - timedelta(days=31)
        date_50_days_ago = date_today - timedelta(days=50)

        params_1 = {"start_date": date_50_days_ago, "end_date": date_31_days_ago}
        params_2 = {"start_date": date_31_days_ago, "end_date": date_30_days_ago}
        params_3 = {"start_date": date_31_days_ago, "end_date": date_10_days_ago}
        params_4 = {"start_date": date_50_days_ago, "end_date": date_today}
        params_5 = {"start_date": date_10_days_ago, "end_date": date_today}

        ref_synsets_1 = {
            r["synset"]
            for r in self.all_records
            if r["days_ago"] <= 50 and r["days_ago"] >= 31
        }
        ref_synsets_2 = {
            r["synset"]
            for r in self.all_records
            if r["days_ago"] <= 31 and r["days_ago"] >= 30
        }
        ref_synsets_3 = {
            r["synset"]
            for r in self.all_records
            if r["days_ago"] <= 31 and r["days_ago"] >= 10
        }
        ref_synsets_4 = {r["synset"] for r in self.all_records if r["days_ago"] <= 50}
        ref_synsets_5 = {r["synset"] for r in self.all_records if r["days_ago"] <= 10}

        scenarios = [
            (ref_synsets_1, params_1),
            (ref_synsets_2, params_2),
            (ref_synsets_3, params_3),
            (ref_synsets_4, params_4),
            (ref_synsets_5, params_5),
        ]
        for ref_synsets, params in scenarios:
            with self.subTest(params=params):
                response = self._get_contributions_response(params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(response.context["edited_synsets"]), ref_synsets)

    def test_contributions_date_and_user_filter(self):
        _, date_today = self._default_date_filters()
        date_10_days_ago = date_today - timedelta(days=10)
        date_50_days_ago = date_today - timedelta(days=50)

        params_1 = {
            "user": self.user_a.pk,
            "start_date": date_50_days_ago,
            "end_date": date_10_days_ago,
        }
        params_2 = {
            "user": self.user_b.pk,
            "start_date": date_50_days_ago,
            "end_date": date_10_days_ago,
        }
        params_3 = {
            "user": self.user_a.pk,
            "start_date": date_10_days_ago,
            "end_date": date_today,
        }
        params_4 = {
            "user": self.user_b.pk,
            "start_date": date_10_days_ago,
            "end_date": date_today,
        }

        ref_synsets_1 = {
            r["synset"]
            for r in self.all_records
            if r["user"] == self.user_a and r["days_ago"] <= 50 and r["days_ago"] >= 10
        }
        ref_synsets_2 = {
            r["synset"]
            for r in self.all_records
            if r["user"] == self.user_b and r["days_ago"] <= 50 and r["days_ago"] >= 10
        }
        ref_synsets_3 = {
            r["synset"]
            for r in self.all_records
            if r["user"] == self.user_a and r["days_ago"] <= 10
        }
        ref_synsets_4 = {
            r["synset"]
            for r in self.all_records
            if r["user"] == self.user_b and r["days_ago"] <= 10
        }

        scenarios = [
            (ref_synsets_1, params_1),
            (ref_synsets_2, params_2),
            (ref_synsets_3, params_3),
            (ref_synsets_4, params_4),
        ]
        for ref_synsets, params in scenarios:
            with self.subTest(params=params):
                response = self._get_contributions_response(params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(response.context["edited_synsets"]), ref_synsets)

    # This tests the view with no date filter, but in practice, the view is
    # always called with a date filter from contributions_view
    def test_synset_contributions_no_filter(self):
        scenarios = [self.synset_a, self.synset_b, self.synset_c]

        for ref_synset in scenarios:
            ref_records = {
                r["change_details"]
                for r in self.all_records
                if r["synset"] == ref_synset
            }
            params = {}
            with self.subTest(params=params):
                response = self._get_synset_contributions_response(
                    ref_synset.pk, params
                )
                self.assertEqual(response.status_code, 200)
                edit_change_details = {
                    e.change_details for e in response.context["edits"]
                }
                self.assertEqual(edit_change_details, ref_records)

    # This tests the view with no date filter, but in practice, the view is
    # always called with a date filter from contributions_view
    def test_synset_contributions_only_user_filter(self):
        scenarios = [
            (self.user_a, self.synset_a),
            (self.user_b, self.synset_a),
            (self.user_a, self.synset_b),
            (self.user_b, self.synset_b),
            (self.user_a, self.synset_c),
            (self.user_b, self.synset_c),
        ]

        for ref_user, ref_synset in scenarios:
            ref_records = {
                r["change_details"]
                for r in self.all_records
                if r["user"] == ref_user and r["synset"] == ref_synset
            }
            params = {
                "user": ref_user.pk,
            }
            with self.subTest(params=params):
                response = self._get_synset_contributions_response(
                    ref_synset.pk, params
                )
                self.assertEqual(response.status_code, 200)
                edit_change_details = {
                    e.change_details for e in response.context["edits"]
                }
                self.assertEqual(edit_change_details, ref_records)

    def test_synset_contributions_only_date_filter(self):
        one_month_ago, today = self._default_date_filters()
        one_month_ago_days = (today - one_month_ago).days

        synsets = [self.synset_a, self.synset_b, self.synset_c]
        days_ago_combos = [
            (50, 31),
            (31, 30),
            (31, 10),
            (50, 0),
            (one_month_ago_days, 0),
            (10, 0),
        ]

        scenarios = [(s, *combo) for s in synsets for combo in days_ago_combos]

        for s, start, end in scenarios:
            ref_records = {
                r["change_details"]
                for r in self.all_records
                if r["synset"] == s and r["days_ago"] <= start and r["days_ago"] >= end
            }

            params = {
                "start_date": today - timedelta(start),
                "end_date": today - timedelta(end),
            }
            with self.subTest(params=params):
                response = self._get_synset_contributions_response(s.pk, params)
                self.assertEqual(response.status_code, 200)
                edit_change_details = {
                    e.change_details for e in response.context["edits"]
                }
                self.assertEqual(edit_change_details, ref_records)

    def test_synset_contributions_date_and_user_filter(self):
        one_month_ago, today = self._default_date_filters()
        one_month_ago_days = (today - one_month_ago).days

        synsets = [self.synset_a, self.synset_b, self.synset_c]
        users = [self.user_a, self.user_b]
        days_ago_combos = [
            (50, 31),
            (31, 30),
            (31, 10),
            (50, 0),
            (one_month_ago_days, 0),
            (10, 0),
        ]

        scenarios = [
            (u, s, *combo) for u in users for s in synsets for combo in days_ago_combos
        ]

        for user, synset, start, end in scenarios:
            ref_records = {
                r["change_details"]
                for r in self.all_records
                if r["user"] == user
                and r["synset"] == synset
                and r["days_ago"] <= start
                and r["days_ago"] >= end
            }

            params = {
                "user": user.pk,
                "start_date": today - timedelta(start),
                "end_date": today - timedelta(end),
            }
            with self.subTest(params=params):
                response = self._get_synset_contributions_response(synset.pk, params)
                self.assertEqual(response.status_code, 200)
                edit_change_details = {
                    e.change_details for e in response.context["edits"]
                }
                self.assertEqual(edit_change_details, ref_records)
