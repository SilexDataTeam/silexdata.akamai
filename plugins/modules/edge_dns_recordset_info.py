#!/usr/bin/python

# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: edge_dns_recordset_info
short_description: Get the record sets of an Akamai Edge DNS zone
version_added: 2.1.0
author:
  - Caleb Denney (@cdenney-silex)
description:
  - Returns one record set, or every record set in an Akamai Edge DNS zone, optionally filtered.
  - Reads every page of the listing, so the result is complete however many record sets there are.
options:
  zone:
    description:
      - Name of the zone, for example V(example.org).
    required: true
    type: str
  name:
    description:
      - Return only the record sets with this fully qualified name.
    type: str
  type:
    description:
      - With O(name), return only the record set of this type.
    type: str
  types:
    description:
      - Return only record sets of these types. Ignored when O(type) is set.
    type: list
    elements: str
  search:
    description:
      - Return only record sets whose name or data contains this text.
    type: str
extends_documentation_fragment:
  - silexdata.akamai.auth
  - silexdata.akamai.retries
attributes:
  check_mode:
    description: Can run in check mode and return a change prediction without modifying the target.
    support: full
    details:
      - The module only reads, so it behaves the same in check mode.
  diff_mode:
    description: Returns details of what changed, or would change in check mode, when run in diff mode.
    support: N/A
seealso:
  - module: silexdata.akamai.edge_dns_recordset
'''

EXAMPLES = r'''
---
- name: Get the A record set for www
  silexdata.akamai.edge_dns_recordset_info:
    zone: example.org
    name: www.example.org
    type: A
    edge_config: ~/.edgerc
  register: www

- name: List the zone's MX and TXT record sets
  silexdata.akamai.edge_dns_recordset_info:
    zone: example.org
    types: [MX, TXT]
    edge_config: ~/.edgerc
  register: mail_records
'''

RETURN = r'''
---
recordsets:
  description:
    - The record sets, as Edge DNS returns them. With O(name) and O(type), a list of one, or empty if it does not exist.
  type: list
  elements: dict
  returned: always
  sample:
    - name: www.example.org
      type: A
      ttl: 300
      rdata:
        - 192.0.2.10
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
    paginate,
    recordset_path,
    zone_path,
)


def names_match(left, right):
    return left.lower().rstrip(".") == right.lower().rstrip(".")


def main():
    argument_spec = {
        "zone": {"required": True, "type": "str"},
        "name": {"type": "str"},
        "type": {"type": "str"},
        "types": {"type": "list", "elements": "str"},
        "search": {"type": "str"},
    }
    argument_spec.update(AUTH_ARGUMENT_SPEC)
    argument_spec.update(RETRY_ARGUMENT_SPEC)

    module = AnsibleModule(
        argument_spec=argument_spec,
        mutually_exclusive=AUTH_MUTUALLY_EXCLUSIVE,
        required_one_of=AUTH_REQUIRED_ONE_OF,
        required_by={"type": "name"},
        supports_check_mode=True,
    )
    check_requirements(module)
    check_retry_params(module)
    params = module.params

    try:
        client = AkamaiClient(params)
        if params["name"] and params["type"]:
            recordset = get_or_none(client, recordset_path(params["zone"], params["name"], params["type"].upper()))
            recordsets = [recordset] if recordset is not None else []
        else:
            query = {}
            if params["types"]:
                query["types"] = ",".join(t.upper() for t in params["types"])
            # The API's search matches substrings, so narrow by name with it
            # and keep exact matches below.
            if params["search"] or params["name"]:
                query["search"] = params["search"] or params["name"]
            recordsets = paginate(client, f"{zone_path(params['zone'])}/recordsets", "recordsets", query)
            if params["name"]:
                recordsets = [r for r in recordsets if names_match(r.get("name", ""), params["name"])]
    except AkamaiRequestError as exc:
        module.fail_json(msg=str(exc))
    except AkamaiApiError as exc:
        module.fail_json(msg=str(exc), status=exc.status, response_body=exc.body)

    module.exit_json(changed=False, recordsets=recordsets)


if __name__ == "__main__":
    main()
