# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest
from ansible_collections.silexdata.akamai.plugins.modules import edge_dns_zone
from ansible_collections.silexdata.akamai.tests.unit.plugins.modules.conftest import response

ZONES = "/config-dns/v2/zones"
ZONE = f"{ZONES}/example.org"
CHANGELIST = "/config-dns/v2/changelists"
CURRENT = {
    "zone": "example.org",
    "type": "PRIMARY",
    "signAndServe": False,
    "comment": "old",
    "contractId": "1-ABCDE",
    "activationState": "ACTIVE",
    "versionId": "v-1",
    "lastModifiedDate": "2026-01-01T00:00:00Z",
}
NOT_FOUND = response(404, {"title": "Not Found"})


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(edge_dns_zone.time, "sleep", lambda seconds: None)


def args(**overrides):
    base = {"zone": "example.org", "contract_id": "1-ABCDE", "group_id": "12345"}
    base.update(overrides)
    return base


def test_creates_a_primary_zone_and_its_default_records(fake_api, run_module):
    created = {"zone": "example.org", "type": "PRIMARY", "signAndServe": False, "comment": "new", "activationState": "NEW"}
    fake_api.on("GET", ZONE, NOT_FOUND).on("POST", ZONES, response(201, created))
    fake_api.on("POST", CHANGELIST, response(201, {"zone": "example.org"})).on("POST", f"{CHANGELIST}/example.org/submit", response(204))

    failed, result = run_module(edge_dns_zone, args(comment="new"), diff=True)

    assert not failed
    assert result["changed"] is True
    assert result["zone"] == created
    assert result["diff"] == {"before": {}, "after": created}
    assert fake_api.sent("POST") == [("POST", ZONES), ("POST", CHANGELIST), ("POST", f"{CHANGELIST}/example.org/submit")]
    create = fake_api.kwargs("POST", ZONES)[0]
    assert create["params"] == {"contractId": "1-ABCDE", "gid": "12345"}
    assert create["json"] == {"zone": "example.org", "type": "PRIMARY", "signAndServe": False, "comment": "new"}
    assert fake_api.kwargs("POST", CHANGELIST)[0]["params"] == {"zone": "example.org"}


@pytest.mark.parametrize("extra", [{"initialize_records": False}, {"type": "SECONDARY", "masters": ["192.0.2.53"]}])
def test_default_records_only_for_new_primary_zones_that_want_them(fake_api, run_module, extra):
    fake_api.on("GET", ZONE, NOT_FOUND).on("POST", ZONES, response(201, {}))

    failed = run_module(edge_dns_zone, args(**extra))[0]

    assert not failed
    assert fake_api.sent("POST") == [("POST", ZONES)]


@pytest.mark.parametrize("missing", ["contract_id", "group_id"])
def test_contract_and_group_are_required_to_create(fake_api, run_module, missing):
    fake_api.on("GET", ZONE, NOT_FOUND)

    failed, result = run_module(edge_dns_zone, args(**{missing: None}))

    assert failed
    assert result["msg"] == f"{missing} is required to create zone example.org."
    assert fake_api.sent("POST") == []


def test_no_change_when_the_given_settings_match(fake_api, run_module):
    fake_api.on("GET", ZONE, response(200, CURRENT))

    failed, result = run_module(edge_dns_zone, args(comment="old", sign_and_serve=False))

    assert not failed
    assert result["changed"] is False
    assert result["zone"] == CURRENT
    assert fake_api.sent() == [("GET", ZONE)]


def test_updates_only_what_differs_and_leaves_read_only_fields_out(fake_api, run_module):
    updated = dict(CURRENT, comment="new")
    fake_api.on("GET", ZONE, response(200, CURRENT)).on("PUT", ZONE, response(200, updated))

    failed, result = run_module(edge_dns_zone, args(comment="new"), diff=True)

    assert not failed
    assert result["changed"] is True
    assert result["zone"] == updated
    assert result["diff"] == {"before": CURRENT, "after": updated}
    assert fake_api.kwargs("PUT", ZONE)[0]["json"] == {
        "zone": "example.org",
        "type": "PRIMARY",
        "signAndServe": False,
        "comment": "new",
        "contractId": "1-ABCDE",
    }


def test_masters_are_compared_in_any_order(fake_api, run_module):
    current = {"zone": "example.org", "type": "SECONDARY", "signAndServe": False, "masters": ["192.0.2.1", "192.0.2.2"]}
    fake_api.on("GET", ZONE, response(200, current))

    failed, result = run_module(edge_dns_zone, args(type="SECONDARY", masters=["192.0.2.2", "192.0.2.1"]))

    assert not failed
    assert result["changed"] is False


@pytest.mark.parametrize(
    ("current_key", "changed"),
    [
        ({"name": "k", "algorithm": "hmac-sha256"}, False),
        ({"name": "k", "algorithm": "hmac-sha256", "secret": "c2VjcmV0"}, False),
        ({"name": "k", "algorithm": "hmac-sha256", "secret": "b3RoZXI="}, True),
        ({"name": "other", "algorithm": "hmac-sha256"}, True),
        (None, True),
    ],
)
def test_tsig_key_compares_only_what_edge_dns_returns(fake_api, run_module, current_key, changed):
    current = {"zone": "example.org", "type": "SECONDARY", "signAndServe": False, "masters": ["192.0.2.1"]}
    if current_key is not None:
        current["tsigKey"] = current_key
    fake_api.on("GET", ZONE, response(200, current)).on("PUT", ZONE, response(200, {}))

    failed, result = run_module(
        edge_dns_zone,
        args(type="SECONDARY", masters=["192.0.2.1"], tsig_key={"name": "k", "algorithm": "hmac-sha256", "secret": "c2VjcmV0"}),
    )

    assert not failed
    assert result["changed"] is changed


