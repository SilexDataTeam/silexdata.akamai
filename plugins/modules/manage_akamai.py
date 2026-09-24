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
  section:
    description:
      - Section of the edgerc file to parse.
    required: false
    default: default
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
  edge_config:
    description:
      - Path to the edgerc file with authentication details
    required: false
    type: path
  edge_auth:
    description:
      - Dictionary containing host, client_token, client_secret and access_token
    required: false
    type: dict
    suboptions:
      host:
        description: Akamai API host.
        required: true
        type: str
      client_token:
        description: EdgeGrid client token.
        required: true
        type: str
      client_secret:
        description: EdgeGrid client secret.
        required: true
        type: str
      access_token:
        description: EdgeGrid access token.
        required: true
        type: str
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
import traceback
from urllib.parse import urljoin

from ansible.module_utils.basic import AnsibleModule, missing_required_lib

REQUESTS_IMP_ERR = None
try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    REQUESTS_IMP_ERR = traceback.format_exc()

EDGEGRID_IMP_ERR = None
try:
    from akamai.edgegrid import EdgeGridAuth, EdgeRc

    HAS_EDGEGRID = True
except ImportError:
    HAS_EDGEGRID = False
    EDGEGRID_IMP_ERR = traceback.format_exc()


def get_request_file(json_file):
    with open(json_file) as j:
        body = json.load(j)

    return body


def authenticate(params, check_mode=False):
    # In check mode, do not contact the API: report a predicted change for
    # write methods and no change for read-only GET requests.
    if check_mode:
        return False, params["method"] != "GET", {}

    s = requests.Session()

    # values from ansible
    endpoint = params["endpoint"]

    if params["edge_config"]:
        filename = params["edge_config"]

        # extract edgerc properties
        edgerc = EdgeRc(filename)

        # values from ansible
        section = params["section"]

        # creates baseurl for akamai
        baseurl = f"https://{edgerc.get(section, 'host')}"
        s.auth = EdgeGridAuth.from_edgerc(edgerc, section)

    if params["edge_auth"]:
        # creates baseurl for akamai
        baseurl = f"https://{params['edge_auth']['host']}"
        s.auth = EdgeGridAuth(
            client_token=params["edge_auth"]['client_token'],
            client_secret=params["edge_auth"]['client_secret'],
            access_token=params["edge_auth"]['access_token'],
        )

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
        "section": {"required": False, "type": "str", "default": "default"},
        "endpoint": {"required": True, "type": "str"},
        "method": {"required": True, "type": "str", "choices": ["GET", "PATCH", "POST", "PUT"]},
        "body": {"required": False, "type": "str"},
        "headers": {"required": False, "type": "str"},
        "edge_config": {"required": False, "type": "path"},
        "edge_auth": {
            "required": False,
            "type": "dict",
            "options": {
                "host": {"required": True, "type": "str"},
                "client_token": {"required": True, "type": "str", "no_log": True},
                "client_secret": {"required": True, "type": "str", "no_log": True},
                "access_token": {"required": True, "type": "str", "no_log": True},
            },
        },
    }

    required_list = [
        ('edge_config', 'edge_auth'),
    ]

    module = AnsibleModule(argument_spec=fields, mutually_exclusive=required_list, required_one_of=required_list, supports_check_mode=True)

    if not HAS_REQUESTS:
        module.fail_json(msg=missing_required_lib("requests"), exception=REQUESTS_IMP_ERR)

    if not HAS_EDGEGRID:
        module.fail_json(msg=missing_required_lib("edgegrid-python"), exception=EDGEGRID_IMP_ERR)

    is_error, has_changed, result = authenticate(module.params, module.check_mode)

    if not is_error:
        module.exit_json(changed=has_changed, msg=result)
    else:
        module.fail_json(msg=result)


if __name__ == "__main__":
    main()
