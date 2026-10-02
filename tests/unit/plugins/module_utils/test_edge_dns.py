# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# Simplified BSD License (see LICENSES/BSD-2-Clause.txt or https://opensource.org/licenses/BSD-2-Clause)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock

import pytest
from ansible_collections.silexdata.akamai.plugins.module_utils import edge_dns
from ansible_collections.silexdata.akamai.plugins.module_utils.api import AkamaiApiError


def test_paths_encode_each_part():
    assert edge_dns.zone_path("example.org") == "/config-dns/v2/zones/example.org"
    assert edge_dns.changelist_path("example.org") == "/config-dns/v2/changelists/example.org"
    assert edge_dns.recordset_path("example.org", "a/b.example.org", "TXT") == ("/config-dns/v2/zones/example.org/names/a%2Fb.example.org/types/TXT")


def test_get_or_none():
    client = MagicMock()
    client.call.return_value = (404, {"title": "Not Found"})
    assert edge_dns.get_or_none(client, "/x") is None
    client.call.assert_called_once_with("GET", "/x", expect=(200, 404))
    client.call.return_value = (200, {"zone": "example.org"})
    assert edge_dns.get_or_none(client, "/x") == {"zone": "example.org"}


def pages(*batches, total=None):
    return [(200, {"metadata": {} if total is None else {"totalElements": total}, "items": batch}) for batch in batches]


@pytest.mark.parametrize(
    ("responses", "expected_pages"),
    [
        (pages([1, 2], total=2), 1),
        (pages(list(range(100)), [100], total=101), 2),
        (pages(list(range(100)), [], total=150), 2),
        (pages(list(range(100)), [100]), 2),
        (pages([]), 1),
    ],
)
def test_paginate(responses, expected_pages):
    client = MagicMock()
    client.call.side_effect = responses

    items = edge_dns.paginate(client, "/list", "items", {"types": "A"})

    assert items == [i for _status, body in responses[:expected_pages] for i in body["items"]]
    assert [c[1]["params"]["page"] for c in client.call.call_args_list] == list(range(1, expected_pages + 1))
    assert client.call.call_args_list[0][1]["params"] == {"types": "A", "page": 1, "pageSize": 100}


def test_paginate_rejects_a_non_object():
    client = MagicMock()
    client.call.return_value = (200, "oops")
    with pytest.raises(AkamaiApiError):
        edge_dns.paginate(client, "/list", "items")


@pytest.mark.parametrize(
    ("record_type", "left", "right"),
    [
        ("A", ["192.0.2.1", "192.0.2.2"], ["192.0.2.2", "192.0.2.1"]),
        ("AAAA", ["2001:DB8:0:0:0:0:0:1"], ["2001:db8::1"]),
        ("CNAME", ["Target.Example.org."], ["target.example.org"]),
        ("MX", ["10  Mail.Example.org."], ["10 mail.example.org"]),
        ("SRV", ["0 5 5060 SIP.example.org."], ["0 5 5060 sip.example.org"]),
        ("TXT", ["v=spf1 -all"], ['"v=spf1 -all"']),
        ("txt", ['say "hi"'], ['"say \\"hi\\""']),
    ],
)
def test_same_rdata(record_type, left, right):
    assert edge_dns.same_rdata(record_type, left, right)


@pytest.mark.parametrize(
    ("record_type", "left", "right"),
    [
        ("A", ["192.0.2.1"], ["192.0.2.1", "192.0.2.2"]),
        ("A", ["192.0.2.1", "192.0.2.1"], ["192.0.2.1"]),
        ("TXT", ["V=spf1 -all"], ['"v=spf1 -all"']),
        ("MX", ["20 mail.example.org"], ["10 mail.example.org"]),
        ("CAA", ['0 issue "Letsencrypt.org"'], ['0 issue "letsencrypt.org"']),
    ],
)
def test_different_rdata(record_type, left, right):
    assert not edge_dns.same_rdata(record_type, left, right)


def test_unparsable_addresses_are_compared_as_text():
    assert edge_dns.normalize_rdata("A", " not-an-ip ") == "not-an-ip"
