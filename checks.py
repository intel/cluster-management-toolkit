#! /usr/bin/env python3
# Requires: python3 (>= 3.8)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
This module provides modules for troubleshooting malfunctioning clusters,
auditing configuration and cluster for potential security issues,
pre-flight checks to run before preparing or installing new systems,
and pre-upgrade checks to run before upgrading a system to a newer version.

This module requires init_ansithemeprint() to have been executed first
"""

import errno
import os
from pathlib import Path, PurePath
import re
import sys
from typing import cast, Dict, Generator, List, Optional, Tuple, Union

from ansible_helper import ansible_configuration
from ansible_helper import ansible_run_playbook_on_selection, ansible_print_play_results

from cmtio import execute_command_with_response
from cmttypes import deep_get, DictPath, FilePath
from cmtpaths import BINDIR, CMTDIR, CMT_LOGS_DIR
from cmtpaths import ANSIBLE_DIR, ANSIBLE_INVENTORY, ANSIBLE_LOG_DIR, ANSIBLE_PLAYBOOK_DIR
from cmtpaths import DEPLOYMENT_DIR, CMT_CONFIG_FILE_DIR, CMT_HOOKS_DIR, KUBE_CONFIG_DIR, PARSER_DIR, THEME_DIR, VIEW_DIR
from cmtpaths import CMT_CONFIG_FILE, KUBE_CONFIG_FILE, KUBE_CREDENTIALS_FILE, SSH_BIN_PATH, NETRC_PATH
import cmtlib
from ansithemeprint import ANSIThemeString, ansithemestring_join_tuple_list, ansithemeprint

from kubernetes_helper import kubectl_get_version

import about

# Check file permissions:
# .ssh should be 700
# .ssh/authorized_keys should be 644, 640, or 600
# .ssh/

# pylint: disable-next=too-many-arguments,unused-argument
def check_security_disable_strict_host_key_checking(cluster_name: str, kubeconfig: Dict, cmtconfig_dict: Dict, user: str,
						    critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[bool, int, int, int, int]:
	"""
	This checks whether or not strict host key checking has been disabled in cmtconfig

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			cmtconfig_dict (dict): The cmtconfig file
			critical (int): The current count of critical severity security issues
			error (int): The current count of error severity security issues
			warning (int): The current count of warning severity security issues
			note (int): The current count of note severity security issues
			kwargs (dict): Additional parameters
		Returns:
			(critical, error, warning, note):
				critical (int): The new count of critical severity security issues
				error (int): The new count of error severity security issues
				warning (int): The new count of warning severity security issues
				note (int): The new count of note severity security issues
	"""

	abort = False

	ansithemeprint([ANSIThemeString("[Checking for insecure configuration options in ", "phase"),
			ANSIThemeString(f"{CMT_CONFIG_FILE}", "path"),
			ANSIThemeString("]", "phase")])
	disablestricthostkeychecking = deep_get(cmtconfig_dict, DictPath("Nodes#disablestricthostkeychecking"), False)
	if not disablestricthostkeychecking:
		ansithemeprint([ANSIThemeString("  OK\n", "emphasis")])
	else:
		ansithemeprint([ANSIThemeString("  ", "default"),
				ANSIThemeString("Warning", "warning"),
				ANSIThemeString(":", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    Strict SSH host key checking is disabled; this is a potential security threat.", "emphasis")], stderr = True)
		ansithemeprint([ANSIThemeString("    If strict SSH host key checking is disabled other systems can impersonate the remote host", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    and thus perform Man in the Middle (MITM) attacks.", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    It is strongly advised that you enable strict SSH host key checking", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    unless you are absolutely certain that your network environment is safe.\n", "default")], stderr = True)
		error += 1

	return abort, critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_sudo_configuration(cluster_name: str, kubeconfig: Dict, cmtconfig_dict: Dict, user: str,
			     critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[bool, int, int, int, int]:
	"""
	This checks whether the user is in /etc/sudoers or /etc/sudoers.d,
	and whether the user can sudo without a password

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			cmtconfig_dict (dict): The cmtconfig file
			critical (int): The current count of critical severity security issues
			error (int): The current count of error severity security issues
			warning (int): The current count of warning severity security issues
			note (int): The current count of note severity security issues
			kwargs (dict): Additional parameters
		Returns:
			(critical, error, warning, note):
				critical (int): The new count of critical severity security issues
				error (int): The new count of error severity security issues
				warning (int): The new count of warning severity security issues
				note (int): The new count of note severity security issues
	"""

	abort = False

	ansithemeprint([ANSIThemeString("[Checking whether ", "phase"),
			ANSIThemeString(f"{user}", "path"),
			ANSIThemeString(" is in ", "phase"),
			ANSIThemeString("/etc/sudoers", "path"),
			ANSIThemeString(" or ", "phase"),
			ANSIThemeString("/etc/sudoers.d", "path"),
			ANSIThemeString(" on ", "phase"),
			ANSIThemeString("localhost", "hostname"),
			ANSIThemeString("]", "phase")])
	args = ["/usr/bin/sudo", "-l"]
	result = execute_command_with_response(args)

	sudoer = True

	sudo_msg_regex = re.compile(r"^User ([^\s]+) is not allowed to run sudo on.*")

	for line in result.splitlines():
		tmp = sudo_msg_regex.match(line)
		if tmp is not None:
			ansithemeprint([ANSIThemeString("  ", "default"),
					ANSIThemeString("Error", "error"),
					ANSIThemeString(":", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("    The user ", "default"),
					ANSIThemeString(user, "path"),
					ANSIThemeString(" is not in ", "default"),
					ANSIThemeString("/etc/sudoers", "path"),
					ANSIThemeString(" or ", "default"),
					ANSIThemeString("/etc/sudoers.d", "path"),
					ANSIThemeString(".\n", "default")], stderr = True)
			error += 1
			sudoer = False
			break

	if sudoer:
		ansithemeprint([ANSIThemeString("  OK\n", "ok")])

		ansithemeprint([ANSIThemeString("[Checking whether", "phase"),
				ANSIThemeString(f" {user} ", "path"),
				ANSIThemeString("can perform passwordless sudo", "phase"),
				ANSIThemeString(" on ", "phase"),
				ANSIThemeString("localhost", "hostname"),
				ANSIThemeString("]", "phase")])
		args = ["/usr/bin/sudo", "-l"]
		result = execute_command_with_response(args)
		passwordless_sudo = False

		sudo_permissions_regex = re.compile(r"^\s*\(ALL(\s*:\s*ALL)?\)\s*NOPASSWD:\s*ALL\s*$")

		for line in result.splitlines():
			tmp = sudo_permissions_regex.match(line)
			if tmp is not None:
				ansithemeprint([ANSIThemeString("  OK\n", "emphasis")])
				passwordless_sudo = True
				break

		if not passwordless_sudo:
			ansithemeprint([ANSIThemeString("  ", "default"),
					ANSIThemeString("Error", "error"),
					ANSIThemeString(":", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("    The user ", "default"),
					ANSIThemeString(user, "path"),
					ANSIThemeString(" cannot perform passwordless sudo.\n", "default")], stderr = True)
			error += 1

	return abort, critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_netrc_permissions(cluster_name: str, kubeconfig: Dict, cmtconfig_dict: Dict, user: str,
			    critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[bool, int, int, int, int]:
	"""
	This checks whether the .netrc are sufficiently strict (0600 is required to satisfy Ansible)

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			cmtconfig_dict (dict): The cmtconfig file
			critical (int): The current count of critical severity security issues
			error (int): The current count of error severity security issues
			warning (int): The current count of warning severity security issues
			note (int): The current count of note severity security issues
			kwargs (dict): Additional parameters
		Returns:
			(critical, error, warning, note):
				critical (int): The new count of critical severity security issues
				error (int): The new count of error severity security issues
				warning (int): The new count of warning severity security issues
				note (int): The new count of note severity security issues
	"""

	abort = False

	ansithemeprint([ANSIThemeString("[Checking whether permissions for ", "phase"),
			ANSIThemeString(".netrc", "path"),
			ANSIThemeString(" are sufficiently strict on ", "phase"),
			ANSIThemeString("localhost", "hostname"),
			ANSIThemeString("]", "phase")])

	path_entry = Path(NETRC_PATH)
	path_stat = path_entry.stat()
	path_permissions = path_stat.st_mode & 0o777

	if path_permissions not in (0o600, 0o400):
		ansithemeprint([ANSIThemeString("  ", "default"),
				ANSIThemeString("Critical", "critical"),
				ANSIThemeString(":", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    The permissions for ", "default"),
				ANSIThemeString(f"{NETRC_PATH}", "path"),
				ANSIThemeString(" are ", "default"),
				ANSIThemeString(f"{path_permissions:03o}", "emphasis"),
				ANSIThemeString(";", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    the recommended permissions are ", "default"),
				ANSIThemeString(f"{0o600:03o}", "emphasis"),
				ANSIThemeString(" (or stricter).", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("  ", "default"),
				ANSIThemeString("Justification", "emphasis"),
				ANSIThemeString(": ", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    Ansible will refuse to fetch files if the permissions for ", "default"),
				ANSIThemeString(f"{NETRC_PATH}", "path"),
				ANSIThemeString(" are not sufficiently strict\n", "default")], stderr = True)
		critical += 1
	else:
		ansithemeprint([ANSIThemeString("  OK\n", "emphasis")])

	return abort, critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_known_hosts_hashing(cluster_name: str, kubeconfig: Dict, cmtconfig_dict: Dict, user: str,
			      critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[bool, int, int, int, int]:
	"""
	This checks whether ssh known_hosts hashing is enabled

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			cmtconfig_dict (dict): The cmtconfig file
			critical (int): The current count of critical severity security issues
			error (int): The current count of error severity security issues
			warning (int): The current count of warning severity security issues
			note (int): The current count of note severity security issues
			kwargs (dict): Additional parameters
		Returns:
			(critical, error, warning, note):
				critical (int): The new count of critical severity security issues
				error (int): The new count of error severity security issues
				warning (int): The new count of warning severity security issues
				note (int): The new count of note severity security issues
	"""

	abort = False

	ansithemeprint([ANSIThemeString("[Checking whether hashing of ", "phase"),
			ANSIThemeString(".ssh/known_hosts", "path"),
			ANSIThemeString(" is enabled on ", "phase"),
			ANSIThemeString("localhost", "hostname"),
			ANSIThemeString("]", "phase")])
	ansithemeprint([ANSIThemeString("  ", "default"),
			ANSIThemeString("Note", "note"),
			ANSIThemeString(":", "default")])
	ansithemeprint([ANSIThemeString("    Since ", "default"),
			ANSIThemeString("ssh", "programname"),
			ANSIThemeString(" settings can vary per host this test is not 100% reliable.\n", "default")])
	args = [SSH_BIN_PATH, "-G", "localhost"]
	result = execute_command_with_response(args)

	hashknownhosts_regex = re.compile(r"^hashknownhosts\s+yes$")

	for line in result.splitlines():
		tmp = hashknownhosts_regex.match(line)
		if tmp is not None:
			ansithemeprint([ANSIThemeString("  ", "default"),
					ANSIThemeString("Warning", "warning"),
					ANSIThemeString(":", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("    Hashing of ", "default"),
					ANSIThemeString(".ssh/known_hosts", "path"),
					ANSIThemeString(" is enabled;", "default"),
					ANSIThemeString(" this may cause issues with ", "default"),
					ANSIThemeString("paramiko", "programname"),
					ANSIThemeString(".\n", "default")], stderr = True)
			warning += 1
			break

	return abort, critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_insecure_kube_config_options(cluster_name: str, kubeconfig: Dict, cmtconfig_dict: Dict, user: str,
				       critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[bool, int, int, int, int]:
	"""
	This checks whether .kube/config has insecure options

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			cmtconfig_dict (dict): The cmtconfig file
			critical (int): The current count of critical severity security issues
			error (int): The current count of error severity security issues
			warning (int): The current count of warning severity security issues
			note (int): The current count of note severity security issues
			kwargs (dict): Additional parameters
		Returns:
			(critical, error, warning, note):
				critical (int): The new count of critical severity security issues
				error (int): The new count of error severity security issues
				warning (int): The new count of warning severity security issues
				note (int): The new count of note severity security issues
	"""

	abort = False

	ansithemeprint([ANSIThemeString("[Checking for insecure ", "phase"),
			ANSIThemeString(f"{KUBE_CONFIG_FILE}", "path"),
			ANSIThemeString(" options]", "phase")])

	insecureskiptlsverify = False

	for cluster in deep_get(kubeconfig, DictPath("clusters"), []):
		if deep_get(cluster, DictPath("name"), "") == cluster_name:
			insecureskiptlsverify = deep_get(cluster, DictPath("insecure-skip-tls-verify"), False)
			break

	if not insecureskiptlsverify:
		ansithemeprint([ANSIThemeString("  OK\n", "emphasis")])
	else:
		# Use critical for highlighting warning here,
		# since the warning is so important
		ansithemeprint([ANSIThemeString("  ", "default"),
				ANSIThemeString("Warning", "critical"),
				ANSIThemeString(":", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    TLS verification has been disabled in ", "emphasis"),
				ANSIThemeString(f"{KUBE_CONFIG_FILE}", "path"),
				ANSIThemeString("; this is a security threat.", "emphasis")], stderr = True)
		ansithemeprint([ANSIThemeString("    If TLS verification is disabled other systems can impersonate the control plane", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    and thus perform Man in the Middle (MITM) attacks.", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    It is advised that you remove the ", "default"),
				ANSIThemeString("insecure-skip-tls-verify", "argument"),
				ANSIThemeString(" option from ", "default"),
				ANSIThemeString(f"{KUBE_CONFIG_FILE}", "path"),
				ANSIThemeString(",", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    unless you are absolutely certain that your network environment is safe.\n", "default")], stderr = True)
		critical += 1

	return abort, critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_client_server_version_match(cluster_name: str, kubeconfig: Dict, cmtconfig_dict: Dict, user: str,
				      critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[bool, int, int, int, int]:
	"""
	This checks whether the versions of the various Kubernetes match properly

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			cmtconfig_dict (dict): The cmtconfig file
			critical (int): The current count of critical severity security issues
			error (int): The current count of error severity security issues
			warning (int): The current count of warning severity security issues
			note (int): The current count of note severity security issues
			kwargs (dict): Additional parameters
		Returns:
			(critical, error, warning, note):
				critical (int): The new count of critical severity security issues
				error (int): The new count of error severity security issues
				warning (int): The new count of warning severity security issues
				note (int): The new count of note severity security issues
	"""

	mismatch = False
	abort = False

	# Is the version of kubectl within one version of the cluster version?
	ansithemeprint([ANSIThemeString("[Checking client/server version match]", "phase")])

	_kubectl_major_version, kubectl_minor_version, kubectl_git_version, server_major_version, server_minor_version, server_git_version = kubectl_get_version()

	if kubectl_git_version == "<unavailable>" or kubectl_minor_version is None:
		ansithemeprint([ANSIThemeString("Critical", "critical"),
				ANSIThemeString(": Could not extract ", "default"),
				ANSIThemeString("kubectl", "programname"),
				ANSIThemeString(" version; will abort.", "default")], stderr = True)
		abort = True
		critical += 1
	else:
		ansithemeprint([ANSIThemeString("         kubectl ", "programname"),
				ANSIThemeString("version: ", "default"),
				ANSIThemeString(f"{kubectl_git_version}", "version")])
	if server_git_version == "<unavailable>" or server_major_version is None or server_minor_version is None:
		ansithemeprint([ANSIThemeString("  ", "default"),
				ANSIThemeString("Critical", "error"),
				ANSIThemeString(":", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    Could not extract ", "default"),
				ANSIThemeString("kube-apiserver", "programname"),
				ANSIThemeString(" version (double-check that the server is running and that ", "default"),
				ANSIThemeString("https_proxy", "argument"),
				ANSIThemeString(" and  ", "default"),
				ANSIThemeString("no_proxy", "argument"),
				ANSIThemeString(" are correctly set); will abort.", "default")], stderr = True)
		https_proxy_env = os.getenv("https_proxy")
		no_proxy_env = os.getenv("no_proxy")
		ansithemeprint([ANSIThemeString("      https_proxy", "argument"),
				ANSIThemeString(" (env): ", "default"),
				ANSIThemeString(f"{https_proxy_env}", "url")], stderr = True)
		ansithemeprint([ANSIThemeString("      no_proxy", "argument"),
				ANSIThemeString(" (env): ", "default"),
				ANSIThemeString(f"{no_proxy_env}", "url")], stderr = True)
		abort = True
		critical += 1
	else:
		ansithemeprint([ANSIThemeString("  kube-apiserver ", "programname"),
				ANSIThemeString("version: ", "default"),
				ANSIThemeString(f"{server_git_version}", "version")])

	if abort:
		return abort, critical, error, warning, note

	kubectl_minor_version = cast(int, kubectl_minor_version)
	server_major_version = cast(int, server_major_version)
	server_minor_version = cast(int, server_minor_version)

	print()

	if server_major_version != 1:
		ansithemeprint([ANSIThemeString("  ", "default"),
				ANSIThemeString("Critical", "critical"),
				ANSIThemeString(": ", "default")], stderr = True)
		ansithemeprint([ANSIThemeString(f"    {about.PROGRAM_SUITE_NAME}", "programname"),
				ANSIThemeString(" has not been tested for any other major version of Kubernetes ", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    than ", "default"),
				ANSIThemeString("v1", "version"),
				ANSIThemeString("; aborting.", "default")], stderr = True)
		sys.exit(errno.ENOTSUP)

	if kubectl_minor_version > server_minor_version and kubectl_minor_version == server_minor_version + 1:
		ansithemeprint([ANSIThemeString("  ", "default"),
				ANSIThemeString("Note", "note"),
				ANSIThemeString(":", "default")])
		ansithemeprint([ANSIThemeString("    The ", "default"),
				ANSIThemeString("kubectl", "programname"),
				ANSIThemeString(" version is one minor version newer than that of ", "default"),
				ANSIThemeString("kube-apiserver", "programname"),
				ANSIThemeString(";", "default")])
		ansithemeprint([ANSIThemeString("    this is a supported configuration, but it is generally recommended to keep", "default")])
		ansithemeprint([ANSIThemeString("    the versions in sync.", "default")])
		note += 1
		mismatch = True
	elif kubectl_minor_version > server_minor_version:
		ansithemeprint([ANSIThemeString("  ", "default"),
				ANSIThemeString("Warning", "warning"),
				ANSIThemeString(":", "default")])
		ansithemeprint([ANSIThemeString("    The ", "default"),
				ANSIThemeString("kubectl", "programname"),
				ANSIThemeString(" version is more than one minor version newer than", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    that of ", "default"),
				ANSIThemeString("kube-apiserver", "programname"),
				ANSIThemeString("; this might work, but it is generally recommended", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    to keep the versions in sync.", "default")], stderr = True)
		warning += 1
		mismatch = True
	elif kubectl_minor_version < server_minor_version and kubectl_minor_version + 1 == server_minor_version:
		ansithemeprint([ANSIThemeString("  ", "default"),
				ANSIThemeString("Warning", "warning"),
				ANSIThemeString(":", "default")])
		ansithemeprint([ANSIThemeString("    The ", "default"),
				ANSIThemeString("kubectl", "programname"),
				ANSIThemeString(" version is one minor version older than that of ", "default"),
				ANSIThemeString("kube-apiserver", "programname"),
				ANSIThemeString(";", "default")])
		ansithemeprint([ANSIThemeString("    this is a supported configuration, but it is generally recommended to keep", "default")])
		ansithemeprint([ANSIThemeString("    the versions in sync.", "default")], stderr = True)
		warning += 1
		mismatch = True
	elif kubectl_minor_version < server_minor_version:
		ansithemeprint([ANSIThemeString("  ", "default"),
				ANSIThemeString("Error", "error"),
				ANSIThemeString(":", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    The ", "default"),
				ANSIThemeString("kubectl", "programname"),
				ANSIThemeString(" version is much older than that of ", "default"),
				ANSIThemeString("kube-apiserver", "programname"),
				ANSIThemeString(";", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    this is ", "default"),
				ANSIThemeString("NOT", "emphasis"),
				ANSIThemeString(" supported and is likely to cause issues.", "default")], stderr = True)
		error += 1
		mismatch = True

	if not mismatch:
		ansithemeprint([ANSIThemeString("  OK", "ok")])

	return abort, critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_kubelet_and_kube_proxy_versions(cluster_name: str, kubeconfig: Dict, cmtconfig_dict: Dict, user: str,
					  critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[bool, int, int, int, int]:
	"""
	This checks whether the versions of kubelet and kube-proxy are acceptable

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			cmtconfig_dict (dict): The cmtconfig file
			critical (int): The current count of critical severity security issues
			error (int): The current count of error severity security issues
			warning (int): The current count of warning severity security issues
			note (int): The current count of note severity security issues
			kwargs (dict): Additional parameters
		Returns:
			(critical, error, warning, note):
				critical (int): The new count of critical severity security issues
				error (int): The new count of error severity security issues
				warning (int): The new count of warning severity security issues
				note (int): The new count of note severity security issues
	"""

	abort = False

	# Check kubelet and kube-proxy versions;
	# they can be up to two minor versions older than kube-apiserver,
	# but must not be newer

	mismatch = False

	_kubectl_major_version, _kubectl_minor_version, _kubectl_git_version, server_major_version, server_minor_version, _server_git_version = kubectl_get_version()
	if server_major_version is None:
		ansithemeprint([ANSIThemeString("  ", "default"),
				ANSIThemeString("Critical", "error"),
				ANSIThemeString(":", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("    Could not extract ", "default"),
				ANSIThemeString("kube-apiserver", "programname"),
				ANSIThemeString(" version (double-check that the server is running and that ", "default"),
				ANSIThemeString("https_proxy", "argument"),
				ANSIThemeString(" and  ", "default"),
				ANSIThemeString("no_proxy", "argument"),
				ANSIThemeString(" are correctly set); will abort.", "default")], stderr = True)
		abort = True
		critical += 1
		return abort, critical, error, warning, note

	server_major_version = cast(int, server_major_version)
	server_minor_version = cast(int, server_minor_version)

	# Kubernetes API based checks
	ansithemeprint([ANSIThemeString("\n[Checking ", "phase"),
			ANSIThemeString("kubelet", "programname"),
			ANSIThemeString(" & ", "phase"),
			ANSIThemeString("kube-proxy", "programname"),
			ANSIThemeString(" versions]", "phase")])

	from kubernetes_helper import KubernetesHelper  # pylint: disable=import-outside-toplevel
	kh = KubernetesHelper(about.PROGRAM_SUITE_NAME, about.PROGRAM_SUITE_VERSION, None)

	vlist, _status = kh.get_list_by_kind_namespace(("Node", ""), "")
	if vlist is None or _status != 200:
		vlist = []

	version_regex = re.compile(r"^v(\d+)\.(\d+)\..*")

	for node in vlist:
		node_name = deep_get(node, DictPath("metadata#name"))
		kubelet_version = deep_get(node, DictPath("status#nodeInfo#kubeletVersion"))
		kubeproxy_version = deep_get(node, DictPath("status#nodeInfo#kubeProxyVersion"))
		tmp = version_regex.match(kubelet_version)

		kubelet_major_version = None
		kubelet_minor_version = None
		kubeproxy_major_version = None
		kubeproxy_minor_version = None
		if tmp is not None:
			kubelet_major_version = int(tmp[1])
			kubelet_minor_version = int(tmp[2])
		else:
			ansithemeprint([ANSIThemeString("  ", "default"),
					ANSIThemeString("Error", "error"),
					ANSIThemeString(":", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("    Failed to extract ", "default"),
					ANSIThemeString("kubelet", "programname"),
					ANSIThemeString(" version on node ", "default"),
					ANSIThemeString(f"{node_name}", "hostname")], stderr = True)
			critical += 1
			mismatch = True

		tmp = version_regex.match(kubeproxy_version)
		if tmp is not None:
			kubeproxy_major_version = int(tmp[1])
			kubeproxy_minor_version = int(tmp[2])
		else:
			ansithemeprint([ANSIThemeString("  ", "default"),
					ANSIThemeString("Error", "error"),
					ANSIThemeString(":", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("    Failed to extract ", "default"),
					ANSIThemeString("kube-proxy", "programname"),
					ANSIThemeString(" version on node ", "default"),
					ANSIThemeString(f"{node_name}", "hostname")], stderr = True)
			critical += 1
			mismatch = True

		if kubelet_major_version is not None and kubelet_major_version != 1:
			ansithemeprint([ANSIThemeString("Critical", "critical"),
					ANSIThemeString(": ", "default"),
					ANSIThemeString(about.PROGRAM_SUITE_NAME, "programname"),
					ANSIThemeString(" has not been tested for any other major version of Kubernetes than v1; node ", "default"),
					ANSIThemeString(f"{node_name}", "hostname"),
					ANSIThemeString(" runs ", "default"),
					ANSIThemeString("kubelet ", "programname"),
					ANSIThemeString("version ", "default"),
					ANSIThemeString(f"{kubelet_version}", "version")], stderr = True)
			critical += 1
			mismatch = True

		if kubeproxy_major_version is not None and kubeproxy_major_version != 1:
			ansithemeprint([ANSIThemeString("Critical", "critical"),
					ANSIThemeString(": ", "default"),
					ANSIThemeString(about.PROGRAM_SUITE_NAME, "programname"),
					ANSIThemeString(" has not been tested for any other major version of Kubernetes than v1; node ", "default"),
					ANSIThemeString(f"{node_name}", "hostname"),
					ANSIThemeString(" runs ", "default"),
					ANSIThemeString("kube-proxy ", "programname"),
					ANSIThemeString("version ", "default"),
					ANSIThemeString(f"{kubeproxy_version}", "version")], stderr = True)
			critical += 1
			mismatch = True

		if kubelet_minor_version is not None and kubelet_minor_version > server_minor_version:
			ansithemeprint([ANSIThemeString("  ", "default"),
					ANSIThemeString("Error", "error"),
					ANSIThemeString(":", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("    The version of ", "default"),
					ANSIThemeString("kubelet", "programname"),
					ANSIThemeString(" (", "default"),
					ANSIThemeString(f"{kubelet_major_version}.{kubelet_minor_version}", "version"),
					ANSIThemeString(") on node ", "default"),
					ANSIThemeString(f"{node_name}", "hostname"),
					ANSIThemeString(" is newer than that of ", "default"),
					ANSIThemeString("kube-apiserver", "programname"),
					ANSIThemeString(" (", "default"),
					ANSIThemeString(f"{server_major_version}.{server_minor_version}", "version"),
					ANSIThemeString(");", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("       this is not supported.", "default")], stderr = True)
			error += 1
			mismatch = True
		elif kubelet_minor_version is not None and server_minor_version - 2 <= kubelet_minor_version < server_minor_version:
			ansithemeprint([ANSIThemeString("  ", "default"),
					ANSIThemeString("Warning", "warning"),
					ANSIThemeString(":", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("    The version of ", "default"),
					ANSIThemeString("kubelet", "programname"),
					ANSIThemeString(" (", "default"),
					ANSIThemeString(f"{kubelet_major_version}.{kubelet_minor_version}", "version"),
					ANSIThemeString(") on node ", "default"),
					ANSIThemeString(f"{node_name}", "hostname"),
					ANSIThemeString(" is a bit older than that of ", "default"),
					ANSIThemeString("kube-apiserver", "programname"),
					ANSIThemeString(" (", "default"),
					ANSIThemeString(f"{server_major_version}.{server_minor_version}", "version"),
					ANSIThemeString(");", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("         this is supported, but not recommended.", "default")], stderr = True)
			warning += 1
			mismatch = True
		elif kubelet_minor_version is not None and kubelet_minor_version < server_minor_version:
			ansithemeprint([ANSIThemeString("  ", "default"),
					ANSIThemeString("Error", "error"),
					ANSIThemeString(":", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("    The version of ", "default"),
					ANSIThemeString("kubelet", "programname"),
					ANSIThemeString(" (", "default"),
					ANSIThemeString(f"{kubelet_major_version}.{kubelet_minor_version}", "version"),
					ANSIThemeString(") on node ", "default"),
					ANSIThemeString(f"{node_name}", "hostname"),
					ANSIThemeString(" is much older than that of ", "default"),
					ANSIThemeString("kube-apiserver", "programname"),
					ANSIThemeString(" (", "default"),
					ANSIThemeString(f"{server_major_version}.{server_minor_version}", "version"),
					ANSIThemeString(");", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("       this is not supported.", "default")], stderr = True)
			error += 1
			mismatch = True

		if kubelet_minor_version is not None and kubeproxy_minor_version is not None and kubelet_minor_version != kubeproxy_minor_version:
			ansithemeprint([ANSIThemeString("  ", "default"),
					ANSIThemeString("Error", "error"),
					ANSIThemeString(":", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("    The version of ", "default"),
					ANSIThemeString("kubelet", "programname"),
					ANSIThemeString(" (", "default"),
					ANSIThemeString(f"{kubelet_major_version}.{kubelet_minor_version}", "version"),
					ANSIThemeString(") on node ", "default"),
					ANSIThemeString(f"{node_name}", "hostname"),
					ANSIThemeString(" is not the same as that of ", "default"),
					ANSIThemeString("kube-proxy", "programname"),
					ANSIThemeString(" (", "default"),
					ANSIThemeString(f"{kubeproxy_major_version}.{kubeproxy_minor_version}", "version"),
					ANSIThemeString(");", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("       this is not supported.", "default")], stderr = True)
			error += 1
			mismatch = True

	if not mismatch:
		ansithemeprint([ANSIThemeString("  OK", "ok")])

	return abort, critical, error, warning, note

required_pods: Dict[str, List[Dict[str, List]]] = {
	"api-server": [
		{
			"any_of": [("kube-system", "kube-apiserver")],
		},
	],
	"coredns": [
		{
			"any_of": [("kube-system", "coredns"), ("", "dns-default")],
		},
	],
	"etcd": [
		{
			"any_of": [("kube-system", "etcd")],
		},
	],
	"kube-controller-manager": [
		{
			"any_of": [("kube-system", "kube-controller-manager")],
		},
	],
	# DaemonSet
	"kube-proxy": [
		{
			"any_of": [("kube-system", "kube-proxy")],
			"note": [ANSIThemeString("Note", "note"),
				 ANSIThemeString(": Optional for ", "default"),
				 ANSIThemeString("CRC", "programname"),
				 ANSIThemeString("/", "separator"),
				 ANSIThemeString("OpenShift", "programname"),
				 ANSIThemeString(".\n", "default")],
		},
	],
	"kube-scheduler": [
		{
			# FIXME
			"any_of": [("kube-system", "kube-scheduler"), ("", "openshift-kube-scheduler")],
		},
	],
	"CNI": [
		{
			# antrea; DaemonSet
			# FIXME
			"any_of": [("kube-system", "antrea-agent")],
		},
		{
			# calico; Deployment
			"all_of": [("calico-apiserver", "calico-apiserver"), ("calico-system", "calico-kube-controllers")],
		},
		{
			# canal; DaemonSet
			# FIXME
			"any_of": [("", "canal")],
		},
		{
			# cilium; Deployment
			# FIXME
			"any_of": [("", "cilium-operator")],
		},
		{
			# flannel; DaemonSet
			# FIXME
			"any_of": [("", "kube-flannel-ds")],
		},
		{
			# kilo; DaemonSet
			# FIXME
			"any_of": [("", "kilo")],
		},
		{
			# kube-ovn; DaemonSet
			# FIXME
			"any_of": [("", "kube-ovn-cni")],
		},
		{
			# kube-router; DaemonSet
			# FIXME
			"any_of": [("", "kube-router")],
		},
		{
			# sdn; DaemonSet
			# FIXME
			"any_of": [("", "sdn")],
		},
		{
			# weave; DaemonSet
			# FIXME
			"any_of": [("", "weave-net")],
		},
	],
}

def get_pod_set(pods: List[Dict], any_of: List[Tuple[str, str]], all_of: List[Tuple[str, str]]) -> Tuple[List[Dict], Dict[Tuple[str, str], List[Dict]]]:
	"""
	Given an any_of list (namespace, pod_prefix), and an all_of list (namespace, pod_prefix),
	returns all pod objects (if any)

		Parameters:
			pods ([pod]): A list of pod objects
			any_of ([(str, str)]): A list of (namespace, name-prefix) of which at least one must exist
			all_of ({[(str, str)]}): A list of (namespace, name-prefix) of which all must exist
		Returns:
			([any_of], [all_of]):
				any_of ([(str, str)]): A list of (namespace, name) for pods matching the any_of criteria
				all_of ([(str, str)]): A dict indexed by (namespace, name-prefix)
						       of list of (namespace, name) for pods matching the all_of criteria
	"""

	any_of_matches: List[Dict] = []
	all_of_matches: Dict[Tuple[str, str], List[Dict]] = {}

	for obj in pods:
		pod_name = deep_get(obj, DictPath("metadata#name"), "")
		pod_namespace = deep_get(obj, DictPath("metadata#namespace"), "")
		for match_namespace, match_name in any_of:
			# If we're instructed to match namespace and the namespace doesn't match, skip this pod
			if len(match_namespace) > 0 and match_namespace != pod_namespace:
				continue
			# If the pod name doesn't start with the name prefix, skip this pod
			if not pod_name.startswith(match_name):
				continue
			any_of_matches.append(obj)

		for match_namespace, match_name in all_of:
			# If we're instructed to match namespace and the namespace doesn't match, skip this pod
			if len(match_namespace) > 0 and match_namespace != pod_namespace:
				continue
			# If the pod name doesn't start with the name prefix, skip this pod
			if not pod_name.startswith(match_name):
				continue
			if (match_namespace, match_name) not in all_of_matches:
				all_of_matches[(match_namespace, match_name)] = []
			all_of_matches[(match_namespace, match_name)].append(obj)

	# If either condition fails, return empty lists
	if len(all_of) > 0 and len(all_of_matches) == 0 or len(any_of) > 0 and len(any_of_matches) == 0:
		any_of_matches = []
		all_of_matches = {}

	return (any_of_matches, all_of_matches)

# pylint: disable-next=too-many-arguments,unused-argument
def check_running_pods(cluster_name: str, kubeconfig: Dict, cmtconfig_dict: Dict, user: str,
		       critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[bool, int, int, int, int]:
	"""
	This checks what pods are running and their status

		Parameters:
			cluster_name (str): The name of the cluster (unused)
			kubeconfig (dict): The kubeconfig file (unused)
			cmtconfig_dict (dict): The cmtconfig file (unused)
			critical (int): The current count of critical severity security issues
			error (int): The current count of error severity security issues
			warning (int): The current count of warning severity security issues
			note (int): The current count of note severity security issues
			kwargs (dict): Additional parameters
		Returns:
			(critical, error, warning, note):
				critical (int): The new count of critical severity security issues
				error (int): The new count of error severity security issues
				warning (int): The new count of warning severity security issues
				note (int): The new count of note severity security issues
	"""

	abort = False

	ansithemeprint([ANSIThemeString("\n[Checking required pods]", "phase")])

	from kubernetes_helper import KubernetesHelper  # pylint: disable=import-outside-toplevel
	kh = KubernetesHelper(about.PROGRAM_SUITE_NAME, about.PROGRAM_SUITE_VERSION, None)

	pods, _status = kh.get_list_by_kind_namespace(("Pod", ""), "")
	all_ok = True

	for rp, rp_data in required_pods.items():
		ansithemeprint([ANSIThemeString("•", "separator"),
				ANSIThemeString(f" {rp}", "programname")])

		matches = []

		for rp_match in rp_data:
			any_of = deep_get(rp_match, DictPath("any_of"), [])
			all_of = deep_get(rp_match, DictPath("all_of"), [])
			additional_info = deep_get(rp_match, DictPath("note"), [])
			any_of_matches, all_of_matches = get_pod_set(cast(List[Dict], pods), any_of, all_of)

			if len(any_of_matches) > 0 or len(all_of_matches) > 0:
				matches.append((any_of_matches, all_of_matches))

		if len(matches) == 0:
			if len(any_of) > 0 and len(any_of_matches) == 0:
				ansithemeprint([ANSIThemeString("  ", "default"),
						ANSIThemeString("Error", "error"),
						ANSIThemeString(":", "default")], stderr = True)
				ansithemeprint([ANSIThemeString("    At least one of the following pods is expected to be running:", "default")], stderr = True)
				for expected_namespace, expected_name in any_of:
					if len(expected_namespace) == 0:
						expected_namespace = "<any>"
					ansithemeprint([ANSIThemeString(f"      {expected_namespace}", "namespace"),
							ANSIThemeString("::", "separator"),
							ANSIThemeString(f"{expected_name}", "default")], stderr = True)
				all_ok = False
				error += 1

			if len(all_of) > 0 and len(all_of_matches) == 0:
				ansithemeprint([ANSIThemeString("  ", "default"),
						ANSIThemeString("Error", "error"),
						ANSIThemeString(":", "default")], stderr = True)
				ansithemeprint([ANSIThemeString("    All of the following pods are expected to be running:", "default")], stderr = True)
				for expected_namespace, expected_name in any_of:
					if len(expected_namespace) == 0:
						expected_namespace = "<any>"
					ansithemeprint([ANSIThemeString(f"      {expected_namespace}", "namespace"),
							ANSIThemeString("::", "separator"),
							ANSIThemeString(f"{expected_name}", "default")], stderr = True)
				all_ok = False
				error += 1

		if len(matches) > 1:
			ansithemeprint([ANSIThemeString("  ", "default"),
					ANSIThemeString("Warning", "warning"),
					ANSIThemeString(":", "default")], stderr = True)
			ansithemeprint([ANSIThemeString("    Multiple possibly conflicting options were detected for ", "default"),
					ANSIThemeString(f"{rp}", "programname"),
					ANSIThemeString(".\n", "default")], stderr = True)
			warning += 1
			all_ok = False

		if len(matches) > 0:
			all_pods = []

			for any_of_matches, all_of_matches in matches:
				all_pods += any_of_matches
				for _key, value in all_of_matches.items():
					all_pods += value

			first = True

			for obj in all_pods:
				pod_name = deep_get(obj, DictPath("metadata#name"), "")
				pod_namespace = deep_get(obj, DictPath("metadata#namespace"), "")
				pod_node = deep_get(obj, DictPath("spec#nodeName"), "<unset>")
				conditions = deep_get(obj, DictPath("status#conditions"), [])
				phase = deep_get(obj, DictPath("status#phase"), "")

				ready = "NotReady"
				for condition in conditions:
					if (deep_get(condition, DictPath("type"), "") == "Ready" and
					    deep_get(condition, DictPath("status"), "False") == "True"):
						ready = "Ready"
				if phase != "Running" or ready != "Ready":
					if first:
						ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString("Error", "error"),
							ANSIThemeString(":", "default")], stderr = True)
						ansithemeprint([ANSIThemeString("    The following pods should be in phase Running, condition Ready:", "default")])
						first = False
					ansithemeprint([ANSIThemeString("        ", "default"),
							ANSIThemeString(f"{pod_namespace}", "namespace"),
							ANSIThemeString("::", "separator"),
							ANSIThemeString(f"{pod_name}", "namespace"),
							ANSIThemeString(" (", "default"),
							ANSIThemeString(f"{phase}", "emphasis"),
							ANSIThemeString("; ", "separator"),
							ANSIThemeString(f"{ready}", "emphasis"),
							ANSIThemeString(")", "default"),
							ANSIThemeString(" on node ", "default"),
							ANSIThemeString(f"{pod_node}", "hostname")], stderr = True)
					error += 1
					all_ok = False

		if all_ok:
			ansithemeprint([ANSIThemeString("    OK\n", "success")])
		elif len(additional_info) > 0:
			ansithemeprint([ANSIThemeString("    ", "default")] + additional_info)

	print()

	return abort, critical, error, warning, note

recommended_directory_permissions = [
	{
		"path": BINDIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can create or overwrite files in ", "default"),
				  ANSIThemeString(f"{BINDIR}", "path"),
				  ANSIThemeString(" they can obtain elevated privileges", "default")]
	},
	{
		"path": CMTDIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("    If other users can create or replace files in ", "default"),
				  ANSIThemeString(f"{CMTDIR}", "path"),
				  ANSIThemeString(" they may be able to obtain elevated privileges", "default")]
	},
	{
		"path": CMT_LOGS_DIR,
		"alertmask": 0o077,
		"usergroup_alertmask": 0o027,
		"severity": "error",
		"justification": [ANSIThemeString("    If other users can read, create or replace files in ", "default"),
				  ANSIThemeString(f"{CMT_LOGS_DIR}\n", "path"),
				  ANSIThemeString("    they can cause ", "default"),
				  ANSIThemeString("cmu", "programname"),
				  ANSIThemeString(" to malfunction and possibly hide signs\n", "default"),
				  ANSIThemeString("    of a compromised cluster and may be able to obtain sensitive information\n", "default"),
				  ANSIThemeString("    from audit messages.", "default")]
	},
	{
		"path": CMT_CONFIG_FILE_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can create or replace files in ", "default"),
				  ANSIThemeString(f"{CMT_CONFIG_FILE_DIR}", "path"),
				  ANSIThemeString(" they may be able to obtain elevated privileges", "default")]
	},
	{
		"path": ANSIBLE_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can create or replace files in ", "default"),
				  ANSIThemeString(f"{ANSIBLE_DIR}", "path"),
				  ANSIThemeString(" they can obtain elevated privileges", "default")]
	},
	{
		"path": CMT_HOOKS_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can create or replace files in ", "default"),
				  ANSIThemeString(f"{CMT_HOOKS_DIR}", "path"),
				  ANSIThemeString(" they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(CMT_HOOKS_DIR, "pre-upgrade.d")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can create or replace files in ", "default"),
				  ANSIThemeString(f"{os.path.join(CMT_HOOKS_DIR, 'pre-upgrade.d')}", "path"),
				  ANSIThemeString(" they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(CMT_HOOKS_DIR, "post-upgrade.d")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can create or replace files in ", "default"),
				  ANSIThemeString(f"{os.path.join(CMT_HOOKS_DIR, 'post-upgrade.d')}", "path"),
				  ANSIThemeString(" they can obtain elevated privileges", "default")]
	},
	{
		"path": DEPLOYMENT_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can create or replace files in ", "default"),
				  ANSIThemeString(f"{DEPLOYMENT_DIR}", "path"),
				  ANSIThemeString(" they can obtain elevated privileges", "default")]
	},
	{
		"path": ANSIBLE_LOG_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "warning",
		"justification": [ANSIThemeString("If others users can create or replace files in ", "default"),
				  ANSIThemeString(f"{ANSIBLE_LOG_DIR}", "path"),
				  ANSIThemeString(" they can spoof results from playbook runs", "default")]
	},
	{
		"path": KUBE_CONFIG_DIR,
		"alertmask": 0o077,
		"usergroup_alertmask": 0o027,
		"severity": "critical",
		"justification": [ANSIThemeString("If others users can read, create or replace files in ", "default"),
				  ANSIThemeString(f"{KUBE_CONFIG_DIR}", "path"),
				  ANSIThemeString(" they can obtain cluster access", "default")]
	},
	{
		"path": THEME_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "error",
		"justification": [ANSIThemeString("If others users can create or replace files in ", "default"),
				  ANSIThemeString(f"{THEME_DIR}", "path"),
				  ANSIThemeString(" they can cause ", "default"),
				  ANSIThemeString("cmu", "programname"),
				  ANSIThemeString(" to malfunction", "default")]
	},
	{
		"path": PARSER_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "error",
		"justification": [ANSIThemeString("If others users can create or replace files in ", "default"),
				  ANSIThemeString(f"{PARSER_DIR}", "path"),
				  ANSIThemeString(" they can cause ", "default"),
				  ANSIThemeString("cmu", "programname"),
				  ANSIThemeString(" to malfunction and possibly hide signs of a compromised cluster", "default")]
	},
	{
		"path": VIEW_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "error",
		"justification": [ANSIThemeString("If others users can create or replace files in ", "default"),
				  ANSIThemeString(f"{VIEW_DIR}", "path"),
				  ANSIThemeString(" they can cause ", "default"),
				  ANSIThemeString("cmu", "programname"),
				  ANSIThemeString(" to malfunction and possibly hide signs of a compromised cluster", "default")]
	},
]

recommended_file_permissions = [
	{
		"path": FilePath(os.path.join(BINDIR, "cmtadm")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"executable": True,
		"severity": "critical",
		"justification": [ANSIThemeString("If others users can modify executables they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(BINDIR, "cmtinv")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"executable": True,
		"severity": "critical",
		"justification": [ANSIThemeString("If others users can modify executables they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(BINDIR, "cmt")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"executable": True,
		"severity": "critical",
		"justification": [ANSIThemeString("If others users can modify executables they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(BINDIR, "cmu")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"executable": True,
		"severity": "critical",
		"justification": [ANSIThemeString("If others users can modify configlets they may be able to obtain elevated privileges", "default")]
	},
	{
		"path": CMT_CONFIG_FILE_DIR,
		"suffixes": (".yml", ".yaml"),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"executable": False,
		"severity": "critical",
		"justification": [ANSIThemeString("If others users can modify configlets they may be able to obtain elevated privileges", "default")]
	},
	{
		"path": ANSIBLE_PLAYBOOK_DIR,
		"suffixes": (".yml", ".yaml"),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"executable": False,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can modify playbooks they can obtain elevated privileges", "default")]
	},
	{
		"path": ANSIBLE_INVENTORY,
		"alertmask": 0o077,
		"usergroup_alertmask": 0o007,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can read or modify the Ansible inventory they can obtain elevated privileges", "default")]
	},
	{
		"path": KUBE_CONFIG_FILE,
		"alertmask": 0o077,
		"usergroup_alertmask": 0o007,
		"executable": False,
		"severity": "critical",
		"justification": [ANSIThemeString("If others users can read or modify cluster configuration files they can obtain cluster access", "default")]
	},
	{
		"path": KUBE_CREDENTIALS_FILE,
		"alertmask": 0o077,
		"usergroup_alertmask": 0o007,
		"executable": False,
		"severity": "critical",
		"justification": [ANSIThemeString("If others users can read or modify cluster credential files they can obtain cluster access", "default")],
		# This is not a required file, so don't warn if it doesn't exist
		"optional": True,
	},
]

# pylint: disable-next=too-many-arguments
def __check_permissions(recommended_permissions: List[Dict], pathtype: str, user: str,
			usergroup: str, critical: int, error: int, warning: int, note: int) -> Tuple[bool, bool, int, int, int, int]:
	"""
	Check permissions for a path
		Parameters:
			recommended_permissions (list[dict]): A dict with the path to check, the recommended permissions, severity, justification, etc.
			pathtype (str): The type of the path
			user (str): The user to check against
			usergroup (str): The usergroup to check against
			critical (int): The current count of critical severity security issues
			error (int): The current count of error severity security issues
			warning (int): The current count of warning severity security issues
			note (int): The current count of note severity security issues
		Returns:
			(issue, critical, error, warning, note):
				issue (bool): Found a security issue
				critical (int): The new count of critical severity security issues
				error (int): The new count of error severity security issues
				warning (int): The new count of warning severity security issues
				note (int): The new count of note severity security issues
	"""

	issue = False
	abort = False

	for permissions in recommended_permissions:
		path = deep_get(permissions, DictPath("path"))
		alertmask = deep_get(permissions, DictPath("alertmask"), 0o077)
		usergroup_alertmask = deep_get(permissions, DictPath("usergroup_alertmask"), alertmask)
		severity = deep_get(permissions, DictPath("severity"), "critical")
		justification = deep_get(permissions, DictPath("justification"), [ANSIThemeString("<no justification provided>", "emphasis")])
		executable = deep_get(permissions, DictPath("executable"), False)
		suffixes = deep_get(permissions, DictPath("suffixes"))
		optional = deep_get(permissions, DictPath("optional"), False)

		if len(usergroup) > 0:
			alertmask = usergroup_alertmask
		notemask = 0o000
		if pathtype == "file" and not executable:
			notemask = 0o111

		path_entry = Path(path)

		if path_entry.exists():
			# If this is a file, but we operate on files we should apply these tests for every matching file in this directory
			paths: Union[List[Path], Generator[Path, None, None]] = []

			if pathtype == "file" and path_entry.is_dir():
				paths = path_entry.iterdir()
			else:
				paths = [path_entry]

			for entry in paths:
				if pathtype == "file":
					if not entry.is_file() and not entry.is_symlink():
						continue

					if suffixes is not None and not str(entry).endswith(suffixes):
						continue

				try:
					path_owner = entry.owner()
				except KeyError:
					ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString("Critical", "error"),
							ANSIThemeString(":", "default")], stderr = True)
					ansithemeprint([ANSIThemeString(f"    The owner of the {pathtype} ", "default"),
							ANSIThemeString(f"{entry}", "path"),
							ANSIThemeString(" does not exist in the system database; aborting.", "default")], stderr = True)
					sys.exit(errno.ENOENT)
				try:
					path_group = entry.group()
				except KeyError:
					ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString("Critical", "error"),
							ANSIThemeString(":", "default")], stderr = True)
					ansithemeprint([ANSIThemeString(f"    The group of the {pathtype} ", "default"),
							ANSIThemeString(f"{entry}", "path"),
							ANSIThemeString(" does not exist in the system database; aborting.", "default")], stderr = True)
					sys.exit(errno.ENOENT)
				path_stat = entry.stat()
				path_permissions = path_stat.st_mode & 0o777
				recommended_permissions = 0o777 & ~(alertmask | notemask)

				if path_owner not in (user, "root"):
					ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString("Critical", severity),
							ANSIThemeString(f": The {pathtype} ", "default"),
							ANSIThemeString(f"{entry}", "path"),
							ANSIThemeString(" is not owned by ", "default"),
							ANSIThemeString(user, "emphasis")], stderr = True)
					ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString("Justification", "emphasis"),
							ANSIThemeString(": if other users can overwrite files they may be able to achieve elevated privileges", "default")], stderr = True)
					critical += 1
					issue = True

				if len(usergroup) > 0 and path_group != usergroup:
					ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString("Critical", severity),
							ANSIThemeString(f": The {pathtype} ", "default"),
							ANSIThemeString(f"{entry}", "path"),
							ANSIThemeString(" does not belong to the user group for ", "default"),
							ANSIThemeString(user, "emphasis")], stderr = True)
					ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString("Justification", "emphasis"),
							ANSIThemeString(": ", "default")] + justification, stderr = True)
					print()
					critical += 1
					issue = True

				if path_permissions & alertmask != 0:
					ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString(f"{severity.capitalize()}", severity),
							ANSIThemeString(":", "default")], stderr = True)
					ansithemeprint([ANSIThemeString(f"    The permissions for the {pathtype} ", "default"),
							ANSIThemeString(f"{entry}", "path"),
							ANSIThemeString(" are ", "default"),
							ANSIThemeString(f"{path_permissions:03o}", "emphasis"),
							ANSIThemeString(";", "default")], stderr = True)
					ansithemeprint([ANSIThemeString("    the recommended permissions are ", "default"),
							ANSIThemeString(f"{recommended_permissions:03o}", "emphasis"),
							ANSIThemeString(" (or stricter).", "default")], stderr = True)
					ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString("Justification", "emphasis"),
							ANSIThemeString(": ", "default")], stderr = True)
					ansithemeprint(justification, stderr = True)
					print()

					if severity == "critical":
						critical += 1
						issue = True
					elif severity == "error":
						error += 1
						issue = True
					elif severity == "warning":
						warning += 1
						issue = True
					elif severity == "note":
						note += 1
						issue = True

				if path_permissions & notemask != 0:
					ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString("Note", "note"),
							ANSIThemeString(":", "default")])
					ansithemeprint([ANSIThemeString(f"    The permissions for the {pathtype} ", "default"),
							ANSIThemeString(f"{entry}", "path"),
							ANSIThemeString(" are ", "default"),
							ANSIThemeString(f"{path_permissions:03o}", "emphasis"),
							ANSIThemeString("; this file is not an executable and should not have the executable bit set", "default")])
		else:
			if not optional:
				ansithemeprint([ANSIThemeString("  ", "default"),
						ANSIThemeString("Warning", "warning"),
						ANSIThemeString(":", "default")], stderr = True)
				ansithemeprint([ANSIThemeString(f"    The {pathtype} ", "default"),
						ANSIThemeString(f"{path}", "path"),
						ANSIThemeString(" does not exist; skipping.\n", "default")], stderr = True)
				warning += 1
				issue = True
			continue

	return abort, issue, critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_file_permissions(cluster_name: str, kubeconfig: Dict, cmtconfig_dict: Dict, user: str,
			   critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[bool, int, int, int, int]:
	"""
	This checks whether any files or directories have insecure permissions

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			cmtconfig_dict (dict): The cmtconfig file
			critical (int): The current count of critical severity security issues
			error (int): The current count of error severity security issues
			warning (int): The current count of warning severity security issues
			note (int): The current count of note severity security issues
			kwargs (dict): Additional parameters
		Returns:
			critical (int), error (int), warning (int), note (int):
				critical: The new count of critical severity security issues
				error: The new count of error severity security issues
				warning: The new count of warning severity security issues
				note: The new count of note severity security issues
	"""

	abort = False

	ansithemeprint([ANSIThemeString("[Checking directory and file permissions]", "phase")])

	usergroup = deep_get(kwargs, DictPath("usergroup"), "")

	abort, issue, critical, error, warning, note = \
		__check_permissions(recommended_directory_permissions, "directory", user, usergroup, critical, error, warning, note)
	abort, issue, critical, error, warning, note = \
		__check_permissions(recommended_file_permissions, "file", user, usergroup, critical, error, warning, note)

	if not issue:
		ansithemeprint([ANSIThemeString("  OK\n", "emphasis")])

	return abort, critical, error, warning, note

# pylint: disable-next=unused-argument
def run_playbook(playbookpath: FilePath, hosts: List[str], extra_values: Optional[Dict] = None, quiet: bool = False) -> Tuple[int, Dict]:
	"""
	Run a playbook

		Parameters:
			playbookpath (FilePath): A path to the playbook to run
			hosts (list[str]): A list of hosts to run the playbook on
			extra_values (dict): A dict of values to set before running the playbook
			quiet (bool): Unused
		Returns:
			retval (int): The return value from ansible_run_playbook_on_selection()
			ansible_results (dict): A dict with the results from the run
	"""

	# Set necessary Ansible keys before running playbooks
	http_proxy = deep_get(cmtlib.cmtconfig, DictPath("Network#http_proxy"), "")
	if http_proxy is None:
		http_proxy = ""
	https_proxy = deep_get(cmtlib.cmtconfig, DictPath("Network#https_proxy"), "")
	if https_proxy is None:
		https_proxy = ""
	no_proxy = deep_get(cmtlib.cmtconfig, DictPath("Network#no_proxy"), "")
	if no_proxy is None:
		no_proxy = ""
	insecure_registries = deep_get(cmtlib.cmtconfig, DictPath("Docker#insecure_registries"), [])
	registry_mirrors = deep_get(cmtlib.cmtconfig, DictPath("Containerd#registry_mirrors"), [])
	retval = 0

	use_proxy = "no"
	if len(http_proxy) > 0 or len(https_proxy) > 0:
		use_proxy = "yes"

	if extra_values is None:
		extra_values = {}

	values = {
		"http_proxy": http_proxy,
		"https_proxy": https_proxy,
		"no_proxy": no_proxy,
		"insecure_registries": insecure_registries,
		"registry_mirrors": registry_mirrors,
		"use_proxy": use_proxy,
	}
	merged_values = { **values, **extra_values }

	retval, ansible_results = ansible_run_playbook_on_selection(playbookpath, selection = hosts, values = merged_values)

	ansible_print_play_results(retval, ansible_results)

	return retval, ansible_results

# pylint: disable-next=too-many-arguments,unused-argument
def check_control_plane(cluster_name: str, kubeconfig: Dict, cmtconfig_dict: Dict, user: str,
			critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[bool, int, int, int, int]:
	"""
	This checks whether a host is suitable to be used as a control plane

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			cmtconfig_dict (dict): The cmtconfig file
			critical (int): The current count of critical severity security issues
			error (int): The current count of error severity security issues
			warning (int): The current count of warning severity security issues
			note (int): The current count of note severity security issues
			kwargs (dict): Additional parameters
		Returns:
			(critical, error, warning, note):
				critical (int): The new count of critical severity security issues
				error (int): The new count of error severity security issues
				warning (int): The new count of warning severity security issues
				note (int): The new count of note severity security issues
	"""

	abort = False

	# The host(s) to check
	hosts = deep_get(kwargs, DictPath("hosts"), [])
	playbookpath = FilePath(str(PurePath(ANSIBLE_PLAYBOOK_DIR).joinpath("preflight_check.yaml")))

	ansithemeprint([ANSIThemeString("[Checking whether ", "phase")] +
		       ansithemestring_join_tuple_list(hosts, formatting = "hostname") +
		       [ANSIThemeString(" are suitable as control plane(s)]", "phase")])

	extra_values = {
		"ansible_become_pass": deep_get(ansible_configuration, DictPath("ansible_password")),
		"ansible_ssh_pass": deep_get(ansible_configuration, DictPath("ansible_password")),
		"role": "control-plane",
	}

	_retval, ansible_results = run_playbook(playbookpath, hosts = hosts, extra_values = extra_values)

	for host, host_results in ansible_results.items():
		ansible_os_family = ""
		for taskdata in host_results:
			taskname = str(deep_get(taskdata, DictPath("task"), ""))

			if taskname == "Gathering Facts":
				ansible_os_family = deep_get(taskdata, DictPath("ansible_facts#ansible_os_family"), "")
				continue

			if taskname == "Checking whether the host runs an OS supported for control planes":
				if deep_get(taskdata, DictPath("retval")) != 0:
					critical += 1
					ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString("Critical", "critical"),
							ANSIThemeString(":", "default")], stderr = True)
					ansithemeprint([ANSIThemeString("    Unsupported Operating System ", "default"),
							ANSIThemeString(f"{ansible_os_family}", "programname"),
							ANSIThemeString("; currently the only supported OS family", "default")], stderr = True)
					ansithemeprint([ANSIThemeString("    for control planes is ", "default"),
							ANSIThemeString("Debian", "programname"),
							ANSIThemeString("; aborting.\n", "default")], stderr = True)
					break

			if taskname == "Check whether the host is a Kubernetes control plane":
				if deep_get(taskdata, DictPath("retval")) != 0:
					critical += 1
					ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString("Critical", "critical"),
							ANSIThemeString(":", "default")])
					ansithemeprint([ANSIThemeString("    Host ", "default"),
							ANSIThemeString(f"{host}", "hostname"),
							ANSIThemeString(" seems to already be running a Kubernetes API-server; aborting.\n", "default")], stderr = True)
					break

			if taskname == "Check whether the host is a Kubernetes node":
				if deep_get(taskdata, DictPath("retval")) != 0:
					critical += 1
					ansithemeprint([ANSIThemeString("  ", "default"),
							ANSIThemeString("Critical", "critical"),
							ANSIThemeString(":", "default")], stderr = True)
					ansithemeprint([ANSIThemeString("    Host ", "default"),
							ANSIThemeString(f"{host}", "hostname"),
							ANSIThemeString(" seems to already have a running kubelet; aborting.\n", "default")], stderr = True)
					break

	return abort, critical, error, warning, note
