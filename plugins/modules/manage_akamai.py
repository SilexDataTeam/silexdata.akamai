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
  - Sends one request to an Akamai API, signed with the Python EdgeGrid library, and returns the response.
  - The response body is returned in RV(msg) as parsed JSON, as V({}) when it is empty (for example
    C(204 No Content)), or as text when it is not JSON (for example a C(text/dns) zone file).
options:
  endpoint:
    description:
      - Path of the API endpoint, for example C(/config-dns/v2/zones). It is joined to the host from
        O(edge_auth) or O(edge_config).
      - It may include a query string, but O(query) is easier to read and encodes values for you.
    required: true
    type: str
  method:
    description:
      - HTTP method to use.
      - V(DELETE) and V(HEAD) were added in 1.2.0.
    required: true
    choices: [GET, HEAD, DELETE, PATCH, POST, PUT]
    type: str
  query:
    description:
      - Query parameters to add to the request, for example C(contractId) and C(gid) when creating an Edge DNS zone.
    required: false
    type: dict
    version_added: 1.2.0
  body:
    description:
      - Body of the request.
      - With O(body_format=json), a dictionary or list is sent as JSON, and a string must be JSON text.
      - With O(body_format=raw), the body must be a string and is sent exactly as given.
      - Before 2.0.0, a string that was the path of an existing file was read as a JSON file. Use O(src) for files.
      - Mutually exclusive with O(src).
    required: false
    type: raw
  src:
    description:
      - Path of a file to send as the body of the request.
      - With O(body_format=json), the file must contain JSON. With O(body_format=raw), it is sent unchanged.
      - Mutually exclusive with O(body).
    required: false
    type: path
    version_added: 1.2.0
  body_format:
    description:
      - How to send O(body) or O(src).
      - V(json) sends JSON with a default C(Content-Type) of C(application/json).
      - V(raw) sends the body unchanged and sets no C(Content-Type). Set one in O(headers), for example
        C(text/dns) to upload an Edge DNS zone file.
    required: false
    choices: [json, raw]
    default: json
    type: str
    version_added: 1.2.0
  headers:
    description:
      - Additional headers to submit with the HTTP request, for example C(Accept), C(If-Match) or C(PAPI-Use-Prefixes).
      - Header names are case-insensitive. A header given here replaces the module's default of the same name,
        such as C(Content-Type).
      - Before 1.2.0 this option was accepted but ignored.
    required: false
    type: dict
  status_code:
    description:
      - HTTP status codes that count as success. Any other status fails the task.
      - Use it to accept an expected error, for example V([201, 409]) to treat "zone already exists" as success.
      - If not set, every status below 400 succeeds and every status of 400 or above fails.
      - Before 2.0.0, only V(400), V(401) and V(404) failed when this was not set.
    required: false
    type: list
    elements: int
    version_added: 1.2.0
extends_documentation_fragment:
  - silexdata.akamai.auth
  - silexdata.akamai.retries
attributes:
  check_mode:
    description: Can run in check mode and return a change prediction without modifying the target.
    support: full
    details:
      - No request is sent. A change is reported for every method except V(GET) and V(HEAD).
  diff_mode:
    description: Returns details of what changed, or would change in check mode, when run in diff mode.
    support: none
notes:
  - The module reports a change for every successful request except V(GET) and V(HEAD). It does not compare state
    first, so it is not idempotent.
seealso:
  - name: Akamai API documentation
    description: Reference for every Akamai API this module can call.
    link: https://techdocs.akamai.com/home/page/products-tools-a-z
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

- name: Create an Edge DNS primary zone, accepting one that already exists
  silexdata.akamai.manage_akamai:
    method: POST
    endpoint: /config-dns/v2/zones
    query:
      contractId: "{{ akamai_contract_id }}"
      gid: "{{ akamai_group_id }}"
    body:
      zone: example.org
      type: PRIMARY
      comment: Managed by Ansible
    status_code: [201, 409]
    edge_config: ~/.edgerc

- name: Add record sets to the zone (Akamai answers 204 No Content)
  silexdata.akamai.manage_akamai:
    method: POST
    endpoint: /config-dns/v2/zones/example.org/recordsets
    body:
      recordsets:
        - name: www.example.org
          type: A
          ttl: 300
          rdata: [192.0.2.10]
    status_code: [204]
    edge_config: ~/.edgerc

- name: Upload a zone file
  silexdata.akamai.manage_akamai:
    method: POST
    endpoint: /config-dns/v2/zones/example.org/zone-file
    src: files/example.org.zone
    body_format: raw
    headers:
      Content-Type: text/dns
    status_code: [204]
    edge_config: ~/.edgerc

- name: Delete a record set
  silexdata.akamai.manage_akamai:
    method: DELETE
    endpoint: /config-dns/v2/zones/example.org/names/www.example.org/types/A
    status_code: [204]
    edge_config: ~/.edgerc

- name: List Property Manager contracts for another account
  silexdata.akamai.manage_akamai:
    method: GET
    endpoint: /papi/v1/contracts
    headers:
      PAPI-Use-Prefixes: "true"
    account_switch_key: "{{ akamai_account_switch_key }}"
    edge_config: ~/.edgerc
