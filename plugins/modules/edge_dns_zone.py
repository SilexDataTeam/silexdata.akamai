#!/usr/bin/python

# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: edge_dns_zone
short_description: Manage an Akamai Edge DNS zone
version_added: 2.1.0
author:
  - Caleb Denney (@cdenney-silex)
description:
  - Creates, updates or deletes an Akamai Edge DNS zone.
  - The module reads the zone first and changes only the settings given that differ, so running it again reports no
    change.
  - A new primary zone is not served until it has SOA and NS records. By default the module has Edge DNS add its
    default ones, as Akamai's "Create a new primary zone" example describes.
options:
  zone:
    description:
      - Name of the zone, for example V(example.org).
    required: true
    type: str
  state:
    description:
      - V(present) creates the zone or updates the settings given.
      - V(absent) deletes the zone and every record in it.
    choices: [present, absent]
    default: present
    type: str
  type:
    description:
      - Zone type. A V(PRIMARY) zone's records are kept in Edge DNS, a V(SECONDARY) zone transfers them from
        O(masters), and an V(ALIAS) zone copies the configuration of O(target).
      - Edge DNS cannot change the type of an existing zone through this operation, so a different type fails the task.
    choices: [PRIMARY, SECONDARY, ALIAS]
    default: PRIMARY
    type: str
  contract_id:
    description:
      - Contract to create the zone in, for example V(1-ABCDE). Required to create a zone, and ignored afterwards.
    type: str
  group_id:
    description:
      - Group to create the zone in. Required to create a zone, and ignored afterwards.
    type: str
  comment:
    description:
      - Free-form comment. Edge DNS also records it with each change.
    type: str
  masters:
    description:
      - For V(SECONDARY) zones, the name servers to transfer the zone from. Compared in any order.
    type: list
    elements: str
  target:
    description:
      - For V(ALIAS) zones, the zone whose configuration this zone copies.
    type: str
  sign_and_serve:
    description:
      - Whether DNSSEC Sign&Serve is enabled. Edge DNS requires a value, so a new zone gets V(false) if this is not set.
    type: bool
  sign_and_serve_algorithm:
    description:
      - DNSSEC Sign&Serve algorithm.
    choices: [RSA_SHA1, RSA_SHA256, RSA_SHA512, ECDSA_P256_SHA256, ECDSA_P384_SHA384]
    type: str
  end_customer_id:
    description:
      - Free-form identifier for the zone, often used by resellers.
    type: str
  tsig_key:
    description:
      - For V(SECONDARY) zones, the TSIG key used for zone transfers.
    type: dict
    suboptions:
      name:
        description: Name of the key.
        required: true
        type: str
      algorithm:
        description: Algorithm of the key, for example V(hmac-sha256).
        required: true
        type: str
      secret:
        description:
          - Base64-encoded secret of the key.
          - If Edge DNS does not return the secret of the current key, a changed secret alone is not detected.
        required: true
        type: str
  initialize_records:
    description:
      - When the task creates a V(PRIMARY) zone, have Edge DNS add default SOA and NS records by creating and
        submitting a change list, so the zone can be served.
      - Set V(false) to add your own SOA and NS records instead, for example with
        M(silexdata.akamai.edge_dns_recordset).
    type: bool
    default: true
  bypass_safety_checks:
    description:
      - With O(state=absent), delete the zone even if Edge DNS's safety checks object, for example because the zone is
        still delegated to Akamai's name servers.
    type: bool
    default: false
  wait:
    description:
      - With O(state=absent), wait until Edge DNS has finished deleting the zone, which it does asynchronously, and fail
        if the deletion fails.
    type: bool
    default: true
  wait_timeout:
    description:
      - How many seconds O(wait) waits for the deletion to finish.
    type: int
    default: 600
extends_documentation_fragment:
  - silexdata.akamai.auth
  - silexdata.akamai.retries
attributes:
  check_mode:
    description: Can run in check mode and return a change prediction without modifying the target.
    support: full
    details:
      - The current zone is still read from the API.
  diff_mode:
    description: Returns details of what changed, or would change in check mode, when run in diff mode.
    support: full
notes:
  - Deleting a zone deletes every record set in it.
seealso:
  - module: silexdata.akamai.edge_dns_zone_info
  - module: silexdata.akamai.edge_dns_recordset
  - name: Example of creating a new primary zone
    description: Akamai's walkthrough of the steps this module takes to create a primary zone.
    link: https://techdocs.akamai.com/edge-dns/reference/example-create-new-primary-zone
