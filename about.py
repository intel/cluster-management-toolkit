#! /usr/bin/env python3
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
This module holds version strings, copyright info, and license info
for Cluster Management Toolkit for Kubernetes
"""

import sys

COPYRIGHT = "Copyright © 2019-2024 Intel Corporation"

LICENSE  = "This is free software; see the source for copying conditions.  There is NO\n"
LICENSE += "warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE."

PROGRAM_SUITE_NAME = "CMT"
PROGRAM_SUITE_FULL_NAME = "Cluster Management Toolkit for Kubernetes"
PROGRAM_SUITE_VERSION = "0.7.1"

UI_PROGRAM_NAME = "cmu"
UI_PROGRAM_VERSION = "0.5.0"

TOOL_PROGRAM_NAME = "cmt"
TOOL_PROGRAM_VERSION = "0.6.4"

INSTALL_PROGRAM_NAME = "cmt-install"
INSTALL_PROGRAM_VERSION = "0.13.4"

ADMIN_PROGRAM_NAME = "cmtadm"
ADMIN_PROGRAM_VERSION = "0.8.12"

INVENTORY_PROGRAM_NAME = "cmtinv"
INVENTORY_PROGRAM_VERSION = "0.4.5"

# We don't support Python-versions older than 3.8
version_info = sys.version_info
if version_info.major < 3 or version_info.minor < 8:  # pragma: no cover
    # pylint: disable-next=invalid-name
    installed_version = str(version_info.major)
    installed_version += "." + str(version_info.minor)
    installed_version += "." + str(version_info.micro)
    # pylint: disable-next=invalid-name
    msg = "Critical: Minimum supported Python-version is 3.8.0.\n"
    msg += "Installed version is " + installed_version
    msg += "; aborting."
    sys.exit(msg)
