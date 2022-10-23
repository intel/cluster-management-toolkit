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
from pathlib import Path
import re
import sys
import typing # pylint: disable=unused-import

from ikttypes import FilePath
from iktpaths import BINDIR, IKTDIR
from iktpaths import ANSIBLE_DIR, ANSIBLE_INVENTORY, ANSIBLE_LOG_DIR, ANSIBLE_PLAYBOOK_DIR
from iktpaths import DEPLOYMENT_DIR, IKT_CONFIG_FILE_DIR, IKT_HOOKS_DIR, KUBE_CONFIG_DIR, PARSER_DIR, THEME_DIR, VIEW_DIR
from iktpaths import IKT_CONFIG_FILE, KUBE_CONFIG_FILE
from iktlib import check_deb_versions, deep_get, execute_command_with_response
from iktprint import iktprint

from kubernetes_helper import kubectl_get_version

import about

# Check file permissions:
# .ssh should be 700
# .ssh/authorized_keys should be 644, 640, or 600
# .ssh/

# pylint: disable-next=too-many-arguments,unused-argument,line-too-long
def check_security_disable_strict_host_key_checking(cluster_name: str, kubeconfig, iktconfig_dict, user: str, critical: int, error: int, warning: int, note: int, **kwargs):
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
			critical (int), error (int), warning (int), note (int):
				critical: The new count of critical severity security issues
				error: The new count of error severity security issues
				warning: The new count of warning severity security issues
				note: The new count of note severity security issues
	"""

	iktprint([("[Checking for insecure configuration options in ", "phase"), (f"{IKT_CONFIG_FILE}", "path"), ("]", "phase")])
	disablestricthostkeychecking = deep_get(iktconfig_dict, "Nodes#disablestricthostkeychecking", False)
	if disablestricthostkeychecking == False:
		iktprint([("  OK\n", "emphasis")])
	else:
		iktprint([("  Warning:", "warning"), (" strict SSH host key checking is disabled; this is a potential security threat.", "emphasis")], stderr = True)
		iktprint([("    If strict SSH host key checking is disabled other systems can impersonate the remote host", "default")], stderr = True)
		iktprint([("    and thus perform Man in the Middle (MITM) attacks.", "default")], stderr = True)
		iktprint([("    It is strongly adviced that you enable strict SSH host key checking unless you're absolutely certain", "default")], stderr = True)
		iktprint([("    that your network environment is safe.\n", "default")], stderr = True)
		error += 1

	return critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_sudo_configuration(cluster_name: str, kubeconfig, iktconfig_dict, user: str, critical: int, error: int, warning: int, note: int, **kwargs):
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
			critical (int), error (int), warning (int), note (int):
				critical: The new count of critical severity security issues
				error: The new count of error severity security issues
				warning: The new count of warning severity security issues
				note: The new count of note severity security issues
	"""

	iktprint([("[Checking whether ", "phase"),
		  (f"{user}", "path"),
		  (" is in ", "phase"), ("/etc/sudoers", "path"), (" or ", "default"), ("/etc/sudoers.d", "path"), ("]", "phase")])
	args = ["/usr/bin/sudo", "-l"]
	result = execute_command_with_response(args)

	sudoer = True

	# Safe
	sudo_msg_regex = re.compile(r"^User ([^\s]+) is not allowed to run sudo on.*")

	for line in result.splitlines():
		tmp = sudo_msg_regex.match(line)
		if tmp is not None:
			iktprint([("  Error:", "error"),
				  (f" {user} ", "path"),
				  ("is not in ", "default"), ("/etc/sudoers", "path"), (" or ", "default"), ("/etc/sudoers.d\n", "path")], stderr = True)
			error += 1
			sudoer = False
			break

	if sudoer == True:
		iktprint([("  OK\n", "emphasis")])

		iktprint([("[Checking whether", "phase") ,(f" {user} ", "path"), ("can perform passwordless sudo]", "phase")])
		args = ["/usr/bin/sudo", "-l"]
		result = execute_command_with_response(args)
		passwordless_sudo = False

		# Safe
		sudo_permissions_regex = re.compile(r"^\s*\(ALL(\s*:\s*ALL)?\)\s*NOPASSWD:\s*ALL\s*$")

		for line in result.splitlines():
			tmp = sudo_permissions_regex.match(line)
			if tmp is not None:
				iktprint([("  OK\n", "emphasis")])
				passwordless_sudo = True
				break

		if passwordless_sudo == False:
			iktprint([("  Error:", "error"), (f" {user} ", "path"), ("cannot perform passwordless sudo\n", "default")], stderr = True)
			error += 1

	return critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_known_hosts_hashing(cluster_name: str, kubeconfig, iktconfig_dict, user: str, critical: int, error: int, warning: int, note: int, **kwargs):
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
			critical (int), error (int), warning (int), note (int):
				critical: The new count of critical severity security issues
				error: The new count of error severity security issues
				warning: The new count of warning severity security issues
				note: The new count of note severity security issues
	"""

	iktprint([("[Checking whether ", "phase"), ("ssh", "command"), (" known_hosts hashing is enabled]", "phase")])
	iktprint([("  Note:", "emphasis"), (" this test is not 100% reliable since ssh settings can vary based on target host\n", "default")])
	args = ["/usr/bin/ssh", "-G", "localhost"]
	result = execute_command_with_response(args)

	# Safe
	hashknownhosts_regex = re.compile(r"^hashknownhosts\s+yes$")

	for line in result.splitlines():
		tmp = hashknownhosts_regex.match(line)
		if tmp is not None:
			iktprint([("  Warning:", "warning"),
				  (" ssh", "command"),
				  (" known_hosts hashing is enabled; this may cause issues with ", "default"), ("paramiko\n", "command")], stderr = True)
			warning += 1
			break

	return critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_insecure_kube_config_options(cluster_name: str, kubeconfig, iktconfig_dict, user: str, critical: int, error: int, warning: int, note: int, **kwargs):
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
			critical (int), error (int), warning (int), note (int):
				critical: The new count of critical severity security issues
				error: The new count of error severity security issues
				warning: The new count of warning severity security issues
				note: The new count of note severity security issues
	"""

	iktprint([("[Checking for insecure ", "phase"), (f"{KUBE_CONFIG_FILE}", "path"), (" options]", "phase")])

	insecureskiptlsverify = False

	for cluster in deep_get(kubeconfig, "clusters", []):
		if deep_get(cluster, "name", "") == cluster_name:
			insecureskiptlsverify = deep_get(cluster, "insecure-skip-tls-verify", False)
			break

	if insecureskiptlsverify == False:
		iktprint([("  OK\n", "emphasis")])
	else:
		iktprint([("  Warning:", "critical"), (" TLS verification has been disabled in ", "emphasis"), (f"{KUBE_CONFIG_FILE}", "path"),
			  ("; this is a potential security threat.", "emphasis")], stderr = True)
		iktprint([("    If TLS verification is disabled other systems can impersonate the control plane", "default")], stderr = True)
		iktprint([("    and thus perform Man in the Middle (MITM) attacks.", "default")], stderr = True)
		iktprint([("    It is adviced that you remove the ", "default"), ("insecure-skip-tls-verify", "argument"), (" option from ", "default"),
			  (f"{KUBE_CONFIG_FILE}", "path"), (",", "default")], stderr = True)
		iktprint([("    unless you're absolutely certain that your network environment is safe.\n", "default")], stderr = True)
		critical += 1

	return critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_client_server_version_match(cluster_name: str, kubeconfig, iktconfig_dict, user: str, critical: int, error: int, warning: int, note: int, **kwargs):
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
			critical (int), error (int), warning (int), note (int):
				critical: The new count of critical severity security issues
				error: The new count of error severity security issues
				warning: The new count of warning severity security issues
				note: The new count of note severity security issues
	"""

	mismatch = False

	# Is the version of kubectl within one version of the cluster version?
	iktprint([("[Checking client/server version match]", "phase")])

	_kubectl_major_version, kubectl_minor_version, kubectl_git_version, server_major_version, server_minor_version, server_git_version = kubectl_get_version()

	iktprint([("         kubectl ", "programname"), ("version: ", "default"), (f"{kubectl_git_version}", "version")])
	iktprint([("  kube-apiserver ", "programname"), ("version: ", "default"), (f"{server_git_version}", "version")])

	print()

	if server_major_version != 1:
		iktprint([("  ", "default"), ("Critical:", "critical"),
			  (f" {about.PROGRAM_SUITE_NAME}", "programname"),
			  (" has not been tested for any other major version of Kubernetes than ", "default"), ("v1", "version"), ("; aborting.", "default")], stderr = True)
		sys.exit(errno.ENOTSUP)

	if kubectl_minor_version > server_minor_version and kubectl_minor_version == server_minor_version + 1:
		iktprint([("  ", "default"), ("Note: ", "note"),
			  ("The ", "default"),
			  ("kubectl", "programname"), (" version is one minor version newer than that of ", "default"), ("kube-apiserver", "programname"), (";", "default")])
		iktprint([("      this is a supported configuration, but it's generally recommended to keep the versions in sync.", "default")])
		note += 1
		mismatch = True
	elif kubectl_minor_version > server_minor_version:
		iktprint([("  ", "default"), ("Warning: ", "warning"),
			  ("The ", "default"),
			  ("kubectl", "programname"),
			  (" version is more than one minor version newer than that of ", "default"), ("kube-apiserver", "programname"), (";", "default")], stderr = True)
		iktprint([("         this might work, but it's generally recommended to keep the versions in sync.", "default")], stderr = True)
		warning += 1
		mismatch = True
	elif kubectl_minor_version < server_minor_version and kubectl_minor_version + 1 == server_minor_version:
		iktprint([("  ", "default"), ("Note: ", "note"),
			  ("The ", "default"),
			  ("kubectl", "programname"),
			  (" version is one minor version older than that of ", "default"), ("kube-apiserver", "programname"), (";", "default")])
		iktprint([("      this is a supported configuration, but it's generally recommended to keep the versions in sync.", "default")])
		warning += 1
		mismatch = True
	elif kubectl_minor_version < server_minor_version:
		iktprint([("  ", "default"), ("Error:", "error"),
			  (" The ", "default"),
			  ("kubectl", "programname"),
			  (" version is much older than that of ", "default"), ("kube-apiserver", "programname"), (";", "default")], stderr = True)
		iktprint([("       this is NOT supported and is likely to cause issues.", "default")], stderr = True)
		error += 1
		mismatch = True

	if mismatch == False:
		iktprint([("OK", "ok")])

	return critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_containerd_and_docker(cluster_name: str, kubeconfig, iktconfig_dict, user: str, critical: int, error: int, warning: int, note: int, **kwargs):
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
			critical (int), error (int), warning (int), note (int):
				critical: The new count of critical severity security issues
				error: The new count of error severity security issues
				warning: The new count of warning severity security issues
				note: The new count of note severity security issues
	"""

	iktprint([("[Checking whether ", "phase"),
		  ("docker-ce / containerd.io", "path"),
		  (" is installed instead of ", "phase"), ("docker.io / containerd", "path"), ("]", "phase")])
	iktprint([("  Note:", "emphasis"), (" this is only an issue if you intend to use this host as a control plane or node\n", "default")])
	deb_versions = check_deb_versions(["docker.io", "containerd", "docker-ce", "containerd.io"])
	conflict = False
	for package, _installed_version, _candidate_version, _all_versions in deb_versions:
		if package in ("docker-ce", "containerd.io"):
			iktprint([("  Error:", "error"),
				  (" docker-ce / containerd.io ", "path"),
				  ("is installed; use ", "default"), ("docker.io / containerd", "path"), (" instead\n", "default")], stderr = True)
			iktprint([("  ", "default"), ("Suggested fix:", "header")])
			iktprint([("    sudo apt ", "programname"), ("install ", "command"), ("docker.io containerd docker-ce- containerd.io-\n", "argument")])
			error += 1
			conflict = True
			break

	if conflict == False:
		iktprint([("  OK\n", "emphasis")])

	return critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument,line-too-long
