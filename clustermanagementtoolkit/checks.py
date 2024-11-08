#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
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

# pylint: disable=too-many-lines

import errno
import os
from pathlib import Path
import re
import sys
from typing import Any, cast, Generator

from clustermanagementtoolkit.ansible_helper import ansible_configuration
from clustermanagementtoolkit.ansible_helper import ansible_run_playbook_on_selection
from clustermanagementtoolkit.ansible_helper import ansible_print_play_results
from clustermanagementtoolkit.ansible_helper import get_playbook_path

from clustermanagementtoolkit.recommended_permissions import recommended_directory_permissions
from clustermanagementtoolkit.recommended_permissions import recommended_file_permissions

from clustermanagementtoolkit.cmtio import execute_command_with_response

from clustermanagementtoolkit.cmttypes import deep_get, DictPath, FilePath, ProgrammingError

from clustermanagementtoolkit.cmtpaths import CMT_CONFIG_FILE, KUBE_CONFIG_FILE
from clustermanagementtoolkit.cmtpaths import SSH_BIN_PATH, NETRC_PATH, DOT_ANSIBLE_PATH

from clustermanagementtoolkit import cmtlib

from clustermanagementtoolkit.ansithemeprint import ANSIThemeStr, ansithemestr_join_list
from clustermanagementtoolkit.ansithemeprint import ansithemeprint

from clustermanagementtoolkit.kubernetes_helper import kubectl_get_version

from clustermanagementtoolkit import about


def check_disable_strict_host_key_checking(**kwargs: Any) -> tuple[bool, int, int, int, int]:
    """
    This checks whether or not strict host key checking has been disabled in cmtconfig

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                cmtconfig_dict (dict): The cmtconfig file
                critical (int): The current count of critical severity security issues
                error (int): The current count of error severity security issues
                warning (int): The current count of warning severity security issues
                note (int): The current count of note severity security issues
        Returns:
            (bool, int, int, int, int):
                (bool): Is this error severe enough that we should abort immediately?
                (int): The new count of critical severity security issues
                (int): The new count of error severity security issues
                (int): The new count of warning severity security issues
                (int): The new count of note severity security issues
    """
    cmtconfig_dict: dict = deep_get(kwargs, DictPath("cmtconfig_dict"), {})
    critical: int = deep_get(kwargs, DictPath("critical"), 0)
    error: int = deep_get(kwargs, DictPath("error"), 0)
    warning: int = deep_get(kwargs, DictPath("warning"), 0)
    note: int = deep_get(kwargs, DictPath("note"), 0)

    abort = False

    ansithemeprint([ANSIThemeStr("[Checking for insecure configuration options in ", "phase"),
                    ANSIThemeStr(f"{CMT_CONFIG_FILE}", "path"),
                    ANSIThemeStr("]", "phase")])
    disablestricthostkeychecking = \
        deep_get(cmtconfig_dict, DictPath("Nodes#disablestricthostkeychecking"), False)

    if not disablestricthostkeychecking:
        ansithemeprint([ANSIThemeStr("  OK\n", "emphasis")])
    else:
        ansithemeprint([ANSIThemeStr("  ", "default"),
                        ANSIThemeStr("Warning", "warning"),
                        ANSIThemeStr(":", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    Strict SSH host key checking is disabled; this is a "
                                     "potential security threat.", "emphasis")], stderr=True)
        ansithemeprint([ANSIThemeStr("    If strict SSH host key checking is disabled other "
                                     "systems can impersonate the remote host",
                                     "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    and thus perform Man in the Middle (MITM) "
                                     "attacks.", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    It is strongly advised that you enable strict SSH "
                                     "host key checking", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    unless you are absolutely certain that your network "
                                     "environment is safe.\n", "default")], stderr=True)
        error += 1

    return abort, critical, error, warning, note


def check_sudo_configuration(**kwargs: Any) -> tuple[bool, int, int, int, int]:
    """
    This checks whether the user is in /etc/sudoers or /etc/sudoers.d,
    and whether the user can sudo without a password

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                user (str): Username of the executing user
                critical (int): The current count of critical severity security issues
                error (int): The current count of error severity security issues
                warning (int): The current count of warning severity security issues
                note (int): The current count of note severity security issues
        Returns:
            (bool, int, int, int, int):
                (bool): Is this error severe enough that we should abort immediately?
                (int): The new count of critical severity security issues
                (int): The new count of error severity security issues
                (int): The new count of warning severity security issues
                (int): The new count of note severity security issues
    """
    user: str = deep_get(kwargs, DictPath("user"))
    critical: int = deep_get(kwargs, DictPath("critical"), 0)
    error: int = deep_get(kwargs, DictPath("error"), 0)
    warning: int = deep_get(kwargs, DictPath("warning"), 0)
    note: int = deep_get(kwargs, DictPath("note"), 0)

    abort = False

    ansithemeprint([ANSIThemeStr("[Checking whether ", "phase"),
                    ANSIThemeStr(f"{user}", "path"),
                    ANSIThemeStr(" is in ", "phase"),
                    ANSIThemeStr("/etc/sudoers", "path"),
                    ANSIThemeStr(" or ", "phase"),
                    ANSIThemeStr("/etc/sudoers.d", "path"),
                    ANSIThemeStr(" on ", "phase"),
                    ANSIThemeStr("localhost", "hostname"),
                    ANSIThemeStr("]", "phase")])
    args = ["/usr/bin/sudo", "-l"]
    result = execute_command_with_response(args)

    sudoer = True

    sudo_msg_regex = re.compile(r"^User ([^\s]+) is not allowed to run sudo on.*")

    for line in result.splitlines():
        tmp = sudo_msg_regex.match(line)
        if tmp is not None:
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(":", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    The user ", "default"),
                            ANSIThemeStr(user, "path"),
                            ANSIThemeStr(" is not in ", "default"),
                            ANSIThemeStr("/etc/sudoers", "path"),
                            ANSIThemeStr(" or ", "default"),
                            ANSIThemeStr("/etc/sudoers.d", "path"),
                            ANSIThemeStr(".\n", "default")], stderr=True)
            error += 1
            sudoer = False
            break

    if sudoer:
        ansithemeprint([ANSIThemeStr("  OK\n", "ok")])

        ansithemeprint([ANSIThemeStr("[Checking whether", "phase"),
                        ANSIThemeStr(f" {user} ", "path"),
                        ANSIThemeStr("can perform passwordless sudo", "phase"),
                        ANSIThemeStr(" on ", "phase"),
                        ANSIThemeStr("localhost", "hostname"),
                        ANSIThemeStr("]", "phase")])
        passwordless_sudo = False

        sudo_permissions_regex = re.compile(r"^\s*\(ALL(\s*:\s*ALL)?\)\s*NOPASSWD:\s*ALL\s*$")

        for line in result.splitlines():
            tmp = sudo_permissions_regex.match(line)
            if tmp is not None:
                ansithemeprint([ANSIThemeStr("  OK\n", "emphasis")])
                passwordless_sudo = True
                break

        if not passwordless_sudo:
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(":", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    The user ", "default"),
                            ANSIThemeStr(user, "path"),
                            ANSIThemeStr(" cannot perform passwordless sudo.\n",
                                         "default")], stderr=True)
            error += 1

    return abort, critical, error, warning, note


