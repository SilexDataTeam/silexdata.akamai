# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Fixtures for the edge_dns_* module tests: a fake Edge DNS API and a module runner."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from http import HTTPStatus
from unittest.mock import MagicMock
from urllib.parse import urlsplit

import pytest
import requests
from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes
from ansible_collections.silexdata.akamai.plugins.module_utils import api

EDGE_AUTH = {
    "host": "akab-example.luna.akamaiapis.net",
    "client_token": "akab-client-token",
    "client_secret": "client-secret",
    "access_token": "akab-access-token",
}


class ModuleExit(Exception):
    """exit_json or fail_json was called; args[0] is (failed, result)."""


def response(status, body=None):
    """A real requests.Response with a JSON body (or none)."""
    resp = requests.models.Response()
    resp.status_code = status
    resp.reason = HTTPStatus(status).phrase
    resp._content = b"" if body is None else json.dumps(body).encode()
    if body is not None:
        resp.headers["Content-Type"] = "application/json"
    return resp


class FakeApi:
    """Answers requests by (method, path), in order, and records what was sent."""

    def __init__(self):
        self.routes = {}
        self.calls = []

    def on(self, method, path, *responses):
        self.routes.setdefault((method, path), []).extend(responses)
        return self

    def __call__(self, method, url, **kwargs):
        path = urlsplit(url).path
        self.calls.append((method, path, kwargs))
        queue = self.routes.get((method, path))
        if not queue:
            raise AssertionError(f"unexpected request: {method} {path}")
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def sent(self, method=None):
        """(method, path) of each request, optionally only one method's."""
        return [(m, p) for m, p, _kwargs in self.calls if method is None or m == method]

    def kwargs(self, method, path):
        return [kw for m, p, kw in self.calls if (m, p) == (method, path)]


@pytest.fixture
def fake_api(monkeypatch):
    fake = FakeApi()
    session = MagicMock()
    session.request.side_effect = fake
    monkeypatch.setattr(api.requests, "Session", MagicMock(return_value=session))
    monkeypatch.setattr(api, "EdgeGridAuth", MagicMock(), raising=False)
    return fake


@pytest.fixture
def run_module(monkeypatch):
    """run_module(module, args, check_mode=False, diff=False) -> (failed, result)."""

    def exit_json(self, **kwargs):
        kwargs.setdefault("changed", False)
        raise ModuleExit((False, kwargs))

    def fail_json(self, **kwargs):
        raise ModuleExit((True, kwargs))

    monkeypatch.setattr(basic.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", fail_json)

    def run(module, args, check_mode=False, diff=False):
        module_args = {"edge_auth": EDGE_AUTH, "_ansible_check_mode": check_mode, "_ansible_diff": diff}
        module_args.update(args)
        basic._ANSIBLE_ARGS = to_bytes(json.dumps({"ANSIBLE_MODULE_ARGS": module_args}))
        # ansible-core 2.19+ requires a serialization profile alongside the args.
        basic._ANSIBLE_PROFILE = "legacy"
        try:
            module.main()
        except ModuleExit as exc:
            return exc.args[0]
        raise AssertionError("module exited without exit_json or fail_json")

    return run
