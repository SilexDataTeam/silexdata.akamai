<!--
SPDX-FileCopyrightText: Silex Data Solutions
SPDX-License-Identifier: Apache-2.0
-->

# Development workflow

Source of truth: `silexdata.collection_skeleton`. Change it there, not here.

## Every change goes through a pull request

1. Branch from an up-to-date default branch: `git switch main && git pull`,
   then `git switch -c <type>/<short-description>` (e.g. `feature/add-foo`,
   `bugfix/timeout-handling`).
2. Commit with Conventional Commit messages.
3. Add or extend a changelog fragment under `changelogs/fragments/` - the
   Changelog check fails a PR without one.
4. Push the branch and open a PR: `git push -u origin HEAD`, then
   `gh pr create`.
5. Merge only when every required check has passed. Do not bypass them.

**Never push directly to the default branch.** Branch protection enforces this
once `/setup-collection-repo` has run. The only exception is the release
identity (the owner of `RELEASE_TOKEN`), which the release workflow uses to push
its release commit and tag.

## What a merge triggers

Merging a PR runs the release workflow, which decides from the pending
changelog fragments whether to cut a release:

| Collection version | Fragments in the merge | Result |
|---|---|---|
| any | only `trivial` / `release_summary` | nothing released |
| below 1.0.0 | anything without `major_changes` | nothing released - fragments accumulate |
| below 1.0.0 | includes `major_changes` | **1.0.0** is released, covering everything accumulated |
| 1.0.0 or above | `breaking_changes`, `major_changes`, `removed_features` | major bump |
| 1.0.0 or above | `minor_changes` | minor bump |
| 1.0.0 or above | anything else | patch bump |

A new collection starts at 0.0.1, so its first release is always exactly
1.0.0, cut deliberately. To cut it, merge a PR carrying a fragment like:

```yaml
release_summary: Initial release of the collection.
major_changes:
  - Initial release.
```

Until the `RELEASE_TOKEN` and `GALAXY_API_KEY` secrets are configured, the
release workflow skips with a notice instead of publishing.

## Resuming a failed release

Once the release commit and tag are pushed, re-running the job cannot finish
it: the fragments were consumed into the changelog, so it would find nothing to
release. Instead, fix the cause (a bad `GALAXY_API_KEY`, say), then open
Actions > **Release** > **Run workflow** and enter the tag. It builds from the
tag, publishes to Galaxy only if that version is not there yet, and creates
the GitHub release only if it is missing - so it is safe to run again. A
release that fails before the tag is pushed pushes nothing: re-run the failed
job instead. When the tag was pushed, the failed run ends with an error naming
the tag to resume with.

## Setting up a new repository

After the **Bootstrap collection** workflow has run, clone the repository over
SSH and run `/setup-collection-repo` in Claude Code. It removes the
template-only workflows, stores the release secrets without exposing them,
enables GitHub Pages and protects the default branch. After the first PR's CI
has passed, it also locks in the required checks.
