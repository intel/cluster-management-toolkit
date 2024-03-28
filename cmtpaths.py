#! /usr/bin/env python3
# Requires: python3 (>= 3.8)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
This file contains paths used by CMT
"""

from pathlib import Path
from typing import List

from cmttypes import FilePath

HOMEDIR = FilePath(Path.home())

BIN_DIRNAME = "bin"
BINDIR = HOMEDIR.joinpath(BIN_DIRNAME)

CMT_DIRNAME = ".cmt"
CMTDIR = HOMEDIR.joinpath(CMT_DIRNAME)

CHANGELOG_DIRNAME = "CHANGELOG"
CHANGELOG_DIR = CMTDIR.joinpath(CHANGELOG_DIRNAME)

LOGS_DIRNAME = "logs"
CMT_LOGS_DIR = CMTDIR.joinpath(LOGS_DIRNAME)
VERSION_CACHE_DIRNAME = "version-cache"
VERSION_CACHE_DIR = CMTDIR.joinpath(VERSION_CACHE_DIRNAME)
VERSION_CACHE_LAST_UPDATED_PATH = CMTDIR.joinpath(VERSION_CACHE_DIRNAME, "last-updated")
SOFTWARE_SOURCES_DIRNAME = "sources"
SOFTWARE_SOURCES_DIR = CMTDIR.joinpath(SOFTWARE_SOURCES_DIRNAME)
AUDIT_LOG_BASENAME = "audit_log_"
DEBUG_LOG_BASENAME = "debug_log_"

CMT_CONFIG_FILENAME = "cmt.yaml"
CMT_CONFIG_FILE = CMTDIR.joinpath(CMT_CONFIG_FILENAME)

CMT_CONFIG_FILE_DIRNAME = f"{CMT_CONFIG_FILENAME}.d"
CMT_CONFIG_FILE_DIR = CMTDIR.joinpath(CMT_CONFIG_FILE_DIRNAME)

CMT_INSTALLATION_INFO_FILE = CMTDIR.joinpath("installation_info.yaml")

DEPLOYMENT_DIRNAME = "deployments"
DEPLOYMENT_DIR = CMTDIR.joinpath(DEPLOYMENT_DIRNAME)

THEME_DIRNAME = "themes"
THEME_DIR = CMTDIR.joinpath(THEME_DIRNAME)
DEFAULT_THEME_FILE = THEME_DIR.joinpath("default.yaml")

ANSIBLE_DIRNAME = "ansible"
ANSIBLE_DIR = CMTDIR.joinpath(ANSIBLE_DIRNAME)

ANSIBLE_PLAYBOOK_DIRNAME = "playbooks"
ANSIBLE_PLAYBOOK_DIR = CMTDIR.joinpath(ANSIBLE_PLAYBOOK_DIRNAME)

ANSIBLE_LOG_DIRNAME = "logs"
ANSIBLE_LOG_DIR = ANSIBLE_DIR.joinpath(ANSIBLE_LOG_DIRNAME)
ANSIBLE_INVENTORY = ANSIBLE_DIR.joinpath("inventory.yaml")

CMT_HOOKS_DIRNAME = "hooks"
CMT_HOOKS_DIR = CMTDIR.joinpath(CMT_HOOKS_DIRNAME)
CMT_PRE_PREPARE_DIR = CMT_HOOKS_DIR.joinpath("pre-prepare.d")
CMT_POST_PREPARE_DIR = CMT_HOOKS_DIR.joinpath("post-prepare.d")
CMT_PRE_SETUP_DIR = CMT_HOOKS_DIR.joinpath("pre-setup.d")
CMT_POST_SETUP_DIR = CMT_HOOKS_DIR.joinpath("post-setup.d")
CMT_PRE_UPGRADE_DIR = CMT_HOOKS_DIR.joinpath("pre-upgrade.d")
CMT_POST_UPGRADE_DIR = CMT_HOOKS_DIR.joinpath("post-upgrade.d")
CMT_PRE_TEARDOWN_DIR = CMT_HOOKS_DIR.joinpath("pre-teardown.d")
CMT_POST_TEARDOWN_DIR = CMT_HOOKS_DIR.joinpath("post-teardown.d")
CMT_PRE_PURGE_DIR = CMT_HOOKS_DIR.joinpath("pre-purge.d")
CMT_POST_PURGE_DIR = CMT_HOOKS_DIR.joinpath("post-purge.d")

PARSER_DIRNAME = "parsers"
PARSER_DIR = CMTDIR.joinpath(PARSER_DIRNAME)

VIEW_DIRNAME = "views"
VIEW_DIR = CMTDIR.joinpath(VIEW_DIRNAME)

KUBE_CONFIG_DIR = HOMEDIR.joinpath(".kube")
KUBE_CONFIG_FILE = KUBE_CONFIG_DIR.joinpath("config")
KUBE_CREDENTIALS_FILE = KUBE_CONFIG_DIR.joinpath("credentials")

SSH_DIR = HOMEDIR.joinpath(".ssh")
SSH_BIN_PATH = FilePath("/usr/bin/ssh")

NETRC_PATH = HOMEDIR.joinpath(".netrc")
DOT_ANSIBLE_PATH = HOMEDIR.joinpath(".ansible")

# Accepted cryptos
SSH_ARGS_STRICT_CRYPTOS = \
    "aes256-gcm@openssh.com," \
    "chacha20-poly1305@openssh.com," \
    "aes256-ctr," \
    "aes256-cbc"

SSH_ARGS_RELAXED_CRYPTOS = \
    f"{SSH_ARGS_STRICT_CRYPTOS}"
# No additional cryptos

# Accepted CA signature algorithms
SSH_ARGS_STRICT_CA_SIGNATURE_ALGORITHMS = \
    "rsa-sha2-512," \
    "ecdsa-sha2-nistp521," \
    "ecdsa-sha2-nistp384"

SSH_ARGS_RELAXED_CA_SIGNATURE_ALGORITHMS = \
    f"{SSH_ARGS_STRICT_CA_SIGNATURE_ALGORITHMS}," \
    "ssh-ed25519," \
    "rsa-sha2-256"

# Accepted key exchange algorithms
SSH_ARGS_STRICT_KEX = \
    "ecdh-sha2-nistp521," \
    "ecdh-sha2-nistp384"

SSH_ARGS_RELAXED_KEX = \
    f"{SSH_ARGS_STRICT_KEX}"
# No additional KEXes

# Accepted MACs
SSH_ARGS_STRICT_MACS = \
    "hmac-sha2-512-etm@openssh.com," \
    "hmac-sha2-256-etm@openssh.com"

SSH_ARGS_RELAXED_MACS = \
    f"{SSH_ARGS_STRICT_MACS}"
# No additional MACs

# Accepted host key algorithms
SSH_ARGS_STRICT_HOST_KEY_ALGORITHMS = \
    "rsa-sha2-512," \
    "rsa-sha2-512-cert-v01@openssh.com," \
    "ecdsa-sha2-nistp521," \
    "ecdsa-sha2-nistp521-cert-v01@openssh.com," \
    "ecdsa-sha2-nistp384," \
    "ecdsa-sha2-nistp384-cert-v01@openssh.com"

SSH_ARGS_RELAXED_HOST_KEY_ALGORITHMS = \
    f"{SSH_ARGS_STRICT_HOST_KEY_ALGORITHMS}," \
    "ssh-ed25519," \
    "ssh-ed25519-cert-v01@openssh.com," \
    "sk-ssh-ed25519@openssh.com," \
    "sk-ssh-ed25519-cert-v01@openssh.com"

# Accepted public key types
SSH_ARGS_STRICT_PUB_KEY_TYPES = \
    "rsa-sha2-512," \
    "rsa-sha2-512-cert-v01@openssh.com," \
    "ecdsa-sha2-nistp521," \
    "ecdsa-sha2-nistp521-cert-v01@openssh.com," \
    "ecdsa-sha2-nistp384," \
    "ecdsa-sha2-nistp384-cert-v01@openssh.com"

SSH_ARGS_RELAXED_PUB_KEY_TYPES = \
    f"{SSH_ARGS_STRICT_PUB_KEY_TYPES}," \
    "rsa-sha2-256," \
    "rsa-sha2-256-cert-v01@openssh.com," \
    "ssh-ed25519," \
    "ssh-ed25519-cert-v01@openssh.com," \
    "sk-ssh-ed25519@openssh.com," \
    "sk-ssh-ed25519-cert-v01@openssh.com"

# Strict SSH configuration
SSH_ARGS_STRICT: List[str] = [
    # Accepted cryptos
    "-c", SSH_ARGS_STRICT_CRYPTOS,
    # Accepted CA signature algorithms
    "-o", f"CASignatureAlgorithms={SSH_ARGS_STRICT_CA_SIGNATURE_ALGORITHMS}",
    # Accepted key exchange algorithms
    "-o", f"KexAlgorithms={SSH_ARGS_STRICT_KEX}",
    # Accepted MACs
    "-o", f"MACs={SSH_ARGS_STRICT_MACS}",
    # Accepted host key algorithms
    "-o", f"HostKeyAlgorithms={SSH_ARGS_STRICT_HOST_KEY_ALGORITHMS}",
    # Accepted public key types
    "-o", f"PubkeyAcceptedKeyTypes={SSH_ARGS_STRICT_PUB_KEY_TYPES}",
]

# Relaxed SSH configuration
SSH_ARGS_RELAXED: List[str] = [
    # Accepted cryptos
    "-c", SSH_ARGS_RELAXED_CRYPTOS,
    # Accepted CA signature algorithms
    "-o", f"CASignatureAlgorithms={SSH_ARGS_RELAXED_CA_SIGNATURE_ALGORITHMS}",
    # Accepted key exchange algorithms
    "-o", f"KexAlgorithms={SSH_ARGS_RELAXED_KEX}",
    # Accepted MACs
    "-o", f"MACs={SSH_ARGS_RELAXED_MACS}",
    # Accepted host key algorithms
    "-o", f"HostKeyAlgorithms={SSH_ARGS_RELAXED_HOST_KEY_ALGORITHMS}",
    # Accepted public key types
    "-o", f"PubkeyAcceptedKeyTypes={SSH_ARGS_RELAXED_PUB_KEY_TYPES}",
]

SSH_KEYGEN_BIN_PATH = FilePath("/usr/bin/ssh-keygen")
SSH_KEYGEN_ARGS = ["-t", "ecdsa", "-b", "521", "-N", ""]

BASH_COMPLETION_DIRNAME = "bash-completion"
BASH_COMPLETION_BASE_DIR = HOMEDIR.joinpath(f".local/share/{BASH_COMPLETION_DIRNAME}")
BASH_COMPLETION_DIR = HOMEDIR.joinpath(f".local/share/{BASH_COMPLETION_DIRNAME}/completions")