def check_kubelet_and_kube_proxy_versions(cluster_name: str, kubeconfig, iktconfig_dict, user: str, critical: int, error: int, warning: int, note: int, **kwargs):
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
			critical (int), error (int), warning (int), note (int):
				critical: The new count of critical severity security issues
				error: The new count of error severity security issues
				warning: The new count of warning severity security issues
				note: The new count of note severity security issues
	"""

	# Check kubelet and kube-proxy versions;
	# they can be up to two minor versions older than kube-apiserver,
	# but must not be newer

	mismatch = False

	# Kubernetes API based checks
	iktprint([("\n[Checking kubelet & kube-proxy versions]", "phase")])

	_kubectl_major_version, _kubectl_minor_version, _kubectl_git_version, server_major_version, server_minor_version, _server_git_version = kubectl_get_version()

	from kubernetes_helper import KubernetesHelper # pylint: disable=import-outside-toplevel
	kh = KubernetesHelper(about.PROGRAM_SUITE_NAME, about.PROGRAM_SUITE_VERSION, None)

	vlist, _status = kh.get_list_by_kind_namespace(("Node", ""), "")

	# Safe
	version_regex = re.compile(r"^v(\d+)\.(\d+)\..*")

	for node in vlist:
		node_name = deep_get(node, "metadata#name")
		kubelet_version = deep_get(node, "status#nodeInfo#kubeletVersion")
		kubeproxy_version = deep_get(node, "status#nodeInfo#kubeProxyVersion")
		tmp = version_regex.match(kubelet_version)

		kubelet_major_version = None
		kubelet_minor_version = None
		kubeproxy_major_version = None
		kubeproxy_minor_version = None
		if tmp is not None:
			kubelet_major_version = int(tmp[1])
			kubelet_minor_version = int(tmp[2])
		else:
			iktprint([("Error:", "error"),
				  (" Failed to extract ", "default"),
				  ("kubelet", "programname"),
				  (" version on node ", "default"), (f"{node_name}", "hostname")], stderr = True)
			critical += 1
			mismatch = True

		tmp = version_regex.match(kubeproxy_version)
		if tmp is not None:
			kubeproxy_major_version = int(tmp[1])
			kubeproxy_minor_version = int(tmp[2])
		else:
			iktprint([("Error:", "error"),
				  (" Failed to extract ", "default"), ("kube-proxy", "programname"), (" version on node ", "default"), (f"{node_name}", "hostname")], stderr = True)
			critical += 1
			mismatch = True

		if kubelet_major_version is not None and kubelet_major_version != 1:
			iktprint([("Critical:", "critical"), (f" {about.PROGRAM_SUITE_NAME}", "programname"),
				  (" has not been tested for any other major version of Kubernetes than v1; node ", "default"), (f"{node_name}", "hostname"),
				  (" runs ", "default"), ("kubelet ", "programname"), ("version ", "default"), (f"{kubelet_version}", "version")], stderr = True)
			critical += 1
			mismatch = True

		if kubeproxy_major_version is not None and kubeproxy_major_version != 1:
			iktprint([("Critical:", "critical"), (f" {about.PROGRAM_SUITE_NAME}", "programname"),
				  (" has not been tested for any other major version of Kubernetes than v1; node ", "default"), (f"{node_name}", "hostname"),
				  (" runs ", "default"), ("kube-proxy ", "programname"), ("version ", "default"), (f"{kubeproxy_version}", "version")], stderr = True)
			critical += 1
			mismatch = True

		if kubelet_minor_version is not None and kubelet_minor_version > server_minor_version:
			iktprint([("Error:", "error"), (" The version of ", "default"),
				  ("kubelet", "programname"), (" (", "default"), (f"{kubelet_major_version}.{kubelet_minor_version}", "version"),
				  (") on node ", "default"), (f"{node_name}", "hostname"),
				  (" is newer than that of ", "default"),
				  ("kube-apiserver", "programname"), (" (", "default"), (f"{server_major_version}.{server_minor_version}", "version"), (");", "default")], stderr = True)
			iktprint([("       this is not supported.", "default")], stderr = True)
			error += 1
			mismatch = True
		elif kubelet_minor_version is not None and server_minor_version - 2 <= kubelet_minor_version < server_minor_version:
			iktprint([("Warning: ", "warning"), ("The version of ", "default"),
				  ("kubelet", "programname"), (" (", "default"), (f"{kubelet_major_version}.{kubelet_minor_version}", "version"),
				  (") on node ", "default"), (f"{node_name}", "hostname"),
				  (" is a bit older than that of ", "default"), ("kube-apiserver", "programname"), (" (", "default"),
				  (f"{server_major_version}.{server_minor_version}", "version"), (");", "default")], stderr = True)
			iktprint([("         this is supported, but not recommended.", "default")], stderr = True)
			warning += 1
			mismatch = True
		elif kubelet_minor_version is not None and kubelet_minor_version < server_minor_version:
			iktprint([("Error:", "error"), (" The version of ", "default"),
				  ("kubelet", "programname"), (" (", "default"), (f"{kubelet_major_version}.{kubelet_minor_version}", "version"),
				  (") on node ", "default"), (f"{node_name}", "hostname"),
				  (" is much older than that of ", "default"),
				  ("kube-apiserver", "programname"), (" (", "default"), (f"{server_major_version}.{server_minor_version}", "version"), (");", "default")], stderr = True)
			iktprint([("       this is not supported.", "default")], stderr = True)
			error += 1
			mismatch = True

		if kubelet_minor_version is not None and kubeproxy_minor_version is not None and kubelet_minor_version != kubeproxy_minor_version:
			iktprint([("Error:", "error"), (" The version of ", "default"),
				  ("kubelet", "programname"), (" (", "default"), (f"{kubelet_major_version}.{kubelet_minor_version}", "version"),
				  (") on node ", "default"), (f"{node_name}", "hostname"),
				  (" is not the same as that of ", "default"),
				  ("kube-proxy", "programname"), (" (", "default"), (f"{kubeproxy_major_version}.{kubeproxy_minor_version}", "version"), (");", "default")], stderr = True)
			iktprint([("       this is not supported.", "default")], stderr = True)
			error += 1
			mismatch = True

	if mismatch == False:
		iktprint([("  OK\n", "emphasis")])

	return critical, error, warning, note

recommended_directory_permissions = [
	{
		"path": BINDIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"severity": "critical",
		"justification": [("If other users can create or overwrite files in ", "default"),
				  (f"{BINDIR}", "path"),
				  (" they can obtain elevated privileges", "default")]
	},
	{
		"path": IKTDIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"severity": "critical",
		"justification": [("If other users can create or replace files in ", "default"),
				  (f"{IKTDIR}", "path"),
				  (" they may be able to obtain elevated privileges", "default")]
	},
	{
		"path": IKT_CONFIG_FILE_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"severity": "critical",
		"justification": [("If other users can create or replace files in ", "default"),
				  (f"{IKT_CONFIG_FILE_DIR}", "path"),
				  (" they may be able to obtain elevated privileges", "default")]
	},
	{
		"path": ANSIBLE_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"severity": "critical",
		"justification": [("If other users can create or replace files in ", "default"),
				  (f"{ANSIBLE_DIR}", "path"),
				  (" they can obtain elevated privileges", "default")]
	},
	{
		"path": IKT_HOOKS_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"severity": "critical",
		"justification": [("If other users can create or replace files in ", "default"),
				  (f"{IKT_HOOKS_DIR}", "path"),
				  (" they can obtain elevated privileges", "default")]
	},
	{
		"path": DEPLOYMENT_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"severity": "critical",
		"justification": [("If other users can create or replace files in ", "default"),
				  (f"{DEPLOYMENT_DIR}", "path"),
				  (" they can obtain elevated privileges", "default")]
	},
	{
		"path": ANSIBLE_LOG_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"severity": "warning",
		"justification": [("If others users can create or replace files in ", "default"),
				  (f"{ANSIBLE_LOG_DIR}", "path"),
				  (" they can spoof results from playbook runs", "default")]
	},
	{
		"path": KUBE_CONFIG_DIR,
		"alertmask": 0o027,
		"usergroup_alertmask": 0o077,
		"severity": "critical",
		"justification": [("If others users can read, create or replace files in ", "default"),
				  (f"{KUBE_CONFIG_DIR}", "path"),
				  (" they can obtain cluster access", "default")]
	},
	{
		"path": THEME_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"severity": "error",
		"justification": [("If others users can create or replace files in ", "default"),
				  (f"{THEME_DIR}", "path"),
				  (" they can cause ", "default"), ("iku", "command"), (" to malfunction", "default")]
	},
	{
		"path": PARSER_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"severity": "error",
		"justification": [("If others users can create or replace files in ", "default"),
				  (f"{PARSER_DIR}", "path"),
				  (" they can cause ", "default"), ("iku", "command"), (" to malfunction and possibly hide signs of a compromised cluster", "default")]
	},
	{
		"path": VIEW_DIR,
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"severity": "error",
		"justification": [("If others users can create or replace files in ", "default"),
				  (f"{VIEW_DIR}", "path"),
				  (" they can cause ", "default"), ("iku", "command"), (" to malfunction and possibly hide signs of a compromised cluster", "default")]
	},
]

recommended_file_permissions = [
	{
		"path": FilePath(os.path.join(BINDIR, "iktadm")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"executable": True,
		"severity": "critical",
		"justification": [("If others users can modify executables they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(BINDIR, "iktinv")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"executable": True,
		"severity": "critical",
		"justification": [("If others users can modify executables they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(BINDIR, "ikt")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"executable": True,
		"severity": "critical",
		"justification": [("If others users can modify executables they can obtain elevated privileges", "default")]
	},
	{
		"path": FilePath(os.path.join(BINDIR, "iku")),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"executable": True,
		"severity": "critical",
		"justification": [("If others users can modify configlets they may be able to obtain elevated privileges", "default")]
	},
	{
		"path": IKT_CONFIG_FILE_DIR,
		"suffixes": (".yml", ".yaml"),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"executable": False,
		"severity": "critical",
		"justification": [("If others users can modify configlets they may be able to obtain elevated privileges", "default")]
	},
	{
		"path": ANSIBLE_PLAYBOOK_DIR,
		"suffixes": (".yml", ".yaml"),
		"alertmask": 0o022,
		"usergroup_alertmask": 0o022,
		"executable": False,
		"severity": "critical",
		"justification": [("If other users can modify playbooks they can obtain elevated privileges", "default")]
	},
	{
		"path": ANSIBLE_INVENTORY,
		"alertmask": 0o027,
		"usergroup_alertmask": 0o077,
		"severity": "critical",
		"justification": [("If other users can read or modify the Ansible inventory they can obtain elevated privileges", "default")]
	},
	{
		"path": KUBE_CONFIG_DIR,
		"alertmask": 0o027,
		"usergroup_alertmask": 0o077,
		"executable": False,
		"severity": "critical",
		"justification": [("If others users can read or modify cluster configuration files they can obtain cluster access", "default")]
	},
]

# pylint: disable-next=too-many-arguments
def __check_permissions(recommended_permissions, pathtype, user: str, usergroup: str, critical: int, error: int, warning: int, note: int):
	issue = False

	for permissions in recommended_permissions:
		path = deep_get(permissions, "path")
		alertmask = deep_get(permissions, "alertmask", 0o000)
		usergroup_alertmask = deep_get(permissions, "usergroup_alertmask", 0o000)
		severity = deep_get(permissions, "severity", "critical")
		justification = deep_get(permissions, "justification", [("<no justification provided>", "emphasis")])
		executable = deep_get(permissions, "executable", False)
		suffixes = deep_get(permissions, "suffixes")

		if len(usergroup) > 0:
			alertmask = usergroup_alertmask
		notemask = 0o000
		if pathtype == "file" and executable == False:
			notemask = 0o111

		path_entry = Path(path)

		if path_entry.exists():
			# If this is a file, but we operate on files we should apply these tests for every matching file in this directory
			if pathtype == "file" and path_entry.is_dir():
				paths = path_entry.iterdir() # type: ignore
			else:
				paths = [path_entry] # type: ignore

			for entry in paths:
				if pathtype == "file":
					if not entry.is_file() and not entry.is_symlink():
						continue

					if suffixes is not None and not str(entry).endswith(suffixes):
						continue

				try:
					path_owner = entry.owner()
				except KeyError:
					iktprint([("Critical:", "critical"), (f" The owner of the {pathtype} ", "default"),
						  (f"{entry}", "path"),
						  (" does not exist in the system database; aborting.", "default")], stderr = True)
					sys.exit(errno.ENOENT)
				try:
					path_group = entry.group()
				except KeyError:
					iktprint([("Critical:", "critical"), (f" The group of the {pathtype} ", "default"),
						  (f"{entry}", "path"),
						  (" does not exist in the system database; aborting.", "default")], stderr = True)
					sys.exit(errno.ENOENT)
				path_stat = entry.stat()
				path_permissions = path_stat.st_mode & 0o777
				recommended_permissions = 0o777 & ~(alertmask | notemask)

				if path_owner not in (user, "root"):
					iktprint([("  ", "default"), ("Critical:", severity), (f" The {pathtype} ", "default"), (f"{entry}", "path"), (" is not owned by ", "default"),
						  (user, "emphasis")], stderr = True)
					iktprint([("  ", "default"), ("Justification: ", "emphasis"),
						  ("if other users can overwrite files they may be able to achieve elevated privileges", "default")], stderr = True)
					critical += 1
					issue = True

				if len(usergroup) > 0 and path_group != usergroup:
					iktprint([("  ", "default"), ("Critical:", severity), (f" The {pathtype} ", "default"),
						  (f"{entry}", "path"),
						  (" does not belong to the user group for ", "default"),
						  (user, "emphasis")], stderr = True)
					iktprint([("  ", "default"), ("Justification: ", "emphasis")] + justification, stderr = True)
					print()
					critical += 1
					issue = True

				if path_permissions & alertmask != 0:
					iktprint([("  ", "default"), (f"{severity.capitalize()}:", severity),
						  (f" The permissions for the {pathtype} ", "default"),
						  (f"{entry}", "path"),
						  (" are ", "default"), (f"{path_permissions:03o}", "emphasis"), ("; the recommended permissions are ", "default"),
						  (f"{recommended_permissions:03o}", "emphasis"), (" (or stricter)", "default")],
						  stderr = True)
					iktprint([("  ", "default"), ("Justification: ", "emphasis")] + justification, stderr = True)
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
					iktprint([("  ", "default"), ("Note:", "note"),
						  (f" The permissions for the {pathtype} ", "default"),
						  (f"{entry}", "path"), (" are ", "default"), (f"{path_permissions:03o}", "emphasis"),
						  ("; this file isn't an executable and shouldn't have the executable bit set", "default")])
		else:
			iktprint([("  Warning:", "warning"), (f" the {pathtype} {path} does not exist; skipping.\n", "default")], stderr = True)
			warning += 1
			issue = True
			continue

	return issue, critical, error, warning, note

# pylint: disable-next=too-many-arguments,unused-argument
def check_file_permissions(cluster_name: str, kubeconfig: dict, iktconfig_dict, user: str, critical: int, error: int, warning: int, note: int, **kwargs):
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

	iktprint([("[Checking directory and file permissions]", "phase")])

	usergroup = deep_get(kwargs, "usergroup", "")

	issue, critical, error, warning, note = __check_permissions(recommended_directory_permissions, "directory", user, usergroup, critical, error, warning, note)

	issue, critical, error, warning, note = __check_permissions(recommended_file_permissions, "file", user, usergroup, critical, error, warning, note)

	if issue == False:
		iktprint([("  OK\n", "emphasis")])

	return critical, error, warning, note