'''

RETURN = r'''
---
msg:
  description:
    - On success, the response body. Parsed JSON when the response is JSON, V({}) when the body is empty, otherwise
      the text. V({}) in check mode.
    - "On failure, a description of the error, such as C(HTTP 409 Conflict: Zone already exists). The error body itself
      is in RV(response_body). Before 2.0.0, a failure's RV(msg) was the error body."
  type: raw
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
response_body:
  description:
    - The response body, on success and on failure. Parsed JSON when the response is JSON, V({}) when the body is
      empty, otherwise the text. Akamai error bodies are usually RFC 9457 problem details objects, with C(type),
      C(title), C(detail) and C(status).
  type: raw
  returned: when a request was sent
  sample:
    type: https://problems.luna.akamaiapis.net/config-dns/v2/ZONE_ALREADY_EXISTS
    title: Zone already exists
    detail: Zone example.org already exists
    status: 409
  version_added: 2.0.0
status:
  description: HTTP status code of the response.
  type: int
  returned: when a request was sent
  sample: 201
  version_added: 1.2.0
url:
  description: URL the request was sent to, including the query string.
  type: str
  returned: when a request was sent
  sample: https://akab-xxxxxxxx.luna.akamaiapis.net/config-dns/v2/zones?contractId=1-ABCDE&gid=12345
  version_added: 1.2.0
attempts:
  description: How many times the request was sent, counting retries.
  type: int
  returned: when a request was sent
  sample: 1
  version_added: 1.2.0
response_headers:
  description:
    - Headers of the response, for example C(Location) for a created resource or C(ETag) for a later C(If-Match).
  type: dict
  returned: when a request was sent
  sample:
    Content-Type: application/json
    Location: /config-dns/v2/zones/example.org
  version_added: 1.2.0
'''

import json

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.silexdata.akamai.plugins.module_utils.api import (
    AUTH_ARGUMENT_SPEC,
    AUTH_MUTUALLY_EXCLUSIVE,
    AUTH_REQUIRED_ONE_OF,
    RETRY_ARGUMENT_SPEC,
    AkamaiClient,
    AkamaiRequestError,
    check_requirements,
    check_retry_params,
    describe_failure,
    merge_headers,
    parse_response_body,
)

READ_ONLY_METHODS = ("GET", "HEAD")


def build_body(module):
    """Return the requests keyword (json= or data=) carrying the request body."""
    body = module.params["body"]
    src = module.params["src"]
    body_format = module.params["body_format"]

    if src is not None:
        try:
            with open(src, "rb") as f:
                content = f.read()
        except OSError as exc:
            module.fail_json(msg=f"Cannot read src {src}: {exc}")
        if body_format == "raw":
            return {"data": content}
        try:
            return {"json": json.loads(content)}
        except ValueError as exc:
            module.fail_json(msg=f"src {src} is not valid JSON: {exc}")

    if body is None:
        return {}

    if body_format == "raw":
        if not isinstance(body, str):
            module.fail_json(msg=f"body_format=raw needs body to be a string, not {type(body).__name__}.")
        return {"data": body.encode("utf-8")}

    if isinstance(body, str):
        try:
            return {"json": json.loads(body)}
        except ValueError as exc:
            module.fail_json(msg=f"body is a string that is not valid JSON: {exc}. To send a file, use src.")

    return {"json": body}


def build_request(module):
    """Return the keyword arguments for the request, validating the body."""
    params = module.params
    kwargs = build_body(module)
    defaults = {"content-type": "application/json"} if params["body_format"] == "json" else {}
    kwargs["headers"] = merge_headers(defaults, params["headers"])
    if params["query"]:
        kwargs["params"] = params["query"]
    return kwargs


def request_failed(module, status):
    """Whether a status fails the task: any status outside status_code, else any of 400 or above."""
    if module.params["status_code"]:
        return status not in module.params["status_code"]
    return status >= 400


def main():
    fields = {
        "endpoint": {"required": True, "type": "str"},
        "method": {"required": True, "type": "str", "choices": ["GET", "HEAD", "DELETE", "PATCH", "POST", "PUT"]},
        "query": {"required": False, "type": "dict"},
        "body": {"required": False, "type": "raw"},
        "src": {"required": False, "type": "path"},
        "body_format": {"required": False, "type": "str", "choices": ["json", "raw"], "default": "json"},
        "headers": {"required": False, "type": "dict"},
        "status_code": {"required": False, "type": "list", "elements": "int"},
    }
    fields.update(AUTH_ARGUMENT_SPEC)
    fields.update(RETRY_ARGUMENT_SPEC)

    module = AnsibleModule(
        argument_spec=fields,
        mutually_exclusive=AUTH_MUTUALLY_EXCLUSIVE + [("body", "src")],
        required_one_of=AUTH_REQUIRED_ONE_OF,
        supports_check_mode=True,
    )

    check_requirements(module)
    check_retry_params(module)

    method = module.params["method"]
    kwargs = build_request(module)

    # In check mode, do not contact the API: report a predicted change for
    # write methods and no change for read-only requests.
    if module.check_mode:
        module.exit_json(changed=method not in READ_ONLY_METHODS, msg={})

    client = AkamaiClient(module.params)
    try:
        response = client.request(method, module.params["endpoint"], **kwargs)
    except AkamaiRequestError as exc:
        module.fail_json(msg=str(exc), attempts=client.attempts)

    body = parse_response_body(response)
    result = {
        "msg": body,
        "response_body": body,
        "status": response.status_code,
        "url": response.url,
        "attempts": client.attempts,
        "response_headers": dict(response.headers),
    }

    if request_failed(module, response.status_code):
        result["msg"] = describe_failure(response, body)
        module.fail_json(**result)

    module.exit_json(changed=method not in READ_ONLY_METHODS, **result)


if __name__ == "__main__":
    main()
