# SPDX-FileCopyrightText: Silex Data Solutions
# SPDX-License-Identifier: Apache-2.0
# /// script
# dependencies = ["nox>=2025.02.09", "antsibull-nox"]
# ///

import sys

import nox

try:
    import antsibull_nox
except ImportError:
    print("Install antsibull-nox in the same Python environment as nox.")
    sys.exit(1)

antsibull_nox.load_antsibull_nox_toml()

if __name__ == "__main__":
    nox.main()
