# Copyright (c) 2024-2026, Silex Data Solutions <info@silexdata.com>
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)
# SPDX-FileCopyrightText: 2024-2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: Apache-2.0

"""EdgeGrid session handling shared by the silexdata.akamai modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import random
import time
import traceback
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

from ansible.module_utils.basic import env_fallback, missing_required_lib

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
    # An account ID, not a credential.
    "account_switch_key": {
        "required": False,
        "type": "str",
        "no_log": False,
        "fallback": (env_fallback, ["AKAMAI_ACCOUNT_KEY"]),
    },
}

# Matches the silexdata.akamai.retries doc fragment.
RETRY_ARGUMENT_SPEC = {
    "max_retries": {"required": False, "type": "int", "default": 0},
    "retry_on_status": {"required": False, "type": "list", "elements": "int", "default": [429, 503]},
    "retry_delay": {"required": False, "type": "float", "default": 5},
    "retry_max_delay": {"required": False, "type": "float", "default": 600},
}

# Property Manager answers 403 when its per-IP rate limit is exceeded and
# blocks the address for 10 minutes; retrying sooner extends the block.
FORBIDDEN_MIN_DELAY = 600

AUTH_MUTUALLY_EXCLUSIVE = [("edge_config", "edge_auth")]
AUTH_REQUIRED_ONE_OF = [("edge_config", "edge_auth")]


def check_requirements(module):
    """Fail the module cleanly when a required Python library is missing."""
    if not HAS_REQUESTS:
        module.fail_json(msg=missing_required_lib("requests"), exception=REQUESTS_IMP_ERR)

    if not HAS_EDGEGRID:
        module.fail_json(msg=missing_required_lib("edgegrid-python"), exception=EDGEGRID_IMP_ERR)


def check_retry_params(module):
    """Fail the module if a retry option is out of range."""
    for name in ("max_retries", "retry_delay", "retry_max_delay"):
        if module.params.get(name) is not None and module.params[name] < 0:
            module.fail_json(msg=f"{name} must not be negative, got {module.params[name]}.")


def retry_after_seconds(response, now=None):
    """Seconds the Retry-After header asks to wait, or None when absent or unreadable."""
    value = response.headers.get("Retry-After")
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - (time.time() if now is None else now))


def open_session(params):
    """Return an EdgeGrid-signed requests session, the API base URL and the account switch key.

    The account switch key is the account_switch_key option (or the
    AKAMAI_ACCOUNT_KEY environment variable), falling back to the edgerc
    section's account_key, as Akamai's EdgeGrid documentation describes.
    The EdgeGrid library itself never reads account_key.
    """
    session = requests.Session()
    account_switch_key = params.get("account_switch_key")

    if params["edge_config"]:
        edgerc = EdgeRc(params["edge_config"])
        section = params["section"]
        baseurl = f"https://{edgerc.get(section, 'host')}"
        session.auth = EdgeGridAuth.from_edgerc(edgerc, section)
        if not account_switch_key:
            account_switch_key = edgerc.get(section, "account_key", fallback=None)

    if params["edge_auth"]:
        baseurl = f"https://{params['edge_auth']['host']}"
        session.auth = EdgeGridAuth(
            client_token=params["edge_auth"]['client_token'],
            client_secret=params["edge_auth"]['client_secret'],
            access_token=params["edge_auth"]['access_token'],
        )

    return session, baseurl, account_switch_key or None


class AkamaiRequestError(Exception):
    """The request never produced an HTTP response (DNS, TLS, connection...)."""


class AkamaiApiError(Exception):
    """The API answered with a status the caller did not expect."""

    def __init__(self, message, status, body):
        super().__init__(message)
        self.status = status
        self.body = body


class AkamaiClient:
    """Send EdgeGrid-signed requests to one Akamai API host, retrying where asked."""

    def __init__(self, params, sleep=time.sleep):
        self.session, self.baseurl, self.account_switch_key = open_session(params)
        self.max_retries = params.get("max_retries") or 0
        self.retry_on_status = params.get("retry_on_status") or []
        self.retry_delay = params.get("retry_delay") or 0
        self.retry_max_delay = params.get("retry_max_delay") or 0
        self.attempts = 0
        self._sleep = sleep

    def retry_wait(self, retry, response):
        """Seconds to wait before retry number `retry` (0 for the first)."""
        backoff = self.retry_delay * (2**retry) * random.uniform(0.5, 1.0)
        wait = min(max(backoff, retry_after_seconds(response) or 0), self.retry_max_delay)
        if response.status_code == 403:
            wait = max(wait, FORBIDDEN_MIN_DELAY)
        return wait

    def request(self, method, endpoint, params=None, **kwargs):
        """Send one request; keyword arguments go to requests.Session.request.

        The account switch key is added as the accountSwitchKey query
        parameter unless the caller already set one. A response whose status
        is in retry_on_status is retried up to max_retries times.
        """
        url = urljoin(self.baseurl, endpoint)
        if self.account_switch_key and "accountSwitchKey" not in (params or {}) and "accountSwitchKey=" not in endpoint:
            params = dict(params or {}, accountSwitchKey=self.account_switch_key)
        if params is not None:
            kwargs["params"] = params
        for retry in range(self.max_retries + 1):
            self.attempts = retry + 1
            try:
                response = self.session.request(method, url, **kwargs)
            except requests.exceptions.RequestException as exc:
                raise AkamaiRequestError(f"{method} {url} failed: {exc}") from exc
            if retry == self.max_retries or response.status_code not in self.retry_on_status:
                return response
            self._sleep(self.retry_wait(retry, response))

    def call(self, method, endpoint, expect=(200,), **kwargs):
        """Send a request and return (status, parsed body).

        Raises AkamaiApiError, described by describe_failure, for any status
        not in expect.
        """
        response = self.request(method, endpoint, **kwargs)
        body = parse_response_body(response)
        if response.status_code not in expect:
            raise AkamaiApiError(f"{method} {endpoint}: {describe_failure(response, body)}", response.status_code, body)
        return response.status_code, body


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


def describe_failure(response, body):
    """One line describing a failed response, e.g. 'HTTP 409 Conflict: Zone already exists: ...'.

    Akamai error bodies are usually RFC 9457 problem details; their title,
    detail and errors[] are included. A text body is included, shortened.
    """
    message = f"HTTP {response.status_code}"
    if response.reason:
        message += f" {response.reason}"
    details = []
    if isinstance(body, dict):
        details = [str(body[key]) for key in ("title", "detail") if body.get(key)]
        errors = body.get("errors")
        if isinstance(errors, list) and errors:
            described = [str(error.get("detail") or error.get("title") or error) if isinstance(error, dict) else str(error) for error in errors[:5]]
            if len(errors) > 5:
                described.append(f"and {len(errors) - 5} more")
            details.append("; ".join(described))
    elif isinstance(body, str) and body.strip():
        text = " ".join(body.split())
        details = [text if len(text) <= 200 else text[:197] + "..."]
    if details:
        message += ": " + ": ".join(details)
    return message
