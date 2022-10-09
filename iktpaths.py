#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

"""
This file contains paths used by iKT
"""

import os
from pathlib import Path

from ikttypes import FilePath

HOMEDIR = FilePath(str(Path.home()))

BIN_DIRNAME = "bin"
BINDIR = FilePath(os.path.join(HOMEDIR, BIN_DIRNAME))

IKT_DIRNAME = ".ikt"
IKTDIR = FilePath(os.path.join(HOMEDIR, IKT_DIRNAME))

IKT_CONFIG_FILENAME = "ikt.yaml"
IKT_CONFIG_FILE = FilePath(os.path.join(IKTDIR, IKT_CONFIG_FILENAME))

IKT_CONFIG_FILE_DIRNAME = f"{IKT_CONFIG_FILENAME}.d"
IKT_CONFIG_FILE_DIR = FilePath(os.path.join(IKTDIR, IKT_CONFIG_FILE_DIRNAME))

IKT_INSTALLATION_INFO_FILE = FilePath(os.path.join(IKTDIR, "installation_info.yaml"))

DEPLOYMENT_DIRNAME = "deployments"
DEPLOYMENT_DIR = FilePath(os.path.join(IKTDIR, DEPLOYMENT_DIRNAME))

THEME_DIRNAME = "themes"
THEME_DIR = FilePath(os.path.join(IKTDIR, THEME_DIRNAME))
DEFAULT_THEME_FILE = FilePath(os.path.join(THEME_DIR, "default.yaml"))

ANSIBLE_DIRNAME = "ansible"
ANSIBLE_DIR = FilePath(os.path.join(IKTDIR, ANSIBLE_DIRNAME))

ANSIBLE_PLAYBOOK_DIRNAME = "playbooks"
ANSIBLE_PLAYBOOK_DIR = os.path.join(ANSIBLE_DIR, ANSIBLE_PLAYBOOK_DIRNAME)

ANSIBLE_LOG_DIRNAME = "logs"
ANSIBLE_LOG_DIR = FilePath(os.path.join(ANSIBLE_DIR, ANSIBLE_LOG_DIRNAME))
ANSIBLE_INVENTORY = FilePath(os.path.join(ANSIBLE_DIR, "inventory.yaml"))
ANSIBLE_TMP_INVENTORY = FilePath(os.path.join(ANSIBLE_DIR, "tmp_inventory.yaml"))

IKT_HOOKS_DIRNAME = "hooks"
IKT_HOOKS_DIR = FilePath(os.path.join(IKTDIR, IKT_HOOKS_DIRNAME))

PARSER_DIRNAME = "parsers"
PARSER_DIR = FilePath(os.path.join(IKTDIR, PARSER_DIRNAME))

VIEW_DIRNAME = "views"
VIEW_DIR = FilePath(os.path.join(IKTDIR, VIEW_DIRNAME))

KUBE_CONFIG_FILE = FilePath(f"{HOMEDIR}/.kube/config")
