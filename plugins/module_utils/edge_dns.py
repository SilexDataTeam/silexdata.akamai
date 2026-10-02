# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# Simplified BSD License (see LICENSES/BSD-2-Clause.txt or https://opensource.org/licenses/BSD-2-Clause)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: BSD-2-Clause

"""Edge DNS (config-dns v2) helpers shared by the edge_dns_* modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import ipaddress
from urllib.parse import quote

from ansible_collections.silexdata.akamai.plugins.module_utils.api import AkamaiApiError

ZONES = "/config-dns/v2/zones"
CHANGELISTS = "/config-dns/v2/changelists"
PAGE_SIZE = 100

# Record types whose rdata names hosts, compared case-insensitively and
# without a trailing dot: the whole rdata, or its last field for MX and SRV.
HOSTNAME_TYPES = frozenset(("CNAME", "DNAME", "NS", "PTR"))
HOSTNAME_LAST_FIELD_TYPES = frozenset(("MX", "SRV"))
QUOTED_TYPES = frozenset(("TXT", "SPF"))


def zone_path(zone):
    return f"{ZONES}/{quote(zone, safe='')}"


def changelist_path(zone):
    return f"{CHANGELISTS}/{quote(zone, safe='')}"


def recordset_path(zone, name, record_type):
    return f"{zone_path(zone)}/names/{quote(name, safe='')}/types/{quote(record_type, safe='')}"


def get_or_none(client, endpoint):
    """GET a resource, returning None when it does not exist (404)."""
    status, body = client.call("GET", endpoint, expect=(200, 404))
    return body if status == 200 else None


def paginate(client, endpoint, key, query=None):
    """Return every item of a paged Edge DNS listing (page, pageSize, metadata.totalElements)."""
    items = []
    page = 1
    while True:
        params = dict(query or {}, page=page, pageSize=PAGE_SIZE)
        body = client.call("GET", endpoint, params=params)[1]
        if not isinstance(body, dict):
            raise AkamaiApiError(f"GET {endpoint}: expected a JSON object, got {type(body).__name__}", 200, body)
        batch = body.get(key) or []
        items.extend(batch)
        total = (body.get("metadata") or {}).get("totalElements")
        if not batch or (total is not None and len(items) >= total) or (total is None and len(batch) < PAGE_SIZE):
            return items
        page += 1


def normalize_rdata(record_type, value):
    """Return rdata in the form Edge DNS stores it, so equal records compare equal.

    Whitespace runs collapse to one space. TXT and SPF data is compared
    quoted, as Edge DNS returns it. Addresses are compared in canonical form,
    and host names case-insensitively without a trailing dot.
    """
    record_type = record_type.upper()
    text = " ".join(str(value).split())
    if record_type in QUOTED_TYPES:
        if not text.startswith('"'):
            text = '"' + text.replace('"', '\\"') + '"'
        return text
    if record_type in ("A", "AAAA"):
        try:
            return str(ipaddress.ip_address(text))
        except ValueError:
            return text
    if record_type in HOSTNAME_TYPES:
        return text.lower().rstrip(".")
    if record_type in HOSTNAME_LAST_FIELD_TYPES:
        fields = text.split(" ")
        fields[-1] = fields[-1].lower().rstrip(".")
        return " ".join(fields)
    return text


def same_rdata(record_type, left, right):
    """Whether two rdata lists hold the same records, in any order."""
    return sorted(normalize_rdata(record_type, v) for v in left or []) == sorted(normalize_rdata(record_type, v) for v in right or [])
