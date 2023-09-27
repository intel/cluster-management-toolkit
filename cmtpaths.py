#! /usr/bin/env python3
# Requires: python3 (>= 3.8)

"""
This file contains paths used by CMT
"""

import os
from pathlib import Path, PurePath
from typing import List

from cmttypes import FilePath

HOMEDIR = FilePath(str(Path.home()))

BIN_DIRNAME = "bin"
BINDIR = FilePath(str(PurePath(HOMEDIR).joinpath(BIN_DIRNAME)))

CMT_DIRNAME = ".cmt"
CMTDIR = FilePath(str(PurePath(HOMEDIR).joinpath(CMT_DIRNAME)))

LOGS_DIRNAME = "logs"
CMT_LOGS_DIR = FilePath(str(PurePath(CMTDIR).joinpath(LOGS_DIRNAME)))
VERSION_CACHE_DIRNAME = "version-cache"
VERSION_CACHE_DIR = FilePath(str(PurePath(CMTDIR).joinpath(VERSION_CACHE_DIRNAME)))
AUDIT_LOG_FILENAME = "audit_log.yaml"
AUDIT_LOG_FILE = FilePath(str(PurePath(CMT_LOGS_DIR).joinpath(AUDIT_LOG_FILENAME)))
DEBUG_LOG_FILENAME = "debug_log.yaml"
DEBUG_LOG_FILE = FilePath(str(PurePath(CMT_LOGS_DIR).joinpath(DEBUG_LOG_FILENAME)))

CMT_CONFIG_FILENAME = "cmt.yaml"
CMT_CONFIG_FILE = FilePath(str(PurePath(CMTDIR).joinpath(CMT_CONFIG_FILENAME)))

CMT_CONFIG_FILE_DIRNAME = f"{CMT_CONFIG_FILENAME}.d"
CMT_CONFIG_FILE_DIR = FilePath(os.path.join(CMTDIR, CMT_CONFIG_FILE_DIRNAME))

CMT_INSTALLATION_INFO_FILE = FilePath(os.path.join(CMTDIR, "installation_info.yaml"))

DEPLOYMENT_DIRNAME = "deployments"
DEPLOYMENT_DIR = FilePath(os.path.join(CMTDIR, DEPLOYMENT_DIRNAME))

THEME_DIRNAME = "themes"
THEME_DIR = FilePath(os.path.join(CMTDIR, THEME_DIRNAME))
DEFAULT_THEME_FILE = FilePath(os.path.join(THEME_DIR, "default.yaml"))

ANSIBLE_DIRNAME = "ansible"
ANSIBLE_DIR = FilePath(os.path.join(CMTDIR, ANSIBLE_DIRNAME))

ANSIBLE_PLAYBOOK_DIRNAME = "playbooks"
ANSIBLE_PLAYBOOK_DIR = FilePath(os.path.join(CMTDIR, ANSIBLE_PLAYBOOK_DIRNAME))

ANSIBLE_LOG_DIRNAME = "logs"
ANSIBLE_LOG_DIR = FilePath(os.path.join(ANSIBLE_DIR, ANSIBLE_LOG_DIRNAME))
ANSIBLE_INVENTORY = FilePath(os.path.join(ANSIBLE_DIR, "inventory.yaml"))

CMT_HOOKS_DIRNAME = "hooks"
CMT_HOOKS_DIR = FilePath(os.path.join(CMTDIR, CMT_HOOKS_DIRNAME))

PARSER_DIRNAME = "parsers"
PARSER_DIR = FilePath(os.path.join(CMTDIR, PARSER_DIRNAME))

VIEW_DIRNAME = "views"
VIEW_DIR = FilePath(os.path.join(CMTDIR, VIEW_DIRNAME))

KUBE_CONFIG_DIR = FilePath(os.path.join(HOMEDIR, ".kube"))
KUBE_CONFIG_FILE = FilePath(os.path.join(KUBE_CONFIG_DIR, "config"))
KUBE_CREDENTIALS_FILE = FilePath(os.path.join(KUBE_CONFIG_DIR, "credentials"))

SSH_DIR = FilePath(os.path.join(HOMEDIR, ".ssh"))
SSH_BIN_PATH = FilePath("/usr/bin/ssh")

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
BASH_COMPLETION_BASE_DIR = FilePath(os.path.join(HOMEDIR, f".local/share/{BASH_COMPLETION_DIRNAME}"))
BASH_COMPLETION_DIR = FilePath(os.path.join(HOMEDIR, f".local/share/{BASH_COMPLETION_DIRNAME}/completions"))
