#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

"""
This file contains paths used by iKT
"""

import os
from pathlib import Path, PurePath
from typing import List

from ikttypes import FilePath

HOMEDIR = FilePath(str(Path.home()))

BIN_DIRNAME = "bin"
BINDIR = FilePath(str(PurePath(HOMEDIR).joinpath(BIN_DIRNAME)))

IKT_DIRNAME = ".ikt"
IKTDIR = FilePath(str(PurePath(HOMEDIR).joinpath(IKT_DIRNAME)))

LOGS_DIRNAME = "logs"
IKT_LOGS_DIR = FilePath(str(PurePath(IKTDIR).joinpath(LOGS_DIRNAME)))
AUDIT_LOG_FILENAME = "audit_log.yaml"
AUDIT_LOG_FILE = FilePath(str(PurePath(IKT_LOGS_DIR).joinpath(AUDIT_LOG_FILENAME)))
DEBUG_LOG_FILENAME = "debug_log.yaml"
DEBUG_LOG_FILE = FilePath(str(PurePath(IKT_LOGS_DIR).joinpath(DEBUG_LOG_FILENAME)))

IKT_CONFIG_FILENAME = "ikt.yaml"
IKT_CONFIG_FILE = FilePath(str(PurePath(IKTDIR).joinpath(IKT_CONFIG_FILENAME)))

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
ANSIBLE_PLAYBOOK_DIR = FilePath(os.path.join(IKTDIR, ANSIBLE_PLAYBOOK_DIRNAME))

ANSIBLE_LOG_DIRNAME = "logs"
ANSIBLE_LOG_DIR = FilePath(os.path.join(ANSIBLE_DIR, ANSIBLE_LOG_DIRNAME))
ANSIBLE_INVENTORY = FilePath(os.path.join(ANSIBLE_DIR, "inventory.yaml"))

IKT_HOOKS_DIRNAME = "hooks"
IKT_HOOKS_DIR = FilePath(os.path.join(IKTDIR, IKT_HOOKS_DIRNAME))

PARSER_DIRNAME = "parsers"
PARSER_DIR = FilePath(os.path.join(IKTDIR, PARSER_DIRNAME))

VIEW_DIRNAME = "views"
VIEW_DIR = FilePath(os.path.join(IKTDIR, VIEW_DIRNAME))

KUBE_CONFIG_DIR = FilePath(os.path.join(HOMEDIR, ".kube"))
KUBE_CONFIG_FILE = FilePath(os.path.join(KUBE_CONFIG_DIR, "config"))

SSH_DIR = FilePath(os.path.join(HOMEDIR, ".ssh"))
SSH_BIN_PATH = FilePath("/usr/bin/ssh")
SSH_ARGS: List[str] = []
SSH_KEYGEN_BIN_PATH = FilePath("/usr/bin/ssh-keygen")
SSH_KEYGEN_ARGS = ["-t", "ecdsa", "-b", "521"]

BASH_COMPLETION_BASE_DIR = FilePath(os.path.join(HOMEDIR, ".local/share/bash-completion"))
BASH_COMPLETION_DIR = FilePath(os.path.join(HOMEDIR, ".local/share/bash-completion/completions"))
