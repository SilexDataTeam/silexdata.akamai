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
    base = {"section": "default", "edge_config": None, "edge_auth": None}
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
    session, baseurl = api.open_session(params(edge_auth=EDGE_AUTH))

    assert baseurl == "https://akab-example.luna.akamaiapis.net"
    mock_auth.assert_called_once_with(
        client_token="akab-client-token",
        client_secret="client-secret",
        access_token="akab-access-token",
    )
    assert session.auth is mock_auth.return_value


@patch.object(api, "EdgeGridAuth", create=True)
@patch.object(api, "EdgeRc", create=True)
def test_open_session_with_edge_config(mock_edgerc_cls, mock_auth):
    mock_edgerc_cls.return_value.get.return_value = "akab-from-edgerc.luna.akamaiapis.net"

    session, baseurl = api.open_session(params(edge_config="/fake/.edgerc", section="dns"))

    mock_edgerc_cls.assert_called_once_with("/fake/.edgerc")
    mock_edgerc_cls.return_value.get.assert_called_once_with("dns", "host")
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
