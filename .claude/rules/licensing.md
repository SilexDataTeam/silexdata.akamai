<!--
SPDX-FileCopyrightText: Silex Data Solutions
SPDX-License-Identifier: Apache-2.0

REUSE-IgnoreStart
The SPDX tags below are worked examples, not declarations for this file.
-->

# Licensing rules

Source of truth: `silexdata.collection_skeleton`. Change it there, not here.

## Rule 0 — never relicense third-party code

**Before changing any license header or `COPYING` file, establish provenance.**

```sh
git log --follow -- <file>                       # who wrote it, and where from
grep -rniE 'adapted from|derived from|based on' plugins/
```

Code forked, copied or adapted from another project **keeps its original
license and attribution**. The defaults below apply only to files Silex
authored. This rule outranks every other rule in this file.

When a file is derived from permissively licensed upstream code:

- Keep the upstream license on that file. Add a Silex copyright line for the
  modifications — do not replace the upstream one.
- State that the file was changed. Apache-2.0 §4(b) *requires* a prominent
  modification notice; it is the obligation most derivations omit.
- Ship the upstream license text in `LICENSES/`. That is Apache-2.0 §4(a).
- If that keeps a module off GPL-3.0-or-later, its
  `validate-modules:missing-gplv3-license` entry in `tests/sanity/ignore-*.txt`
  is **correct and permanent**. Record the reason in review, not by deleting it.

Apache-2.0 → GPL-3.0-or-later compatibility is **one-way**: permissive code may
be combined into a GPLv3 work, but GPLv3 code can never be relicensed the other
way.

## Default licenses for Silex-authored files

| Path | License | Why |
|---|---|---|
| plugin code in `plugins/`: modules, doc_fragments, lookup, filter, inventory, callback, connection, action, ... | `GPL-3.0-or-later` | Ansible requires it for every plugin outside `modules/` and `module_utils/` (they run inside the GPL controller); `ansible-test`'s validate-modules requires the GPLv3 header on modules |
| `plugins/module_utils/` | `BSD-2-Clause` | copied into the payload that runs on managed nodes, where copyleft would extend to every third-party module importing it. Ansible requires only GPLv3-*compatible* here and recommends BSD-2-Clause |
| code outside `plugins/` that imports GPL code — typically unit tests importing a GPL plugin | `GPL-3.0-or-later` | Ansible's rule. **No tool checks this**; catch it in review |
| everything else: `COPYING`, docs, READMEs, `galaxy.yml`, `meta/`, tooling, CI, integration test tasks | `Apache-2.0` | the collection's default license |

`COPYING` holds the default license, Apache-2.0. It is named `COPYING`, not
`LICENSE`, because antsibull-nox's check exempts a file by that exact name.

## `LICENSES/` holds exactly the licenses in use

Every license any file declares needs `LICENSES/<SPDX-ID>.txt`, and **only**
licenses actually in use may be there: `reuse lint` fails on an unused one, and
antsibull-nox derives its set of allowed licenses from
`glob("LICENSES/*.txt")`.

A new collection is Apache-2.0 throughout, so it ships only
`LICENSES/Apache-2.0.txt`, and `galaxy.yml` lists only `Apache-2.0`. When you add:

- the **first plugin** → add `LICENSES/GPL-3.0-or-later.txt` and list
  `GPL-3.0-or-later` in `galaxy.yml`;
- the **first `module_utils` file** → add `LICENSES/BSD-2-Clause.txt` and list
  `BSD-2-Clause` in `galaxy.yml`.

Forgetting the license text fails the license check with a clear error. Nothing
checks `galaxy.yml` against `LICENSES/`, so keep the two in step by hand.

## Every file declares its own license

Licensing is checked on **every** file by the `license-check` nox session,
which the Nox workflow's "Run extra sanity tests" job runs on each PR. Each file
states its own license:

| File type | How |
|---|---|
| YAML, TOML, Python, shell, `.gitignore`, `requirements.txt`, `aliases` | `# SPDX-FileCopyrightText:` and `# SPDX-License-Identifier:` comment lines — in YAML, directly *after* the `---` line |
| Markdown | the same two lines inside an HTML comment at the top |
| reStructuredText | the same two lines as `..` comments at the top |
| anything that cannot hold a comment, or that a tool rewrites | a `<file>.license` sidecar next to it holding the two lines: JSON configs, `changelogs/changelog.yaml`, `CHANGELOG.md`, and `tests/sanity/ignore-*.txt` (ansible-test rejects comment-only lines in those) |

