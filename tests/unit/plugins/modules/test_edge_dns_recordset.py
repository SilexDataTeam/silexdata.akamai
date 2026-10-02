# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest
from ansible_collections.silexdata.akamai.plugins.modules import edge_dns_recordset
from ansible_collections.silexdata.akamai.tests.unit.plugins.modules.conftest import response

PATH = "/config-dns/v2/zones/example.org/names/www.example.org/types/A"
CURRENT = {"name": "www.example.org", "type": "A", "ttl": 300, "rdata": ["192.0.2.10", "192.0.2.11"]}
NOT_FOUND = response(404, {"title": "Not Found"})


def args(**overrides):
    base = {"zone": "example.org", "name": "www.example.org", "type": "A", "ttl": 300, "rdata": ["192.0.2.10", "192.0.2.11"]}
    base.update(overrides)
    return base


def test_creates_a_missing_record_set(fake_api, run_module):
    fake_api.on("GET", PATH, NOT_FOUND).on("POST", PATH, response(201, CURRENT))

    failed, result = run_module(edge_dns_recordset, args(), diff=True)

    assert not failed
    assert result["changed"] is True
    assert result["recordset"] == CURRENT
    assert result["diff"] == {"before": {}, "after": CURRENT}
    assert fake_api.kwargs("POST", PATH)[0]["json"] == CURRENT


def test_no_change_when_it_already_matches_in_another_order(fake_api, run_module):
    fake_api.on("GET", PATH, response(200, CURRENT))

    failed, result = run_module(edge_dns_recordset, args(rdata=["192.0.2.11", "192.0.2.10"]))

    assert not failed
    assert result["changed"] is False
    assert fake_api.sent() == [("GET", PATH)]


@pytest.mark.parametrize("change", [{"ttl": 600}, {"rdata": ["192.0.2.12"]}])
def test_updates_a_record_set_that_differs(fake_api, run_module, change):
    wanted = dict(CURRENT, **change)
    fake_api.on("GET", PATH, response(200, CURRENT)).on("PUT", PATH, response(200, wanted))

    failed, result = run_module(edge_dns_recordset, args(**change), diff=True)

    assert not failed
    assert result["changed"] is True
    assert result["recordset"] == wanted
    assert result["diff"] == {"before": CURRENT, "after": wanted}
    assert fake_api.kwargs("PUT", PATH)[0]["json"] == wanted


def test_keeps_the_current_ttl_when_none_is_given(fake_api, run_module):
    fake_api.on("GET", PATH, response(200, CURRENT)).on("PUT", PATH, response(200, {}))

    run_module(edge_dns_recordset, args(ttl=None, rdata=["192.0.2.12"]))

    assert fake_api.kwargs("PUT", PATH)[0]["json"]["ttl"] == 300


def test_ttl_is_required_to_create(fake_api, run_module):
    fake_api.on("GET", PATH, NOT_FOUND)

    failed, result = run_module(edge_dns_recordset, args(ttl=None))

    assert failed
    assert result["msg"] == "ttl is required to create the A record set www.example.org."
    assert fake_api.sent("POST") == []


def test_deletes_an_existing_record_set(fake_api, run_module):
    fake_api.on("GET", PATH, response(200, CURRENT)).on("DELETE", PATH, response(204))

    failed, result = run_module(edge_dns_recordset, args(state="absent", ttl=None, rdata=None), diff=True)

    assert not failed
    assert result["changed"] is True
    assert result["recordset"] == {}
    assert result["diff"] == {"before": CURRENT, "after": {}}


def test_absent_and_missing_is_no_change(fake_api, run_module):
    fake_api.on("GET", PATH, NOT_FOUND)

    failed, result = run_module(edge_dns_recordset, args(state="absent", ttl=None, rdata=None))

    assert not failed
    assert result["changed"] is False
    assert fake_api.sent() == [("GET", PATH)]


@pytest.mark.parametrize(
    ("current", "state", "extra", "changed"),
    [(None, "present", {}, True), (CURRENT, "present", {"ttl": 60}, True), (CURRENT, "present", {}, False), (CURRENT, "absent", {}, True)],
)
def test_check_mode_reads_but_never_writes(fake_api, run_module, current, state, extra, changed):
    fake_api.on("GET", PATH, response(200, current) if current else NOT_FOUND)

    failed, result = run_module(edge_dns_recordset, args(state=state, **extra), check_mode=True)

    assert not failed
    assert result["changed"] is changed
    assert fake_api.sent() == [("GET", PATH)]


def test_type_is_sent_in_upper_case(fake_api, run_module):
    fake_api.on("GET", PATH, response(200, CURRENT))

    failed, result = run_module(edge_dns_recordset, args(type="a"))

    assert not failed
    assert result["changed"] is False


def test_rdata_is_required_when_present(run_module):
    failed, result = run_module(edge_dns_recordset, args(rdata=None))

    assert failed
    assert "rdata" in result["msg"]


def test_empty_rdata_is_rejected_when_present(fake_api, run_module):
    failed, result = run_module(edge_dns_recordset, args(rdata=[]))

    assert failed
    assert result["msg"].startswith("rdata must hold at least one record")
    assert fake_api.sent() == []


def test_api_errors_fail_with_a_description(fake_api, run_module):
    problem = {"title": "Invalid rdata", "detail": "300.1.1.1 is not an IPv4 address"}
    fake_api.on("GET", PATH, NOT_FOUND).on("POST", PATH, response(422, problem))

    failed, result = run_module(edge_dns_recordset, args(rdata=["300.1.1.1"]))

    assert failed
    assert result["msg"].startswith(f"POST {PATH}: HTTP 422 ")
    assert result["msg"].endswith("Invalid rdata: 300.1.1.1 is not an IPv4 address")
    assert result["status"] == 422
    assert result["response_body"] == problem


def test_names_with_special_characters_are_encoded(fake_api, run_module):
    path = "/config-dns/v2/zones/example.org/names/_dmarc.example.org/types/TXT"
    fake_api.on("GET", path, response(200, {"name": "_dmarc.example.org", "type": "TXT", "ttl": 300, "rdata": ['"v=DMARC1; p=none"']}))

    failed, result = run_module(edge_dns_recordset, args(name="_dmarc.example.org", type="TXT", rdata=["v=DMARC1; p=none"]))

    assert not failed
    assert result["changed"] is False
