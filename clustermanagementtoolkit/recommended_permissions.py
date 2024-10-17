#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
List of recommended permissions for files and directories;
used when auditing the local system.
"""

import os
from typing import Dict, List

from clustermanagementtoolkit.cmttypes import FilePath

from clustermanagementtoolkit.cmtpaths import BINDIR, CMTDIR, CMT_LOGS_DIR
from clustermanagementtoolkit.cmtpaths import ANSIBLE_DIR, ANSIBLE_INVENTORY, ANSIBLE_LOG_DIR
from clustermanagementtoolkit.cmtpaths import ANSIBLE_PLAYBOOK_DIR
from clustermanagementtoolkit.cmtpaths import DEPLOYMENT_DIR, CMT_CONFIG_FILE_DIR, CMT_HOOKS_DIR
from clustermanagementtoolkit.cmtpaths import KUBE_CONFIG_DIR, PARSER_DIR, THEME_DIR, VIEW_DIR
from clustermanagementtoolkit.cmtpaths import CMT_CONFIG_FILE, KUBE_CONFIG_FILE
from clustermanagementtoolkit.cmtpaths import KUBE_CREDENTIALS_FILE


# TODO:
# Check file permissions:
# .ssh should be 700
# .ssh/authorized_keys should be 644, 640, or 600
# .ssh/known_hosts should be 600
# .ssh/config should be 644, 640, or 600
# .ssh/id_*.pub should be 644, 640, or 600
# .ssh/id_* should be 600

recommended_directory_permissions: List[Dict] = [
    {
        "path": BINDIR,
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "severity": "critical",
        "justification": [
            ("If other users can create or overwrite files in ", "default"),
            (f"{BINDIR}", "path"),
            (" they can obtain elevated privileges", "default")]
    },
    {
        "path": CMTDIR,
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "severity": "critical",
        "justification": [
            ("    If other users can create or replace files in ", "default"),
            (f"{CMTDIR}", "path"),
            (" they may be able to obtain elevated privileges", "default")]
    },
    {
        "path": CMT_LOGS_DIR,
        "alertmask": 0o077,
        "usergroup_alertmask": 0o027,
        "severity": "error",
        "justification": [
            ("    If other users can read, create or replace files in ", "default"),
            (f"{CMT_LOGS_DIR}\n", "path"),
            ("    they can cause ", "default"),
            ("cmu", "programname"),
            (" to malfunction and possibly hide signs\n", "default"),
            ("    of a compromised cluster and may be able to "
             "obtain sensitive information\n", "default"),
            ("    from audit messages.", "default")]
    },
    {
        "path": CMT_CONFIG_FILE_DIR,
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "severity": "critical",
        "justification": [
            ("If other users can create or replace files in ", "default"),
            (f"{CMT_CONFIG_FILE_DIR}", "path"),
            (" they may be able to obtain elevated privileges", "default")]
    },
    {
        "path": ANSIBLE_DIR,
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "severity": "critical",
        "justification": [
            ("If other users can create or replace files in ", "default"),
            (f"{ANSIBLE_DIR}", "path"),
            (" they can obtain elevated privileges", "default")]
    },
    {
        "path": CMT_HOOKS_DIR,
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "severity": "critical",
        "justification": [
            ("If other users can create or replace files in ", "default"),
            (f"{CMT_HOOKS_DIR}", "path"),
            (" they can obtain elevated privileges", "default")]
    },
    {
        "path": FilePath(os.path.join(CMT_HOOKS_DIR, "pre-upgrade.d")),
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "severity": "critical",
        "justification": [
            ("If other users can create or replace files in ", "default"),
            (f"{os.path.join(CMT_HOOKS_DIR, 'pre-upgrade.d')}", "path"),
            (" they can obtain elevated privileges", "default")]
    },
    {
        "path": FilePath(os.path.join(CMT_HOOKS_DIR, "post-upgrade.d")),
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "severity": "critical",
        "justification": [
            ("If other users can create or replace files in ", "default"),
            (f"{os.path.join(CMT_HOOKS_DIR, 'post-upgrade.d')}", "path"),
            (" they can obtain elevated privileges", "default")]
    },
    {
        "path": DEPLOYMENT_DIR,
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "severity": "critical",
        "justification": [
            ("If other users can create or replace files in ", "default"),
            (f"{DEPLOYMENT_DIR}", "path"),
            (" they can obtain elevated privileges", "default")]
    },
    {
        "path": ANSIBLE_LOG_DIR,
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "severity": "warning",
        "justification": [
            ("If others users can create or replace files in ", "default"),
            (f"{ANSIBLE_LOG_DIR}", "path"),
            (" they can spoof results from playbook runs", "default")]
    },
    {
        "path": KUBE_CONFIG_DIR,
        "alertmask": 0o077,
        "usergroup_alertmask": 0o027,
        "severity": "critical",
        "justification": [
            ("If others users can read, create or replace files in ", "default"),
            (f"{KUBE_CONFIG_DIR}", "path"),
            (" they can obtain cluster access", "default")]
    },
    {
        "path": THEME_DIR,
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "severity": "error",
        "justification": [
            ("If others users can create or replace files in ", "default"),
            (f"{THEME_DIR}", "path"),
            (" they can cause ", "default"),
            ("cmu", "programname"),
            (" to malfunction", "default")]
    },
    {
        "path": PARSER_DIR,
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "severity": "error",
        "justification": [
            ("If others users can create or replace files in ", "default"),
            (f"{PARSER_DIR}", "path"),
            (" they can cause ", "default"),
            ("cmu", "programname"),
            (" to malfunction and possibly hide signs "
             "of a compromised cluster", "default")]
    },
    {
        "path": VIEW_DIR,
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "severity": "error",
        "justification": [
            ("If others users can create or replace files in ", "default"),
            (f"{VIEW_DIR}", "path"),
            (" they can cause ", "default"),
            ("cmu", "programname"),
            (" to malfunction and possibly hide signs of a "
             "compromised cluster", "default")]
    },
]

recommended_file_permissions: List[Dict] = [
    {
        "path": FilePath(os.path.join(BINDIR, "cmtadm")),
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "executable": True,
        "severity": "critical",
        "justification": [
            ("If others users can modify executables they can obtain "
             "elevated privileges", "default")]
    },
    {
        "path": FilePath(os.path.join(BINDIR, "cmtinv")),
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "executable": True,
        "severity": "critical",
        "justification": [
            ("If others users can modify executables they can obtain "
             "elevated privileges", "default")]
    },
    {
        "path": FilePath(os.path.join(BINDIR, "cmt")),
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "executable": True,
        "severity": "critical",
        "justification": [
            ("If others users can modify executables they can obtain "
             "elevated privileges", "default")]
    },
    {
        "path": FilePath(os.path.join(BINDIR, "cmu")),
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "executable": True,
        "severity": "critical",
        "justification": [
            ("If others users can modify configlets they may be able "
             "to obtain elevated privileges", "default")]
    },
    {
        "path": CMT_CONFIG_FILE,
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "executable": False,
        "severity": "critical",
        "justification": [
            ("If others users can modify the CMT configuration file they may be "
             "able to obtain elevated privileges", "default")]
    },
    {
        "path": CMT_CONFIG_FILE_DIR,
        "suffixes": (".yml", ".yaml"),
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "executable": False,
        "severity": "critical",
        "justification": [
            ("If others users can modify configlets they may be "
             "able to obtain elevated privileges", "default")]
    },
    {
        "path": ANSIBLE_PLAYBOOK_DIR,
        "suffixes": (".yml", ".yaml"),
        "alertmask": 0o022,
        "usergroup_alertmask": 0o002,
        "executable": False,
        "severity": "critical",
        "justification": [
            ("If other users can modify playbooks they can obtain "
             "elevated privileges", "default")]
    },
    {
        "path": ANSIBLE_INVENTORY,
        "alertmask": 0o077,
        "usergroup_alertmask": 0o007,
        "severity": "critical",
        "justification": [
            ("If other users can read or modify the Ansible inventory "
             "they can obtain elevated privileges", "default")]
    },
    {
        "path": KUBE_CONFIG_FILE,
        "alertmask": 0o077,
        "usergroup_alertmask": 0o077,
        "executable": False,
        "severity": "critical",
        "justification": [
            ("If others users can read or modify cluster configuration files "
             "they can obtain cluster access", "default")]
    },
    {
        "path": KUBE_CREDENTIALS_FILE,
        "alertmask": 0o077,
        "usergroup_alertmask": 0o077,
        "executable": False,
        "severity": "critical",
        "justification": [
            ("If others users can read or modify cluster credential "
             "files they can obtain cluster access", "default")],
        # This is not a required file, so don't warn if it doesn't exist
        "optional": True,
    },
]
