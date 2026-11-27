from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.template.loader import render_to_string
from django.test import (
    Client,
    RequestFactory,
    SimpleTestCase,
    TestCase,
    override_settings,
)
from django.urls import reverse
from django.views.defaults import (
    bad_request,
    page_not_found,
    permission_denied,
    server_error,
)

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

    def test_login_redirects_to_work_list(self):
        response = self.client.post(
            reverse("login"), {"username": "testuser", "password": "password"}
        )

        self.assertRedirects(response, reverse("editor:work_list"))
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

        # Ignores the other site, and goes to the work list as without "next"
        self.assertRedirects(response, reverse("editor:work_list"))

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

    def test_error_messages_and_reload_option_depend_on_htmx(self):
        cases = [
            (
                403,
                permission_denied,
                "You do not have permission to access this page.",
                (
                    "Your permissions may have changed since you opened the page. "
                    "Please reload the page."
                ),
            ),
            (
                404,
                page_not_found,
                "The requested page was not found on this server.",
                (
                    "This content may have been deleted or changed since you opened "
                    "the page. Please reload the page."
                ),
            ),
        ]
        for status, handler, normal_message, htmx_message in cases:
            for htmx, message in ((False, normal_message), (True, htmx_message)):
                with self.subTest(status=status, htmx=htmx):
                    self.request.htmx = htmx
                    response = handler(self.request, Exception())
                    self.assertContains(response, message, status_code=status)
                    self.assertContains(
                        response, "Reload page", count=int(htmx), status_code=status
                    )

    def test_server_error_uses_custom_500_page(self):
        with self.assertTemplateUsed("500.html"):
            response = server_error(self.request)

        self.assertEqual(response.status_code, 500)
        self.assertNotContains(response, "Reload page", status_code=500)
        self.assertContains(response, "<!DOCTYPE html>", status_code=500)
        self.assertContains(response, "Internal Server Error (500)", status_code=500)
        self.assertContains(
            response,
            "Something unexpected prevented the server from fulfilling the request.",
            status_code=500,
        )

    def test_explicit_custom_error_content_is_escaped(self):
        html = render_to_string(
            "base_error.html",
            {
                "error_title": "Cannot <create>",
                "error_message": "You can't create this while <X>.",
            },
        )

        self.assertInHTML("<h1>Cannot &lt;create&gt;</h1>", html)
        self.assertIn("while &lt;X&gt;.", html)
        self.assertNotIn("<X>", html)