`COPYING` and `LICENSES/*.txt` need nothing: both checkers exempt them.

`REUSE.toml` is **not** where licenses live. antsibull-nox's check ignores it;
it exists only to cover changelog fragments, which that check exempts but
`reuse lint` does not. Per-file headers are also the only mechanism that can
express provenance — a path glob cannot say "this one module keeps its upstream
license".

When you add a file, add its header in the same commit. CI names the file if you
forget.

## Canonical headers

A plugin (module, lookup, doc_fragment, ...):

```python
#!/usr/bin/python

# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later
```

A `module_utils` file — swap the prose and the tag:

```python
# Simplified BSD License (see LICENSES/BSD-2-Clause.txt or https://opensource.org/licenses/BSD-2-Clause)
# SPDX-License-Identifier: BSD-2-Clause
```

Anything else:

```yaml
# SPDX-FileCopyrightText: Silex Data Solutions
# SPDX-License-Identifier: Apache-2.0
```

## Five traps that will fail CI

1. **An SPDX tag alone does not satisfy `validate-modules`.** It greps the
   first 20 lines of every module and plugin for the literal string
   `GNU General Public License` *and* either `version 3` or `v3.0`.
   `SPDX-License-Identifier: GPL-3.0-or-later` contains neither. Keep the prose
   line.
2. **The GPL prose line must stay within the first 20 lines.** A long
   provenance block can silently push it out of the window. Recount after
   editing a header.
3. **`Copyright:` with a colon is an error.** antsibull-nox rejects it. Use
   `Copyright (c) ...` or `SPDX-FileCopyrightText:`.
4. **The prose license name must agree with the SPDX tag.** antsibull-nox
   string-sniffs prose and compares. Never write the literal
   `Apache License 2.0` on a file whose tag is not `Apache-2.0` — write
   `Apache License, Version 2.0` (with the comma) or `Apache-2.0` instead.
5. **The check reads every line of every file, not just the header.** A
   document that *quotes* an example header — like this one — is read as
   declaring those licenses, which fails as a duplicate or conflicting
   declaration. Don't quote literal header lines in checked files, or list the
   file in `license_check_extra_ignore_paths` (below).

antsibull-nox forces everything under `plugins/` **except** `modules/`,
`module_utils/` and `doc_fragments/` to exactly `GPL-3.0-or-later`; a dual
`A OR B` tag is rejected there.

## Exceptions, and how provenance cases fit

Upstream provenance almost never needs an exception:

- The allowed licenses are exactly the files in `LICENSES/`, so a collection
  carrying upstream Apache-2.0 code tags those files `Apache-2.0`.
- `plugins/modules/`, `plugins/module_utils/` and `plugins/doc_fragments/`
  accept any license in `LICENSES/` as far as antsibull-nox is concerned, so
  upstream-derived code there can keep its upstream license. For a module that
  also means a sanity ignore (Rule 0).
- Other plugin types (lookup, inventory, filter, ...) must be
  `GPL-3.0-or-later`. Code adapted from a GPLv3-*compatible* upstream
  (Apache-2.0, MIT, BSD) can still live there: tag it GPL-3.0-or-later, keep
  the upstream copyright line and credit it in prose. Code under a
  GPLv3-*incompatible* license cannot, and no label fixes that.
- An upstream license file keeps its text. Rename it to `COPYING`, or leave it
  as `LICENSE` with a `LICENSE.license` sidecar.

For the rare file that genuinely cannot pass a whole-file scan, list it under
`license_check_extra_ignore_paths` in `antsibull-nox.toml` **with a comment
saying why**. Treat that list like `tests/sanity/ignore-*.txt`: every entry is a
reviewed exception. `reuse lint` still checks those files.

What no tool can decide is *whether* a file is derived from upstream — that is
Rule 0, and it stays a human judgement.

## galaxy.yml

`license:` (an SPDX list) and `license_file:` are **mutually exclusive** —
galaxy-importer rejects a `galaxy.yml` that sets both. We use `license:`, listing
every license in `LICENSES/`. Deprecated SPDX spellings (`GPL-3.0`, `GPL-3.0+`)
are rejected; use `GPL-3.0-or-later`.

## Verifying

```sh
nox -e license-check    # both halves: `reuse lint`, then antsibull-nox's own check
```

The two halves disagree about what counts: `reuse lint` honours `REUSE.toml`,
antsibull-nox's check reads per-file headers only. A tree can pass the first and
fail the second, so run the session, not `reuse lint` on its own.

<!-- REUSE-IgnoreEnd -->
