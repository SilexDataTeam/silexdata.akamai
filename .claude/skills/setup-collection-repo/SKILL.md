---
name: setup-collection-repo
description: >-
  One-time GitHub setup for a silexdata.* collection repository after the
  Bootstrap collection workflow has run - removes the template-only workflows,
  stores the release secrets without exposing them, enables GitHub Pages, lets
  the skeleton sync open its PRs, protects the default branch, and later locks in
  the required CI checks. Also used to rotate RELEASE_TOKEN or GALAXY_API_KEY.
disable-model-invocation: true
argument-hint: "[OWNER/REPO]"
---

# Set up a collection repository

A repository created from the collection_skeleton template gets its files but
none of its settings: no secrets, no GitHub Pages, no branch protection. This
skill applies them, in order. Run each script with `bash` -
`ansible-galaxy collection init` does not preserve the executable bit.

Scripts live in `${CLAUDE_SKILL_DIR}/scripts/`.

## Secrets: rules that are never relaxed

- **Never ask the user to type or paste a token or API key into the
  conversation**, whole or in part. If one is pasted anyway, stop, and tell the
  user to revoke it: it is now in a transcript.
- **Never put a secret value in a command** - not as an argument, not in
  `--body`, not in a heredoc, not in a file.
- **Never print or inspect one** - no `echo`, `printenv`, `env`, `set -x`,
  `declare -p`, or reading a file that holds one.
- **Only `set-release-secrets.sh` touches the values.** It reads them from the
  environment or prompts for them with echo off, and passes them to GitHub
  through stdin. If they are not already exported in the environment you run in,
  do not try to obtain them: ask the user to run the script themselves in their
  own terminal, then carry on.
- Verify with `configure-repo.sh status`, which shows secret *names* only.

## 0. Preconditions

Resolve OWNER/REPO from `$ARGUMENTS`, or with
`gh repo view --json nameWithOwner --jq .nameWithOwner`. Then confirm, stopping
with an explanation if any fails:

- the working directory is the collection's repository root, and `galaxy.yml`
  exists;
- `skeleton/` does **not** exist - otherwise bootstrap has not run yet; tell the
  user to run the **Bootstrap collection** workflow from the Actions tab first;
- `git remote get-url origin` is an SSH URL (`git@...`) - step 1 depends on it;
- `gh api repos/OWNER/REPO --jq .permissions.admin` prints `true`.

## 1. Remove the template-only workflows

Only if `.github/workflows/bootstrap.yml`, `refresh-automation-hub-token.yml` or
`selfcheck.yml` still exist. Do this **before step 4**: once the branch is
protected, a direct push is refused.

```sh
git pull --ff-only
git rm --ignore-unmatch .github/workflows/bootstrap.yml \
  .github/workflows/refresh-automation-hub-token.yml .github/workflows/selfcheck.yml
git commit -m "chore: remove collection_skeleton template-only workflows"
git push
```

Show the user the commit before pushing. This has to go over SSH: GitHub does
not let a workflow's `GITHUB_TOKEN` delete files under `.github/workflows/`, but
an SSH push is not subject to that. This push is also what starts the
collection's first CI run - bootstrap's own commit did not, because pushes made
with `GITHUB_TOKEN` do not trigger workflows.

## 2. Release secrets

```sh
bash "${CLAUDE_SKILL_DIR}/scripts/set-release-secrets.sh" OWNER/REPO
```

Follow the secrets rules above. The script checks the token works and has push
access before storing anything, then prints `RELEASE_TOKEN acts as: <login>` -
note that login for step 4.

- `RELEASE_TOKEN` - a personal access token whose owner has push access to the
  repository. Fine-grained: Contents read and write on this repository. Classic:
  `repo`. The release workflow uses it to push the release commit and tag past
  branch protection.
- `GALAXY_API_KEY` - a **galaxy.ansible.com** API token (Collections > API
  token management there) with rights to the namespace. Not a Red Hat
  Automation Hub token: Galaxy rejects those with `401`, and only at publish
  time. The script checks the key against Galaxy, including the namespace,
  before storing anything. Galaxy tokens do not expire; loading a new one in
  the Galaxy UI invalidates the old one, so update this secret everywhere it
  is used when that happens.

This step can be deferred: until both secrets exist, the Release workflow skips
with a notice rather than failing. Nothing is published below 1.0.0 in any case.

## 3. GitHub Pages

```sh
bash "${CLAUDE_SKILL_DIR}/scripts/configure-repo.sh" pages OWNER/REPO
```

### Let the skeleton sync open its PRs

```sh
bash "${CLAUDE_SKILL_DIR}/scripts/configure-repo.sh" actions-prs OWNER/REPO
```

Turns on "Allow GitHub Actions to create and approve pull requests", so the
**Sync from the skeleton** workflow can propose drift in the skeleton-managed
files as a PR. An
organization policy can forbid it; the script then says so and exits cleanly,
because the workflow falls back to warning with a one-click link. Tell the user
which happened. Either way, a sync PR opened by the workflow needs a maintainer
to select **Approve workflows to run** on it before its checks report.

## 4. Protect the default branch

```sh
bash "${CLAUDE_SKILL_DIR}/scripts/configure-repo.sh" protect OWNER/REPO RELEASE_LOGIN [APPROVALS]
```

Creates a ruleset requiring a pull request with 1 approving review (pass
APPROVALS to change it), and forbidding direct pushes, force-pushes and
deletion. Two bypasses, nothing broader:

- `RELEASE_LOGIN`, the owner of `RELEASE_TOKEN`, may push directly, for the
  release workflow's release commit and tag. GitHub checks the token's owner,
  not the `github-actions[bot]` name on the commit, so this is a bypass for that
  account as a whole: tell the user it can also push to the default branch
  without a PR.
- Repository admins may bypass, but only inside a PR - for example to merge
  their own PR, which they cannot approve themselves. They cannot push directly.

Re-running it updates the ruleset and keeps any required checks already locked
in. Adding a bypass is a permission grant: confirm `RELEASE_LOGIN` with the user
before running it. If step 2 was deferred, ask the user which account will own
`RELEASE_TOKEN`, and re-run this step if that changes. Do **not** substitute a
broader bypass without the user deciding to. The built-in GitHub Actions
identity cannot be used instead: GitHub rejects it as a bypass actor.

## 5. Lock in the required checks - after the first PR's CI has passed

```sh
bash "${CLAUDE_SKILL_DIR}/scripts/configure-repo.sh" lock-checks OWNER/REPO PR_NUMBER
```

Requires five fixed-name checks - lint, the nox and coverage result gates,
docs, and the changelog check - and refuses to act unless every one has passed
on that PR. It waits for that first PR because a required check that has never
reported blocks every PR.

## Verify

```sh
bash "${CLAUDE_SKILL_DIR}/scripts/configure-repo.sh" status OWNER/REPO
```

## Rotating a secret

Run step 2 again. If the token's owner changes, re-run step 4 with the new login.
