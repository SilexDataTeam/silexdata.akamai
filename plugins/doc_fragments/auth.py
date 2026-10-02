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
requirements:
  - requests
  - edgegrid-python
'''
