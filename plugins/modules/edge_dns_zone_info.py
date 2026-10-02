#!/usr/bin/python

# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: edge_dns_zone_info
short_description: Get Akamai Edge DNS zones
version_added: 2.1.0
author:
  - Caleb Denney (@cdenney-silex)
description:
  - Returns one Akamai Edge DNS zone, or every zone the API client can see, optionally filtered.
  - Reads every page of the listing, so the result is complete however many zones there are.
options:
  zone:
    description:
      - Name of one zone to return. When set, the filters below are ignored.
    type: str
  contract_ids:
    description:
      - Return only zones in these contracts.
    type: list
    elements: str
  types:
    description:
      - Return only zones of these types.
    type: list
    elements: str
    choices: [PRIMARY, SECONDARY, ALIAS]
  search:
    description:
      - Return only zones whose name contains this text.
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
  - module: silexdata.akamai.edge_dns_zone
'''

EXAMPLES = r'''
---
- name: Get one zone
  silexdata.akamai.edge_dns_zone_info:
    zone: example.org
    edge_config: ~/.edgerc
  register: example_org

- name: List the primary zones in a contract
  silexdata.akamai.edge_dns_zone_info:
    contract_ids: [1-ABCDE]
    types: [PRIMARY]
    edge_config: ~/.edgerc
  register: primary_zones
'''

RETURN = r'''
---
zones:
  description:
    - The zones, as Edge DNS returns them. With O(zone), a list of one zone, or empty if it does not exist.
  type: list
  elements: dict
  returned: always
  sample:
    - zone: example.org
      type: PRIMARY
      signAndServe: false
      contractId: 1-ABCDE
      activationState: ACTIVE
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
from ansible_collections.silexdata.akamai.plugins.module_utils.edge_dns import ZONES, get_or_none, paginate, zone_path


def main():
    argument_spec = {
        "zone": {"type": "str"},
        "contract_ids": {"type": "list", "elements": "str"},
        "types": {"type": "list", "elements": "str", "choices": ["PRIMARY", "SECONDARY", "ALIAS"]},
        "search": {"type": "str"},
    }
    argument_spec.update(AUTH_ARGUMENT_SPEC)
    argument_spec.update(RETRY_ARGUMENT_SPEC)

    module = AnsibleModule(
        argument_spec=argument_spec,
        mutually_exclusive=AUTH_MUTUALLY_EXCLUSIVE,
        required_one_of=AUTH_REQUIRED_ONE_OF,
        supports_check_mode=True,
    )
    check_requirements(module)
    check_retry_params(module)
    params = module.params

    try:
        client = AkamaiClient(params)
        if params["zone"]:
            zone = get_or_none(client, zone_path(params["zone"]))
            zones = [zone] if zone is not None else []
        else:
            query = {}
            if params["contract_ids"]:
                query["contractIds"] = ",".join(params["contract_ids"])
            if params["types"]:
                query["types"] = ",".join(params["types"])
            if params["search"]:
                query["search"] = params["search"]
            zones = paginate(client, ZONES, "zones", query)
    except AkamaiRequestError as exc:
        module.fail_json(msg=str(exc))
    except AkamaiApiError as exc:
        module.fail_json(msg=str(exc), status=exc.status, response_body=exc.body)

    module.exit_json(changed=False, zones=zones)


if __name__ == "__main__":
    main()
