#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

"""
This module provides modules for troubleshooting malfunctioning clusters,
auditing configuration and cluster for potential security issues,
pre-flight checks to run before preparing or installing new systems,
and pre-upgrade checks to run before upgrading a system to a newer version.

This module requires init_iktprint() to have been executed first
"""

import errno
import os
from pathlib import Path, PurePath
import re
import sys
from typing import Dict, Generator, List, Tuple, Union

from ansible_helper import ansible_configuration
from ansible_helper import ansible_run_playbook_on_selection, ansible_print_play_results

from iktio import execute_command_with_response
from ikttypes import ANSIThemeString, deep_get, DictPath, FilePath
from iktpaths import BINDIR, IKTDIR, IKT_LOGS_DIR
from iktpaths import ANSIBLE_DIR, ANSIBLE_INVENTORY, ANSIBLE_LOG_DIR, ANSIBLE_PLAYBOOK_DIR
from iktpaths import DEPLOYMENT_DIR, IKT_CONFIG_FILE_DIR, IKT_HOOKS_DIR, KUBE_CONFIG_DIR, PARSER_DIR, THEME_DIR, VIEW_DIR
from iktpaths import IKT_CONFIG_FILE, KUBE_CONFIG_FILE, SSH_BIN_PATH
import iktlib
from iktlib import check_deb_versions
from iktprint import ansithemestring_join_tuple_list, iktprint

from kubernetes_helper import kubectl_get_version

import about

# Check file permissions:
# .ssh should be 700
# .ssh/authorized_keys should be 644, 640, or 600
# .ssh/

