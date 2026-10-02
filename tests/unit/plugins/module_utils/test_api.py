# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock, patch

import pytest
import requests
from ansible_collections.silexdata.akamai.plugins.module_utils import api

EDGE_AUTH = {
    "host": "akab-example.luna.akamaiapis.net",
    "client_token": "akab-client-token",
    "client_secret": "client-secret",
    "access_token": "akab-access-token",
}


def params(**overrides):
    base = {"section": "default", "edge_config": None, "edge_auth": None, "account_switch_key": None}
    base.update(overrides)
    return base


class ModuleFailed(Exception):
    pass


def raise_module_failed(**kwargs):
    raise ModuleFailed(kwargs)


def failing_module():
    module = MagicMock()
    module.fail_json.side_effect = raise_module_failed
    return module


@patch.object(api, "EdgeGridAuth", create=True)
def test_open_session_with_edge_auth(mock_auth):
    session, baseurl, account_switch_key = api.open_session(params(edge_auth=EDGE_AUTH))

    assert baseurl == "https://akab-example.luna.akamaiapis.net"
    mock_auth.assert_called_once_with(
        client_token="akab-client-token",
        client_secret="client-secret",
        access_token="akab-access-token",
    )
    assert session.auth is mock_auth.return_value
    assert account_switch_key is None


@patch.object(api, "EdgeGridAuth", create=True)
@patch.object(api, "EdgeRc", create=True)
def test_open_session_with_edge_config(mock_edgerc_cls, mock_auth):
    mock_edgerc_cls.return_value.get.return_value = "akab-from-edgerc.luna.akamaiapis.net"

    session, baseurl = api.open_session(params(edge_config="/fake/.edgerc", section="dns"))[:2]

    mock_edgerc_cls.assert_called_once_with("/fake/.edgerc")
    mock_edgerc_cls.return_value.get.assert_any_call("dns", "host")
    mock_auth.from_edgerc.assert_called_once_with(mock_edgerc_cls.return_value, "dns")
    assert baseurl == "https://akab-from-edgerc.luna.akamaiapis.net"
    assert session.auth is mock_auth.from_edgerc.return_value


@pytest.mark.parametrize(("flag", "library"), [("HAS_REQUESTS", "requests"), ("HAS_EDGEGRID", "edgegrid-python")])
def test_check_requirements_names_the_missing_library(monkeypatch, flag, library):
    monkeypatch.setattr(api, flag, False)
    with pytest.raises(ModuleFailed) as exc_info:
        api.check_requirements(failing_module())
    assert library in exc_info.value.args[0]["msg"]


def test_check_requirements_passes_when_libraries_are_present():
    module = failing_module()
    api.check_requirements(module)
    module.fail_json.assert_not_called()


def fake_response(content=b"", content_type=None):
    response = requests.models.Response()
    response.status_code = 200
    response._content = content
    if content_type:
        response.headers["Content-Type"] = content_type
    return response


@pytest.mark.parametrize(
    ("content", "content_type", "expected"),
    [
        (b"", None, {}),
        (b"", "application/json", {}),
        (b'{"a": 1}', "application/json", {"a": 1}),
        (b'{"a": 1}', "application/json; charset=utf-8", {"a": 1}),
        (b'{"title": "Conflict"}', "application/problem+json", {"title": "Conflict"}),
        (b'[1, 2]', None, [1, 2]),
        (b"example.org. 300 IN A 192.0.2.1\n", "text/dns", "example.org. 300 IN A 192.0.2.1\n"),
        (b'{"looks": "like json"}', "text/csv", '{"looks": "like json"}'),
        (b"not json", "application/json", "not json"),
    ],
)
def test_parse_response_body(content, content_type, expected):
    assert api.parse_response_body(fake_response(content, content_type)) == expected


def test_merge_headers_lets_the_caller_override_case_insensitively():
    merged = api.merge_headers({"content-type": "application/json"}, {"Content-Type": "text/dns", "If-Match": 3})
    assert merged == {"Content-Type": "text/dns", "If-Match": "3"}


def test_merge_headers_without_extra_headers():
    assert api.merge_headers({"content-type": "application/json"}, None) == {"content-type": "application/json"}


@patch.object(api, "EdgeGridAuth", create=True)
def test_client_joins_the_endpoint_to_the_host(_mock_auth):
    client = api.AkamaiClient(params(edge_auth=EDGE_AUTH))
    client.session = MagicMock()

    client.request("GET", "/config-dns/v2/zones", params={"page": 2})

    client.session.request.assert_called_once_with("GET", "https://akab-example.luna.akamaiapis.net/config-dns/v2/zones", params={"page": 2})


@patch.object(api, "EdgeGridAuth", create=True)
def test_client_wraps_transport_errors(_mock_auth):
    client = api.AkamaiClient(params(edge_auth=EDGE_AUTH))
    client.session = MagicMock()
    client.session.request.side_effect = requests.exceptions.Timeout("timed out")

    with pytest.raises(api.AkamaiRequestError, match="^GET https://akab-example.luna.akamaiapis.net/x failed: timed out$"):
        client.request("GET", "/x")


def write_edgerc(tmp_path, extra=""):
    edgerc = tmp_path / ".edgerc"
    edgerc.write_text("[default]\nhost = akab-example.luna.akamaiapis.net\nclient_token = a\nclient_secret = b\naccess_token = c\n" + extra)
    return str(edgerc)


@pytest.mark.parametrize(
    ("option", "edgerc_line", "expected"),
    [
        (None, "", None),
        (None, "account_key = 1-FROMRC\n", "1-FROMRC"),
        (None, "account-key = 1-FROMRC\n", "1-FROMRC"),
        ("1-OPTION", "account_key = 1-FROMRC\n", "1-OPTION"),
    ],
)
def test_account_switch_key_option_wins_over_edgerc(tmp_path, option, edgerc_line, expected):
    edgerc = write_edgerc(tmp_path, edgerc_line)
    account_switch_key = api.open_session(params(edge_config=edgerc, account_switch_key=option))[2]
    assert account_switch_key == expected


@patch.object(api, "EdgeGridAuth", create=True)
def test_account_switch_key_is_sent_as_a_query_parameter(_mock_auth):
    client = api.AkamaiClient(params(edge_auth=EDGE_AUTH, account_switch_key="1-ABC"))
    client.session = MagicMock()

    client.request("GET", "/papi/v1/contracts", params={"page": 1})

    assert client.session.request.call_args[1]["params"] == {"page": 1, "accountSwitchKey": "1-ABC"}


@pytest.mark.parametrize(
    ("endpoint", "query"),
    [("/papi/v1/contracts", {"accountSwitchKey": "1-MINE"}), ("/papi/v1/contracts?accountSwitchKey=1-MINE", None)],
)
@patch.object(api, "EdgeGridAuth", create=True)
def test_an_explicit_accountswitchkey_is_not_overridden(_mock_auth, endpoint, query):
    client = api.AkamaiClient(params(edge_auth=EDGE_AUTH, account_switch_key="1-ABC"))
    client.session = MagicMock()

    client.request("GET", endpoint, params=query)

    assert client.session.request.call_args[1].get("params") == query


def test_account_switch_key_falls_back_to_the_environment(monkeypatch):
    from ansible.module_utils.basic import env_fallback

    monkeypatch.setenv("AKAMAI_ACCOUNT_KEY", "1-ENV")
    fallback, args = api.AUTH_ARGUMENT_SPEC["account_switch_key"]["fallback"]
    assert fallback is env_fallback
    assert fallback(*args) == "1-ENV"
