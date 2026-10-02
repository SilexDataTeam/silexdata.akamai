# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment:
    # Retry options shared by every module that sends requests.
    DOCUMENTATION = r'''
---
options:
  max_retries:
    description:
      - How many times to resend a request that got a status listed in O(retry_on_status). V(0) never retries.
      - The wait before each retry doubles, starting from O(retry_delay), with random jitter, and never exceeds
        O(retry_max_delay). A longer C(Retry-After) header from the API is honoured, up to O(retry_max_delay).
      - Requests that fail without a response, such as connection errors, are not retried.
    required: false
    type: int
    default: 0
    version_added: 1.2.0
  retry_on_status:
    description:
      - HTTP statuses that are retried when O(max_retries) is above V(0).
      - Akamai answers V(429) when a rate limit is exceeded and V(503) when the service is unavailable.
      - Property Manager (PAPI) answers V(403) when its per-IP request rate limit is exceeded, and blocks the address
        for 10 minutes, a block that grows if requests continue. In every other case V(403) means the API client
        lacks permission and a retry cannot help. If you add V(403) here, each wait after a V(403) is at least
        600 seconds, whatever O(retry_max_delay) says.
    required: false
    type: list
    elements: int
    default: [429, 503]
    version_added: 1.2.0
  retry_delay:
    description:
      - Seconds to wait before the first retry. Each later retry waits twice as long as the one before.
    required: false
    type: float
    default: 5
    version_added: 1.2.0
  retry_max_delay:
    description:
      - The longest wait between two attempts, in seconds.
    required: false
    type: float
    default: 600
    version_added: 1.2.0
seealso:
  - name: Property Manager rate and resource limits
    description: Akamai's documentation of the PAPI rate limits and the 10-minute block.
    link: https://techdocs.akamai.com/property-mgr/reference/rate-and-resource-limiting
'''
