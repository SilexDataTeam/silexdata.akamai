# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.silexdata.akamai.plugins.modules import edge_dns_zone_info
from ansible_collections.silexdata.akamai.tests.unit.plugins.modules.conftest import response

ZONES = "/config-dns/v2/zones"


def test_one_zone(fake_api, run_module):
    fake_api.on("GET", f"{ZONES}/example.org", response(200, {"zone": "example.org"}))

    failed, result = run_module(edge_dns_zone_info, {"zone": "example.org", "types": ["ALIAS"]})

    assert not failed
    assert result == {"changed": False, "zones": [{"zone": "example.org"}]}
    assert fake_api.kwargs("GET", f"{ZONES}/example.org")[0].get("params") is None


def test_one_missing_zone(fake_api, run_module):
    fake_api.on("GET", f"{ZONES}/example.org", response(404, {}))

    failed, result = run_module(edge_dns_zone_info, {"zone": "example.org"})

    assert not failed
    assert result["zones"] == []


def test_every_page_with_filters(fake_api, run_module):
    first = [{"zone": f"z{n}.example"} for n in range(100)]
    fake_api.on(
        "GET",
        ZONES,
        response(200, {"metadata": {"totalElements": 101}, "zones": first}),
        response(200, {"metadata": {"totalElements": 101}, "zones": [{"zone": "last.example"}]}),
    )

    failed, result = run_module(edge_dns_zone_info, {"contract_ids": ["1-ABC", "1-DEF"], "types": ["PRIMARY", "SECONDARY"], "search": "example"})

    assert not failed
    assert len(result["zones"]) == 101
    assert [kw["params"] for kw in fake_api.kwargs("GET", ZONES)] == [
        {"contractIds": "1-ABC,1-DEF", "types": "PRIMARY,SECONDARY", "search": "example", "page": 1, "pageSize": 100},
        {"contractIds": "1-ABC,1-DEF", "types": "PRIMARY,SECONDARY", "search": "example", "page": 2, "pageSize": 100},
    ]


def test_check_mode_still_reads(fake_api, run_module):
    fake_api.on("GET", ZONES, response(200, {"metadata": {"totalElements": 0}, "zones": []}))

    failed, result = run_module(edge_dns_zone_info, {}, check_mode=True)

    assert not failed
    assert result["zones"] == []
