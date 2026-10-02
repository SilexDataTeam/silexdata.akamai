# manage_akamai integration target

This target validates the `silexdata.akamai.manage_akamai` module. Tests are
grouped by category under `tasks/tests/`; `tasks/main.yml` simply discovers and
runs every file there.

## Test categories

- `expected-failures.yml` — validation that happens before any request is sent:
  the argument spec (`required_one_of`, `mutually_exclusive`, required params,
  choices) and the request body. Service-independent; always runs.
- `check-mode.yml` — asserts every method runs in check mode, sends nothing and
  reports a change only for write methods, and that a body file works through
  `src` and (deprecated) through `body`. Service-independent; fails if the
  module does not support check mode.
- `expected-return-values.yml` — **live**, service-dependent checks of the data
  returned by the API. Skipped when the service is unavailable.

## Service availability

The `setup_akamai` role (a dependency declared in `meta/main.yml`) probes the
Akamai API and sets `setup_akamai_service_available`. Live test blocks are gated
on this flag.

- **Service down (default):** live tests are skipped and a warning is emitted.
- **Service down with `setup_akamai_require_service: true`:** the run fails.

Only tests that genuinely require the service are skipped when it is down; all
other tests still run and are expected to fail on real problems.

## Running locally

From within the collection path (`.../ansible_collections/silexdata/akamai`):

```bash
ansible-test integration manage_akamai --docker -v --requirements
```

To run the live tests, copy `tests/integration/integration_config.yml.template`
to `tests/integration/integration_config.yml` and supply real credentials.
