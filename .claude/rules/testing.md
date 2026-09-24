<!--
SPDX-FileCopyrightText: Silex Data Solutions
SPDX-License-Identifier: Apache-2.0
-->

# Testing rules

Source of truth: `silexdata.collection_skeleton`. Change it there, not here.

## Every plugin gets tests

For each module or plugin `plugins/<plugin_type>/<name>.py`, also add:

- a unit test at `tests/unit/plugins/<plugin_type>/test_<name>.py`, and
- an integration test target at `tests/integration/targets/<name>/` that
  depends on the collection's `setup_<collection>` role.

Keep `plugins/` to Python: antsibull-nox's `no-unwanted-files` check (part of
`extra-checks`) rejects anything else under it, READMEs and `.gitkeep`s
included.

The YAML inside a plugin's `DOCUMENTATION`, `EXAMPLES` and `RETURN` strings is
linted against `.yamllint` (the `yamllint` session's plugin half), so each
block starts with `---` and keeps lines within 160 columns, like any other YAML
file in the repo.

## The `setup_<collection>` role

Every collection has exactly one `tests/integration/targets/setup_<name>/`
role. It is responsible for two things and no others:

1. Initialising/normalising the variables the tests depend on.
2. Probing whether the live service is reachable, and recording the result in
   `setup_<name>_service_available`.

Every `manage_*` / module target declares it as a dependency in
`meta/main.yml`:

```yaml
dependencies:
  - setup_<name>
```

## Unavailable service: skip by default, fail on demand

When the service is down the default is to **skip** the live tests and emit a
warning, not to fail. `setup_<name>_require_service` (default `false`) flips
that to a hard failure so a pipeline can demand real coverage.

The warning must surface as a **native CI annotation**. An Ansible
`debug`/`assert` message is not printed at column 0, so it is never parsed as a
workflow command. Use the marker-token bridge:

- The setup role prints the stable token `SETUP_SERVICE_UNAVAILABLE` in its
  message.
- CI runs the tests with `set -o pipefail`, tees to a log outside the repo
  tree, then greps that log and emits `::warning title=...::`.

This is already wired up in the shared `reusable-coverage.yml`; a collection
only has to print the token.

## "Dry run" is not "make it pass"

Gating applies **only** to genuinely service-dependent tests. Argument
validation, check-mode behaviour and return-value shape must always run and
must fail for real. Never coerce a test into passing because a service is
unavailable.

## Variable prefixing

- A role owns only variables prefixed with its own name: `setup_<name>_*` in
  the setup role, `manage_<name>_*` in a manage role.
- A `manage_*` role **must not read a `setup_*` variable directly.** Inherit it
  in `defaults/main.yml` instead:

  ```yaml
  manage_<name>_edge_auth: "{{ setup_<name>_edge_auth }}"
  ```

  and have tasks reference only the `manage_*` names.

## Target layout

`tasks/main.yml` performs no tests itself — only role initialisation not
already done by the setup role. It loops over the real test files:

```yaml
- name: Run the test suites
  ansible.builtin.include_tasks: "{{ item }}"
  loop: "{{ query('fileglob', 'tests/*.yml') | sort }}"
```

`tasks/tests/` holds the tests, grouped one file per category, named for the
category: `expected-failures.yml`, `check-mode.yml`,
`expected-return-values.yml`.

## Check mode

Write check-mode tests **assuming the module supports check mode** — assert it
runs and makes no changes. Never make them conditional on whether the module
currently declares support: the test failing is exactly how missing support
gets surfaced.