'''

EXAMPLES = r'''
---
- name: Create a primary zone with Edge DNS's default SOA and NS records
  silexdata.akamai.edge_dns_zone:
    zone: example.org
    contract_id: 1-ABCDE
    group_id: "12345"
    comment: Managed by Ansible
    edge_config: ~/.edgerc

- name: Create a secondary zone
  silexdata.akamai.edge_dns_zone:
    zone: example.net
    type: SECONDARY
    masters:
      - 192.0.2.53
    contract_id: 1-ABCDE
    group_id: "12345"
    edge_config: ~/.edgerc

- name: Delete a zone and wait for Edge DNS to finish
  silexdata.akamai.edge_dns_zone:
    zone: old.example.org
    state: absent
    edge_config: ~/.edgerc
'''

RETURN = r'''
---
zone:
  description:
    - The zone's settings after the task, as Edge DNS returns them. Empty when the zone does not exist.
    - In check mode, the settings the task would leave.
  type: dict
  returned: always
  sample:
    zone: example.org
    type: PRIMARY
    signAndServe: false
    comment: Managed by Ansible
    contractId: 1-ABCDE
    activationState: NEW
delete_request_id:
  description: ID of the Edge DNS delete request, when the task deleted the zone.
  type: str
  returned: when a delete request was submitted
  sample: e585a640-0849-4b87-8dd9-91afdaf8851c
