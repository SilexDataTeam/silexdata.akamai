<!--
SPDX-FileCopyrightText: Silex Data Solutions
SPDX-License-Identifier: Apache-2.0
-->

# CI rules

Source of truth: `silexdata.collection_skeleton`. Change it there, not here.

## How CI is wired

`.github/workflows/` in this repo contains **thin callers only**. Each one
delegates to a reusable workflow hosted on the orphan `ci` branch of
[silexdata.collection_skeleton](https://github.com/SilexDataTeam/silexdata.collection_skeleton/tree/ci):

```yaml
jobs:
  lint:
    uses: SilexDataTeam/silexdata.collection_skeleton/.github/workflows/reusable-lint.yml@v1
```

| Caller | Delegates to | Does |
|---|---|---|
| `lint.yml` | `reusable-lint.yml` | pre-commit over all files |
| `nox.yml` | `reusable-nox.yml` | every default antsibull-nox session (licensing, docs, build/import, lint) plus ansible-test sanity and units across the ansible-core matrix |
| `coverage.yml` | `reusable-coverage.yml` | ansible-test units + integration across the ansible-core matrix, aggregated |
| `docs.yml` | `reusable-docs.yml` | antsibull-docs site + coverage report → GitHub Pages |
| `changelog.yml` | `reusable-changelog.yml` | requires a changelog fragment on every PR |
| `release.yml` | `reusable-release.yml` | version bump, changelog, tag, publish to Galaxy |
| `sync-rules.yml` | `reusable-sync-rules.yml` | weekly: keeps the skeleton-managed files identical to the skeleton's and proposes any drift as a PR |

**To change CI behaviour, edit the `ci` branch of the skeleton repo and move
the tag.** Do not fork logic into this repo — it will drift silently.
Dependabot bumps the `@v1` pins here when a new major ships.

The Nox workflow uses antsibull-nox's two reusable workflows, as
community.sops does. "Run extra sanity tests" runs every *default* session:
`lint`, `docs-check`, `license-check`, `extra-checks`, `build-import-check`,
`ansible-lint`. The matrix jobs run the ansible-test sessions. Keep the
ansible-test sessions at `default = false` in `antsibull-nox.toml` - the
matrix runs them anyway, and marking them default would make the extra job
repeat the whole matrix, so the Nox workflow fails if any of them - or
`ee_check` - is set `default = true`. To enforce something new, make it a default nox
session.

## Required checks

Branch protection requires these five, and nothing else:

- `lint / pre-commit (lint)`
- `nox / Nox result`
- `coverage / Coverage result`
- `docs / Build collection documentation`
- `changelog / Require a changelog fragment`

`Nox result` and `Coverage result` are dedicated gate jobs. They exist because
GitHub reports a **skipped** job as *passing* a required check, and because the
matrix legs have names that change with the ansible-core matrix. Each gate runs
`if: always()` and fails explicitly unless everything it depends on succeeded.
Never require a matrix leg, or any job that is skipped on failure.

## What is detected, not configured

Do not hardcode these in a caller; they are read at run time:

- **namespace / name** — from `galaxy.yml`.
- **minimum ansible-core** — from `meta/runtime.yml`'s `requires_ansible`, for
  both the Nox matrix and the Coverage matrix. To change the floor, edit that
  file.
- **release tarball name** — derived from `galaxy.yml`.

## Skeleton-managed files are synced, not edited here

The files the skeleton repo's `sync-manifest.txt` lists are exact copies of
its `skeleton/`: `.claude/` (everything but `CLAUDE.md`), and the shared
tooling configuration - `.pre-commit-config.yaml`, `.yamllint`,
`.ansible-lint`, `.pymarkdown.json`, `.markdownlint.json`, `noxfile.py`,
`pyproject.toml` and `.github/dependabot.yml`. `sync-rules.yml` (**Sync from
the skeleton**) runs weekly, and on demand from the Actions tab: it copies
them, mirroring `.claude/` and deleting what the skeleton no longer has, and
commits the result with a `trivial` changelog fragment to the `sync/skeleton`
branch.

- It opens a PR from that branch. Whenever the sync pushes to it, the PR's CI
  runs wait for a maintainer to select **Approve workflows to run** in the
  merge box - GitHub's rule for pushes made with `GITHUB_TOKEN`.
- Where the organization forbids GitHub Actions from creating PRs, the run
  instead warns with a link that opens the PR in one click. A PR a human opens
  runs CI straight away.

So change any of these in the skeleton repo; an edit made here is reverted by
the next sync. If code trips a lint or ruff rule, fix the code rather than
loosening the shared configuration. `CLAUDE.md` is this collection's own - put
collection-specific guidance there - as are `antsibull-nox.toml`,
`tests/config.yml`, `galaxy.yml`, the README and the docs.

## Secrets

Only the release path needs secrets. Everything else runs on the automatic
`GITHUB_TOKEN`. Both are optional: until both are configured, the release
workflow skips with a notice rather than failing. Set them with
`/setup-collection-repo`, which never exposes the values.

| Secret | Needed by | Why |
|---|---|---|
| `RELEASE_TOKEN` | `release.yml` | pushes the release commit/tag past branch protection |
| `GALAXY_API_KEY` | `release.yml` | publishes to Ansible Galaxy |

## A constraint worth knowing

`GITHUB_TOKEN` is **categorically forbidden** from creating, updating or
deleting anything under `.github/workflows/`, and no `permissions:` key can
grant it — there is no `workflows:` key. Any automation that needs to rewrite
workflow files requires a PAT with `workflow` scope, or must be run locally
over SSH (SSH pushes are not subject to the restriction).

## Changelog fragments

Every PR needs one under `changelogs/fragments/`. CI checks for an added *or
modified* fragment, so extending an existing one counts.

```yaml
# changelogs/fragments/my-change.yml
minor_changes:
  - my_module - add support for X (https://github.com/.../pull/42).
```

Sections that do not trigger a release on their own: `trivial`,
`release_summary`. Below 1.0.0 nothing is released at all until a
`major_changes` fragment cuts 1.0.0 - see `workflow.md`.
