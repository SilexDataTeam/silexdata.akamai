# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.silexdata.akamai.plugins.modules import edge_dns_recordset_info
from ansible_collections.silexdata.akamai.tests.unit.plugins.modules.conftest import response

ZONE = "/config-dns/v2/zones/example.org"
WWW_A = {"name": "www.example.org", "type": "A", "ttl": 300, "rdata": ["192.0.2.10"]}


def listing(*recordsets):
    return response(200, {"metadata": {"totalElements": len(recordsets)}, "recordsets": list(recordsets)})


def test_one_record_set(fake_api, run_module):
    fake_api.on("GET", f"{ZONE}/names/www.example.org/types/A", response(200, WWW_A))

    failed, result = run_module(edge_dns_recordset_info, {"zone": "example.org", "name": "www.example.org", "type": "a"})

    assert not failed
    assert result["recordsets"] == [WWW_A]


def test_one_missing_record_set(fake_api, run_module):
    fake_api.on("GET", f"{ZONE}/names/www.example.org/types/A", response(404, {}))

    failed, result = run_module(edge_dns_recordset_info, {"zone": "example.org", "name": "www.example.org", "type": "A"})

    assert not failed
    assert result["recordsets"] == []


def test_every_type_for_a_name_keeps_exact_matches(fake_api, run_module):
    www_aaaa = {"name": "www.example.org", "type": "AAAA", "ttl": 300, "rdata": ["2001:db8::10"]}
    lookalike = {"name": "www2.example.org", "type": "A", "ttl": 300, "rdata": ["192.0.2.20"]}
    fake_api.on("GET", f"{ZONE}/recordsets", listing(WWW_A, www_aaaa, lookalike))

    failed, result = run_module(edge_dns_recordset_info, {"zone": "example.org", "name": "WWW.example.org."})

    assert not failed
    assert result["recordsets"] == [WWW_A, www_aaaa]
    assert fake_api.kwargs("GET", f"{ZONE}/recordsets")[0]["params"] == {"search": "WWW.example.org.", "page": 1, "pageSize": 100}


def test_filter_by_types(fake_api, run_module):
    fake_api.on("GET", f"{ZONE}/recordsets", listing(WWW_A))

    failed, result = run_module(edge_dns_recordset_info, {"zone": "example.org", "types": ["a", "mx"], "search": "www"})

    assert not failed
    assert fake_api.kwargs("GET", f"{ZONE}/recordsets")[0]["params"] == {"types": "A,MX", "search": "www", "page": 1, "pageSize": 100}


def test_type_needs_a_name(run_module):
    failed, result = run_module(edge_dns_recordset_info, {"zone": "example.org", "type": "A"})

    assert failed
    assert "name" in result["msg"]
