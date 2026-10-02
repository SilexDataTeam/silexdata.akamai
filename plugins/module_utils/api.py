# Copyright (c) 2024-2026, Silex Data Solutions <info@silexdata.com>
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)
# SPDX-FileCopyrightText: 2024-2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: Apache-2.0

"""EdgeGrid session handling shared by the silexdata.akamai modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import traceback
from urllib.parse import urljoin

from ansible.module_utils.basic import missing_required_lib

REQUESTS_IMP_ERR = None
try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    REQUESTS_IMP_ERR = traceback.format_exc()

EDGEGRID_IMP_ERR = None
try:
    from akamai.edgegrid import EdgeGridAuth, EdgeRc

    HAS_EDGEGRID = True
except ImportError:
    HAS_EDGEGRID = False
    EDGEGRID_IMP_ERR = traceback.format_exc()


# Matches the silexdata.akamai.auth doc fragment.
AUTH_ARGUMENT_SPEC = {
    "section": {"required": False, "type": "str", "default": "default"},
    "edge_config": {"required": False, "type": "path"},
    "edge_auth": {
        "required": False,
        "type": "dict",
        "options": {
            "host": {"required": True, "type": "str"},
            "client_token": {"required": True, "type": "str", "no_log": True},
            "client_secret": {"required": True, "type": "str", "no_log": True},
            "access_token": {"required": True, "type": "str", "no_log": True},
        },
    },
}

AUTH_MUTUALLY_EXCLUSIVE = [("edge_config", "edge_auth")]
AUTH_REQUIRED_ONE_OF = [("edge_config", "edge_auth")]


def check_requirements(module):
    """Fail the module cleanly when a required Python library is missing."""
    if not HAS_REQUESTS:
        module.fail_json(msg=missing_required_lib("requests"), exception=REQUESTS_IMP_ERR)

    if not HAS_EDGEGRID:
        module.fail_json(msg=missing_required_lib("edgegrid-python"), exception=EDGEGRID_IMP_ERR)


def open_session(params):
    """Return an EdgeGrid-signed requests session and the API base URL."""
    session = requests.Session()

    if params["edge_config"]:
        edgerc = EdgeRc(params["edge_config"])
        section = params["section"]
        baseurl = f"https://{edgerc.get(section, 'host')}"
        session.auth = EdgeGridAuth.from_edgerc(edgerc, section)

    if params["edge_auth"]:
        baseurl = f"https://{params['edge_auth']['host']}"
        session.auth = EdgeGridAuth(
            client_token=params["edge_auth"]['client_token'],
            client_secret=params["edge_auth"]['client_secret'],
            access_token=params["edge_auth"]['access_token'],
        )

    return session, baseurl


class AkamaiRequestError(Exception):
    """The request never produced an HTTP response (DNS, TLS, connection...)."""


class AkamaiClient:
    """Send EdgeGrid-signed requests to one Akamai API host."""

    def __init__(self, params):
        self.session, self.baseurl = open_session(params)

    def request(self, method, endpoint, **kwargs):
        """Send one request; keyword arguments go to requests.Session.request."""
        url = urljoin(self.baseurl, endpoint)
        try:
            return self.session.request(method, url, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise AkamaiRequestError(f"{method} {url} failed: {exc}") from exc


def merge_headers(defaults, extra):
    """Merge request headers case-insensitively, the caller's taking precedence."""
    merged = {name.lower(): (name, value) for name, value in defaults.items()}
    for name, value in (extra or {}).items():
        merged[name.lower()] = (name, str(value))
    return dict(merged.values())


def parse_response_body(response):
    """Return the response body: parsed JSON, {} when empty, otherwise the text.

    Many Akamai operations answer 204 No Content, and some return non-JSON
    media types such as text/dns zone files, so the body is only parsed as
    JSON when it has one and it is (or claims to be) JSON.
    """
    if not response.content:
        return {}
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if not content_type or content_type == "application/json" or content_type.endswith("+json"):
        try:
            return response.json()
        except ValueError:
            pass
    return response.text
