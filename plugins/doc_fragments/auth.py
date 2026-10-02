# Copyright (c) 2024-2026, Silex Data Solutions <info@silexdata.com>
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)
# SPDX-FileCopyrightText: 2024-2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment:
    # EdgeGrid authentication options shared by every module in the collection.
    DOCUMENTATION = r'''
---
options:
  section:
    description:
      - Section of the edgerc file to parse.
    required: false
    default: default
    type: str
  edge_config:
    description:
      - Path to the edgerc file with authentication details.
      - Mutually exclusive with O(edge_auth); one of the two is required.
    required: false
    type: path
  edge_auth:
    description:
      - Dictionary containing host, client_token, client_secret and access_token.
      - Mutually exclusive with O(edge_config); one of the two is required.
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
  account_switch_key:
    description:
      - Account switch key, for an API client that manages more than one account (for example a partner or Akamai
        internal client). It is sent as the C(accountSwitchKey) query parameter on every request, unless the request
        already sets that parameter.
      - If not set, the E(AKAMAI_ACCOUNT_KEY) environment variable is used, then C(account_key) in the O(edge_config)
        section, as Akamai's EdgeGrid documentation describes.
      - A few Akamai APIs do not accept C(accountSwitchKey). Leave this unset for those.
    required: false
    type: str
    version_added: 1.2.0
requirements:
  - requests
  - edgegrid-python
'''
