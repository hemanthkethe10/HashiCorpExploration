"""
Unit and property-based tests for AppRegistrationService.
"""
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from services.local_groups_to_entra_sync.app_registration_service import AppRegistrationService
from services.local_groups_to_entra_sync.token_provider import TokenProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(token: str = "test-token") -> AppRegistrationService:
    token_provider = MagicMock(spec=TokenProvider)
    token_provider.get_token.return_value = token
    return AppRegistrationService(token_provider)


def _mock_response(status_code: int, json_body: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.ok = status_code < 400
    if status_code >= 400:
        from requests import HTTPError
        resp.raise_for_status.side_effect = HTTPError(response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Unit tests — create_app_registration
# ---------------------------------------------------------------------------

class TestCreateAppRegistration:
    def test_create_posts_to_applications_endpoint(self):
        svc = _make_service()
        resp = _mock_response(201, {"id": "app-id-1"})

        with patch("services.local_groups_to_entra_sync.app_registration_service.requests.post", return_value=resp) as mock_post:
            svc.create_app_registration("My App")

        url = mock_post.call_args.args[0]
        assert url.endswith("/applications")

    def test_create_sends_display_name_in_body(self):
        svc = _make_service()
        resp = _mock_response(201, {"id": "app-id-2"})

        with patch("services.local_groups_to_entra_sync.app_registration_service.requests.post", return_value=resp) as mock_post:
            svc.create_app_registration("Client Alpha")

        body = mock_post.call_args.kwargs["json"]
        assert body["displayName"] == "Client Alpha"

    def test_create_returns_ms_object_id(self):
        svc = _make_service()
        resp = _mock_response(201, {"id": "returned-app-id"})

        with patch("services.local_groups_to_entra_sync.app_registration_service.requests.post", return_value=resp):
            result = svc.create_app_registration("App")

        assert result == "returned-app-id"

    def test_create_raises_on_error(self):
        from requests import HTTPError
        svc = _make_service()
        resp = _mock_response(400)

        with patch("services.local_groups_to_entra_sync.app_registration_service.requests.post", return_value=resp):
            with pytest.raises(HTTPError):
                svc.create_app_registration("App")

    def test_create_sends_bearer_token(self):
        svc = _make_service(token="my-token")
        resp = _mock_response(201, {"id": "id"})

        with patch("services.local_groups_to_entra_sync.app_registration_service.requests.post", return_value=resp) as mock_post:
            svc.create_app_registration("App")

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer my-token"


# ---------------------------------------------------------------------------
# Unit tests — get_app_registration
# ---------------------------------------------------------------------------

class TestGetAppRegistration:
    def test_get_returns_dict_on_success(self):
        svc = _make_service()
        resp = _mock_response(200, {"id": "app-id", "displayName": "My App"})

        with patch("services.local_groups_to_entra_sync.app_registration_service.requests.get", return_value=resp):
            result = svc.get_app_registration("app-id")

        assert result == {"id": "app-id", "displayName": "My App"}

    def test_get_returns_none_on_404(self):
        svc = _make_service()
        resp = _mock_response(404)

        with patch("services.local_groups_to_entra_sync.app_registration_service.requests.get", return_value=resp):
            result = svc.get_app_registration("nonexistent-id")

        assert result is None

    def test_get_raises_on_non_404_error(self):
        from requests import HTTPError
        svc = _make_service()
        resp = _mock_response(500)

        with patch("services.local_groups_to_entra_sync.app_registration_service.requests.get", return_value=resp):
            with pytest.raises(HTTPError):
                svc.get_app_registration("some-id")

    def test_get_uses_correct_url(self):
        svc = _make_service()
        resp = _mock_response(200, {"id": "abc"})

        with patch("services.local_groups_to_entra_sync.app_registration_service.requests.get", return_value=resp) as mock_get:
            svc.get_app_registration("abc")

        url = mock_get.call_args.args[0]
        assert "abc" in url
        assert "/applications/" in url


# ---------------------------------------------------------------------------
# Unit tests — update_app_registration
# ---------------------------------------------------------------------------

class TestUpdateAppRegistration:
    def test_update_sends_patch_with_display_name(self):
        svc = _make_service()
        resp = _mock_response(204)

        with patch("services.local_groups_to_entra_sync.app_registration_service.requests.patch", return_value=resp) as mock_patch:
            svc.update_app_registration("app-id", "New Name")

        body = mock_patch.call_args.kwargs["json"]
        assert body["displayName"] == "New Name"

    def test_update_uses_correct_url(self):
        svc = _make_service()
        resp = _mock_response(204)

        with patch("services.local_groups_to_entra_sync.app_registration_service.requests.patch", return_value=resp) as mock_patch:
            svc.update_app_registration("my-app-id", "Name")

        url = mock_patch.call_args.args[0]
        assert "my-app-id" in url
        assert "/applications/" in url

    def test_update_raises_on_error(self):
        from requests import HTTPError
        svc = _make_service()
        resp = _mock_response(403)

        with patch("services.local_groups_to_entra_sync.app_registration_service.requests.patch", return_value=resp):
            with pytest.raises(HTTPError):
                svc.update_app_registration("id", "Name")
