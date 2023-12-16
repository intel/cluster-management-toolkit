#! /usr/bin/env python3

"""
This module holds version strings, copyright info, and license info
for Cluster Management Toolkit for Kubernetes
"""

import sys

COPYRIGHT = "Copyright © 2019-2023 Intel Corporation"
LICENSE  = "This is free software; see the source for copying conditions.  There is NO\n"
LICENSE += "warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE."

PROGRAM_SUITE_NAME = "CMT"
PROGRAM_SUITE_FULL_NAME = "Cluster Management Toolkit for Kubernetes"
PROGRAM_SUITE_VERSION = "0.6.3"

UI_PROGRAM_NAME = "cmu"
UI_PROGRAM_VERSION = "0.4.6"

TOOL_PROGRAM_NAME = "cmt"
TOOL_PROGRAM_VERSION = "0.6.3"

INSTALL_PROGRAM_NAME = "cmt-install"
INSTALL_PROGRAM_VERSION = "0.13.2"

ADMIN_PROGRAM_NAME = "cmtadm"
ADMIN_PROGRAM_VERSION = "0.8.3"

INVENTORY_PROGRAM_NAME = "cmtinv"
INVENTORY_PROGRAM_VERSION = "0.4.4"

# We don't support Python-versions older than 3.8
version_info = sys.version_info
if version_info.major < 3 or version_info.minor < 8:
	sys.exit("Critical: Minimum supported Python-version is 3.8.0; installed version is " + str(version_info.major) + "." + str(version_info.minor) + "." + str(version_info.micro) + "; aborting.")
