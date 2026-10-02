# Copyright: (c) 2024, Silex Data
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from unittest.mock import MagicMock

import pytest
import requests
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
BASE_URL = "https://akab-example.luna.akamaiapis.net"


def fake_response(status, body=None, text=None, content_type="application/json", headers=None):
    """Build a real requests.Response, as the API would return it."""
    response = requests.models.Response()
    response.status_code = status
    if body is not None:
        response._content = json.dumps(body).encode()
    elif text is not None:
        response._content = text.encode()
    else:
        response._content = b""
    if response._content and content_type:
        response.headers["Content-Type"] = content_type
    response.headers.update(headers or {})
    return response


@pytest.fixture
def session(monkeypatch):
    """The EdgeGrid session the module sends through; set request.return_value."""
    mock_session = MagicMock()
    monkeypatch.setattr(api.requests, "Session", MagicMock(return_value=mock_session))
    monkeypatch.setattr(api, "EdgeGridAuth", MagicMock(), raising=False)
    monkeypatch.setattr(api, "EdgeRc", MagicMock(), raising=False)
    return mock_session


def run_module(args, check_mode=False):
    """Run main() and return (failed, result)."""
    module_args = {} if "edge_config" in args else {"edge_auth": EDGE_AUTH}
    module_args.update(args)
    if check_mode:
        module_args["_ansible_check_mode"] = True
    set_module_args(module_args)
    try:
        manage_akamai.main()
    except AnsibleExitJson as exc:
        return False, exc.args[0]
    except AnsibleFailJson as exc:
        return True, exc.args[0]
    raise AssertionError("module exited without exit_json or fail_json")


def sent(session):
    """(method, url, kwargs) of the single request the module sent."""
    session.request.assert_called_once()
    args, kwargs = session.request.call_args
    return args[0], args[1], kwargs


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


def test_main_fails_without_requests(monkeypatch):
    monkeypatch.setattr(api, "HAS_REQUESTS", False)
    failed, result = run_module({"endpoint": "/test", "method": "GET"})
    assert failed
    assert "requests" in result["msg"]


def test_main_fails_without_edgegrid(monkeypatch):
    monkeypatch.setattr(api, "HAS_EDGEGRID", False)
    failed, result = run_module({"endpoint": "/test", "method": "GET"})
    assert failed
    assert "edgegrid" in result["msg"].lower()


def test_get_success(session):
    session.request.return_value = fake_response(200, {"siteShieldMaps": []})

    failed, result = run_module({"endpoint": "/siteshield/v1/maps", "method": "GET"})

    assert not failed
    assert result["changed"] is False
    assert result["msg"] == {"siteShieldMaps": []}
    assert sent(session)[:2] == ("GET", BASE_URL + "/siteshield/v1/maps")


def test_get_with_edge_config(session):
    api.EdgeRc.return_value.get.return_value = "akab-from-edgerc.luna.akamaiapis.net"
    session.request.return_value = fake_response(200, {"result": "ok"})

    failed, result = run_module({"endpoint": "/test", "method": "GET", "edge_config": "/fake/.edgerc"})

    assert not failed
    assert result["msg"] == {"result": "ok"}
    api.EdgeRc.assert_called_once_with("/fake/.edgerc")
    assert sent(session)[1] == "https://akab-from-edgerc.luna.akamaiapis.net/test"


@pytest.mark.parametrize("status", [400, 401, 404])
def test_error_status_fails_with_the_error_body(session, status):
    session.request.return_value = fake_response(status, {"detail": "nope"}, content_type="application/problem+json")

    failed, result = run_module({"endpoint": "/test", "method": "GET"})

    assert failed
    assert result["msg"] == {"detail": "nope"}


def test_post_with_body_file(session, tmp_path):
    payload = {"key": "value"}
    body_file = tmp_path / "body.json"
    body_file.write_text(json.dumps(payload))
    session.request.return_value = fake_response(201, {"created": True})

    failed, result = run_module({"endpoint": "/test/resource", "method": "POST", "body": str(body_file)})

    assert not failed
    assert result["changed"] is True
    assert result["msg"] == {"created": True}
    assert sent(session)[2]["json"] == payload


@pytest.mark.parametrize("method", ["POST", "PUT"])
def test_no_content_response_succeeds_with_an_empty_msg(session, method):
    # e.g. POST /config-dns/v2/zones/{zone}/recordsets and
    # POST /config-dns/v2/changelists/{zone}/submit answer 204 No Content.
    session.request.return_value = fake_response(204)

    failed, result = run_module({"endpoint": "/config-dns/v2/changelists/example.org/submit", "method": method})

    assert not failed
    assert result["changed"] is True
    assert result["msg"] == {}


def test_non_json_response_is_returned_as_text(session):
    zone_file = "example.org. 86400 IN SOA a1-1.akam.net. hostmaster.example.org. 1 3600 600 604800 300\n"
    session.request.return_value = fake_response(200, text=zone_file, content_type="text/dns")

    failed, result = run_module({"endpoint": "/config-dns/v2/zones/example.org/zone-file", "method": "GET"})

    assert not failed
    assert result["msg"] == zone_file


def test_invalid_json_is_returned_as_text_instead_of_crashing(session):
    session.request.return_value = fake_response(502, text="<html>Bad Gateway</html>", content_type="application/json")

    failed, result = run_module({"endpoint": "/test", "method": "GET"})

    assert not failed
    assert result["msg"] == "<html>Bad Gateway</html>"


def test_json_without_a_content_type_is_still_parsed(session):
    session.request.return_value = fake_response(200, {"ok": True}, content_type=None)

    failed, result = run_module({"endpoint": "/test", "method": "GET"})

    assert result["msg"] == {"ok": True}


def test_headers_are_sent_and_override_defaults_case_insensitively(session):
    session.request.return_value = fake_response(200, {})

    run_module(
        {
            "endpoint": "/papi/v1/properties",
            "method": "GET",
            "headers": {"PAPI-Use-Prefixes": True, "Content-Type": "application/vnd.akamai.papirules.latest+json"},
        }
    )

    assert sent(session)[2]["headers"] == {
        "Content-Type": "application/vnd.akamai.papirules.latest+json",
        "PAPI-Use-Prefixes": "True",
    }


def test_default_content_type_is_kept_without_headers(session):
    session.request.return_value = fake_response(200, {})

    run_module({"endpoint": "/test", "method": "GET"})

    assert sent(session)[2]["headers"] == {"content-type": "application/json"}


def test_connection_error_fails_cleanly(session):
    session.request.side_effect = requests.exceptions.ConnectionError("Name or service not known")

    failed, result = run_module({"endpoint": "/test", "method": "GET"})

    assert failed
    assert result["msg"] == f"GET {BASE_URL}/test failed: Name or service not known"


@pytest.mark.parametrize(("method", "changed"), [("GET", False), ("POST", True), ("PUT", True), ("PATCH", True)])
def test_check_mode_sends_nothing(session, method, changed):
    failed, result = run_module({"endpoint": "/test", "method": method}, check_mode=True)

    assert not failed
    assert result["changed"] is changed
    session.request.assert_not_called()
