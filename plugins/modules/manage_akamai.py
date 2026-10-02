# Copyright: (c) 2024, Silex Data
# SPDX-License-Identifier: Apache-2.0
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: manage_akamai
short_description: Module to use edgerc auth with Edgegrid to interact with the Akamai API
author:
  - Jacob Hudson (@jacob-hudson)
  - Matt Hyclak (@mhyclak-silex)
  - Caleb Denney (@cdenney-silex)
version_added: "1.0.0"
description:
  - Interacts with the Akamai API using the Python EdgeGrid library.

options:
  endpoint:
    description:
      - Endpoint of the URL you wish to interact with
    required: true
    type: str
  method:
    description:
      - HTTP method to perform
    required: true
    choices: [GET, PATCH, POST, PUT]
    type: str
  body:
    description:
      - Additional data to submit with the HTTP request
    required: false
    type: str
  headers:
    description:
      - Additional headers to submit with the HTTP request
    required: false
    type: str
extends_documentation_fragment:
  - silexdata.akamai.auth
'''

EXAMPLES = r'''
---
- name: Gather siteshield maps
  silexdata.akamai.manage_akamai:
    method: GET
    endpoint: "/siteshield/v1/maps"
    edge_auth:
      host: "{{ akamai_api_host }}"
      client_token: "{{ akamai_client_token }}"
      client_secret: "{{ akamai_client_secret }}"
      access_token: "{{ akamai_access_token }}"
'''

RETURN = r'''
---
changed:
  description: Changed status
  type: bool
  returned: always
  sample: false
failed:
  description: Changed status
  type: bool
  returned: always
  sample: false
msg:
  description: Changed status
  type: list
  elements: dict
  returned: always
  sample:
    siteShieldMaps:
      - acknowledgeRequiredBy: 1234567891011
        acknowledged: false
        acknowledgedBy: foo@bar.baz
        acknowledgedOn: 1774378500000
        contacts:
          - foo@bar.baz
        currentCidrs:
          - 192.168.0.0/24
        id: 123456
        latestTicketId: 1234
        mapAlias: Foo SS Map
        mcmMapRuleId: 1234
        proposedCidrs:
          - 192.168.0.0/24
        ruleName: s123.akamai.net
        service: W
        shared: false
        sureRouteName: Foo-Bar-Baz.akasrg.akamai.com
        type: Production
'''

import json
from urllib.parse import urljoin

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.silexdata.akamai.plugins.module_utils.api import (
    AUTH_ARGUMENT_SPEC,
    AUTH_MUTUALLY_EXCLUSIVE,
    AUTH_REQUIRED_ONE_OF,
    check_requirements,
    open_session,
)


def get_request_file(json_file):
    with open(json_file) as j:
        body = json.load(j)

    return body


def authenticate(params, check_mode=False):
    # In check mode, do not contact the API: report a predicted change for
    # write methods and no change for read-only GET requests.
    if check_mode:
        return False, params["method"] != "GET", {}

    s, baseurl = open_session(params)
    endpoint = params["endpoint"]

    method = getattr(s, params["method"].lower())
    headers = {'content-type': 'application/json'}
    url = urljoin(baseurl, endpoint)
    if params["body"] is not None:
        body = get_request_file(params["body"])
        response = method(url, json=body, headers=headers)
    else:
        response = method(url, headers=headers)
    changed = params["method"].upper() != "GET"
    if response.status_code not in [400, 401, 404]:
        return False, changed, response.json()
    else:
        return True, False, response.json()


def main():
    fields = {
        "endpoint": {"required": True, "type": "str"},
        "method": {"required": True, "type": "str", "choices": ["GET", "PATCH", "POST", "PUT"]},
        "body": {"required": False, "type": "str"},
        "headers": {"required": False, "type": "str"},
    }
    fields.update(AUTH_ARGUMENT_SPEC)

    module = AnsibleModule(
        argument_spec=fields,
        mutually_exclusive=AUTH_MUTUALLY_EXCLUSIVE,
        required_one_of=AUTH_REQUIRED_ONE_OF,
        supports_check_mode=True,
    )

    check_requirements(module)

    is_error, has_changed, result = authenticate(module.params, module.check_mode)

    if not is_error:
        module.exit_json(changed=has_changed, msg=result)
    else:
        module.fail_json(msg=result)


if __name__ == "__main__":
    main()