'''

import time

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.silexdata.akamai.plugins.module_utils.api import (
    AUTH_ARGUMENT_SPEC,
    AUTH_MUTUALLY_EXCLUSIVE,
    AUTH_REQUIRED_ONE_OF,
    RETRY_ARGUMENT_SPEC,
    AkamaiApiError,
    AkamaiClient,
    AkamaiRequestError,
    check_requirements,
    check_retry_params,
)
from ansible_collections.silexdata.akamai.plugins.module_utils.edge_dns import (
    CHANGELISTS,
    ZONES,
    changelist_path,
    get_or_none,
    zone_path,
)

# Module option -> Edge DNS zone field, for the settings compared and sent.
SETTINGS = {
    "comment": "comment",
    "masters": "masters",
    "target": "target",
    "sign_and_serve": "signAndServe",
    "sign_and_serve_algorithm": "signAndServeAlgorithm",
    "end_customer_id": "endCustomerId",
    "tsig_key": "tsigKey",
}
# Fields Edge DNS sets itself, left out of an update.
READ_ONLY_FIELDS = (
    "activationState",
    "aliasCount",
    "category",
    "lastActivationDate",
    "lastModifiedBy",
    "lastModifiedDate",
    "versionId",
)
POLL_SECONDS = 5


def wanted_settings(params):
    """The zone fields the task sets, by Edge DNS name."""
    return {field: params[option] for option, field in SETTINGS.items() if params[option] is not None}


def differs(field, wanted, current):
    if field == "masters":
        return sorted(wanted) != sorted(current or [])
    if field == "tsigKey" and isinstance(current, dict):
        # Compare only what Edge DNS returns: it may leave out the secret.
        return any(wanted[key] != current[key] for key in wanted if key in current) or not current
    return wanted != current


def create(module, client):
    params = module.params
    missing = [name for name in ("contract_id", "group_id") if not params[name]]
    if missing:
        module.fail_json(msg=f"{' and '.join(missing)} {'is' if len(missing) == 1 else 'are'} required to create zone {params['zone']}.")
    zone = {"zone": params["zone"], "type": params["type"], "signAndServe": False}
    zone.update(wanted_settings(params))
    if module.check_mode:
        return zone
    created = client.call("POST", ZONES, expect=(201,), params={"contractId": params["contract_id"], "gid": params["group_id"]}, json=zone)[1]
    if params["type"] == "PRIMARY" and params["initialize_records"]:
        # A new change list is filled with default SOA and NS records;
        # submitting it adds them to the zone.
        client.call("POST", CHANGELISTS, expect=(201,), params={"zone": params["zone"]})
        client.call("POST", f"{changelist_path(params['zone'])}/submit", expect=(204,))
    return created or zone


def update(module, client, current):
    wanted = wanted_settings(module.params)
    changes = {field: value for field, value in wanted.items() if differs(field, value, current.get(field))}
    if not changes:
        return False, current
    zone = {field: value for field, value in current.items() if field not in READ_ONLY_FIELDS}
    zone.update(changes)
    if module.check_mode:
        return True, dict(current, **changes)
    return True, client.call("PUT", zone_path(module.params["zone"]), expect=(200,), json=zone)[1] or zone


def delete(module, client):
    """Submit a delete request and, with wait, see it through. Return its ID."""
    params = module.params
    body = client.call(
        "POST",
        f"{ZONES}/delete-requests",
        expect=(201,),
        params={"bypassSafetyChecks": str(params["bypass_safety_checks"]).lower()},
        json={"zones": [params["zone"]]},
    )[1]
    request_id = body["requestId"]
    if not params["wait"]:
        return request_id

    deadline = time.time() + params["wait_timeout"]
    while True:
        status = client.call("GET", f"{ZONES}/delete-requests/{request_id}")[1]
        if status.get("isComplete"):
            break
        if time.time() >= deadline:
            module.fail_json(
                msg=f"Timed out after {params['wait_timeout']}s waiting for Edge DNS to delete zone {params['zone']}.",
                delete_request_id=request_id,
            )
        time.sleep(POLL_SECONDS)

    result = client.call("GET", f"{ZONES}/delete-requests/{request_id}/result")[1]
    for failure in result.get("failedZones") or []:
        if failure.get("zone") == params["zone"]:
            module.fail_json(
                msg=f"Edge DNS could not delete zone {params['zone']}: {failure.get('failureReason')}.",
                delete_request_id=request_id,
                response_body=result,
            )
    return request_id


def main():
    argument_spec = {
        "zone": {"required": True, "type": "str"},
        "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
        "type": {"type": "str", "choices": ["PRIMARY", "SECONDARY", "ALIAS"], "default": "PRIMARY"},
        "contract_id": {"type": "str"},
        "group_id": {"type": "str"},
        "comment": {"type": "str"},
        "masters": {"type": "list", "elements": "str"},
        "target": {"type": "str"},
        "sign_and_serve": {"type": "bool"},
        "sign_and_serve_algorithm": {
            "type": "str",
            "choices": ["RSA_SHA1", "RSA_SHA256", "RSA_SHA512", "ECDSA_P256_SHA256", "ECDSA_P384_SHA384"],
        },
        "end_customer_id": {"type": "str"},
        "tsig_key": {
            "type": "dict",
            # The secret suboption is no_log; the key's name and algorithm are not secret.
            "no_log": False,
            "options": {
                "name": {"required": True, "type": "str"},
                "algorithm": {"required": True, "type": "str"},
                "secret": {"required": True, "type": "str", "no_log": True},
            },
        },
        "initialize_records": {"type": "bool", "default": True},
        "bypass_safety_checks": {"type": "bool", "default": False},
        "wait": {"type": "bool", "default": True},
        "wait_timeout": {"type": "int", "default": 600},
    }
    argument_spec.update(AUTH_ARGUMENT_SPEC)
    argument_spec.update(RETRY_ARGUMENT_SPEC)

    module = AnsibleModule(
        argument_spec=argument_spec,
        mutually_exclusive=AUTH_MUTUALLY_EXCLUSIVE,
        required_one_of=AUTH_REQUIRED_ONE_OF,
        required_if=[("type", "SECONDARY", ["masters"]), ("type", "ALIAS", ["target"])],
        supports_check_mode=True,
    )
    check_requirements(module)
    check_retry_params(module)
    params = module.params

    result = {"changed": False}
    try:
        client = AkamaiClient(params)
        current = get_or_none(client, zone_path(params["zone"]))
        before = current or {}
        if params["state"] == "absent":
            after = {}
            if current is not None:
                result["changed"] = True
                if not module.check_mode:
                    result["delete_request_id"] = delete(module, client)
        elif current is None:
            result["changed"] = True
            after = create(module, client)
        else:
            if current.get("type") != params["type"]:
                module.fail_json(
                    msg=f"Zone {params['zone']} is a {current.get('type')} zone, not {params['type']}. Edge DNS cannot change a zone's type here.",
                    zone=current,
                )
            result["changed"], after = update(module, client, current)
    except AkamaiRequestError as exc:
        module.fail_json(msg=str(exc), **result)
    except AkamaiApiError as exc:
        module.fail_json(msg=str(exc), status=exc.status, response_body=exc.body, **result)

    result["zone"] = after
    if module._diff:
        result["diff"] = {"before": before, "after": after}
    module.exit_json(**result)


if __name__ == "__main__":
    main()
