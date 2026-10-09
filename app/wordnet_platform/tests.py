from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.test import (
    Client,
    RequestFactory,
    SimpleTestCase,
    TestCase,
    override_settings,
)
from django.urls import reverse
from django.views.defaults import bad_request, permission_denied, server_error

from editor.forms import DefinitionForm
from wordnet_platform.forms import AuthenticationForm


class LoginTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="testuser", password="password")

    def test_login_uses_shared_registration_layout(self):
        response = self.client.get(reverse("login"))

        self.assertTemplateUsed(response, "registration/login.html")
        self.assertTemplateUsed(response, "registration/registration_base.html")
        self.assertTemplateUsed(response, "editor/base.html")
        self.assertContains(response, "<title>Log in")
        self.assertContains(response, '<div class="container limit-text-width">')
        self.assertContains(response, '<div class="card">')
        self.assertContains(response, '<div class="card-body">')
        self.assertContains(response, "css/editor")
        self.assertContains(response, '<h1 id="main-heading">Log in</h1>', html=True)
        self.assertNotContains(response, '<p class="alert alert-info">')
        self.assertContains(response, '<form method="post" hx-disable>')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'class="form-control"', count=2)
        self.assertNotContains(response, 'href="/register/')
        self.assertNotContains(response, 'href="/password_reset/')

    def test_login_fields_use_spaced_wrappers(self):
        response = self.client.get(reverse("login"))

        self.assertTemplateUsed(response, "django/forms/field.html")
        self.assertContains(response, 'class="mb-3"', count=2)
        for field in response.context["form"]:
            self.assertContains(
                response,
                f'<div class="mb-3">{field.label_tag()}{field}</div>',
                html=True,
            )

    def test_login_help_text_is_muted_and_below_input(self):
        form = AuthenticationForm()
        form.fields["username"].help_text = "Use your staff username."
        field = form["username"]

        self.assertInHTML(
            f'<div class="mb-3">{field.label_tag()}{field}'
            '<div class="text-muted" id="id_username_helptext">'
            "Use your staff username.</div></div>",
            form.as_div(),
        )

    def test_editor_forms_keep_default_rendering(self):
        self.assertNotIn('class="mb-3"', DefinitionForm().as_div())

    def test_login_redirects_to_front_page(self):
        response = self.client.post(
            reverse("login"), {"username": "testuser", "password": "password"}
        )

        self.assertRedirects(response, reverse("editor:front_page"))
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_login_preserves_next_redirect(self):
        next_url = reverse("editor:browse_synsets")
        response = self.client.get(reverse("login"), {"next": next_url})

        self.assertContains(
            response,
            f'<input type="hidden" name="next" value="{next_url}">',
            html=True,
        )

        response = self.client.post(
            reverse("login"),
            {"username": "testuser", "password": "password", "next": next_url},
        )

        self.assertRedirects(response, next_url)

    def test_login_rejects_external_next_redirect(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser",
                "password": "password",
                "next": "https://example.com/",
            },
        )

        self.assertRedirects(response, reverse("editor:front_page"))

    def test_invalid_credentials_show_errors(self):
        response = self.client.post(
            reverse("login"), {"username": "testuser", "password": "incorrect"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/registration_base.html")
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertContains(response, 'class="errorlist nonfield"')
        self.assertContains(response, 'class="form-control"', count=2)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_required_fields_show_styled_errors(self):
        response = self.client.post(reverse("login"), {})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context["form"].errors), {"username", "password"})
        self.assertContains(response, 'class="alert alert-danger"', count=2)
        self.assertContains(response, 'class="errorlist"', count=2)
        for field in response.context["form"]:
            self.assertContains(
                response,
                f'<div class="mb-3">{field.label_tag()}{field.errors}{field}</div>',
                html=True,
            )

    def test_login_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("login"), {"username": "testuser", "password": "password"}
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("_auth_user_id", client.session)


@override_settings(DEBUG=False)
class ErrorPageTest(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")

    def test_unknown_url_uses_custom_404_page(self):
        response = self.client.get("/unknown-url/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_bad_request_uses_custom_400_page(self):
        with self.assertTemplateUsed("400.html"):
            response = bad_request(self.request, SuspiciousOperation())

        self.assertEqual(response.status_code, 400)

    def test_permission_denied_uses_custom_403_page(self):
        with self.assertTemplateUsed("403.html"):
            response = permission_denied(self.request, PermissionDenied())

        self.assertEqual(response.status_code, 403)

    def test_server_error_uses_custom_500_page(self):
        with self.assertTemplateUsed("500.html"):
            response = server_error(self.request)

        self.assertEqual(response.status_code, 500)
