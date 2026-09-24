<!--
SPDX-FileCopyrightText: Silex Data Solutions
SPDX-License-Identifier: Apache-2.0
-->

# silexdata.akamai

An Ansible collection maintained by Silex Data Solutions.

CI for this repository is **not defined here**. The workflows under
`.github/workflows/` are thin callers; all logic lives in
[silexdata.collection_skeleton](https://github.com/SilexDataTeam/silexdata.collection_skeleton),
which is the single source of truth for collection CI. Fix CI there, not here.

## Rules

@rules/workflow.md
@rules/licensing.md
@rules/testing.md
@rules/ci.md

## Layout

- `plugins/` — modules, lookups, `module_utils/`, `doc_fragments/`
- `tests/unit/` — pytest unit tests
- `tests/integration/targets/` — one target per module, plus the
  `setup_akamai` role every other target depends on
- `changelogs/fragments/` — one fragment per PR (CI enforces this)

## Local checks

```sh
pre-commit run --all-files     # everything CI's Lint job runs
nox                            # every default antsibull-nox session, as CI's "Run extra sanity tests" job runs them
nox -e license-check           # licensing on its own: reuse lint + antsibull-nox's per-file check
nox -e ansible-test-sanity     # sanity tests locally (CI runs these as a matrix)
```

## Setting up this repository

`/setup-collection-repo` applies the GitHub settings a template copy does not
carry: secrets, Pages, branch protection and required checks. See
`rules/workflow.md`.
