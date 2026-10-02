# Copyright: (c) 2024, Silex Data
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import sys

if sys.version_info < (3, 3):
    from mock import MagicMock, patch
else:
    from unittest.mock import MagicMock, patch

import pytest
from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes
from ansible_collections.silexdata.akamai.plugins.module_utils import api
from ansible_collections.silexdata.akamai.plugins.modules import manage_akamai


class AnsibleExitJson(Exception):
    """Raised by the patched exit_json to halt module execution in tests."""


class AnsibleFailJson(Exception):
    """Raised by the patched fail_json to halt module execution in tests."""


def exit_json(*args, **kwargs):
    if "changed" not in kwargs:
        kwargs["changed"] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args, **kwargs):
    kwargs["failed"] = True
    raise AnsibleFailJson(kwargs)


def set_module_args(args):
    """Prepare module arguments the way Ansible would pass them on stdin."""
    serialized = json.dumps({"ANSIBLE_MODULE_ARGS": args})
    basic._ANSIBLE_ARGS = to_bytes(serialized)
    # ansible-core 2.19+ requires a serialization profile to be set alongside
    # the raw args buffer when params are injected directly.
    basic._ANSIBLE_PROFILE = "legacy"


@pytest.fixture(autouse=True)
def patch_ansible_module(monkeypatch):
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", fail_json)


EDGE_AUTH = {
    "host": "akab-example.luna.akamaiapis.net",
    "client_token": "akab-client-token",
    "client_secret": "client-secret",
    "access_token": "akab-access-token",
}


def test_get_request_file_reads_json(tmp_path):
    payload = {"productId": "prd_Alta", "propertyName": "my.new.property.com"}
    body_file = tmp_path / "body.json"
    body_file.write_text(json.dumps(payload))

    assert manage_akamai.get_request_file(str(body_file)) == payload


def test_requires_one_of_edge_config_or_edge_auth():
    """Neither edge_config nor edge_auth -> module must fail."""
    set_module_args({"endpoint": "/siteshield/v1/maps", "method": "GET"})
    with pytest.raises(AnsibleFailJson):
        manage_akamai.main()


def test_edge_config_and_edge_auth_are_mutually_exclusive(tmp_path):
    edgerc = tmp_path / ".edgerc"
    edgerc.write_text("[default]\nhost = example\n")
    set_module_args(
        {
            "endpoint": "/siteshield/v1/maps",
            "method": "GET",
            "edge_config": str(edgerc),
            "edge_auth": EDGE_AUTH,
        }
    )
    with pytest.raises(AnsibleFailJson):
        manage_akamai.main()


@patch.object(api, "EdgeGridAuth", create=True)
@patch.object(api.requests, "Session")
def test_authenticate_get_success(mock_session_cls, _mock_edgegrid):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"siteShieldMaps": []}

    session = MagicMock()
    session.get.return_value = response
    mock_session_cls.return_value = session

    params = {
        "endpoint": "/siteshield/v1/maps",
        "method": "GET",
        "section": "default",
        "body": None,
        "headers": None,
        "edge_config": None,
        "edge_auth": EDGE_AUTH,
    }

    is_error, has_changed, result = manage_akamai.authenticate(params)

    assert is_error is False
    assert has_changed is False
    assert result == {"siteShieldMaps": []}
    session.get.assert_called_once()


@patch.object(api, "EdgeGridAuth", create=True)
@patch.object(api.requests, "Session")
def test_authenticate_get_error_status(mock_session_cls, _mock_edgegrid):
    response = MagicMock()
    response.status_code = 404
    response.json.return_value = {"detail": "not found"}

    session = MagicMock()
    session.get.return_value = response
    mock_session_cls.return_value = session

    params = {
        "endpoint": "/siteshield/v1/maps/does-not-exist",
        "method": "GET",
        "section": "default",
        "body": None,
        "headers": None,
        "edge_config": None,
        "edge_auth": EDGE_AUTH,
    }

    is_error, has_changed, result = manage_akamai.authenticate(params)

    assert is_error is True
    assert has_changed is False
    assert result == {"detail": "not found"}


