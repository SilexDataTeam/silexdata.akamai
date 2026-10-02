# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock, patch

import pytest
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
