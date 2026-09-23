from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.views.defaults import bad_request, permission_denied, server_error


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
