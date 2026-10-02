# manage_akamai Module

Ansible module that sends one request to an Akamai API, signed with
EdgeGrid, and returns the response. The full option and return-value
reference is in the
[collection documentation](https://silexdatateam.github.io/silexdata.akamai/).

## Prerequisites

- Python 3.6 or later on the host that runs the module (usually the
  controller, with `delegate_to: localhost`).
- The `requests` and `edgegrid-python` Python packages
  (`pip install requests edgegrid-python`).

## Install

- Install the collection from Ansible Galaxy:

  ```shell
  ansible-galaxy collection install silexdata.akamai
  ```

- Or install directly from the source repository:

  ```shell
  ansible-galaxy collection install git+https://github.com/SilexDataTeam/silexdata.akamai.git
  ```

- Once installed, invoke the module by its fully qualified collection name, `silexdata.akamai.manage_akamai`

## Credentials

Akamai API client credentials are required. See Akamai's
[Create authentication credentials](https://techdocs.akamai.com/developer/docs/set-up-authentication-credentials).

Pass them in one of two ways:

- `edge_config` - the path of an `.edgerc` file, with `section` naming the
  section to use (default `default`).
- `edge_auth` - a dictionary with `host`, `client_token`, `client_secret`
  and `access_token`.

An API client that manages several accounts sets `account_switch_key`. If
that is not set, the module uses the `AKAMAI_ACCOUNT_KEY` environment
variable, then `account_key` in the `.edgerc` section.

## Options

| Option | Purpose |
| --- | --- |
| `endpoint` | API path, such as `/config-dns/v2/zones` |
| `method` | `GET`, `HEAD`, `DELETE`, `PATCH`, `POST` or `PUT` |
| `query` | Query parameters, such as `contractId` and `gid` |
| `body` | Request body: a dictionary or list sent as JSON, or a string |
| `src` | File to send as the request body instead of `body` |
| `body_format` | `json` (default) or `raw`, which sends the body unchanged |
| `headers` | Extra request headers, such as `If-Match` or `PAPI-Use-Prefixes` |
| `status_code` | HTTP statuses that count as success; without it, every status of 400 or above fails |
| `max_retries`, `retry_on_status`, `retry_delay`, `retry_max_delay` | Retry rate-limited (`429`) and unavailable (`503`) responses with backoff |

The response body comes back in `msg` and `response_body`: parsed JSON,
`{}` when the body is empty (for example `204 No Content`), or text when it
is not JSON. On failure, `msg` describes the error instead. The module also
returns `status`, `url`, `attempts` and `response_headers`.

## Example: an Edge DNS zone

```yaml
- name: Create the zone, accepting one that already exists
  silexdata.akamai.manage_akamai:
    method: POST
    endpoint: /config-dns/v2/zones
    query:
      contractId: "{{ akamai_contract_id }}"
      gid: "{{ akamai_group_id }}"
    body:
      zone: example.org
      type: PRIMARY
    status_code: [201, 409]
    edge_config: ~/.edgerc

- name: Add record sets
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
    max_retries: 3
    edge_config: ~/.edgerc
```

## Upgrading from 1.x to 2.0.0

| 1.x | 2.0.0 |
| --- | --- |
| `body: /path/to/file.json` read the file | `src: /path/to/file.json`; a string `body` is the body itself |
| Without `status_code`, only `400`, `401` and `404` failed | Without `status_code`, every status of 400 or above fails |
| A failed task's `msg` was the error body | A failed task's `msg` describes the error, such as `HTTP 409 Conflict: Zone already exists`; the error body is in `response_body` |
| `silexdata.akamai.akamai` redirected to `manage_akamai` | `silexdata.akamai.akamai` is removed; use `silexdata.akamai.manage_akamai` |

1.2.0 warns about the first two wherever a task relies on them, so a
playbook that runs on 1.2.0 without deprecation warnings needs only the
last two rows checked.

## Acknowledgements

- The Akamai Technologies [api-kickstart](https://github.com/akamai/api-kickstart) repository where many other Akamai API examples are available!
- The Akamai API documentation: <https://techdocs.akamai.com/home/page/products-tools-a-z>
- Jacob Hudson (@jacob-hudson) for the initial work on the library.
