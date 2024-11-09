#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
This file contains helpers that provide an obj for use in info views,
for cases where the obj provided from the list view is not sufficient
"""

from pathlib import Path, PurePath
import sys
from typing import Callable, Dict, List

try:
    from natsort import natsorted
except ModuleNotFoundError:  # pragma: no cover
    sys.exit("ModuleNotFoundError: Could not import natsort; "
             "you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

from clustermanagementtoolkit.cmttypes import deep_get, DictPath, FilePath, FilePathAuditError
from clustermanagementtoolkit.cmttypes import SecurityChecks, SecurityStatus

from clustermanagementtoolkit.ansible_helper import ansible_run_playbook_on_selection
from clustermanagementtoolkit.ansible_helper import get_playbook_path

from clustermanagementtoolkit.cmtio import check_path, join_securitystatus_set

from clustermanagementtoolkit.cmtio_yaml import secure_read_yaml


def objgetter_ansible_facts(obj: Dict) -> Dict:
    """
    Get an obj by using ansible facts

        Parameters:
            obj (dict): The obj to use as reference
        Returns:
            (dict): An ansible facts object
    """
    hostname = deep_get(obj, DictPath("name"), "")
    get_facts_path = get_playbook_path(FilePath("get_facts.yaml"))
    retval, ansible_results = ansible_run_playbook_on_selection(get_facts_path, [hostname])
    if retval != 0:
        return {}

    ar = {}

    for result in deep_get(ansible_results, DictPath(hostname), []):
        if deep_get(result, DictPath("task"), "") == "Gathering host facts":
            ar = deep_get(result, DictPath("ansible_facts"))
            break
    return ar


def objgetter_journalctl_log(obj: List[Dict]) -> Dict:
    """
    Format a journalctl log message

        Parameters:
            obj ([dict]): The obj to get data from
        Returns:
            (dict): A journalctl facts object
    """
    data = {
        # This should only be logs from one host, so we can get the hostname
        "name": deep_get(obj[0], DictPath("name")),
        "host": deep_get(obj[0], DictPath("host")),
        "created_at": deep_get(obj[0], DictPath("created_at")),
        "obj": obj,
    }
    return data


def objgetter_ansible_log(obj: FilePath) -> Dict:
    """
    Get an obj from an ansible log entry

        Parameters:
            obj (FilePath): The obj to use as reference
        Returns:
            (dict): An ansible log entry
    """
    tmpobj: Dict = secure_read_yaml(obj.joinpath("metadata.yaml"))
    tmpobj["log_path"] = str(obj)

    # The playbook directory itself may be a symlink.
    # This is expected behaviour when installing from a git repo,
    # but we only allow it if the rest of the path components are secure
    checks = [
        SecurityChecks.PARENT_RESOLVES_TO_SELF,
        SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
        SecurityChecks.OWNER_IN_ALLOWLIST,
        SecurityChecks.PARENT_PERMISSIONS,
        SecurityChecks.PERMISSIONS,
        SecurityChecks.EXISTS,
        SecurityChecks.IS_DIR,
    ]

    playbook_path = FilePath(tmpobj["playbook_path"])
    playbook_dir = FilePath(PurePath(playbook_path).parent)

    violations = check_path(playbook_dir, checks=checks)
    if violations != [SecurityStatus.OK]:
        violations_joined = join_securitystatus_set(",", set(violations))
        raise FilePathAuditError(f"Violated rules: {violations_joined}", path=playbook_dir)

    # We do not want to check that parent resolves to itself,
    # because when we have an installation with links directly to the git repo
    # the playbooks directory will be a symlink
    checks = [
        SecurityChecks.RESOLVES_TO_SELF,
        SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
        SecurityChecks.OWNER_IN_ALLOWLIST,
        SecurityChecks.PARENT_PERMISSIONS,
        SecurityChecks.PERMISSIONS,
        SecurityChecks.IS_FILE,
    ]
    try:
        playbook = secure_read_yaml(playbook_path, checks=checks)
        tmpobj["name"] = deep_get(playbook, DictPath("vars#metadata#description"))
        tmpobj["playbook_types"] = deep_get(playbook,
                                            DictPath("vars#metadata#playbook_types"), ["<any>"])
        tmpobj["category"] = deep_get(playbook,
                                      DictPath("vars#metadata#category"), "Uncategorized")
    except FileNotFoundError:
        tmpobj["name"] = "File not found"
        tmpobj["playbook_types"] = ["Unavailable"]
        tmpobj["category"] = "Unavailable"

    logs = []
    for path in natsorted(Path(str(obj)).iterdir()):
        if (filename := PurePath(str(path)).name) == "metadata.yaml":
            continue
        log = secure_read_yaml(FilePath(str(path)))
        logs.append({
            "index": filename.split("-", maxsplit=1)[0],
            "log": log
        })
    tmpobj["logs"] = logs

    return tmpobj


# Objgetters acceptable for direct use in view files
objgetter_allowlist: Dict[str, Callable] = {
    "objgetter_ansible_facts": objgetter_ansible_facts,
    "objgetter_ansible_log": objgetter_ansible_log,
    "objgetter_journalctl_log": objgetter_journalctl_log,
}