def test_a_different_type_fails(fake_api, run_module):
    fake_api.on("GET", ZONE, response(200, CURRENT))

    failed, result = run_module(edge_dns_zone, args(type="ALIAS", target="example.net"))

    assert failed
    assert result["msg"] == "Zone example.org is a PRIMARY zone, not ALIAS. Edge DNS cannot change a zone's type here."
    assert fake_api.sent() == [("GET", ZONE)]


def test_deletes_and_waits_for_the_request(fake_api, run_module):
    request = f"{ZONES}/delete-requests/req-1"
    fake_api.on("GET", ZONE, response(200, CURRENT))
    fake_api.on("POST", f"{ZONES}/delete-requests", response(201, {"requestId": "req-1"}))
    fake_api.on("GET", request, response(200, {"isComplete": False}), response(200, {"isComplete": True}))
    fake_api.on("GET", f"{request}/result", response(200, {"successfullyDeletedZones": ["example.org"], "failedZones": []}))

    failed, result = run_module(edge_dns_zone, args(state="absent"), diff=True)

    assert not failed
    assert result["changed"] is True
    assert result["delete_request_id"] == "req-1"
    assert result["zone"] == {}
    assert result["diff"] == {"before": CURRENT, "after": {}}
    submit = fake_api.kwargs("POST", f"{ZONES}/delete-requests")[0]
    assert submit["json"] == {"zones": ["example.org"]}
    assert submit["params"] == {"bypassSafetyChecks": "false"}
    assert fake_api.sent("GET").count(("GET", request)) == 2


def test_a_failed_deletion_fails_with_the_reason(fake_api, run_module):
    request = f"{ZONES}/delete-requests/req-1"
    fake_api.on("GET", ZONE, response(200, CURRENT))
    fake_api.on("POST", f"{ZONES}/delete-requests", response(201, {"requestId": "req-1"}))
    fake_api.on("GET", request, response(200, {"isComplete": True}))
    fake_api.on("GET", f"{request}/result", response(200, {"failedZones": [{"zone": "example.org", "failureReason": "ZONE_DELEGATION_ERROR"}]}))

    failed, result = run_module(edge_dns_zone, args(state="absent", bypass_safety_checks=True))

    assert failed
    assert result["msg"] == "Edge DNS could not delete zone example.org: ZONE_DELEGATION_ERROR."
    assert result["delete_request_id"] == "req-1"
    assert fake_api.kwargs("POST", f"{ZONES}/delete-requests")[0]["params"] == {"bypassSafetyChecks": "true"}


def test_deletion_times_out(fake_api, run_module, monkeypatch):
    clock = iter(range(0, 10000, 400))
    monkeypatch.setattr(edge_dns_zone.time, "time", lambda: next(clock))
    fake_api.on("GET", ZONE, response(200, CURRENT))
    fake_api.on("POST", f"{ZONES}/delete-requests", response(201, {"requestId": "req-1"}))
    fake_api.on("GET", f"{ZONES}/delete-requests/req-1", response(200, {"isComplete": False}))

    failed, result = run_module(edge_dns_zone, args(state="absent", wait_timeout=600))

    assert failed
    assert result["msg"] == "Timed out after 600s waiting for Edge DNS to delete zone example.org."


def test_delete_without_waiting(fake_api, run_module):
    fake_api.on("GET", ZONE, response(200, CURRENT))
    fake_api.on("POST", f"{ZONES}/delete-requests", response(201, {"requestId": "req-1"}))

    failed, result = run_module(edge_dns_zone, args(state="absent", wait=False))

    assert not failed
    assert result["delete_request_id"] == "req-1"
    assert fake_api.sent() == [("GET", ZONE), ("POST", f"{ZONES}/delete-requests")]


def test_absent_and_missing_is_no_change(fake_api, run_module):
    fake_api.on("GET", ZONE, NOT_FOUND)

    failed, result = run_module(edge_dns_zone, args(state="absent"))

    assert not failed
    assert result["changed"] is False


@pytest.mark.parametrize(
    ("current", "extra", "changed"),
    [(None, {}, True), (CURRENT, {"comment": "new"}, True), (CURRENT, {"comment": "old"}, False), (CURRENT, {"state": "absent"}, True)],
)
def test_check_mode_reads_but_never_writes(fake_api, run_module, current, extra, changed):
    fake_api.on("GET", ZONE, response(200, current) if current else NOT_FOUND)

    failed, result = run_module(edge_dns_zone, args(**extra), check_mode=True)

    assert not failed
    assert result["changed"] is changed
    assert fake_api.sent() == [("GET", ZONE)]


@pytest.mark.parametrize(("zone_type", "missing"), [("SECONDARY", "masters"), ("ALIAS", "target")])
def test_type_specific_options_are_required(run_module, zone_type, missing):
    failed, result = run_module(edge_dns_zone, args(type=zone_type))

    assert failed
    assert missing in result["msg"]