def check_ansible_dir_permissions(**kwargs: Any) -> tuple[bool, int, int, int, int]:
    """
    This checks whether .ansible is owned and accessible by the user

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                user (str): Username of the executing user
                critical (int): The current count of critical severity security issues
                error (int): The current count of error severity security issues
                warning (int): The current count of warning severity security issues
                note (int): The current count of note severity security issues
                verbose (bool): True for verbose output about actions
                exit_on_error (bool): Exit if there an error?
                quiet_on_ok (bool): Only output messages when issues are found?
        Returns:
            (bool, int, int, int, int):
                (bool): Is this error severe enough that we should abort immediately?
                (int): The new count of critical severity security issues
                (int): The new count of error severity security issues
                (int): The new count of warning severity security issues
                (int): The new count of note severity security issues
    """
    abort = False

    user: str = deep_get(kwargs, DictPath("user"))
    critical: int = deep_get(kwargs, DictPath("critical"), 0)
    error: int = deep_get(kwargs, DictPath("error"), 0)
    warning: int = deep_get(kwargs, DictPath("warning"), 0)
    note: int = deep_get(kwargs, DictPath("note"), 0)
    verbose: bool = deep_get(kwargs, DictPath("verbose"), True)
    exit_on_error: bool = deep_get(kwargs, DictPath("exit_on_error"), False)
    quiet_on_ok: bool = deep_get(kwargs, DictPath("quiet_on_ok"), False)

    if verbose:
        ansithemeprint([ANSIThemeStr("[Checking whether ownership for ", "phase"),
                        ANSIThemeStr(".ansible", "path"),
                        ANSIThemeStr(" is correct on ", "phase"),
                        ANSIThemeStr("localhost", "hostname"),
                        ANSIThemeStr("]", "phase")])

    path_entry = Path(DOT_ANSIBLE_PATH)
    # It's OK if .ansible doesn't exist; it will be created on execution
    if path_entry.exists():
        path_stat = path_entry.stat()
        path_permissions = path_stat.st_mode

        if path_permissions & 0o300 != 0o300:
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Critical", "critical"),
                            ANSIThemeStr(":", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    The permissions for ", "default"),
                            ANSIThemeStr(f"{DOT_ANSIBLE_PATH}", "path"),
                            ANSIThemeStr(" are ", "default"),
                            ANSIThemeStr(f"{path_permissions:03o}", "emphasis"),
                            ANSIThemeStr(";", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    Ansible will not be able to ", "default"),
                            ANSIThemeStr("run properly.", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Justification", "emphasis"),
                            ANSIThemeStr(": ", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    Ansible will fail to run if it cannot write to ",
                                         "default"),
                            ANSIThemeStr(f"{DOT_ANSIBLE_PATH}", "path"),
                            ANSIThemeStr("\n", "default")], stderr=True)
            if exit_on_error:
                sys.exit(errno.EPERM)
            critical += 1
        if path_entry.owner() != user:
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Critical", "critical"),
                            ANSIThemeStr(":", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    The executing user ", "default"),
                            ANSIThemeStr(f"{user}", "path"),
                            ANSIThemeStr(" is not the owner of ", "default"),
                            ANSIThemeStr(f"{DOT_ANSIBLE_PATH}", "path")], stderr=True)
            ansithemeprint([ANSIThemeStr("    Ansible will not be able to ", "default"),
                            ANSIThemeStr("run properly.", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Justification", "emphasis"),
                            ANSIThemeStr(": ", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    Ansible will fail to run if it cannot write to ",
                                         "default"),
                            ANSIThemeStr(f"{DOT_ANSIBLE_PATH}", "path"),
                            ANSIThemeStr("\n", "default")], stderr=True)
            if exit_on_error:
                sys.exit(errno.EPERM)
            critical += 1
        elif not quiet_on_ok:
            ansithemeprint([ANSIThemeStr("  OK\n", "emphasis")])
    elif not quiet_on_ok:
        ansithemeprint([ANSIThemeStr("  OK\n", "emphasis")])

    return abort, critical, error, warning, note


def check_netrc_permissions(**kwargs: Any) -> tuple[bool, int, int, int, int]:
    """
    This checks whether the .netrc are sufficiently strict (0600 is required to satisfy Ansible)

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                critical (int): The current count of critical severity security issues
                error (int): The current count of error severity security issues
                warning (int): The current count of warning severity security issues
                note (int): The current count of note severity security issues
                verbose (bool): True for verbose output about actions
                exit_on_error (bool): Exit if there an error?
                quiet_on_ok (bool): Only output messages when issues are found?
        Returns:
            (bool, int, int, int, int):
                (bool): Is this error severe enough that we should abort immediately?
                (int): The new count of critical severity security issues
                (int): The new count of error severity security issues
                (int): The new count of warning severity security issues
                (int): The new count of note severity security issues
    """
    critical: int = deep_get(kwargs, DictPath("critical"), 0)
    error: int = deep_get(kwargs, DictPath("error"), 0)
    warning: int = deep_get(kwargs, DictPath("warning"), 0)
    note: int = deep_get(kwargs, DictPath("note"), 0)
    verbose = deep_get(kwargs, DictPath("verbose"), True)
    exit_on_error = deep_get(kwargs, DictPath("exit_on_error"), False)
    quiet_on_ok = deep_get(kwargs, DictPath("quiet_on_ok"), False)

    abort = False

    if verbose:
        ansithemeprint([ANSIThemeStr("[Checking whether permissions for ", "phase"),
                        ANSIThemeStr(".netrc", "path"),
                        ANSIThemeStr(" are sufficiently strict on ", "phase"),
                        ANSIThemeStr("localhost", "hostname"),
                        ANSIThemeStr("]", "phase")])

    path_entry = Path(NETRC_PATH)
    if not path_entry.exists():
        if verbose:
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Note", "critical"),
                            ANSIThemeStr(":", "default")])
            ansithemeprint([ANSIThemeStr(f"    {NETRC_PATH}", "path"),
                            ANSIThemeStr(" does not exist.\n", "default")])
        note += 1
        return abort, critical, error, warning, note

    path_stat = path_entry.stat()
    path_permissions = path_stat.st_mode & 0o777

    if path_permissions not in (0o600, 0o400):
        ansithemeprint([ANSIThemeStr("  ", "default"),
                        ANSIThemeStr("Critical", "critical"),
                        ANSIThemeStr(":", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    The permissions for ", "default"),
                        ANSIThemeStr(f"{NETRC_PATH}", "path"),
                        ANSIThemeStr(" are ", "default"),
                        ANSIThemeStr(f"{path_permissions:03o}", "emphasis"),
                        ANSIThemeStr(";", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    the required permissions are ", "default"),
                        ANSIThemeStr(f"{0o600:03o}", "emphasis"),
                        ANSIThemeStr(" (or stricter).", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("  ", "default"),
                        ANSIThemeStr("Justification", "emphasis"),
                        ANSIThemeStr(": ", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    Ansible will refuse to fetch files if "
                                     "the permissions for ", "default"),
                        ANSIThemeStr(f"{NETRC_PATH}", "path"),
                        ANSIThemeStr(" are not sufficiently strict\n", "default")], stderr=True)
        if exit_on_error:
            sys.exit(errno.EPERM)
        critical += 1
    elif not quiet_on_ok:
        ansithemeprint([ANSIThemeStr("  OK\n", "emphasis")])

    return abort, critical, error, warning, note


def check_known_hosts_hashing(**kwargs: Any) -> tuple[bool, int, int, int, int]:
    """
    This checks whether ssh known_hosts hashing is enabled

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                critical (int): The current count of critical severity security issues
                error (int): The current count of error severity security issues
                warning (int): The current count of warning severity security issues
                note (int): The current count of note severity security issues
                verbose (bool): True for verbose output about actions
        Returns:
            (bool, int, int, int, int):
                (bool): Is this error severe enough that we should abort immediately?
                (int): The new count of critical severity security issues
                (int): The new count of error severity security issues
                (int): The new count of warning severity security issues
                (int): The new count of note severity security issues
    """
    critical: int = deep_get(kwargs, DictPath("critical"), 0)
    error: int = deep_get(kwargs, DictPath("error"), 0)
    warning: int = deep_get(kwargs, DictPath("warning"), 0)
    note: int = deep_get(kwargs, DictPath("note"), 0)
    verbose = deep_get(kwargs, DictPath("verbose"), True)

    abort = False

    if verbose:
        ansithemeprint([ANSIThemeStr("[Checking whether hashing of ", "phase"),
                        ANSIThemeStr(".ssh/known_hosts", "path"),
                        ANSIThemeStr(" is enabled on ", "phase"),
                        ANSIThemeStr("localhost", "hostname"),
                        ANSIThemeStr("]", "phase")])
        ansithemeprint([ANSIThemeStr("  ", "default"),
                        ANSIThemeStr("Note", "note"),
                        ANSIThemeStr(":", "default")])
        ansithemeprint([ANSIThemeStr("    Since ", "default"),
                        ANSIThemeStr("ssh", "programname"),
                        ANSIThemeStr(" settings can vary per host this test "
                                     "is not 100% reliable.\n", "default")])
    args = [SSH_BIN_PATH, "-G", "localhost"]
    result = execute_command_with_response(args)

    hashknownhosts_regex = re.compile(r"^hashknownhosts\s+yes$")

    for line in result.splitlines():
        tmp = hashknownhosts_regex.match(line)
        if tmp is not None:
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Warning", "warning"),
                            ANSIThemeStr(":", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    Hashing of ", "default"),
                            ANSIThemeStr(".ssh/known_hosts", "path"),
                            ANSIThemeStr(" is enabled;", "default"),
                            ANSIThemeStr(" this may cause issues with ", "default"),
                            ANSIThemeStr("paramiko", "programname"),
                            ANSIThemeStr(".\n", "default")], stderr=True)
            warning += 1
            break

    return abort, critical, error, warning, note


def check_insecure_kube_config_options(**kwargs: Any) -> tuple[bool, int, int, int, int]:
    """
    This checks whether .kube/config has insecure options

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                cluster_name (str): The name of the cluster
                kubeconfig (dict): The kubeconfig file
                critical (int): The current count of critical severity security issues
                error (int): The current count of error severity security issues
                warning (int): The current count of warning severity security issues
                note (int): The current count of note severity security issues
                verbose (bool): True for verbose output about actions
                quiet_on_ok (bool): Only output messages when issues are found?
        Returns:
            (bool, int, int, int, int):
                (bool): Is this error severe enough that we should abort immediately?
                (int): The new count of critical severity security issues
                (int): The new count of error severity security issues
                (int): The new count of warning severity security issues
                (int): The new count of note severity security issues
    """
    cluster_name: str = deep_get(kwargs, DictPath("cluster_name"))
    kubeconfig: dict = deep_get(kwargs, DictPath("kubeconfig"), {})
    critical: int = deep_get(kwargs, DictPath("critical"), 0)
    error: int = deep_get(kwargs, DictPath("error"), 0)
    warning: int = deep_get(kwargs, DictPath("warning"), 0)
    note: int = deep_get(kwargs, DictPath("note"), 0)
    verbose = deep_get(kwargs, DictPath("verbose"), True)
    quiet_on_ok = deep_get(kwargs, DictPath("quiet_on_ok"), False)

    abort = False

    if verbose:
        ansithemeprint([ANSIThemeStr("[Checking for insecure ", "phase"),
                        ANSIThemeStr(f"{KUBE_CONFIG_FILE}", "path"),
                        ANSIThemeStr(" options]", "phase")])

    insecureskiptlsverify = False

    for cluster in deep_get(kubeconfig, DictPath("clusters"), []):
        if deep_get(cluster, DictPath("name"), "") == cluster_name:
            insecureskiptlsverify = deep_get(cluster, DictPath("insecure-skip-tls-verify"), False)
            break

    if not insecureskiptlsverify:
        if not quiet_on_ok:
            ansithemeprint([ANSIThemeStr("  OK\n", "emphasis")])
    else:
        # Use critical for highlighting warning here, since the warning is so important
        ansithemeprint([ANSIThemeStr("  ", "default"),
                        ANSIThemeStr("Warning", "critical"),
                        ANSIThemeStr(":", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    TLS verification has been disabled in ", "emphasis"),
                        ANSIThemeStr(f"{KUBE_CONFIG_FILE}", "path"),
                        ANSIThemeStr("; this is a security threat.", "emphasis")], stderr=True)
        ansithemeprint([ANSIThemeStr("    If TLS verification is disabled other systems can "
                                     "impersonate the control plane", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    and thus perform Man in the Middle (MITM) "
                                     "attacks.", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    It is advised that you remove the ", "default"),
                        ANSIThemeStr("insecure-skip-tls-verify", "argument"),
                        ANSIThemeStr(" option from ", "default"),
                        ANSIThemeStr(f"{KUBE_CONFIG_FILE}", "path"),
                        ANSIThemeStr(",", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    unless you are absolutely certain that your "
                                     "network environment is safe", "default")],
                       stderr=True)
        ansithemeprint([ANSIThemeStr("    and this is a development cluster.\n", "default")],
                       stderr=True)
        critical += 1

    return abort, critical, error, warning, note


# pylint: disable-next=too-many-statements
def check_client_server_version_match(**kwargs: Any) -> tuple[bool, int, int, int, int]:
    """
    This checks whether the versions of the various Kubernetes match properly

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                critical (int): The current count of critical severity security issues
                error (int): The current count of error severity security issues
                warning (int): The current count of warning severity security issues
                note (int): The current count of note severity security issues
        Returns:
            (bool, int, int, int, int):
                (bool): Is this error severe enough that we should abort immediately?
                (int): The new count of critical severity security issues
                (int): The new count of error severity security issues
                (int): The new count of warning severity security issues
                (int): The new count of note severity security issues
    """
    critical: int = deep_get(kwargs, DictPath("critical"), 0)
    error: int = deep_get(kwargs, DictPath("error"), 0)
    warning: int = deep_get(kwargs, DictPath("warning"), 0)
    note: int = deep_get(kwargs, DictPath("note"), 0)

    mismatch = False
    abort = False

    # Is the version of kubectl within one version of the cluster version?
    ansithemeprint([ANSIThemeStr("[Checking client/server version match]", "phase")])

    _kubectl_major_version, kubectl_minor_version, kubectl_git_version, \
        server_major_version, server_minor_version, server_git_version = kubectl_get_version()

    if kubectl_git_version == "<unavailable>" or kubectl_minor_version is None:
        ansithemeprint([ANSIThemeStr("Critical", "critical"),
                        ANSIThemeStr(": Could not extract ", "default"),
                        ANSIThemeStr("kubectl", "programname"),
                        ANSIThemeStr(" version; will abort.", "default")], stderr=True)
        abort = True
        critical += 1
    else:
        ansithemeprint([ANSIThemeStr("         kubectl ", "programname"),
                        ANSIThemeStr("version: ", "default"),
                        ANSIThemeStr(f"{kubectl_git_version}", "version")])
    if server_git_version == "<unavailable>" or \
            server_major_version is None or server_minor_version is None:
        ansithemeprint([ANSIThemeStr("  ", "default"),
                        ANSIThemeStr("Critical", "error"),
                        ANSIThemeStr(":", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    Could not extract ", "default"),
                        ANSIThemeStr("kube-apiserver", "programname"),
                        ANSIThemeStr(" version (double-check that the server is "
                                     "running and that ", "default"),
                        ANSIThemeStr("https_proxy", "argument"),
                        ANSIThemeStr(" and  ", "default"),
                        ANSIThemeStr("no_proxy", "argument"),
                        ANSIThemeStr(" are correctly set); will abort.",
                                     "default")], stderr=True)
        https_proxy_env = os.getenv("https_proxy")
        no_proxy_env = os.getenv("no_proxy")
        ansithemeprint([ANSIThemeStr("      https_proxy", "argument"),
                        ANSIThemeStr(" (env): ", "default"),
                        ANSIThemeStr(f"{https_proxy_env}", "url")], stderr=True)
        ansithemeprint([ANSIThemeStr("      no_proxy", "argument"),
                        ANSIThemeStr(" (env): ", "default"),
                        ANSIThemeStr(f"{no_proxy_env}", "url")], stderr=True)
        abort = True
        critical += 1
    else:
        ansithemeprint([ANSIThemeStr("  kube-apiserver ", "programname"),
                        ANSIThemeStr("version: ", "default"),
                        ANSIThemeStr(f"{server_git_version}", "version")])

    if abort:
        return abort, critical, error, warning, note

    kubectl_minor_version = cast(int, kubectl_minor_version)
    server_major_version = cast(int, server_major_version)
    server_minor_version = cast(int, server_minor_version)

    print()

    if server_major_version != 1:
        ansithemeprint([ANSIThemeStr("  ", "default"),
                        ANSIThemeStr("Critical", "critical"),
                        ANSIThemeStr(": ", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr(f"    {about.PROGRAM_SUITE_NAME}", "programname"),
                        ANSIThemeStr(" has not been tested for any other major version of "
                                     "Kubernetes ", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    than ", "default"),
                        ANSIThemeStr("v1", "version"),
                        ANSIThemeStr("; aborting.", "default")], stderr=True)
        sys.exit(errno.ENOTSUP)

    if kubectl_minor_version > server_minor_version and \
            kubectl_minor_version == server_minor_version + 1:
        ansithemeprint([ANSIThemeStr("  ", "default"),
                        ANSIThemeStr("Note", "note"),
                        ANSIThemeStr(":", "default")])
        ansithemeprint([ANSIThemeStr("    The ", "default"),
                        ANSIThemeStr("kubectl", "programname"),
                        ANSIThemeStr(" version is one minor version newer than that of ",
                                     "default"),
                        ANSIThemeStr("kube-apiserver", "programname"),
                        ANSIThemeStr(";", "default")])
        ansithemeprint([ANSIThemeStr("    this is a supported configuration, "
                                     "but it is generally recommended to keep", "default")])
        ansithemeprint([ANSIThemeStr("    the versions in sync.", "default")])
        note += 1
        mismatch = True
    elif kubectl_minor_version > server_minor_version:
        ansithemeprint([ANSIThemeStr("  ", "default"),
                        ANSIThemeStr("Warning", "warning"),
                        ANSIThemeStr(":", "default")])
        ansithemeprint([ANSIThemeStr("    The ", "default"),
                        ANSIThemeStr("kubectl", "programname"),
                        ANSIThemeStr(" version is more than one minor version newer than",
                                     "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    that of ", "default"),
                        ANSIThemeStr("kube-apiserver", "programname"),
                        ANSIThemeStr("; this might work, but it is generally recommended",
                                     "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    to keep the versions in sync.",
                                     "default")], stderr=True)
        warning += 1
        mismatch = True
    elif kubectl_minor_version < server_minor_version and \
            kubectl_minor_version + 1 == server_minor_version:
        ansithemeprint([ANSIThemeStr("  ", "default"),
                        ANSIThemeStr("Warning", "warning"),
                        ANSIThemeStr(":", "default")])
        ansithemeprint([ANSIThemeStr("    The ", "default"),
                        ANSIThemeStr("kubectl", "programname"),
                        ANSIThemeStr(" version is one minor version older "
                                     "than that of ", "default"),
                        ANSIThemeStr("kube-apiserver", "programname"),
                        ANSIThemeStr(";", "default")])
        ansithemeprint([ANSIThemeStr("    this is a supported configuration, "
                                     "but it is generally recommended to keep", "default")])
        ansithemeprint([ANSIThemeStr("    the versions in sync.", "default")], stderr=True)
        warning += 1
        mismatch = True
    elif kubectl_minor_version < server_minor_version:
        ansithemeprint([ANSIThemeStr("  ", "default"),
                        ANSIThemeStr("Error", "error"),
                        ANSIThemeStr(":", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    The ", "default"),
                        ANSIThemeStr("kubectl", "programname"),
                        ANSIThemeStr(" version is much older than that of ", "default"),
                        ANSIThemeStr("kube-apiserver", "programname"),
                        ANSIThemeStr(";", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    this is ", "default"),
                        ANSIThemeStr("NOT", "emphasis"),
                        ANSIThemeStr(" supported and is likely to "
                                     "cause issues.", "default")], stderr=True)
        error += 1
        mismatch = True

    if not mismatch:
        ansithemeprint([ANSIThemeStr("  OK", "ok")])

    return abort, critical, error, warning, note


# pylint: disable-next=too-many-statements,too-many-locals,too-many-branches
def check_kubelet_and_kube_proxy_versions(**kwargs: Any) -> tuple[bool, int, int, int, int]:
    """
    This checks whether the versions of kubelet and kube-proxy are acceptable

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                critical (int): The current count of critical severity security issues
                error (int): The current count of error severity security issues
                warning (int): The current count of warning severity security issues
                note (int): The current count of note severity security issues
        Returns:
            (bool, int, int, int, int):
                (bool): Is this error severe enough that we should abort immediately?
                (int): The new count of critical severity security issues
                (int): The new count of error severity security issues
                (int): The new count of warning severity security issues
                (int): The new count of note severity security issues
    """
    critical: int = deep_get(kwargs, DictPath("critical"), 0)
    error: int = deep_get(kwargs, DictPath("error"), 0)
    warning: int = deep_get(kwargs, DictPath("warning"), 0)
    note: int = deep_get(kwargs, DictPath("note"), 0)

    abort = False

    # Check kubelet and kube-proxy versions;
    # they can be up to two minor versions older than kube-apiserver,
    # but must not be newer

    mismatch = False

    _kubectl_major_version, _kubectl_minor_version, _kubectl_git_version, \
        server_major_version, server_minor_version, _server_git_version = kubectl_get_version()

    if server_major_version is None:
        ansithemeprint([ANSIThemeStr("  ", "default"),
                        ANSIThemeStr("Critical", "error"),
                        ANSIThemeStr(":", "default")], stderr=True)
        ansithemeprint([ANSIThemeStr("    Could not extract ", "default"),
                        ANSIThemeStr("kube-apiserver", "programname"),
                        ANSIThemeStr(" version (double-check that the server "
                                     "is running and that ", "default"),
                        ANSIThemeStr("https_proxy", "argument"),
                        ANSIThemeStr(" and  ", "default"),
                        ANSIThemeStr("no_proxy", "argument"),
                        ANSIThemeStr(" are correctly set); will abort.",
                                     "default")], stderr=True)
        abort = True
        critical += 1
        return abort, critical, error, warning, note

    server_major_version = cast(int, server_major_version)
    server_minor_version = cast(int, server_minor_version)

    # Kubernetes API based checks
    ansithemeprint([ANSIThemeStr("\n[Checking ", "phase"),
                    ANSIThemeStr("kubelet", "programname"),
                    ANSIThemeStr(" & ", "phase"),
                    ANSIThemeStr("kube-proxy", "programname"),
                    ANSIThemeStr(" versions]", "phase")])

    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("check_kubelet_and_kube_proxy_versions() "
                               "called without kubernetes_helper")

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
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(":", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    Failed to extract ", "default"),
                            ANSIThemeStr("kubelet", "programname"),
                            ANSIThemeStr(" version on node ", "default"),
                            ANSIThemeStr(f"{node_name}", "hostname")], stderr=True)
            critical += 1
            mismatch = True

        tmp = version_regex.match(kubeproxy_version)
        if tmp is not None:
            kubeproxy_major_version = int(tmp[1])
            kubeproxy_minor_version = int(tmp[2])
        else:
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(":", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    Failed to extract ", "default"),
                            ANSIThemeStr("kube-proxy", "programname"),
                            ANSIThemeStr(" version on node ", "default"),
                            ANSIThemeStr(f"{node_name}", "hostname")], stderr=True)
            critical += 1
            mismatch = True

        if kubelet_major_version is not None and kubelet_major_version != 1:
            ansithemeprint([ANSIThemeStr("Critical", "critical"),
                            ANSIThemeStr(": ", "default"),
                            ANSIThemeStr(about.PROGRAM_SUITE_NAME, "programname"),
                            ANSIThemeStr(" has not been tested for any other major version "
                                         "of Kubernetes than v1; node ", "default"),
                            ANSIThemeStr(f"{node_name}", "hostname"),
                            ANSIThemeStr(" runs ", "default"),
                            ANSIThemeStr("kubelet ", "programname"),
                            ANSIThemeStr("version ", "default"),
                            ANSIThemeStr(f"{kubelet_version}", "version")], stderr=True)
            critical += 1
            mismatch = True

        if kubeproxy_major_version is not None and kubeproxy_major_version != 1:
            ansithemeprint([ANSIThemeStr("Critical", "critical"),
                            ANSIThemeStr(": ", "default"),
                            ANSIThemeStr(about.PROGRAM_SUITE_NAME, "programname"),
                            ANSIThemeStr(" has not been tested for any other major version "
                                         "of Kubernetes than v1; node ", "default"),
                            ANSIThemeStr(f"{node_name}", "hostname"),
                            ANSIThemeStr(" runs ", "default"),
                            ANSIThemeStr("kube-proxy ", "programname"),
                            ANSIThemeStr("version ", "default"),
                            ANSIThemeStr(f"{kubeproxy_version}", "version")], stderr=True)
            critical += 1
            mismatch = True

        if kubelet_minor_version is not None and kubelet_minor_version > server_minor_version:
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(":", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    The version of ", "default"),
                            ANSIThemeStr("kubelet", "programname"),
                            ANSIThemeStr(" (", "default"),
                            ANSIThemeStr(f"{kubelet_major_version}.{kubelet_minor_version}",
                                         "version"),
                            ANSIThemeStr(") on node ", "default"),
                            ANSIThemeStr(f"{node_name}", "hostname"),
                            ANSIThemeStr(" is newer than that of ", "default"),
                            ANSIThemeStr("kube-apiserver", "programname"),
                            ANSIThemeStr(" (", "default"),
                            ANSIThemeStr(f"{server_major_version}.{server_minor_version}",
                                         "version"),
                            ANSIThemeStr(");", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("       this is not supported.", "default")], stderr=True)
            error += 1
            mismatch = True
        elif kubelet_minor_version is not None and \
                server_minor_version - 2 <= kubelet_minor_version < server_minor_version:
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Warning", "warning"),
                            ANSIThemeStr(":", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    The version of ", "default"),
                            ANSIThemeStr("kubelet", "programname"),
                            ANSIThemeStr(" (", "default"),
                            ANSIThemeStr(f"{kubelet_major_version}.{kubelet_minor_version}",
                                         "version"),
                            ANSIThemeStr(") on node ", "default"),
                            ANSIThemeStr(f"{node_name}", "hostname"),
                            ANSIThemeStr(" is a bit older than that of ", "default"),
                            ANSIThemeStr("kube-apiserver", "programname"),
                            ANSIThemeStr(" (", "default"),
                            ANSIThemeStr(f"{server_major_version}.{server_minor_version}",
                                         "version"),
                            ANSIThemeStr(");", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("         this is supported, but not recommended.",
                                         "default")], stderr=True)
            warning += 1
            mismatch = True
        elif kubelet_minor_version is not None and kubelet_minor_version < server_minor_version:
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(":", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    The version of ", "default"),
                            ANSIThemeStr("kubelet", "programname"),
                            ANSIThemeStr(" (", "default"),
                            ANSIThemeStr(f"{kubelet_major_version}.{kubelet_minor_version}",
                                         "version"),
                            ANSIThemeStr(") on node ", "default"),
                            ANSIThemeStr(f"{node_name}", "hostname"),
                            ANSIThemeStr(" is much older than that of ", "default"),
                            ANSIThemeStr("kube-apiserver", "programname"),
                            ANSIThemeStr(" (", "default"),
                            ANSIThemeStr(f"{server_major_version}.{server_minor_version}",
                                         "version"),
                            ANSIThemeStr(");", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("       this is not supported.",
                                         "default")], stderr=True)
            error += 1
            mismatch = True

        if kubelet_minor_version is not None and \
                kubeproxy_minor_version is not None and \
                kubelet_minor_version != kubeproxy_minor_version:
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(":", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    The version of ", "default"),
                            ANSIThemeStr("kubelet", "programname"),
                            ANSIThemeStr(" (", "default"),
                            ANSIThemeStr(f"{kubelet_major_version}.{kubelet_minor_version}",
                                         "version"),
                            ANSIThemeStr(") on node ", "default"),
                            ANSIThemeStr(f"{node_name}", "hostname"),
                            ANSIThemeStr(" is not the same as that of ", "default"),
                            ANSIThemeStr("kube-proxy", "programname"),
                            ANSIThemeStr(" (", "default"),
                            ANSIThemeStr(f"{kubeproxy_major_version}."
                                         f"{kubeproxy_minor_version}", "version"),
                            ANSIThemeStr(");", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("       this is not supported.",
                                         "default")], stderr=True)
            error += 1
            mismatch = True

    if not mismatch:
        ansithemeprint([ANSIThemeStr("  OK", "ok")])

    return abort, critical, error, warning, note


required_pods: dict[str, list[dict[str, list]]] = {
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
            "note": [ANSIThemeStr("Note", "note"),
                     ANSIThemeStr(": Optional for ", "default"),
                     ANSIThemeStr("CRC", "programname"),
                     ANSIThemeStr("/", "separator"),
                     ANSIThemeStr("OpenShift", "programname"),
                     ANSIThemeStr(".\n", "default")],
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
            "all_of": [("calico-apiserver", "calico-apiserver"),
                       ("calico-system", "calico-kube-controllers")],
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


def get_pod_set(pods: list[dict],
                any_of: list[tuple[str, str]],
                all_of: list[tuple[str, str]]) -> tuple[list[dict],
                                                        dict[tuple[str, str], list[dict]]]:
    """
    Given an any_of list (namespace, pod_prefix), and an all_of list (namespace, pod_prefix),
    returns all pod objects (if any)

        Parameters:
            pods ([pod]): A list of pod objects
            any_of ([(str, str)]): A list of (namespace, name-prefix)
                                   of which at least one must exist
            all_of ({[(str, str)]}): A list of (namespace, name-prefix) of which all must exist
        Returns:
            ([(str, str)], [(str, str)]):
                ([(str, str)]): A list of (namespace, name) for pods matching the any_of criteria
                ([(str, str)]): A dict indexed by (namespace, name-prefix)
                                of list of (namespace, name) for pods matching the all_of criteria
    """
    any_of_matches: list[dict] = []
    all_of_matches: dict[tuple[str, str], list[dict]] = {}

    for obj in pods:
        pod_name = deep_get(obj, DictPath("metadata#name"), "")
        pod_namespace = deep_get(obj, DictPath("metadata#namespace"), "")
        for match_namespace, match_name in any_of:
            # If we're instructed to match namespace and the namespace doesn't match, skip this pod
            if match_namespace and match_namespace != pod_namespace:
                continue
            # If the pod name doesn't start with the name prefix, skip this pod
            if not pod_name.startswith(match_name):
                continue
            any_of_matches.append(obj)

        for match_namespace, match_name in all_of:
            # If we're instructed to match namespace and the namespace doesn't match, skip this pod
            if match_namespace and match_namespace != pod_namespace:
                continue
            # If the pod name doesn't start with the name prefix, skip this pod
            if not pod_name.startswith(match_name):
                continue
            if (match_namespace, match_name) not in all_of_matches:
                all_of_matches[(match_namespace, match_name)] = []
            all_of_matches[(match_namespace, match_name)].append(obj)

    # If either condition fails, return empty lists
    if all_of and not all_of_matches or any_of and not any_of_matches:
        any_of_matches = []
        all_of_matches = {}

    return (any_of_matches, all_of_matches)


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def check_running_pods(**kwargs: Any) -> tuple[bool, int, int, int, int]:
    """
    This checks what pods are running and their status

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                kubernetes_helper (KubernetesHelper): A reference to a KubernetesHelper object
                critical (int): The current count of critical severity security issues
                error (int): The current count of error severity security issues
                warning (int): The current count of warning severity security issues
                note (int): The current count of note severity security issues
        Returns:
            (bool, int, int, int, int):
                (bool): Is this error severe enough that we should abort immediately?
                    (int): The new count of critical severity security issues
                    (int): The new count of error severity security issues
                    (int): The new count of warning severity security issues
                    (int): The new count of note severity security issues
    """
    critical: int = deep_get(kwargs, DictPath("critical"), 0)
    error: int = deep_get(kwargs, DictPath("error"), 0)
    warning: int = deep_get(kwargs, DictPath("warning"), 0)
    note: int = deep_get(kwargs, DictPath("note"), 0)

    abort = False

    ansithemeprint([ANSIThemeStr("\n[Checking required pods]", "phase")])

    if (kh := deep_get(kwargs, DictPath("kubernetes_helper"))) is None:
        raise ProgrammingError("check_running_pods() called without kubernetes_helper")

    pods, _status = kh.get_list_by_kind_namespace(("Pod", ""), "")
    all_ok = True

    for rp, rp_data in required_pods.items():
        ansithemeprint([ANSIThemeStr("•", "separator"),
                        ANSIThemeStr(f" {rp}", "programname")])

        matches = []

        for rp_match in rp_data:
            any_of = deep_get(rp_match, DictPath("any_of"), [])
            all_of = deep_get(rp_match, DictPath("all_of"), [])
            additional_info = deep_get(rp_match, DictPath("note"), [])
            any_of_matches, all_of_matches = get_pod_set(cast(list[dict], pods), any_of, all_of)

            if any_of_matches or all_of_matches:
                matches.append((any_of_matches, all_of_matches))

        if not matches:
            if any_of and not any_of_matches:
                ansithemeprint([ANSIThemeStr("  ", "default"),
                                ANSIThemeStr("Error", "error"),
                                ANSIThemeStr(":", "default")], stderr=True)
                ansithemeprint([ANSIThemeStr("    At least one of the following pods is "
                                             "expected to be running:", "default")], stderr=True)
                for expected_namespace, expected_name in any_of:
                    if not expected_namespace:
                        expected_namespace = "<any>"
                    ansithemeprint([ANSIThemeStr(f"      {expected_namespace}", "namespace"),
                                    ANSIThemeStr("::", "separator"),
                                    ANSIThemeStr(f"{expected_name}", "default")], stderr=True)
                all_ok = False
                error += 1

            if all_of and not all_of_matches:
                ansithemeprint([ANSIThemeStr("  ", "default"),
                                ANSIThemeStr("Error", "error"),
                                ANSIThemeStr(":", "default")], stderr=True)
                ansithemeprint([ANSIThemeStr("    All of the following pods are expected to "
                                             "be running:", "default")], stderr=True)
                for expected_namespace, expected_name in any_of:
                    if not expected_namespace:
                        expected_namespace = "<any>"
                    ansithemeprint([ANSIThemeStr(f"      {expected_namespace}", "namespace"),
                                    ANSIThemeStr("::", "separator"),
                                    ANSIThemeStr(f"{expected_name}", "default")], stderr=True)
                all_ok = False
                error += 1

        if len(matches) > 1:
            ansithemeprint([ANSIThemeStr("  ", "default"),
                            ANSIThemeStr("Warning", "warning"),
                            ANSIThemeStr(":", "default")], stderr=True)
            ansithemeprint([ANSIThemeStr("    Multiple possibly conflicting options were "
                                         "detected for ", "default"),
                            ANSIThemeStr(f"{rp}", "programname"),
                            ANSIThemeStr(".\n", "default")], stderr=True)
            warning += 1
            all_ok = False

        if matches:
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
                    if deep_get(condition, DictPath("type"), "") == "Ready" and \
                            deep_get(condition, DictPath("status"), "False") == "True":
                        ready = "Ready"
                if phase != "Running" or ready != "Ready":
                    if first:
                        ansithemeprint([ANSIThemeStr("  ", "default"),
                                        ANSIThemeStr("Error", "error"),
                                        ANSIThemeStr(":", "default")], stderr=True)
                        ansithemeprint([ANSIThemeStr("    The following pods should be in "
                                                     "phase Running, "
                                                     "condition Ready:", "default")])
                        first = False
                    ansithemeprint([ANSIThemeStr("        ", "default"),
                                    ANSIThemeStr(f"{pod_namespace}", "namespace"),
                                    ANSIThemeStr("::", "separator"),
                                    ANSIThemeStr(f"{pod_name}", "namespace"),
                                    ANSIThemeStr(" (", "default"),
                                    ANSIThemeStr(f"{phase}", "emphasis"),
                                    ANSIThemeStr("; ", "separator"),
                                    ANSIThemeStr(f"{ready}", "emphasis"),
                                    ANSIThemeStr(")", "default"),
                                    ANSIThemeStr(" on node ", "default"),
                                    ANSIThemeStr(f"{pod_node}", "hostname")], stderr=True)
                    error += 1
                    all_ok = False

        if all_ok:
            ansithemeprint([ANSIThemeStr("    OK\n", "success")])
        elif additional_info:
            ansithemeprint([ANSIThemeStr("    ", "default")] + additional_info)

    print()

    return abort, critical, error, warning, note


# pylint: disable-next=too-many-statements,too-many-locals,too-many-branches
def __check_permissions(recommended_permissions: list[dict], pathtype: str,
                        **kwargs: Any) -> tuple[bool, bool, int, int, int, int]:
    """
    Check permissions for a path
        Parameters:
            recommended_permissions ([dict]): A list of dicts with the path to check,
                                              the recommended permissions,
                                              severity, justification, etc.
            pathtype (str): The type of the path
            **kwargs (dict[str, Any]): Keyword arguments
                user (str): Username of the executing user
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
            (bool, bool, int, int, int, int):
                (bool): Should we abort?
                (bool): Found a security issue
                (int): The new count of critical severity security issues
                (int): The new count of error severity security issues
                (int): The new count of warning severity security issues
                (int): The new count of note severity security issues
    """
    user: str = deep_get(kwargs, DictPath("user"))
    usergroup: str = deep_get(kwargs, DictPath("usergroup"))
    critical: int = deep_get(kwargs, DictPath("critical"), 0)
    error: int = deep_get(kwargs, DictPath("error"), 0)
    warning: int = deep_get(kwargs, DictPath("warning"), 0)
    note: int = deep_get(kwargs, DictPath("note"), 0)

    issue = False
    abort = False

    if not user or not usergroup:
        raise ProgrammingError("__check_permissions() called without user and/or usergroup")

    for permissions in recommended_permissions:
        path = deep_get(permissions, DictPath("path"))
        alertmask = deep_get(permissions, DictPath("alertmask"), 0o077)
        usergroup_alertmask = deep_get(permissions, DictPath("usergroup_alertmask"), alertmask)
        severity = deep_get(permissions, DictPath("severity"), "critical")
        tmp_justification = deep_get(permissions, DictPath("justification"),
                                     [("<no justification provided>", "emphasis")])
        justification = ANSIThemeStr.tuplelist_to_ansithemearray(tmp_justification)
        executable = deep_get(permissions, DictPath("executable"), False)
        suffixes = deep_get(permissions, DictPath("suffixes"))
        optional = deep_get(permissions, DictPath("optional"), False)

        if usergroup:
            alertmask = usergroup_alertmask
        notemask = 0o000
        if pathtype == "file" and not executable:
            notemask = 0o111

        path_entry = Path(path)

        if path_entry.exists():
            # If this is a directory, but we operate on files we should apply these tests
            # for every matching file in this directory
            paths: list[Path] | Generator[Path, None, None] = []

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
                    ansithemeprint([ANSIThemeStr("  ", "default"),
                                    ANSIThemeStr("Critical", "error"),
                                    ANSIThemeStr(":", "default")], stderr=True)
                    ansithemeprint([ANSIThemeStr(f"    The owner of the {pathtype} ",
                                                 "default"),
                                    ANSIThemeStr(f"{entry}", "path"),
                                    ANSIThemeStr(" does not exist in the system database; "
                                                 "aborting.", "default")], stderr=True)
                    sys.exit(errno.ENOENT)
                try:
                    path_group = entry.group()
                except KeyError:
                    ansithemeprint([ANSIThemeStr("  ", "default"),
                                    ANSIThemeStr("Critical", "error"),
                                    ANSIThemeStr(":", "default")], stderr=True)
                    ansithemeprint([ANSIThemeStr(f"    The group of the {pathtype} ", "default"),
                                    ANSIThemeStr(f"{entry}", "path"),
                                    ANSIThemeStr(" does not exist in the system database; "
                                                 "aborting.", "default")], stderr=True)
                    sys.exit(errno.ENOENT)
                path_stat = entry.stat()
                path_permissions = path_stat.st_mode & 0o777
                recommended_permissions = 0o777 & ~(alertmask | notemask)

                if path_owner not in (user, "root"):
                    ansithemeprint([ANSIThemeStr("  ", "default"),
                                    ANSIThemeStr("Critical", severity),
                                    ANSIThemeStr(f": The {pathtype} ", "default"),
                                    ANSIThemeStr(f"{entry}", "path"),
                                    ANSIThemeStr(" is not owned by ", "default"),
                                    ANSIThemeStr(user, "emphasis")], stderr=True)
                    ansithemeprint([ANSIThemeStr("  ", "default"),
                                    ANSIThemeStr("Justification", "emphasis"),
                                    ANSIThemeStr(": if other users can overwrite files they "
                                                 "may be able to achieve elevated "
                                                 "privileges", "default")], stderr=True)
                    critical += 1
                    issue = True

                if usergroup and path_group != usergroup:
                    ansithemeprint([ANSIThemeStr("  ", "default"),
                                    ANSIThemeStr("Critical", severity),
                                    ANSIThemeStr(f": The {pathtype} ", "default"),
                                    ANSIThemeStr(f"{entry}", "path"),
                                    ANSIThemeStr(" does not belong to the user group for ",
                                                 "default"),
                                    ANSIThemeStr(user, "emphasis")], stderr=True)
                    ansithemeprint([ANSIThemeStr("  ", "default"),
                                    ANSIThemeStr("Justification", "emphasis"),
                                    ANSIThemeStr(": ", "default")] + justification,
                                   stderr=True)
                    print()
                    critical += 1
                    issue = True

                if path_permissions & alertmask != 0:
                    ansithemeprint([ANSIThemeStr("  ", "default"),
                                    ANSIThemeStr(f"{severity.capitalize()}", severity),
                                    ANSIThemeStr(":", "default")], stderr=True)
                    ansithemeprint([ANSIThemeStr(f"    The permissions for the {pathtype} ",
                                                 "default"),
                                    ANSIThemeStr(f"{entry}", "path"),
                                    ANSIThemeStr(" are ", "default"),
                                    ANSIThemeStr(f"{path_permissions:03o}", "emphasis"),
                                    ANSIThemeStr(";", "default")], stderr=True)
                    ansithemeprint([ANSIThemeStr("    the recommended permissions are ",
                                                 "default"),
                                    ANSIThemeStr(f"{recommended_permissions:03o}", "emphasis"),
                                    ANSIThemeStr(" (or stricter).", "default")], stderr=True)
                    ansithemeprint([ANSIThemeStr("  ", "default"),
                                    ANSIThemeStr("Justification", "emphasis"),
                                    ANSIThemeStr(": ", "default")], stderr=True)
                    ansithemeprint(justification, stderr=True)
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
                    ansithemeprint([ANSIThemeStr("  ", "default"),
                                    ANSIThemeStr("Note", "note"),
                                    ANSIThemeStr(":", "default")])
                    ansithemeprint([ANSIThemeStr("    The permissions for the "
                                                 f"{pathtype} ", "default"),
                                    ANSIThemeStr(f"{entry}", "path"),
                                    ANSIThemeStr(" are ", "default"),
                                    ANSIThemeStr(f"{path_permissions:03o}", "emphasis"),
                                    ANSIThemeStr("; this file is not an executable and should "
                                                 "not have the executable bit set", "default")])
        else:
            if not optional:
                ansithemeprint([ANSIThemeStr("  ", "default"),
                                ANSIThemeStr("Warning", "warning"),
                                ANSIThemeStr(":", "default")], stderr=True)
                ansithemeprint([ANSIThemeStr(f"    The {pathtype} ", "default"),
                                ANSIThemeStr(f"{path}", "path"),
                                ANSIThemeStr(" does not exist; skipping.\n",
                                             "default")], stderr=True)
                warning += 1
                issue = True
            continue

    return abort, issue, critical, error, warning, note


# pylint: disable-next=too-many-arguments,unused-argument
def check_file_permissions(**kwargs: Any) -> tuple[bool, int, int, int, int]:
    """
    This checks whether any files or directories have insecure permissions

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                user (str): Username of the executing user
                usergroup (str): The usergroup of the user
                cluster_name (str): The name of the cluster
                kubeconfig (dict)): The kubeconfig file
                cmtconfig_dict (dict): The cmtconfig file
                critical (int): The current count of critical severity security issues
                error (int): The current count of error severity security issues
                warning (int): The current count of warning severity security issues
                note (int): The current count of note severity security issues
        Returns:
            (bool, int, int, int, int):
                (bool): Is this error severe enough that we should abort immediately?
                (int): The new count of critical severity security issues
                (int): The new count of error severity security issues
                (int): The new count of warning severity security issues
                (int): The new count of note severity security issues
    """
    user: str = deep_get(kwargs, DictPath("user"), "")
    usergroup = deep_get(kwargs, DictPath("usergroup"), "")
    critical: int = deep_get(kwargs, DictPath("critical"), 0)
    error: int = deep_get(kwargs, DictPath("error"), 0)
    warning: int = deep_get(kwargs, DictPath("warning"), 0)
    note: int = deep_get(kwargs, DictPath("note"), 0)

    abort = False

    ansithemeprint([ANSIThemeStr("[Checking directory and file permissions]", "phase")])

    abort, issue, critical, error, warning, note = \
        __check_permissions(recommended_directory_permissions, "directory",
                            user=user, usergroup=usergroup,
                            critical=critical, error=error, warning=warning, note=note)
    abort, issue, critical, error, warning, note = \
        __check_permissions(recommended_file_permissions, "file",
                            user=user, usergroup=usergroup,
                            critical=critical, error=error, warning=warning, note=note)

    if not issue:
        ansithemeprint([ANSIThemeStr("  OK\n", "emphasis")])

    return abort, critical, error, warning, note


# pylint: disable-next=unused-argument
def run_playbook(playbookpath: FilePath, hosts: list[str], **kwargs: Any) -> tuple[int, dict]:
    """
    Run a playbook

        Parameters:
            playbookpath (FilePath): A path to the playbook to run
            hosts (list[str]): A list of hosts to run the playbook on
            **kwargs (dict[str, Any]): Keyword arguments
                extra_values (dict): A dict of values to set before running the playbook
        Returns:
            (int, dict):
                (int): The return value from ansible_run_playbook_on_selection()
                (dict): A dict with the results from the run
    """
    extra_values = deep_get(kwargs, DictPath("extra_values"))

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
    if http_proxy or https_proxy:
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
    merged_values = {**values, **extra_values}

    retval, ansible_results = ansible_run_playbook_on_selection(playbookpath, selection=hosts,
                                                                values=merged_values, quiet=False)

    ansible_print_play_results(retval, ansible_results)

    return retval, ansible_results


# pylint: disable-next=too-many-locals
def check_control_plane(**kwargs: Any) -> tuple[bool, int, int, int, int]:
    """
    This checks whether a host is suitable to be used as a control plane

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                critical (int): The current count of critical severity security issues
                error (int): The current count of error severity security issues
                warning (int): The current count of warning severity security issues
                note (int): The current count of note severity security issues
        Returns:
            (bool, int, int, int, int):
                (bool): Is this error severe enough that we should abort immediately?
                critical (int): The new count of critical severity security issues
                error (int): The new count of error severity security issues
                warning (int): The new count of warning severity security issues
                note (int): The new count of note severity security issues
    """
    critical: int = deep_get(kwargs, DictPath("critical"), 0)
    error: int = deep_get(kwargs, DictPath("error"), 0)
    warning: int = deep_get(kwargs, DictPath("warning"), 0)
    note: int = deep_get(kwargs, DictPath("note"), 0)

    abort = False

    # The host(s) to check
    hosts = deep_get(kwargs, DictPath("hosts"), [])
    playbookpath = get_playbook_path(FilePath("preflight_check.yaml"))

    ansithemeprint([ANSIThemeStr("[Checking whether ", "phase")]
                   + ansithemestr_join_list(hosts, formatting="hostname")
                   + [ANSIThemeStr(" are suitable as control plane(s)]", "phase")])

    extra_values = {
        "ansible_become_pass": deep_get(ansible_configuration, DictPath("ansible_password")),
        "ansible_ssh_pass": deep_get(ansible_configuration, DictPath("ansible_password")),
        "role": "control-plane",
    }

    _retval, ansible_results = run_playbook(playbookpath, hosts=hosts, extra_values=extra_values)

    for host, host_results in ansible_results.items():
        ansible_os_family = ""
        for taskdata in host_results:
            taskname = str(deep_get(taskdata, DictPath("task"), ""))

            if taskname == "Gathering Facts":
                ansible_os_family = deep_get(taskdata,
                                             DictPath("ansible_facts#ansible_os_family"), "")
                continue

            if taskname == "Checking whether the host runs an OS supported for control planes":
                if deep_get(taskdata, DictPath("retval")) != 0:
                    abort = True
                    critical += 1
                    ansithemeprint([ANSIThemeStr("  ", "default"),
                                    ANSIThemeStr("Critical", "critical"),
                                    ANSIThemeStr(":", "default")], stderr=True)
                    ansithemeprint([ANSIThemeStr("    Unsupported Operating System ",
                                                 "default"),
                                    ANSIThemeStr(f"{ansible_os_family}", "programname"),
                                    ANSIThemeStr("; currently the only supported OS families",
                                                 "default")], stderr=True)
                    ansithemeprint([ANSIThemeStr("    for control planes are ", "default"),
                                    ANSIThemeStr("Debian", "programname"),
                                    ANSIThemeStr(" and ", "default"),
                                    ANSIThemeStr("Red Hat", "programname"),
                                    ANSIThemeStr("; aborting.\n", "default")], stderr=True)
                    break

            if taskname == "Check whether the host is a Kubernetes control plane":
                if deep_get(taskdata, DictPath("retval")) != 0:
                    abort = True
                    critical += 1
                    ansithemeprint([ANSIThemeStr("  ", "default"),
                                    ANSIThemeStr("Critical", "critical"),
                                    ANSIThemeStr(":", "default")])
                    ansithemeprint([ANSIThemeStr("    Host ", "default"),
                                    ANSIThemeStr(f"{host}", "hostname"),
                                    ANSIThemeStr(" seems to already be running a Kubernetes "
                                                 "API-server; aborting.\n",
                                                 "default")], stderr=True)
                    break

            if taskname == "Check whether the host is a Kubernetes node":
                if deep_get(taskdata, DictPath("retval")) != 0:
                    abort = True
                    critical += 1
                    ansithemeprint([ANSIThemeStr("  ", "default"),
                                    ANSIThemeStr("Critical", "critical"),
                                    ANSIThemeStr(":", "default")], stderr=True)
                    ansithemeprint([ANSIThemeStr("    Host ", "default"),
                                    ANSIThemeStr(f"{host}", "hostname"),
                                    ANSIThemeStr(" seems to already have a running kubelet; "
                                                 "aborting.\n", "default")], stderr=True)
                    break
    if not abort:
        print()

    return abort, critical, error, warning, note