# pylint: disable-next=too-many-arguments,unused-argument
def check_security_disable_strict_host_key_checking(cluster_name: str, kubeconfig: Dict, iktconfig_dict: Dict, user: str,
						    critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[int, int, int, int]:
	"""
	This checks whether or not strict host key checking has been disabled in iktconfig

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			iktconfig_dict (dict): The iktconfig file
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

	iktprint([ANSIThemeString("[Checking for insecure configuration options in ", "phase"),
		  ANSIThemeString(f"{IKT_CONFIG_FILE}", "path"),
		  ANSIThemeString("]", "phase")])
	disablestricthostkeychecking = deep_get(iktconfig_dict, DictPath("Nodes#disablestricthostkeychecking"), False)
	if disablestricthostkeychecking == False:
		iktprint([ANSIThemeString("  OK\n", "emphasis")])
	else:
		iktprint([ANSIThemeString("  Warning", "warning"),
			  ANSIThemeString(": strict SSH host key checking is disabled; this is a potential security threat.", "emphasis")], stderr = True)
		iktprint([ANSIThemeString("    If strict SSH host key checking is disabled other systems can impersonate the remote host", "default")], stderr = True)
		iktprint([ANSIThemeString("    and thus perform Man in the Middle (MITM) attacks.", "default")], stderr = True)
		iktprint([ANSIThemeString("    It is strongly adviced that you enable strict SSH host key checking", "default")], stderr = True)
		iktprint([ANSIThemeString("    unless you're absolutely certain that your network environment is safe.\n", "default")], stderr = True)
		error += 1

	return critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_sudo_configuration(cluster_name: str, kubeconfig: Dict, iktconfig_dict: Dict, user: str,
			     critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[int, int, int, int]:
	"""
	This checks whether the user is in /etc/sudoers or /etc/sudoers.d,
	and whether the user can sudo without a password

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			iktconfig_dict (dict): The iktconfig file
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

	iktprint([ANSIThemeString("[Checking whether ", "phase"),
		  ANSIThemeString(f"{user}", "path"),
		  ANSIThemeString(" is in ", "phase"),
		  ANSIThemeString("/etc/sudoers", "path"),
		  ANSIThemeString(" or ", "default"),
		  ANSIThemeString("/etc/sudoers.d", "path"),
		  ANSIThemeString("]", "phase")])
	args = ["/usr/bin/sudo", "-l"]
	result = execute_command_with_response(args)

	sudoer = True

	# Safe
	sudo_msg_regex = re.compile(r"^User ([^\s]+) is not allowed to run sudo on.*")

	for line in result.splitlines():
		tmp = sudo_msg_regex.match(line)
		if tmp is not None:
			iktprint([ANSIThemeString("  Error", "error"),
				  ANSIThemeString(": ", "default"),
				  ANSIThemeString(user, "path"),
				  ANSIThemeString(" is not in ", "default"),
				  ANSIThemeString("/etc/sudoers", "path"),
				  ANSIThemeString(" or ", "default"),
				  ANSIThemeString("/etc/sudoers.d\n", "path")], stderr = True)
			error += 1
			sudoer = False
			break

	if sudoer == True:
		iktprint([ANSIThemeString("  OK\n", "emphasis")])

		iktprint([ANSIThemeString("[Checking whether", "phase"),
			  ANSIThemeString(f" {user} ", "path"),
			  ANSIThemeString("can perform passwordless sudo]", "phase")])
		args = ["/usr/bin/sudo", "-l"]
		result = execute_command_with_response(args)
		passwordless_sudo = False

		# Safe
		sudo_permissions_regex = re.compile(r"^\s*\(ALL(\s*:\s*ALL)?\)\s*NOPASSWD:\s*ALL\s*$")

		for line in result.splitlines():
			tmp = sudo_permissions_regex.match(line)
			if tmp is not None:
				iktprint([ANSIThemeString("  OK\n", "emphasis")])
				passwordless_sudo = True
				break

		if passwordless_sudo == False:
			iktprint([ANSIThemeString("  Error", "error"),
				  ANSIThemeString(": ", "default"),
				  ANSIThemeString(user, "path"),
				  ANSIThemeString(" cannot perform passwordless sudo\n", "default")], stderr = True)
			error += 1

	return critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_known_hosts_hashing(cluster_name: str, kubeconfig: Dict, iktconfig_dict: Dict, user: str,
			      critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[int, int, int, int]:
	"""
	This checks whether ssh known_hosts hashing is enabled

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			iktconfig_dict (dict): The iktconfig file
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

	iktprint([ANSIThemeString("[Checking whether ", "phase"),
		  ANSIThemeString("ssh", "command"),
		  ANSIThemeString(" known_hosts hashing is enabled]", "phase")])
	iktprint([ANSIThemeString("  Note", "note"),
		  ANSIThemeString(": this test is not 100% reliable since ssh settings can vary based on target host\n", "default")])
	args = [SSH_BIN_PATH, "-G", "localhost"]
	result = execute_command_with_response(args)

	# Safe
	hashknownhosts_regex = re.compile(r"^hashknownhosts\s+yes$")

	for line in result.splitlines():
		tmp = hashknownhosts_regex.match(line)
		if tmp is not None:
			iktprint([ANSIThemeString("  Warning", "warning"),
				  ANSIThemeString(": ", "default"),
				  ANSIThemeString("ssh", "command"),
				  ANSIThemeString(" known_hosts hashing is enabled; this may cause issues with ", "default"),
				  ANSIThemeString("paramiko\n", "command")], stderr = True)
			warning += 1
			break

	return critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_insecure_kube_config_options(cluster_name: str, kubeconfig: Dict, iktconfig_dict: Dict, user: str,
				       critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[int, int, int, int]:
	"""
	This checks whether .kube/config has insecure options

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			iktconfig_dict (dict): The iktconfig file
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

	iktprint([ANSIThemeString("[Checking for insecure ", "phase"),
		  ANSIThemeString(f"{KUBE_CONFIG_FILE}", "path"),
		  ANSIThemeString(" options]", "phase")])

	insecureskiptlsverify = False

	for cluster in deep_get(kubeconfig, DictPath("clusters"), []):
		if deep_get(cluster, DictPath("name"), "") == cluster_name:
			insecureskiptlsverify = deep_get(cluster, DictPath("insecure-skip-tls-verify"), False)
			break

	if insecureskiptlsverify == False:
		iktprint([ANSIThemeString("  OK\n", "emphasis")])
	else:
		iktprint([ANSIThemeString("  Warning", "critical"),
			  ANSIThemeString(": TLS verification has been disabled in ", "emphasis"),
			  ANSIThemeString(f"{KUBE_CONFIG_FILE}", "path"),
			  ANSIThemeString("; this is a potential security threat.", "emphasis")], stderr = True)
		iktprint([ANSIThemeString("    If TLS verification is disabled other systems can impersonate the control plane", "default")], stderr = True)
		iktprint([ANSIThemeString("    and thus perform Man in the Middle (MITM) attacks.", "default")], stderr = True)
		iktprint([ANSIThemeString("    It is adviced that you remove the ", "default"),
			  ANSIThemeString("insecure-skip-tls-verify", "argument"),
			  ANSIThemeString(" option from ", "default"),
			  ANSIThemeString(f"{KUBE_CONFIG_FILE}", "path"),
			  ANSIThemeString(",", "default")], stderr = True)
		iktprint([ANSIThemeString("    unless you're absolutely certain that your network environment is safe.\n", "default")], stderr = True)
		critical += 1

	return critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_client_server_version_match(cluster_name: str, kubeconfig: Dict, iktconfig_dict: Dict, user: str,
				      critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[int, int, int, int]:
	"""
	This checks whether the versions of the various Kubernetes match properly

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			iktconfig_dict (dict): The iktconfig file
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

	# Is the version of kubectl within one version of the cluster version?
	iktprint([ANSIThemeString("[Checking client/server version match]", "phase")])

	_kubectl_major_version, kubectl_minor_version, kubectl_git_version, server_major_version, server_minor_version, server_git_version = kubectl_get_version()

	iktprint([ANSIThemeString("         kubectl ", "programname"),
		  ANSIThemeString("version: ", "default"),
		  ANSIThemeString(f"{kubectl_git_version}", "version")])
	iktprint([ANSIThemeString("  kube-apiserver ", "programname"),
		  ANSIThemeString("version: ", "default"),
		  ANSIThemeString(f"{server_git_version}", "version")])

	print()

	if server_major_version != 1:
		iktprint([ANSIThemeString("  ", "default"),
			  ANSIThemeString("Critical", "critical"),
			  ANSIThemeString(": ", "default"),
			  ANSIThemeString(f"{about.PROGRAM_SUITE_NAME}", "programname"),
			  ANSIThemeString(" has not been tested for any other major version of Kubernetes than ", "default"),
			  ANSIThemeString("v1", "version"),
			  ANSIThemeString("; aborting.", "default")], stderr = True)
		sys.exit(errno.ENOTSUP)

	if kubectl_minor_version > server_minor_version and kubectl_minor_version == server_minor_version + 1:
		iktprint([ANSIThemeString("  ", "default"),
			  ANSIThemeString("Note", "note"),
			  ANSIThemeString(": The ", "default"),
			  ANSIThemeString("kubectl", "programname"),
			  ANSIThemeString(" version is one minor version newer than that of ", "default"),
			  ANSIThemeString("kube-apiserver", "programname"),
			  ANSIThemeString(";", "default")])
		iktprint([ANSIThemeString("      this is a supported configuration, but it's generally recommended to keep the versions in sync.", "default")])
		note += 1
		mismatch = True
	elif kubectl_minor_version > server_minor_version:
		iktprint([ANSIThemeString("  ", "default"),
			  ANSIThemeString("Warning", "note"),
			  ANSIThemeString(": The ", "default"),
			  ANSIThemeString("kubectl", "programname"),
			  ANSIThemeString(" version is more than one minor version newer than that of ", "default"),
			  ANSIThemeString("kube-apiserver", "programname"),
			  ANSIThemeString(";", "default")], stderr = True)
		iktprint([ANSIThemeString("         this might work, but it's generally recommended to keep the versions in sync.", "default")], stderr = True)
		warning += 1
		mismatch = True
	elif kubectl_minor_version < server_minor_version and kubectl_minor_version + 1 == server_minor_version:
		iktprint([ANSIThemeString("  ", "default"),
			  ANSIThemeString("Warning", "note"),
			  ANSIThemeString(": The ", "default"),
			  ANSIThemeString("kubectl", "programname"),
			  ANSIThemeString(" version is one minor version older than that of ", "default"),
			  ANSIThemeString("kube-apiserver", "programname"),
			  ANSIThemeString(";", "default")])
		iktprint([ANSIThemeString("      this is a supported configuration, but it's generally recommended to keep the versions in sync.", "default")])
		warning += 1
		mismatch = True
	elif kubectl_minor_version < server_minor_version:
		iktprint([ANSIThemeString("  ", "default"),
			  ANSIThemeString("Error", "note"),
			  ANSIThemeString(": The ", "default"),
			  ANSIThemeString("kubectl", "programname"),
			  ANSIThemeString(" version is much older than that of ", "default"),
			  ANSIThemeString("kube-apiserver", "programname"),
			  ANSIThemeString(";", "default")], stderr = True)
		iktprint([ANSIThemeString("       this is NOT supported and is likely to cause issues.", "default")], stderr = True)
		error += 1
		mismatch = True

	if mismatch == False:
		iktprint([ANSIThemeString("OK", "ok")])

	return critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_containerd_and_docker(cluster_name: str, kubeconfig: Dict, iktconfig_dict: Dict, user: str,
				critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[int, int, int, int]:
	"""
	This checks whether docker-ce / containerd.io is installed instead of docker.io / containerd

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			iktconfig_dict (dict): The iktconfig file
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

	iktprint([ANSIThemeString("[Checking whether ", "phase"),
		  ANSIThemeString("docker-ce / containerd.io", "path"),
		  ANSIThemeString(" is installed instead of ", "phase"),
		  ANSIThemeString("docker.io / containerd", "path"),
		  ANSIThemeString("]", "phase")])
	iktprint([ANSIThemeString("  Note", "emphasis"),
		  ANSIThemeString(": this is only an issue if you intend to use this host as a control plane or node\n", "default")])
	deb_versions = check_deb_versions(["docker.io", "containerd", "docker-ce", "containerd.io"])
	conflict = False
	for package, _installed_version, _candidate_version, _all_versions in deb_versions:
		if package in ("docker-ce", "containerd.io"):
			iktprint([ANSIThemeString("  Error", "error"),
				  ANSIThemeString(": ", "default"),
				  ANSIThemeString("docker-ce / containerd.io", "path"),
				  ANSIThemeString(" is installed; use ", "default"),
				  ANSIThemeString("docker.io / containerd", "path"),
				  ANSIThemeString(" instead\n", "default")], stderr = True)
			iktprint([ANSIThemeString("  ", "default"),
				  ANSIThemeString("Suggested fix:", "header")])
			iktprint([ANSIThemeString("    sudo apt ", "programname"),
				  ANSIThemeString("install ", "command"),
				  ANSIThemeString("docker.io containerd docker-ce- containerd.io-\n", "argument")])
			error += 1
			conflict = True
			break

	if conflict == False:
		iktprint([ANSIThemeString("  OK\n", "emphasis")])

	return critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_kubelet_and_kube_proxy_versions(cluster_name: str, kubeconfig: Dict, iktconfig_dict: Dict, user: str,
					  critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[int, int, int, int]:
	"""
	This checks whether the versions of kubelet and kube-proxy are acceptable

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			iktconfig_dict (dict): The iktconfig file
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

	# Check kubelet and kube-proxy versions;
	# they can be up to two minor versions older than kube-apiserver,
	# but must not be newer

	mismatch = False

	# Kubernetes API based checks
	iktprint([ANSIThemeString("\n[Checking kubelet & kube-proxy versions]", "phase")])

	_kubectl_major_version, _kubectl_minor_version, _kubectl_git_version, server_major_version, server_minor_version, _server_git_version = kubectl_get_version()

	from kubernetes_helper import KubernetesHelper # pylint: disable=import-outside-toplevel
	kh = KubernetesHelper(about.PROGRAM_SUITE_NAME, about.PROGRAM_SUITE_VERSION, None)

	vlist, _status = kh.get_list_by_kind_namespace(("Node", ""), "")

	# Safe
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
			iktprint([ANSIThemeString("Error", "error"),
				  ANSIThemeString(": Failed to extract ", "default"),
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
			iktprint([ANSIThemeString("Error", "error"),
				  ANSIThemeString(": Failed to extract ", "default"),
				  ANSIThemeString("kube-proxy", "programname"),
				  ANSIThemeString(" version on node ", "default"),
				  ANSIThemeString(f"{node_name}", "hostname")], stderr = True)
			critical += 1
			mismatch = True

		if kubelet_major_version is not None and kubelet_major_version != 1:
			iktprint([ANSIThemeString("Critical", "critical"),
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
			iktprint([ANSIThemeString("Critical", "critical"),
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
			iktprint([ANSIThemeString("Error", "error"),
				  ANSIThemeString(": The version of ", "default"),
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
			iktprint([ANSIThemeString("       this is not supported.", "default")], stderr = True)
			error += 1
			mismatch = True
		elif kubelet_minor_version is not None and server_minor_version - 2 <= kubelet_minor_version < server_minor_version:
			iktprint([ANSIThemeString("Warning", "warning"),
				  ANSIThemeString(": The version of ", "default"),
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
			iktprint([ANSIThemeString("         this is supported, but not recommended.", "default")], stderr = True)
			warning += 1
			mismatch = True
		elif kubelet_minor_version is not None and kubelet_minor_version < server_minor_version:
			iktprint([ANSIThemeString("Error", "error"),
				  ANSIThemeString(": The version of ", "default"),
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
			iktprint([ANSIThemeString("       this is not supported.", "default")], stderr = True)
			error += 1
			mismatch = True

		if kubelet_minor_version is not None and kubeproxy_minor_version is not None and kubelet_minor_version != kubeproxy_minor_version:
			iktprint([ANSIThemeString("Error", "error"),
				  ANSIThemeString(": The version of ", "default"),
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
			iktprint([ANSIThemeString("       this is not supported.", "default")], stderr = True)
			error += 1
			mismatch = True

	if mismatch == False:
		iktprint([ANSIThemeString("  OK\n", "emphasis")])

	return critical, error, warning, note

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
		"path": IKTDIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can create or replace files in ", "default"),
				  ANSIThemeString(f"{IKTDIR}", "path"),
				  ANSIThemeString(" they may be able to obtain elevated privileges", "default")]
	},
	{
		"path": IKT_LOGS_DIR,
		"alertmask": 0o077,
		"usergroup_alertmask": 0o027,
		"severity": "error",
		"justification": [ANSIThemeString("If other users can read, create or replace files in ", "default"),
				  ANSIThemeString(f"{IKT_LOGS_DIR}", "path"),
				  ANSIThemeString(" they can cause ", "default"),
				  ANSIThemeString("iku", "command"),
				  ANSIThemeString(" to malfunction and possibly hide signs of a compromised cluster ", "default"),
				  ANSIThemeString("and may be able to obtain sensitive information from audit messages", "default")]
	},
	{
		"path": IKT_CONFIG_FILE_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can create or replace files in ", "default"),
				  ANSIThemeString(f"{IKT_CONFIG_FILE_DIR}", "path"),
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
		"path": IKT_HOOKS_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can create or replace files in ", "default"),
				  ANSIThemeString(f"{IKT_HOOKS_DIR}", "path"),
				  ANSIThemeString(" they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(IKT_HOOKS_DIR, "pre-upgrade.d")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can create or replace files in ", "default"),
				  ANSIThemeString(f"{os.path.join(IKT_HOOKS_DIR, 'pre-upgrade.d')}", "path"),
				  ANSIThemeString(" they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(IKT_HOOKS_DIR, "post-upgrade.d")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"severity": "critical",
		"justification": [ANSIThemeString("If other users can create or replace files in ", "default"),
				  ANSIThemeString(f"{os.path.join(IKT_HOOKS_DIR, 'post-upgrade.d')}", "path"),
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
				  ANSIThemeString("iku", "command"),
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
				  ANSIThemeString("iku", "command"),
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
				  ANSIThemeString("iku", "command"),
				  ANSIThemeString(" to malfunction and possibly hide signs of a compromised cluster", "default")]
	},
]

recommended_file_permissions = [
	{
		"path": FilePath(os.path.join(BINDIR, "iktadm")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"executable": True,
		"severity": "critical",
		"justification": [ANSIThemeString("If others users can modify executables they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(BINDIR, "iktinv")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"executable": True,
		"severity": "critical",
		"justification": [ANSIThemeString("If others users can modify executables they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(BINDIR, "ikt")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"executable": True,
		"severity": "critical",
		"justification": [ANSIThemeString("If others users can modify executables they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(BINDIR, "iku")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o002,
		"executable": True,
		"severity": "critical",
		"justification": [ANSIThemeString("If others users can modify configlets they may be able to obtain elevated privileges", "default")]
	},
	{
		"path": IKT_CONFIG_FILE_DIR,
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
]

# pylint: disable-next=too-many-arguments
def __check_permissions(recommended_permissions: List[Dict], pathtype: str, user: str,
			usergroup: str, critical: int, error: int, warning: int, note: int) -> Tuple[bool, int, int, int, int]:
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

	for permissions in recommended_permissions:
		path = deep_get(permissions, DictPath("path"))
		alertmask = deep_get(permissions, DictPath("alertmask"), 0o077)
		usergroup_alertmask = deep_get(permissions, DictPath("usergroup_alertmask"), alertmask)
		severity = deep_get(permissions, DictPath("severity"), "critical")
		justification = deep_get(permissions, DictPath("justification"), [ANSIThemeString("<no justification provided>", "emphasis")])
		executable = deep_get(permissions, DictPath("executable"), False)
		suffixes = deep_get(permissions, DictPath("suffixes"))

		if len(usergroup) > 0:
			alertmask = usergroup_alertmask
		notemask = 0o000
		if pathtype == "file" and executable == False:
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
					iktprint([ANSIThemeString("Critical", "critical"),
						  ANSIThemeString(f": The owner of the {pathtype} ", "default"),
						  ANSIThemeString(f"{entry}", "path"),
						  ANSIThemeString(" does not exist in the system database; aborting.", "default")], stderr = True)
					sys.exit(errno.ENOENT)
				try:
					path_group = entry.group()
				except KeyError:
					iktprint([ANSIThemeString("Critical", "critical"),
						  ANSIThemeString(f": The group of the {pathtype} ", "default"),
						  ANSIThemeString(f"{entry}", "path"),
						  ANSIThemeString(" does not exist in the system database; aborting.", "default")], stderr = True)
					sys.exit(errno.ENOENT)
				path_stat = entry.stat()
				path_permissions = path_stat.st_mode & 0o777
				recommended_permissions = 0o777 & ~(alertmask | notemask)

				if path_owner not in (user, "root"):
					iktprint([ANSIThemeString("  ", "default"),
						  ANSIThemeString("Critical", severity),
						  ANSIThemeString(f": The {pathtype} ", "default"),
						  ANSIThemeString(f"{entry}", "path"),
						  ANSIThemeString(" is not owned by ", "default"),
						  ANSIThemeString(user, "emphasis")], stderr = True)
					iktprint([ANSIThemeString("  ", "default"),
						  ANSIThemeString("Justification", "emphasis"),
						  ANSIThemeString(": if other users can overwrite files they may be able to achieve elevated privileges", "default")], stderr = True)
					critical += 1
					issue = True

				if len(usergroup) > 0 and path_group != usergroup:
					iktprint([ANSIThemeString("  ", "default"),
						  ANSIThemeString("Critical", severity),
						  ANSIThemeString(f": The {pathtype} ", "default"),
						  ANSIThemeString(f"{entry}", "path"),
						  ANSIThemeString(" does not belong to the user group for ", "default"),
						  ANSIThemeString(user, "emphasis")], stderr = True)
					iktprint([ANSIThemeString("  ", "default"),
						  ANSIThemeString("Justification", "emphasis"),
						  ANSIThemeString(": ", "default")] + justification, stderr = True)
					print()
					critical += 1
					issue = True

				if path_permissions & alertmask != 0:
					iktprint([ANSIThemeString("  ", "default"),
						  ANSIThemeString(f"{severity.capitalize()}", severity),
						  ANSIThemeString(f": The permissions for the {pathtype} ", "default"),
						  ANSIThemeString(f"{entry}", "path"),
						  ANSIThemeString(" are ", "default"),
						  ANSIThemeString(f"{path_permissions:03o}", "emphasis"),
						  ANSIThemeString("; the recommended permissions are ", "default"),
						  ANSIThemeString(f"{recommended_permissions:03o}", "emphasis"),
						  ANSIThemeString(" (or stricter)", "default")],
						  stderr = True)
					iktprint([ANSIThemeString("  ", "default"),
						  ANSIThemeString("Justification", "emphasis"),
						  ANSIThemeString(": ", "default")] + justification, stderr = True)
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
					iktprint([ANSIThemeString("  ", "default"),
						  ANSIThemeString("Note", "note"),
						  ANSIThemeString(f": The permissions for the {pathtype} ", "default"),
						  ANSIThemeString(f"{entry}", "path"),
						  ANSIThemeString(" are ", "default"),
						  ANSIThemeString(f"{path_permissions:03o}", "emphasis"),
						  ANSIThemeString("; this file isn't an executable and shouldn't have the executable bit set", "default")])
		else:
			iktprint([ANSIThemeString("  Warning", "warning"),
				  ANSIThemeString(f": the {pathtype} ", "default"),
				  ANSIThemeString(f"{path}", "path"),
				  ANSIThemeString(" does not exist; skipping.\n", "default")], stderr = True)
			warning += 1
			issue = True
			continue

	return issue, critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_file_permissions(cluster_name: str, kubeconfig: Dict, iktconfig_dict: Dict, user: str,
			   critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[int, int, int, int]:
	"""
	This checks whether any files or directories have insecure permissions

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			iktconfig_dict (dict): The iktconfig file
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

	iktprint([ANSIThemeString("[Checking directory and file permissions]", "phase")])

	usergroup = deep_get(kwargs, DictPath("usergroup"), "")

	issue, critical, error, warning, note = __check_permissions(recommended_directory_permissions, "directory", user, usergroup, critical, error, warning, note)

	issue, critical, error, warning, note = __check_permissions(recommended_file_permissions, "file", user, usergroup, critical, error, warning, note)

	if issue == False:
		iktprint([ANSIThemeString("  OK\n", "emphasis")])

	return critical, error, warning, note

# pylint: disable-next=unused-argument
def run_playbook(playbookpath: FilePath, hosts = None, extra_values = None, quiet = False) -> Tuple[int, Dict]:
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
	http_proxy = deep_get(iktlib.iktconfig, DictPath("Network#http_proxy"), "")
	if http_proxy is None:
		http_proxy = ""
	https_proxy = deep_get(iktlib.iktconfig, DictPath("Network#https_proxy"), "")
	if https_proxy is None:
		https_proxy = ""
	no_proxy = deep_get(iktlib.iktconfig, DictPath("Network#no_proxy"), "")
	if no_proxy is None:
		no_proxy = ""
	insecure_registries = deep_get(iktlib.iktconfig, DictPath("Docker#insecure_registries"), [])
	registry_mirrors = deep_get(iktlib.iktconfig, DictPath("Containerd#registry_mirrors"), [])
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
def check_control_plane(cluster_name: str, kubeconfig: Dict, iktconfig_dict: Dict, user: str,
			critical: int, error: int, warning: int, note: int, **kwargs: Dict) -> Tuple[int, int, int, int]:
	"""
	This checks whether a host is suitable to be used as a control plane

		Parameters:
			cluster_name (str): The name of the cluster
			kubeconfig (dict)): The kubeconfig file
			iktconfig_dict (dict): The iktconfig file
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

	# The host(s) to check
	hosts = deep_get(kwargs, DictPath("hosts"), [])
	playbookpath = FilePath(str(PurePath(ANSIBLE_PLAYBOOK_DIR).joinpath("preflight_check.yaml")))

	iktprint([ANSIThemeString("[Checking whether ", "phase")] +
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

			if taskname == "Checking whether the host runs an Operating System supported for control planes":
				if deep_get(taskdata, DictPath("retval")) != 0:
					critical += 1
					iktprint([ANSIThemeString("Critical", "critical"),
						  ANSIThemeString(": Unsupported Operating System ", "default"),
						  ANSIThemeString(f"{ansible_os_family}", "programname"),
						  ANSIThemeString(" currently the only supported OS family for control planes is ", "default"),
						  ANSIThemeString("Debian", "programname"),
						  ANSIThemeString("; aborting.", "default\n")], stderr = True)
					break

			if taskname == "Check whether the host is a Kubernetes control plane":
				if deep_get(taskdata, DictPath("retval")) != 0:
					critical += 1
					iktprint([ANSIThemeString("Critical", "critical"),
						  ANSIThemeString(": Host ", "default"),
						  ANSIThemeString(f"{host}", "hostname"),
						  ANSIThemeString(" seems to already be running a Kubernetes api-server; aborting.\n", "default")], stderr = True)
					break

			if taskname == "Check whether the host is a Kubernetes node":
				if deep_get(taskdata, DictPath("retval")) != 0:
					critical += 1
					iktprint([ANSIThemeString("Critical", "critical"),
						  ANSIThemeString(": Host ", "default"),
						  ANSIThemeString(f"{host}", "hostname"),
						  ANSIThemeString(" seems to already have a running kubelet; aborting.\n", "default")], stderr = True)
					break

	return critical, error, warning, note
