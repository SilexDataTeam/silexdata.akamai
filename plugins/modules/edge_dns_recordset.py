#!/usr/bin/python

# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: edge_dns_recordset
short_description: Manage one Akamai Edge DNS record set
version_added: 2.1.0
author:
  - Caleb Denney (@cdenney-silex)
description:
  - Creates, updates or deletes the record set for one name and type in an Akamai Edge DNS primary zone.
  - The module reads the record set first and changes it only when its TTL or records differ, so running it again
    reports no change.
  - Each change is made directly in the zone, which activates a new zone version. To group many changes into one
    version, use M(silexdata.akamai.manage_akamai) with Edge DNS change lists.
options:
  zone:
    description:
      - Name of the zone, for example V(example.org).
    required: true
    type: str
  name:
    description:
      - Fully qualified name of the record set, for example V(www.example.org). Use the zone name for the zone apex.
    required: true
    type: str
  type:
    description:
      - Record type, for example V(A), V(CNAME), V(MX) or V(TXT).
    required: true
    type: str
  state:
    description:
      - V(present) creates the record set or makes it match O(ttl) and O(rdata).
      - V(absent) deletes it.
    choices: [present, absent]
    default: present
    type: str
  ttl:
    description:
      - Time to live, in seconds.
      - Required to create a record set. When updating, the current TTL is kept if this is not set.
    type: int
  rdata:
    description:
      - The records, one string each, in presentation format, for example V(192.0.2.10), V(10 mail.example.org.)
        or V(v=spf1 -all).
      - Required when O(state=present).
      - Records are compared in any order. Before comparing, runs of whitespace become one space, TXT and SPF data is
        quoted the way Edge DNS returns it, addresses are put in canonical form, and host names are compared without
        case or a trailing dot.
    type: list
    elements: str
extends_documentation_fragment:
  - silexdata.akamai.auth
  - silexdata.akamai.retries
attributes:
  check_mode:
    description: Can run in check mode and return a change prediction without modifying the target.
    support: full
    details:
      - The current record set is still read from the API.
  diff_mode:
    description: Returns details of what changed, or would change in check mode, when run in diff mode.
    support: full
seealso:
  - module: silexdata.akamai.edge_dns_recordset_info
  - module: silexdata.akamai.edge_dns_zone
  - name: Edge DNS record set operations
    description: Akamai's reference for the record set endpoints this module uses.
    link: https://techdocs.akamai.com/edge-dns/reference/get-zone-name-type
'''

EXAMPLES = r'''
---
- name: Point www at two web servers
  silexdata.akamai.edge_dns_recordset:
    zone: example.org
    name: www.example.org
    type: A
    ttl: 300
    rdata:
      - 192.0.2.10
      - 192.0.2.11
    edge_config: ~/.edgerc

- name: Publish an SPF record, retrying if rate limited
  silexdata.akamai.edge_dns_recordset:
    zone: example.org
    name: example.org
    type: TXT
    ttl: 3600
    rdata:
      - v=spf1 include:_spf.example.org -all
    max_retries: 3
    edge_config: ~/.edgerc

- name: Remove an old record set
  silexdata.akamai.edge_dns_recordset:
    zone: example.org
    name: old.example.org
    type: CNAME
    state: absent
    edge_config: ~/.edgerc
'''

RETURN = r'''
---
recordset:
  description:
    - The record set after the task, as Edge DNS returns it. Empty when it does not exist.
    - In check mode, the record set the task would leave.
  type: dict
  returned: always
  sample:
    name: www.example.org
    type: A
    ttl: 300
    rdata:
      - 192.0.2.10
      - 192.0.2.11
'''

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
    get_or_none,
    recordset_path,
    same_rdata,
)


def ensure(module, client):
    """Bring the record set to the requested state; return (changed, before, after)."""
    params = module.params
    record_type = params["type"].upper()
    path = recordset_path(params["zone"], params["name"], record_type)
    current = get_or_none(client, path)

    if params["state"] == "absent":
        if current is None:
            return False, {}, {}
        if not module.check_mode:
            client.call("DELETE", path, expect=(204,))
        return True, current, {}

    desired = {
        "name": params["name"],
        "type": record_type,
        "ttl": params["ttl"] if params["ttl"] is not None else (current or {}).get("ttl"),
        "rdata": params["rdata"],
    }
    if current is None:
        if desired["ttl"] is None:
            module.fail_json(msg=f"ttl is required to create the {record_type} record set {params['name']}.")
        after = desired
        if not module.check_mode:
            after = client.call("POST", path, expect=(201,), json=desired)[1] or desired
        return True, {}, after

    if desired["ttl"] == current.get("ttl") and same_rdata(record_type, desired["rdata"], current.get("rdata")):
        return False, current, current

    after = desired
    if not module.check_mode:
        after = client.call("PUT", path, expect=(200,), json=desired)[1] or desired
    return True, current, after


def main():
    argument_spec = {
        "zone": {"required": True, "type": "str"},
        "name": {"required": True, "type": "str"},
        "type": {"required": True, "type": "str"},
        "state": {"type": "str", "choices": ["present", "absent"], "default": "present"},
        "ttl": {"type": "int"},
        "rdata": {"type": "list", "elements": "str"},
    }
    argument_spec.update(AUTH_ARGUMENT_SPEC)
    argument_spec.update(RETRY_ARGUMENT_SPEC)

    module = AnsibleModule(
        argument_spec=argument_spec,
        mutually_exclusive=AUTH_MUTUALLY_EXCLUSIVE,
        required_one_of=AUTH_REQUIRED_ONE_OF,
        required_if=[("state", "present", ["rdata"])],
        supports_check_mode=True,
    )
    check_requirements(module)
    check_retry_params(module)
    if module.params["state"] == "present" and not module.params["rdata"]:
        module.fail_json(msg="rdata must hold at least one record when state=present. To delete, use state=absent.")

    try:
        changed, before, after = ensure(module, AkamaiClient(module.params))
    except AkamaiRequestError as exc:
        module.fail_json(msg=str(exc))
    except AkamaiApiError as exc:
        module.fail_json(msg=str(exc), status=exc.status, response_body=exc.body)

    result = {"changed": changed, "recordset": after}
    if module._diff:
        result["diff"] = {"before": before, "after": after}
    module.exit_json(**result)


if __name__ == "__main__":
    main()