@patch.object(api, "EdgeGridAuth", create=True)
@patch.object(api, "EdgeRc", create=True)
@patch.object(api.requests, "Session")
def test_authenticate_get_with_edge_config(mock_session_cls, mock_edgerc_cls, _mock_edgegrid):
    mock_edgerc_instance = MagicMock()
    mock_edgerc_instance.get.return_value = "akab-example.luna.akamaiapis.net"
    mock_edgerc_cls.return_value = mock_edgerc_instance

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"result": "ok"}

    session = MagicMock()
    session.get.return_value = response
    mock_session_cls.return_value = session

    params = {
        "endpoint": "/test",
        "method": "GET",
        "section": "default",
        "body": None,
        "headers": None,
        "edge_config": "/fake/.edgerc",
        "edge_auth": None,
    }

    is_error, has_changed, result = manage_akamai.authenticate(params)

    assert is_error is False
    assert has_changed is False
    assert result == {"result": "ok"}
    mock_edgerc_cls.assert_called_once_with("/fake/.edgerc")


@patch.object(api, "EdgeGridAuth", create=True)
@patch.object(api.requests, "Session")
def test_authenticate_post_with_body(mock_session_cls, _mock_edgegrid, tmp_path):
    payload = {"key": "value"}
    body_file = tmp_path / "body.json"
    body_file.write_text(json.dumps(payload))

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"created": True}

    session = MagicMock()
    session.post.return_value = response
    mock_session_cls.return_value = session

    params = {
        "endpoint": "/test/resource",
        "method": "POST",
        "section": "default",
        "body": str(body_file),
        "headers": None,
        "edge_config": None,
        "edge_auth": EDGE_AUTH,
    }

    is_error, has_changed, result = manage_akamai.authenticate(params)

    assert is_error is False
    assert has_changed is True
    assert result == {"created": True}
    session.post.assert_called_once()


def test_main_fails_without_requests(monkeypatch):
    monkeypatch.setattr(api, "HAS_REQUESTS", False)
    set_module_args({"endpoint": "/test", "method": "GET", "edge_auth": EDGE_AUTH})
    with pytest.raises(AnsibleFailJson) as exc_info:
        manage_akamai.main()
    assert "requests" in exc_info.value.args[0]["msg"]


def test_main_fails_without_edgegrid(monkeypatch):
    monkeypatch.setattr(api, "HAS_EDGEGRID", False)
    set_module_args({"endpoint": "/test", "method": "GET", "edge_auth": EDGE_AUTH})
    with pytest.raises(AnsibleFailJson) as exc_info:
        manage_akamai.main()
    assert "edgegrid" in exc_info.value.args[0]["msg"].lower()


@patch.object(api, "EdgeGridAuth", create=True)
@patch.object(api.requests, "Session")
def test_main_get_success(mock_session_cls, _mock_edgegrid):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"data": "ok"}

    session = MagicMock()
    session.get.return_value = response
    mock_session_cls.return_value = session

    set_module_args({"endpoint": "/test", "method": "GET", "edge_auth": EDGE_AUTH})

    with pytest.raises(AnsibleExitJson) as exc_info:
        manage_akamai.main()

    assert exc_info.value.args[0]["changed"] is False
    assert exc_info.value.args[0]["msg"] == {"data": "ok"}


@patch.object(api, "EdgeGridAuth", create=True)
@patch.object(api.requests, "Session")
def test_main_get_error(mock_session_cls, _mock_edgegrid):
    response = MagicMock()
    response.status_code = 401
    response.json.return_value = {"detail": "unauthorized"}

    session = MagicMock()
    session.get.return_value = response
    mock_session_cls.return_value = session

    set_module_args({"endpoint": "/test", "method": "GET", "edge_auth": EDGE_AUTH})

    with pytest.raises(AnsibleFailJson) as exc_info:
        manage_akamai.main()

    assert exc_info.value.args[0]["msg"] == {"detail": "unauthorized"}
