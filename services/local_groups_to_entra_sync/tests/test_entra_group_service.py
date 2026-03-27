"""
Unit and property-based tests for EntraGroupService.
"""
from unittest.mock import MagicMock, patch, call

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from services.local_groups_to_entra_sync.entra_group_service import EntraGroupService, _slugify
from services.local_groups_to_entra_sync.token_provider import TokenProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(token: str = "test-token") -> EntraGroupService:
    token_provider = MagicMock(spec=TokenProvider)
    token_provider.get_token.return_value = token
    return EntraGroupService(token_provider)


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
# Task 4.1 — Unit tests for Graph API request body shapes
# ---------------------------------------------------------------------------

class TestCreateSecurityGroup:
    def test_create_sets_security_enabled_true_and_mail_enabled_false(self):
        """Assert securityEnabled=true and mailEnabled=false in create payload."""
        svc = _make_service()
        create_resp = _mock_response(201, {"id": "abc-123"})
        ext_resp = _mock_response(201, {"id": "com.lumen.groupSync", "lumenId": "lumen-1"})

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.post") as mock_post:
            mock_post.side_effect = [create_resp, ext_resp]
            ms_id = svc.create_security_group("My Group", "lumen-1")

        assert ms_id == "abc-123"
        create_call_kwargs = mock_post.call_args_list[0]
        body = create_call_kwargs.kwargs["json"]
        assert body["securityEnabled"] is True
        assert body["mailEnabled"] is False

    def test_create_sets_display_name(self):
        svc = _make_service()
        create_resp = _mock_response(201, {"id": "xyz"})
        ext_resp = _mock_response(201, {})

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.post") as mock_post:
            mock_post.side_effect = [create_resp, ext_resp]
            svc.create_security_group("Peer Group Alpha", "lumen-42")

        body = mock_post.call_args_list[0].kwargs["json"]
        assert body["displayName"] == "Peer Group Alpha"

    def test_create_extension_payload_contains_correct_lumen_id(self):
        """Assert extension payload contains correct lumenId."""
        svc = _make_service()
        create_resp = _mock_response(201, {"id": "group-id-999"})
        ext_resp = _mock_response(201, {})

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.post") as mock_post:
            mock_post.side_effect = [create_resp, ext_resp]
            svc.create_security_group("Test Group", "my-lumen-id")

        ext_call_kwargs = mock_post.call_args_list[1]
        ext_body = ext_call_kwargs.kwargs["json"]
        assert ext_body["lumenId"] == "my-lumen-id"
        assert ext_body["extensionName"] == "com.lumen.groupSync"

    def test_create_extension_uses_correct_group_id_in_url(self):
        svc = _make_service()
        create_resp = _mock_response(201, {"id": "the-group-id"})
        ext_resp = _mock_response(201, {})

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.post") as mock_post:
            mock_post.side_effect = [create_resp, ext_resp]
            svc.create_security_group("Group", "lumen-x")

        ext_url = mock_post.call_args_list[1].args[0]
        assert "the-group-id" in ext_url
        assert ext_url.endswith("/extensions")

    def test_create_returns_ms_object_id(self):
        svc = _make_service()
        create_resp = _mock_response(201, {"id": "returned-id"})
        ext_resp = _mock_response(201, {})

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.post") as mock_post:
            mock_post.side_effect = [create_resp, ext_resp]
            result = svc.create_security_group("G", "l")

        assert result == "returned-id"


class TestGetSecurityGroup:
    def test_get_returns_dict_on_success(self):
        svc = _make_service()
        resp = _mock_response(200, {"id": "abc", "displayName": "My Group"})

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.get", return_value=resp):
            result = svc.get_security_group("abc")

        assert result == {"id": "abc", "displayName": "My Group"}

    def test_get_returns_none_on_404(self):
        """Assert 404 on get_security_group returns None."""
        svc = _make_service()
        resp = _mock_response(404)

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.get", return_value=resp):
            result = svc.get_security_group("nonexistent-id")

        assert result is None

    def test_get_raises_on_non_404_error(self):
        from requests import HTTPError
        svc = _make_service()
        resp = _mock_response(500)

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.get", return_value=resp):
            with pytest.raises(HTTPError):
                svc.get_security_group("some-id")

    def test_get_uses_select_query_param(self):
        svc = _make_service()
        resp = _mock_response(200, {"id": "abc", "displayName": "G"})

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.get", return_value=resp) as mock_get:
            svc.get_security_group("abc")

        params = mock_get.call_args.kwargs.get("params", {})
        assert "$select" in params
        assert "id" in params["$select"]
        assert "displayName" in params["$select"]


class TestUpdateSecurityGroup:
    def test_update_sends_patch_with_display_name(self):
        svc = _make_service()
        resp = _mock_response(204)

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.patch", return_value=resp) as mock_patch:
            svc.update_security_group("group-id", "New Name")

        body = mock_patch.call_args.kwargs["json"]
        assert body["displayName"] == "New Name"

    def test_update_uses_correct_url(self):
        svc = _make_service()
        resp = _mock_response(204)

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.patch", return_value=resp) as mock_patch:
            svc.update_security_group("my-group-id", "Name")

        url = mock_patch.call_args.args[0]
        assert "my-group-id" in url

    def test_update_raises_on_error(self):
        from requests import HTTPError
        svc = _make_service()
        resp = _mock_response(403)

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.patch", return_value=resp):
            with pytest.raises(HTTPError):
                svc.update_security_group("id", "Name")


class TestAuthHeader:
    def test_bearer_token_sent_in_header(self):
        svc = _make_service(token="my-secret-token")
        create_resp = _mock_response(201, {"id": "id1"})
        ext_resp = _mock_response(201, {})

        with patch("services.local_groups_to_entra_sync.entra_group_service.requests.post") as mock_post:
            mock_post.side_effect = [create_resp, ext_resp]
            svc.create_security_group("G", "l")

        headers = mock_post.call_args_list[0].kwargs["headers"]
        assert headers["Authorization"] == "Bearer my-secret-token"


# ---------------------------------------------------------------------------
# Task 4.2 — Property 9: Security group type invariant
# Feature: local-groups-to-entra-sync, Property 9: Security group type invariant
# Validates: Requirements 4.2
# ---------------------------------------------------------------------------

@given(
    display_name=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    lumen_id=st.text(min_size=1, max_size=50),
)
@settings(max_examples=100)
def test_property_9_security_group_type_invariant(display_name, lumen_id):
    # Feature: local-groups-to-entra-sync, Property 9: Security group type invariant
    # For any call to EntraGroupService.create_security_group, the HTTP request body
    # sent to the Graph API should have securityEnabled=true and mailEnabled=false.
    svc = _make_service()
    create_resp = _mock_response(201, {"id": "some-id"})
    ext_resp = _mock_response(201, {})

    with patch("services.local_groups_to_entra_sync.entra_group_service.requests.post") as mock_post:
        mock_post.side_effect = [create_resp, ext_resp]
        svc.create_security_group(display_name, lumen_id)

    body = mock_post.call_args_list[0].kwargs["json"]
    assert body["securityEnabled"] is True
    assert body["mailEnabled"] is False


# ---------------------------------------------------------------------------
# Task 4.3 — Property 10: Lumen_ID extension attached on creation
# Feature: local-groups-to-entra-sync, Property 10: Lumen_ID extension attached on creation
# Validates: Requirements 4.3
# ---------------------------------------------------------------------------

@given(
    display_name=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    lumen_id=st.text(min_size=1, max_size=50),
    ms_object_id=st.text(min_size=1, max_size=50),
)
@settings(max_examples=100)
def test_property_10_lumen_id_extension_attached_on_creation(display_name, lumen_id, ms_object_id):
    # Feature: local-groups-to-entra-sync, Property 10: Lumen_ID extension attached on creation
    # For any successfully created security group, the Graph API extension endpoint
    # (/groups/{id}/extensions) should be called with the correct lumenId value.
    svc = _make_service()
    create_resp = _mock_response(201, {"id": ms_object_id})
    ext_resp = _mock_response(201, {})

    with patch("services.local_groups_to_entra_sync.entra_group_service.requests.post") as mock_post:
        mock_post.side_effect = [create_resp, ext_resp]
        returned_id = svc.create_security_group(display_name, lumen_id)

    assert returned_id == ms_object_id

    # Extension call must use the ms_object_id in the URL
    ext_url = mock_post.call_args_list[1].args[0]
    assert ms_object_id in ext_url

    # Extension body must carry the correct lumenId
    ext_body = mock_post.call_args_list[1].kwargs["json"]
    assert ext_body["lumenId"] == lumen_id
