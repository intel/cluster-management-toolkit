#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.8)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Ansible-related helpers
"""

# pylint: disable=too-many-lines

from datetime import datetime
import errno
import os
from pathlib import Path, PurePath
import re
import sys
from typing import Any, cast, Dict, List, Optional, Tuple, Union
try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    # This is acceptable; we don't benefit from a backtrace or log message
    sys.exit("ModuleNotFoundError: Could not import yaml; "
             "you may need to (re-)run `cmt-install` or `pip3 install PyYAML`; aborting.")

import cmtlib
from cmtio import check_path, join_securitystatus_set, secure_mkdir, secure_rm, secure_rmdir
from cmtio_yaml import secure_read_yaml, secure_write_yaml
from cmtpaths import HOMEDIR
from cmtpaths import ANSIBLE_DIR, ANSIBLE_PLAYBOOK_DIR, ANSIBLE_LOG_DIR
from cmtpaths import ANSIBLE_INVENTORY
from ansithemeprint import ANSIThemeString, ansithemeprint
from cmttypes import deep_get, deep_set, DictPath, FilePath, FilePathAuditError
from cmttypes import SecurityChecks, SecurityStatus, validate_args

ansible_configuration: Dict = {
    "ansible_forks": 10,
    "ansible_password": None,
    "ansible_user": None,
    "disable_strict_host_key_checking": False,
    "save_logs": False,
}

# Used by Ansible
try:
    import ansible_runner  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    # This is acceptable; we don't benefit from a backtrace or log message
    sys.exit("ModuleNotFoundError: Could not import ansible_runner; "
             "you may need to (re-)run `cmt-install` or `pip3 install ansible-runner`; aborting.")

# Exit if the ansible directory does not exist
if not Path(ANSIBLE_DIR).exists():  # pragma: no cover
    # This is acceptable; we don't benefit from a backtrace or log message
    sys.exit(f"{ANSIBLE_DIR} not found; try (re-)running cmt-install")

# Exit if the ansible log directory does not exist
if not Path(ANSIBLE_LOG_DIR).exists():  # pragma: no cover
    # This is acceptable; we don't benefit from a backtrace or log message
    sys.exit(f"{ANSIBLE_LOG_DIR} not found; try (re-)running cmt-install")


def get_playbook_path(playbook: FilePath) -> FilePath:
    """
    Pass in the name of a playbook that exists in {ANSIBLE_PLAYBOOK_DIR};
    returns the path to the drop-in playbook with the highest priority
    (or the same playbook in case there is no override)

        Parameters:
            playbook (str): The name of the playbook to get the path to
        Returns:
            (FilePath): The playbook path with the highest priority
    """
    path = ""

    if not isinstance(playbook, str):
        raise TypeError(f"playbook is type: {type(playbook)}, expected str")
    if not playbook:
        raise ValueError("len(playbook) == 0; expected a filename")

    # Check if there's a local playbook overriding this one
    local_playbooks = deep_get(cmtlib.cmtconfig, DictPath("Ansible#local_playbooks"), [])
    for playbook_path in local_playbooks:
        # Substitute {HOME}/ for {HOMEDIR}
        if playbook_path.startswith("{HOME}/"):
            playbook_path = f"{HOMEDIR}/{playbook_path[len('{HOME}/'):]}"
        playbook_path_entry = Path(playbook_path)
        # Skip non-existing playbook paths
        if not playbook_path_entry.is_dir():
            continue
        # We can have multiple directories with local playbooks;
        # the first match wins
        if Path(f"{playbook_path}/{playbook}").is_file():
            path = f"{playbook_path}/{playbook}"
            break
    if not path:
        path = f"{ANSIBLE_PLAYBOOK_DIR}/{playbook}"
    return FilePath(path)


# Add all playbooks in the array
def populate_playbooks_from_paths(paths: List[FilePath]) -> List[Tuple[List[ANSIThemeString],
                                                                       FilePath]]:
    """
    Populate a playbook list

        Parameters:
            paths ([FilePath]): A list of paths to playbooks
        Returns:
            [([ANSIThemeString], FilePath)]:
                ([ANSIThemeString]): An ansithemearray with the namer of the playbook
                (FilePath): The path to the playbook
    """
    playbooks = []

    yaml_regex = re.compile(r"^(.*)\.ya?ml$")

    for playbookpath in paths:
        pathname = PurePath(playbookpath).name
        playbook_dir = FilePath(str(PurePath(playbookpath).parent))

        # Do not process backups, etc.
        if pathname.startswith(("~", ".")):
            continue

        # Only process playbooks
        if (tmp := yaml_regex.match(pathname)) is None:
            raise ValueError(f"The playbook filename “{pathname}“ does not end with "
                             ".yaml or .yml; this is most likely a programming error.")

        playbookname = tmp[1]

        # The playbook directory itself may be a symlink.
        # This is expected behaviour when installing from a git repo,
        # but we only allow it if the rest of the path components are secure.
        checks = [
            SecurityChecks.PARENT_RESOLVES_TO_SELF,
            SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
            SecurityChecks.OWNER_IN_ALLOWLIST,
            SecurityChecks.PARENT_PERMISSIONS,
            SecurityChecks.PERMISSIONS,
            SecurityChecks.EXISTS,
            SecurityChecks.IS_DIR,
        ]

        if (violations := check_path(playbook_dir, checks=checks)) != [SecurityStatus.OK]:
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
            SecurityChecks.EXISTS,
            SecurityChecks.IS_FILE,
        ]

        d = secure_read_yaml(playbookpath, checks=checks)
        description = None
        if (t_description := deep_get(d[0], DictPath("vars#metadata#description"), "")):
            description = [ANSIThemeString(t_description, "play")]

        if description is None or not description:
            description = [ANSIThemeString("Running “", "play"),
                           ANSIThemeString(playbookname, "programname"),
                           ANSIThemeString("“", "play")]

        # If there's no description we fallback to just using the filename
        playbooks.append(([ANSIThemeString("  • ", "separator")] + description, playbookpath))
    return playbooks


# pylint: disable-next=unused-argument
def ansible_print_action_summary(playbooks: List[Tuple[List[ANSIThemeString], FilePath]]) -> None:
    """
    Given a list of playbook paths, print a summary of the actions that will be performed

        Parameters:
            playbook (str): The name of the playbook to print a summary for
    """
    if not isinstance(playbooks, list):
        raise TypeError(f"playbooks is type: {type(playbooks)}, expected: {list}")

    if not playbooks:
        raise ValueError("playbooks is empty")

    if not (isinstance(playbooks[0], tuple) and len(playbooks[0]) == 2
            and isinstance(playbooks[0][0], list) and isinstance(playbooks[0][1], str)):
        raise TypeError("playbooks[] is wrong type; "
                        f"expected: [([{ANSIThemeString}], {FilePath})]")

    # We do not want to check that parent resolves to itself,
    # because when we have an installation with links directly to the git repo
    # the playbooks directory will be a symlink
    checks = [
        SecurityChecks.RESOLVES_TO_SELF,
        SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
        SecurityChecks.OWNER_IN_ALLOWLIST,
        SecurityChecks.PARENT_PERMISSIONS,
        SecurityChecks.PERMISSIONS,
        SecurityChecks.EXISTS,
        SecurityChecks.IS_FILE,
    ]

    ansithemeprint([ANSIThemeString("\n• ", "separator"),
                    ANSIThemeString("Playbooks to be executed:", "action")])
    for playbook in playbooks:
        playbook_string, playbook_path = playbook
        playbook_data = secure_read_yaml(FilePath(playbook_path), checks=checks)

        ansithemeprint(playbook_string + [ANSIThemeString(" (path: ", "default"),
                                          ANSIThemeString(f"{playbook_path}", "path"),
                                          ANSIThemeString(")", "default")])
        # None of our playbooks have more than one play per file
        summary = deep_get(playbook_data[0], DictPath("vars#metadata#summary"), {})
        if not summary:
            ansithemeprint([ANSIThemeString("      Error", "error"),
                            ANSIThemeString(": playbook lacks a summary; "
                                            "please file a bug report unless it's a "
                                            "locally modified playbook!", "default")],
                           stderr=True)
        for section_description, section_data in summary.items():
            ansithemeprint([ANSIThemeString(f"      {section_description}:", "emphasis")])
            for section_item in section_data:
                description = deep_get(section_item, DictPath("description"), "")
                ansithemeprint([ANSIThemeString(f"        {description}", "default")])


def ansible_get_inventory_dict() -> Dict:
    """
        Get the Ansible inventory and return it as a dict

        Returns:
            (dict): A dictionary with an Ansible inventory
    """
    if not Path(ANSIBLE_INVENTORY).is_file():
        return {
            "all": {
                "hosts": {},
                "vars": {},
            }}

    d = secure_read_yaml(ANSIBLE_INVENTORY)
    if d.get("all") is None:
        d["all"] = {
            "hosts": {},
            "vars": {}
        }
    else:
        if d["all"].get("hosts") is None:
            d["all"]["hosts"] = {}
        if d["all"].get("vars") is None:
            d["all"]["vars"] = {}

    return d


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def ansible_get_inventory_pretty(**kwargs: Any) -> List[Union[List[ANSIThemeString], str]]:
    """
        Get the Ansible inventory and return it neatly formatted

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                groups ([str]): What groups to include
                highlight (bool): Apply syntax highlighting?
                include_groupvars (bool): Should group variables be included
                include_hostvars (bool): Should host variables be included
                include_hosts (bool): Should hosts be included
        Returns:
            ([str|[ANSIThemeString]]): An unformatted list of strings
                                       or a formatted list of themearrays
    """
    groups: List[str] = deep_get(kwargs, DictPath("groups"), [])
    highlight: bool = deep_get(kwargs, DictPath("highlight"), False)
    include_groupvars: bool = deep_get(kwargs, DictPath("include_groupvars"), False)
    include_hostvars: bool = deep_get(kwargs, DictPath("include_hostvars"), False)
    include_hosts: bool = deep_get(kwargs, DictPath("include_hosts"), True)

    tmp = {}

    if not Path(ANSIBLE_INVENTORY).is_file():
        return []

    d = secure_read_yaml(ANSIBLE_INVENTORY)

    # We want the entire inventory
    if not groups:
        tmp = d
    else:
        if not (isinstance(groups, list) and groups and isinstance(groups[0], str)):
            raise TypeError(f"groups is type: {type(groups)}, expected {list}")
        for group in groups:
            item = d.pop(group, None)
            if item is not None:
                tmp[group] = item

    # OK, now we have a dict with only the groups we are interested in;
    # time for further post-processing.

    # do we want groupvars?
    if not include_groupvars:
        for group in tmp:
            tmp[group].pop("vars", None)
    else:
        for group in tmp:
            if tmp[group].get("vars") is None or not tmp[group].get("vars"):
                tmp[group].pop("vars", None)

    # Do we want hosts?
    if not include_hosts:
        for group in tmp:
            tmp[group].pop("hosts", None)
    else:
        for group in tmp:
            if not deep_get(tmp, DictPath(f"{group}#hosts"), {}):
                tmp[group].pop("hosts", None)

        # OK, but do we want hostvars?
        if not include_hostvars:
            for group in tmp:
                for host in deep_get(tmp, DictPath(f"{group}#hosts"), {}):
                    deep_set(tmp, DictPath(f"{group}#hosts#{host}"), None)

    tmp_dump = yaml.safe_dump(tmp, default_flow_style=False)
    tmp_dump = tmp_dump.replace(r"''", "").replace("null", "").replace("{}", "")
    dump: List[Union[List[ANSIThemeString], str]] = []
    cast(List[Union[List[ANSIThemeString], str]], tmp_dump.splitlines())

    if highlight and tmp_dump:
        i = 0
        list_regex = re.compile(r"^(\s*)((- )+)(.*)")
        key_value_regex = re.compile(r"^(.*?)(:)(.*)")
        for i, data in enumerate(tmp_dump.splitlines()):
            # Is it a list?
            tmp2 = list_regex.match(cast(str, data))
            if tmp2 is not None:
                indent = tmp2[1]
                listmarker = tmp2[2]
                item = tmp2[4]
                dump.append([ANSIThemeString(indent, "default"),
                             ANSIThemeString(listmarker, "yaml_list"),
                             ANSIThemeString(item, "yaml_value")])
                continue

            # Is it key: value?
            tmp2 = key_value_regex.match(cast(str, data))
            if tmp2 is not None:
                key = tmp2[1]
                separator = tmp2[2]
                value = tmp2[3]
                dump.append([ANSIThemeString(key, "yaml_key"),
                             ANSIThemeString(separator, "yaml_key_separator"),
                             ANSIThemeString(value, "yaml_value")])
                continue

            # Nope, then we will use default format
            dump.append([ANSIThemeString(cast(str, tmp_dump[i]), "default")])
    else:
        dump = list(tmp_dump.splitlines())

    return dump


def ansible_get_hosts_by_group(inventory: FilePath, group: str) -> List[str]:
    """
    Get the list of hosts belonging to a group

        Parameters:
            inventory (FilePath): The inventory to use
            group (str): The group to return hosts for
        Returns:
            ([str]): A list of hosts
    """
    hosts = []

    if not Path(inventory).exists():
        return []

    d = secure_read_yaml(inventory)

    if d.get(group) is not None and d[group].get("hosts") is not None:
        for host in d[group]["hosts"]:
            hosts.append(host)

    return hosts


def ansible_get_groups(inventory: FilePath) -> List[str]:
    """
    Get the list of groups in the inventory

        Parameters:
            inventory (FilePath): The inventory to use
        Returns:
            ([str]): A list of groups
    """
    if not Path(inventory).exists():
        return []

    d = secure_read_yaml(inventory)
    return list(d.keys())


def ansible_get_groups_by_host(inventory_dict: Dict, host: str) -> List[str]:
    """
    Given an inventory, returns the groups a host belongs to

        Parameters:
            inventory_dict (dict): An Ansible inventory
            host (str): The host to return groups for
        Returns:
            ([str]): The list of groups the host belongs to
        Raises:
            ArgumentValidationError: At least one of the arguments failed validation
    """
    validate_args(kwargs_spec={"__allof": ("inventory_dict", "host"),
                               "inventory_dict": {"types": (dict,)},
                               "host": {"types": (str,), "range": (1, None)}},
                  kwargs={"inventory_dict": inventory_dict, "host": host})

    groups = []

    for group in inventory_dict:
        if host in deep_get(inventory_dict, DictPath(f"{group}#hosts")):
            groups.append(group)

    return groups


def __ansible_create_inventory(inventory: FilePath, **kwargs: Any) -> bool:
    """
    Create a new inventory at the path given if no inventory exists

        Parameters:
            inventory (FilePath): A path where to create a new inventory (if non-existing)
            **kwargs (dict[str, Any]): Keyword arguments
                overwrite (bool): True: Overwrite the existing inventory?
                temporary (bool): Is the inventory a tempfile?
        Return:
            (bool): True if inventory was created, False if nothing was done
    """
    overwrite: bool = deep_get(kwargs, DictPath("overwrite"), False)
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    if not isinstance(inventory, str):
        raise TypeError(f"inventory is type: {type(inventory)}, expected str")
    if not isinstance(overwrite, bool):
        raise TypeError(f"inventory is type: {type(overwrite)}, expected bool")

    # Do not create anything if the inventory exists;
    # unless overwrite is set
    if Path(inventory).exists() and not overwrite:
        return False

    # If the ansible directory does not exist, create it
    secure_mkdir(ANSIBLE_DIR, permissions=0o755, exit_on_failure=True)

    # Create the basic yaml structure that we will write later on
    d: Dict = {
        "all": {
            "hosts": {},
            # Workaround for Ubuntu 18.04 and various other older operating systems
            # that have python3 installed, but not as default.
            "vars": {
                "ansible_python_interpreter": "/usr/bin/python3",
            }
        }
    }

    if (ansible_user := deep_get(ansible_configuration, DictPath("ansible_user"))) is not None:
        deep_set(d, DictPath("all#vars#ansible_user"), ansible_user, create_path=True)

    if (ansible_password := deep_get(ansible_configuration,
                                     DictPath("ansible_password"))) is not None:
        deep_set(d, DictPath("all#vars#ansible_ssh_pass"), ansible_password, create_path=True)

    if deep_get(ansible_configuration, DictPath("disable_strict_host_key_checking"), False):
        deep_set(d, DictPath("ansible_ssh_common_args"), "-o StrictHostKeyChecking=no",
                 create_path=True)

    secure_write_yaml(inventory, d, permissions=0o600, replace_empty=True, temporary=temporary)

    return True


def ansible_create_groups(inventory: FilePath, groups: List[str], **kwargs: Any) -> bool:
    """
    Create new groups

        Parameters:
            inventory (FilePath): The path to the inventory
            groups ([str]): The groups to create
            **kwargs (dict[str, Any]): Keyword arguments
                temporary (bool): Is the inventory a tempfile?
        Returns:
            (bool): True on success, False on failure
        Raises:
            TypeError: group is not a str
    """
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    changed: bool = False

    if groups is None or not groups:
        return True

    if not Path(inventory).is_file():
        __ansible_create_inventory(inventory, overwrite=False, temporary=temporary)

    d = secure_read_yaml(inventory, temporary=temporary)

    for group in groups:
        if not isinstance(group, str):
            raise TypeError(f"group is type: {type(group)}; expected str")
        # Group already exists; ignore
        if group in d:
            continue

        d[group] = {
            "hosts": {},
        }

        changed = True

    if changed:
        secure_write_yaml(inventory, d, permissions=0o600,
                          replace_empty=True, replace_null=True, temporary=temporary)

    return True


def ansible_set_vars(inventory: FilePath, group: str, values: Dict, **kwargs: Any) -> bool:
    """
    Set one or several values for a group

        Parameters:
            inventory (FilePath): The path to the inventory
            group (str): The group to set variables for
            values (dict): The values to set
            **kwargs (dict[str, Any]): Keyword arguments
                temporary (bool): Is the inventory a tempfile?
        Returns:
            (bool): True on success, False on failure
        Raises:
            ArgumentValidationError: At least one of the arguments failed validation
    """
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    changed = False

    validate_args(kwargs_spec={"__allof": ("inventory", "group", "values", "temporary"),
                               "inventory": {"types": (str,), "range": (1, None)},
                               "group": {"types": (str,), "range": (1, None)},
                               "values": {"types": (dict,), "range": (1, None)},
                               "temporary": {"types": (bool,)}},
                  kwargs={"inventory": inventory,
                          "group": group,
                          "values": values,
                          "temporary": temporary})

    if not Path(inventory).is_file():
        __ansible_create_inventory(inventory, overwrite=False, temporary=temporary)

    d = secure_read_yaml(inventory, temporary=temporary)

    # If the group does not exist we create it
    if d.get(group) is None:
        d[group] = {}

    if d[group].get("vars") is None:
        d[group]["vars"] = {}

    for key in values:
        if key in d[group]["vars"] and d[group]["vars"].get(key) == values[key]:
            continue

        # Set the variable (overwriting previous value)
        d[group]["vars"][key] = values[key]
        changed = True

    if changed:
        secure_write_yaml(inventory, d, permissions=0o600,
                          replace_empty=True, replace_null=True, temporary=temporary)

    return True


def ansible_set_groupvars(inventory: FilePath,
                          groups: List[str],
                          groupvars: List[Tuple[str, Union[str, int]]], **kwargs: Any) -> bool:
    """
    Set one or several vars for the specified groups

        Parameters:
            inventory (FilePath): The path to the inventory
            groups (list[str]): The groups to set variables for
            groupvars (list[(str, str|int)]): The values to set
            **kwargs (dict[str, Any]): Keyword arguments
                temporary (bool): Is the inventory a tempfile?
        Returns:
            (bool): True on success, False on failure
        Raises:
            ArgumentValidationError: At least one of the arguments failed validation
    """
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    changed = False

    validate_args(kwargs_spec={"__allof": ("inventory", "groups", "groupvars", "temporary"),
                               "inventory": {"types": (str,), "range": (1, None)},
                               "groups": {"types": (list, dict), "range": (1, None)},
                               "groupvars": {"types": (list, dict), "range": (1, None)},
                               "temporary": {"types": (bool,)}},
                  kwargs={"inventory": inventory,
                          "groups": groups,
                          "groupvars": groupvars,
                          "temporary": temporary})

    d = secure_read_yaml(inventory, temporary=temporary)

    for group in groups:
        # Silently ignore non-existing groups
        if group not in d:
            continue

        if d[group] is None:
            d[group] = {}

        if d[group].get("vars") is None:
            d[group]["vars"] = {}

        for key, value in groupvars:
            # Set the variable (overwriting previous value)
            d[group]["vars"][key] = value
            changed = True

    if changed:
        secure_write_yaml(inventory, d, permissions=0o600,
                          replace_empty=True, replace_null=True, temporary=temporary)

    return True


# Set one or several vars for hosts in the group all
def ansible_set_hostvars(inventory: FilePath,
                         hosts: List[str],
                         hostvars: List[Tuple[str, Union[str, int]]], **kwargs: Any) -> bool:
    """
    Set one or several vars for the specified hosts

        Parameters:
            inventory (FilePath): The path to the inventory
            groups (list[str]): The hosts to set variables for
            hostvars (list[(str, str|int)]): The values to set
            **kwargs (dict[str, Any]): Keyword arguments
                temporary (bool): Is the inventory a tempfile?
        Returns:
            (bool): True on success, False on failure
        Raises:
            ArgumentValidationError: At least one of the arguments failed validation
    """
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    changed = False

    validate_args(kwargs_spec={"__allof": ("inventory", "hosts", "hostvars", "temporary"),
                               "inventory": {"types": (str,), "range": (1, None)},
                               "hosts": {"types": (list, dict), "range": (1, None)},
                               "hostvars": {"types": (list, dict), "range": (1, None)},
                               "temporary": {"types": (bool,)}},
                  kwargs={"inventory": inventory,
                          "hosts": hosts,
                          "hostvars": hostvars,
                          "temporary": temporary})

    d = secure_read_yaml(inventory, temporary=temporary)

    for host in hosts:
        # Silently ignore non-existing hosts
        if host not in d["all"]["hosts"]:
            continue

        if d["all"]["hosts"][host] is None:
            d["all"]["hosts"][host] = {}

        for key, value in hostvars:
            # Set the variable (overwriting previous value)
            d["all"]["hosts"][host][key] = value
            changed = True

    if changed:
        secure_write_yaml(inventory, d, permissions=0o600,
                          replace_empty=True, replace_null=True, temporary=temporary)

    return True


# Unset one or several vars in the specified groups
def ansible_unset_groupvars(inventory: FilePath,
                            groups: List[str], groupvars: List[str], **kwargs: Any) -> bool:
    """
    Unset one or several vars for the specified groups

        Parameters:
            inventory (FilePath): The path to the inventory
            groups (list[str]): The groups to unset variables for
            groupvars (list[(str]): The values to unset
            **kwargs (dict[str, Any]): Keyword arguments
                temporary (bool): Is the inventory a tempfile?
        Returns:
            (bool): True on success, False on failure
        Raises:
            ArgumentValidationError: At least one of the arguments failed validation
    """
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    changed = False

    validate_args(kwargs_spec={"__allof": ("inventory", "groups", "groupvars", "temporary"),
                               "inventory": {"types": (str,), "range": (1, None)},
                               "groups": {"types": (list, dict), "range": (1, None)},
                               "groupvars": {"types": (list, dict), "range": (1, None)},
                               "temporary": {"types": (bool,)}},
                  kwargs={"inventory": inventory,
                          "groups": groups,
                          "groupvars": groupvars,
                          "temporary": temporary})

    d = secure_read_yaml(inventory, temporary=temporary)

    for group in groups:
        # Silently ignore non-existing groups
        if group not in d:
            continue

        if d[group] is None:
            continue

        if d[group].get("vars") is None:
            continue

        for key in groupvars:
            # Set the variable (overwriting previous value)
            d[group]["vars"].pop(key, None)
            changed = True

        # If the group no longer has any vars set,
        # remove vars
        if not d[group]["vars"]:
            d[group].pop("vars", None)

    if changed:
        secure_write_yaml(inventory, d, permissions=0o600,
                          replace_empty=True, replace_null=True, temporary=temporary)

    return True


# Unset one or several vars for the specified host in the group all
def ansible_unset_hostvars(inventory: FilePath,
                           hosts: List[str], hostvars: List[str], **kwargs: Any) -> bool:
    """
    Unset one or several vars for the specified hosts

        Parameters:
            inventory (FilePath): The path to the inventory
            groups (list[str]): The hosts to unset variables for
            hostvars (list[(str]): The values to unset
            **kwargs (dict[str, Any]): Keyword arguments
                temporary (bool): Is the inventory a tempfile?
        Returns:
            (bool): True on success, False on failure
        Raises:
            ArgumentValidationError: At least one of the arguments failed validation
    """
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    changed = False

    validate_args(kwargs_spec={"__allof": ("inventory", "hosts", "hostvars", "temporary"),
                               "inventory": {"types": (str,), "range": (1, None)},
                               "hosts": {"types": (list, dict), "range": (1, None)},
                               "hostvars": {"types": (list, dict), "range": (1, None)},
                               "temporary": {"types": (bool,)}},
                  kwargs={"inventory": inventory,
                          "hosts": hosts,
                          "hostvars": hostvars,
                          "temporary": temporary})

    d = secure_read_yaml(inventory, temporary=temporary)

    for host in hosts:
        # Silently ignore non-existing hosts
        if host not in d["all"]["hosts"]:
            continue

        if d["all"]["hosts"][host] is None:
            continue

        for key in hostvars:
            # Set the variable (overwriting previous value)
            d["all"]["hosts"][host].pop(key, None)
            changed = True

        if not d["all"]["hosts"][host]:
            d["all"]["hosts"][host] = None

    if changed:
        secure_write_yaml(inventory, d, permissions=0o600,
                          replace_empty=True, replace_null=True, temporary=temporary)

    return True


# pylint: disable-next=too-many-branches
def ansible_add_hosts(inventory: FilePath, hosts: List[str], **kwargs: Any) -> bool:
    """
    Add hosts to the ansible inventory; if the inventory does not exist, create it

        Parameters:
            inventory (FilePath): The path to the inventory
            hosts (list[str]): The hosts to add to the inventory
            **kwargs (dict[str, Any]): Keyword arguments
                group (str): The group to add the hosts to
                skip_all (bool): If True we do not create a new inventory if it does not exist
                temporary (bool): Is the inventory a tempfile?
        Returns:
            (bool): True on success, False on failure
        Raises:
            ArgumentValidationError: At least one of the arguments failed validation
    """
    group: str = deep_get(kwargs, DictPath("group"), "")
    skip_all: bool = deep_get(kwargs, DictPath("skip_all"), False)
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    changed = False

    validate_args(kwargs_spec={"__allof": ("inventory", "hosts", "group", "skip_all", "temporary"),
                               "inventory": {"types": (str,), "range": (1, None)},
                               "hosts": {"types": (list, tuple,), "range": (1, None)},
                               "group": {"types": (str,), "range": (0, None)},
                               "skip_all": {"types": (bool,)},
                               "temporary": {"types": (bool,)}},
                  kwargs={"inventory": inventory,
                          "hosts": hosts,
                          "group": group,
                          "skip_all": skip_all,
                          "temporary": temporary})

    d: Dict[str, Any] = {}

    # The inventory does not exist; if the user specified skip_all
    # we do not mind, otherwise we need to create it
    if not Path(inventory).is_file():
        if skip_all and group != "all":
            changed = True
        else:
            __ansible_create_inventory(inventory, overwrite=False)
            d = secure_read_yaml(inventory, temporary=temporary)
    else:
        d = secure_read_yaml(inventory, temporary=temporary)

    for host in hosts:
        # Kubernetes doesn't like uppercase hostnames
        host = host.lower()

        # All nodes go into the "hosts" group of the "all" group,
        # no matter if the caller also supplies a group, unless
        # skip_all has been specified; the exception being
        # if the group is all
        #
        # Do not add a host that already exists in all;
        # that will wipe its vars
        if not skip_all and group != "all":
            if d["all"]["hosts"] is None:
                d["all"]["hosts"] = {}
            if host not in cast(List, d["all"]["hosts"]):
                d = cast(Dict, d)
                d["all"]["hosts"][host] = {}
                changed = True

        # If the group does not exist,
        # create it--we currently do not support
        # nested groups, node vars or anything like that
        #
        # We do not want to overwrite groups
        if group not in ("", "all"):
            if d.get(group) is None:
                d[group] = {}
                changed = True

            if d[group].get("hosts") is None:
                changed = True
                d[group]["hosts"] = {}

            if host not in d[group]["hosts"]:
                d[group]["hosts"][host] = {}
                changed = True

    if changed:
        secure_write_yaml(inventory, d, permissions=0o600,
                          replace_empty=True, replace_null=True, temporary=temporary)

    return True


# Remove hosts from ansible groups
def ansible_remove_hosts(inventory: FilePath, hosts: List[str], **kwargs: Any) -> bool:
    """
    Remove hosts from the inventory

        Parameters:
            inventory (FilePath): The inventory to use
            hosts (list[str]): The hosts to remove
            **kwargs (dict[str, Any]): Keyword arguments
                group (str): The group to remove the hosts from
                temporary (bool): Is the inventory a tempfile?
        Returns:
            (bool): True on success, False on failure
        Raises:
            ArgumentValidationError: At least one of the arguments failed validation
    """
    group: str = deep_get(kwargs, DictPath("group"), "")
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    changed = False

    validate_args(kwargs_spec={"__allof": ("inventory", "hosts", "group", "temporary"),
                               "inventory": {"types": (str,), "range": (1, None)},
                               "hosts": {"types": (list, tuple,), "range": (1, None)},
                               "group": {"types": (str,), "range": (0, None)},
                               "temporary": {"types": (bool,)}},
                  kwargs={"inventory": inventory,
                          "hosts": hosts,
                          "group": group,
                          "temporary": temporary})

    d = secure_read_yaml(inventory, temporary=temporary)

    for host in hosts:
        if group in d and d[group].get("hosts") is not None:
            if host in d[group]["hosts"]:
                d[group]["hosts"].pop(host, None)
                changed = True

    if changed:
        secure_write_yaml(inventory, d, permissions=0o600,
                          replace_empty=True, replace_null=True, temporary=temporary)

    return True


def ansible_remove_groups(inventory: FilePath, groups: List[str], **kwargs: Any) -> bool:
    """
    Remove groups from the inventory

        Parameters:
            inventory (FilePath): The inventory to use
            groups (list[str]): The groups to remove
            **kwargs (dict[str, Any]): Keyword arguments
                force (bool): Force allows for removal of non-empty groups
                temporary (bool): Is the inventory a tempfile?
        Returns:
            (bool): True on success, False on failure
        Raises:
            ArgumentValidationError: At least one of the arguments failed validation
    """
    force: bool = deep_get(kwargs, DictPath("force"), False)
    temporary: bool = deep_get(kwargs, DictPath("temporary"), False)

    changed = False

    validate_args(kwargs_spec={"__allof": ("inventory", "groups", "force", "temporary"),
                               "inventory": {"types": (str,), "range": (1, None)},
                               "groups": {"types": (list, tuple,), "range": (1, None)},
                               "force": {"types": (bool,)},
                               "temporary": {"types": (bool,)}},
                  kwargs={"inventory": inventory,
                          "groups": groups,
                          "force": force,
                          "temporary": temporary})

    if not Path(inventory).is_file():
        return False

    d = secure_read_yaml(inventory, temporary=temporary)

    for group in groups:
        if d.get(group) is None:
            continue

        if d[group].get("hosts") is not None and not force:
            continue

        d.pop(group)
        changed = True

    if changed:
        secure_write_yaml(inventory, d, permissions=0o600,
                          replace_empty=True, replace_null=True, temporary=temporary)

    return True


def ansible_get_logs() -> List[Tuple[str, str, FilePath, datetime]]:
    """
    Returns a list of all available logs

        Returns:
            (str, str, FilePath, datetime):
                (str): Full name
                (str): Name
                (FilePath): The path to the log file
                (datetime): The timestamp
    """
    logs = []

    timestamp_regex = re.compile(r"^(\d{4}-\d\d-\d\d_\d\d:\d\d:\d\d\.\d+)_(.*)")

    for path in Path(ANSIBLE_LOG_DIR).iterdir():
        filename = str(path.name)
        tmp = timestamp_regex.match(filename)
        if tmp is None:
            # Skip files that cannot be interpreted as filenames
            continue
        date = datetime.strptime(tmp[1], "%Y-%m-%d_%H:%M:%S.%f")
        name = tmp[2]
        logs.append((filename, name, FilePath(str(path)), date))
    return logs


# pylint: disable-next=too-many-branches
def ansible_extract_failure(retval: int, error_msg_lines: List[str], **kwargs: Any) -> str:
    """
    Given error information from an ansible run, return a suitable error message

        Parameters:
            retval (int): The retval from the run
            error_msg_lines ([str]): A list of error messages
            **kwargs (dict[str, Any]): Keyword arguments
                skipped (bool): Was the task skipped?
                unreachable (bool): Was the target unreachable?
        Returns:
            (str): A status string
    """
    skipped: bool = deep_get(kwargs, DictPath("skipped"), False)
    unreachable: bool = deep_get(kwargs, DictPath("unreachable"), False)

    status = ""

    if unreachable:
        if error_msg_lines:
            for line in error_msg_lines:
                if "Name or service not known" in line:
                    status = "COULD NOT RESOLVE"
                    break
                if "Permission denied" in line:
                    status = "PERMISSION DENIED"
                    break
                if "No route to host" in line:
                    status = "NO ROUTE TO HOST"
                    break
                if "Connection timed out" in line:
                    status = "CONNECTION TIMED OUT"
                    break
            if not status:
                status = "UNREACHABLE (unknown error)"
        else:
            status = "UNREACHABLE (unknown reason)"
    elif skipped:
        status = "SKIPPED"
    else:
        if retval:
            if error_msg_lines:
                for line in error_msg_lines:
                    if "The module failed to execute correctly" in line:
                        status = "MISSING INTERPRETER?"
                        break
                if not status:
                    status = "FAILED (unknown error)"
            if not status:
                status = "FAILED (unknown reason)"
        else:
            status = "SUCCESS"

    return status


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def ansible_results_extract(event: Dict) -> Tuple[int, Dict]:
    """
    Extract a result from an Ansible play

        Parameters:
            event (dict): The output from the run
        Returns:
            (int, dict):
                (int): 0 on success, -1 if host is unreachable, retval on other failure
                (dict): A dict
    """
    retval_: Optional[int] = -1

    # Special events
    if deep_get(event, DictPath("event"), "") == "playbook_on_no_hosts_matched":
        d: Dict = {
            "task": "",
            "start_date": "",
            "end_date": "",
            "retval": retval_,
            "no_hosts_matched": True,
            "unreachable": False,
            "status": "NO HOSTS MATCHED",
            "skipped": False,
            "stdout_lines": [],
            "stderr_lines": [],
            "msg_lines": [],
            "ansible_facts": {},
        }
        return -1, d

    if not deep_get(event, DictPath("event_data#host"), ""):
        return 0, {}

    if not (task := deep_get(event, DictPath("event_data#task"), "")):
        return 0, {}

    ansible_facts = deep_get(event, DictPath("event_data#res#ansible_facts"), {})

    skipped = deep_get(event, DictPath("event"), "") == "runner_on_skipped"
    failed = deep_get(event, DictPath("event"), "") == "runner_on_failed"
    unreachable = deep_get(event, DictPath("event_data#res#unreachable"), False)

    if unreachable:
        retval_ = -1
    elif skipped or deep_get(event, DictPath("event"), "") == "runner_on_ok":
        retval_ = 0
    elif failed:
        retval_ = -1
    else:
        retval_ = deep_get(event, DictPath("event_data#res#rc"))

    if task.startswith("hide_on_ok: "):
        if not retval_:
            retval_ = None
        else:
            task = task[len("hide_on_ok: "):]
    elif task == "Gathering Facts" and not retval_:
        retval_ = None

    if retval_ is None:
        return 0, {}

    msg = deep_get(event, DictPath("event_data#res#msg"), "")
    msg_lines = []
    if msg:
        msg_lines = msg.split("\n")

    start_date_timestamp = deep_get(event, DictPath("event_data#start"))
    end_date_timestamp = deep_get(event, DictPath("event_data#end"))

    stdout = deep_get(event, DictPath("event_data#res#stdout"), "")
    stderr = deep_get(event, DictPath("event_data#res#stderr"), "")
    stdout_lines = deep_get(event, DictPath("event_data#res#stdout_lines"), [])
    stderr_lines = deep_get(event, DictPath("event_data#res#stderr_lines"), [])

    if not stdout_lines and stdout:
        stdout_lines = stdout.split("\n")
    if not stderr_lines and stderr:
        stderr_lines = stderr.split("\n")

    d = {
        "task": task,
        "start_date": start_date_timestamp,
        "end_date": end_date_timestamp,
        "retval": retval_,
        "no_hosts_matched": False,
        "unreachable": unreachable,
        "status": "UNKNOWN",
        "skipped": skipped,
        "stdout_lines": [],
        "stderr_lines": [],
        "msg_lines": [],
        "ansible_facts": ansible_facts,
    }

    if not unreachable and not retval_:
        d["status"] = "SUCCESS"

    if msg_lines or stdout_lines or stderr_lines:
        if stdout_lines:
            d["stdout_lines"] = stdout_lines
        if stderr_lines:
            d["stderr_lines"] = stderr_lines
        # We do not want msg unless both stdout_lines and stderr_lines are empty.
        if not stdout_lines and not stderr_lines and msg_lines:
            if retval_:
                d["stderr_lines"] = msg_lines
            else:
                d["msg_lines"] = msg_lines
    else:
        d["stdout_lines"] = ["<no output>"]

    error_msg_lines = stderr_lines
    if not error_msg_lines:
        error_msg_lines = msg_lines
    d["status"] = ansible_extract_failure(retval_, error_msg_lines,
                                          skipped=skipped, unreachable=unreachable)

    return retval_, d


def ansible_delete_log(log: str) -> None:
    """
    Delete a log file

        Parameters:
            (str): The name of the log to delete
    """
    logpath = Path(f"{ANSIBLE_LOG_DIR}/{log}")
    if logpath.exists():
        for file in logpath.iterdir():
            secure_rm(FilePath(str(file)))
        secure_rmdir(FilePath(str(logpath)))


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def ansible_write_log(start_date: datetime, playbook: str, events: List[Dict]) -> None:
    """
    Save an Ansible log entry to a file

        Parameters:
            start_date (date): A timestamp in the format YYYY-MM-DD_HH:MM:SS.ssssss
            playbook (str): The name of the playbook
            events ([dict]): The list of Ansible runs
    """
    save_logs: bool = deep_get(ansible_configuration, DictPath("save_logs"), False)

    if not save_logs:
        return

    playbook_name = playbook
    if "/" in playbook_name:
        tmp2 = str(PurePath(playbook_name).name)
        tmp = re.match(r"^(.*)\.ya?ml$", tmp2)
        if tmp is not None:
            playbook_name = tmp[1]

    directory_name = f"{start_date}_{playbook_name}".replace(" ", "_")
    secure_mkdir(FilePath(f"{ANSIBLE_LOG_DIR}/{directory_name}"), exit_on_failure=True)

    # Start by creating a file with metadata about the whole run
    d = {
        "playbook_path": playbook,
        "created_at": start_date,
    }

    metadata_path = FilePath(f"{ANSIBLE_LOG_DIR}/{directory_name}/metadata.yaml")
    secure_write_yaml(metadata_path, d, permissions=0o600, sort_keys=False)

    i = 0

    for event in events:
        host = deep_get(event, DictPath("event_data#host"), "")
        if not host:
            continue

        task = deep_get(event, DictPath("event_data#task"), "")
        if not task:
            continue

        skipped = deep_get(event, DictPath("event"), "") == "runner_on_skipped"
        unreachable = deep_get(event, DictPath("event_data#res#unreachable"), False)

        if unreachable:
            retval = -1
        elif skipped or deep_get(event, DictPath("event"), "") == "runner_on_ok":
            retval = 0
        else:
            retval = deep_get(event, DictPath("event_data#res#rc"))

        if retval is None:
            continue

        taskname = task
        i += 1

        filename = f"{i:02d}-{host}_{taskname}.yaml".replace(" ", "_").replace("/", "_")
        msg = deep_get(event, DictPath("event_data#res#msg"), "")
        msg_lines = []
        if msg:
            msg_lines = msg.split("\n")

        start_date_timestamp = deep_get(event, DictPath("event_data#start"))
        end_date_timestamp = deep_get(event, DictPath("event_data#end"))

        stdout = deep_get(event, DictPath("event_data#res#stdout"), "")
        stderr = deep_get(event, DictPath("event_data#res#stderr"), "")
        stdout_lines = deep_get(event, DictPath("event_data#res#stdout_lines"), "")
        stderr_lines = deep_get(event, DictPath("event_data#res#stderr_lines"), "")

        if not stdout_lines and stdout:
            stdout_lines = stdout.split("\n")
        if not stderr_lines and stderr:
            stderr_lines = stderr.split("\n")

        error_msg_lines = stderr_lines
        if not error_msg_lines:
            error_msg_lines = msg_lines
        status = ansible_extract_failure(retval,
                                         error_msg_lines,
                                         skipped=skipped, unreachable=unreachable)

        d = {
            "playbook": playbook_name,
            "playbook_file": playbook,
            "task": task,
            "host": host,
            "start_date": start_date_timestamp,
            "end_date": end_date_timestamp,
            "retval": retval,
            "no_hosts_matched": False,
            "unreachable": unreachable,
            "skipped": skipped,
            "status": status,
        }

        if msg_lines or stdout_lines or stderr_lines:
            if stdout_lines:
                d["stdout_lines"] = stdout_lines
            if stderr_lines:
                d["stderr_lines"] = stderr_lines
            # We do not want msg unless both stdout_lines and stderr_lines are empty.
            if not stdout_lines and not stderr_lines and msg_lines:
                if retval:
                    d["stderr_lines"] = msg_lines
                else:
                    d["msg_lines"] = msg_lines
        else:
            d["stdout_lines"] = ["<no output>"]

        logentry_path = FilePath(f"{ANSIBLE_LOG_DIR}/{directory_name}/{filename}")
        secure_write_yaml(logentry_path, d, permissions=0o600, sort_keys=False)


# pylint: disable-next=too-many-branches,too-many-arguments
def ansible_print_task_results(task: str,
                               msg_lines: List[str],
                               stdout_lines: List[str],
                               stderr_lines: List[str], retval: int, **kwargs: Any) -> None:
    """
    Pretty-print the result of an Ansible task run

        Parameters:
            task (str): The name of the task
            msg_lines (list[str]): msg from tasks that do not split the output into stdout+stderr
            stdout_lines (list[str]): output from stdout
            stderr_lines (list[str]): output from stderr
            retval (int): The return value from the task
            **kwargs (dict[str, Any]): Keyword arguments
                unreachable (bool): Was the host unreachable?
                skipped (bool): Was the task skipped?
                verbose (bool): Should skipped tasks be outputted?
    """
    unreachable: bool = deep_get(kwargs, DictPath("unreachable"), False)
    skipped: bool = deep_get(kwargs, DictPath("skipped"), False)
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)

    if unreachable:
        ansithemeprint([ANSIThemeString("• ", "separator"),
                        ANSIThemeString(f"{task}", "error")], stderr=True)
    elif skipped:
        if verbose:
            ansithemeprint([ANSIThemeString("• ", "separator"),
                            ANSIThemeString(f"{task} [skipped]", "skip")], stderr=True)
            ansithemeprint([ANSIThemeString("", "default")])
        return
    elif retval:
        ansithemeprint([ANSIThemeString("• ", "separator"),
                        ANSIThemeString(f"{task}", "error"),
                        ANSIThemeString(" (retval: ", "default"),
                        ANSIThemeString(f"{retval}", "errorvalue"),
                        ANSIThemeString(")", "default")], stderr=True)
    else:
        ansithemeprint([ANSIThemeString("• ", "separator"),
                        ANSIThemeString(f"{task}", "success")])

    if msg_lines:
        ansithemeprint([ANSIThemeString("msg:", "header")])
        for line in msg_lines:
            ansithemeprint([ANSIThemeString(line.replace("\x00", "<NUL>"), "default")])
        ansithemeprint([ANSIThemeString("", "default")])

    if stdout_lines or not msg_lines and not stderr_lines:
        ansithemeprint([ANSIThemeString("stdout:", "header")])
        for line in stdout_lines:
            ansithemeprint([ANSIThemeString(line.replace("\x00", "<NUL>"), "default")])
        if not stdout_lines:
            ansithemeprint([ANSIThemeString("<no output>", "none")])
        ansithemeprint([ANSIThemeString("", "default")])

    # If retval is not 0 we do not really care if stderr is empty
    if stderr_lines or retval:
        ansithemeprint([ANSIThemeString("stderr:", "header")])
        for line in stderr_lines:
            ansithemeprint([ANSIThemeString(line.replace("\x00", "<NUL>"), "default")],
                           stderr=True)
        if not stderr_lines:
            ansithemeprint([ANSIThemeString("<no output>", "none")])
        ansithemeprint([ANSIThemeString("", "default")])


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def ansible_print_play_results(retval: int, ansible_results: Dict, **kwargs: Any) -> None:
    """
    Pretty-print the result of an Ansible play

        Parameters:
            retval (int): The return value from the play
            ansible_results (opaque): The data from a playbook run
            **kwargs (dict[str, Any]): Keyword arguments
                verbose (bool): Should skipped tasks be outputted?
    """
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)

    count_total = 0
    count_task_total = 0
    count_no_hosts_match = 0
    count_unreachable = 0
    count_skip = 0
    count_success = 0
    count_fail = 0

    if retval and not ansible_results:
        ansithemeprint([ANSIThemeString("Failed to execute playbook; retval: ", "error"),
                        ANSIThemeString(f"{retval}", "errorvalue")], stderr=True)
    else:
        for host in ansible_results:
            count_total += 1

            plays = ansible_results[host]
            header_output = False

            for play in plays:
                count_task_total += 1
                task = deep_get(play, DictPath("task"))

                no_hosts_matched = deep_get(play, DictPath("no_hosts_matched"), False)
                unreachable = deep_get(play, DictPath("unreachable"), False)
                skipped = deep_get(play, DictPath("skipped"), False)
                retval = deep_get(play, DictPath("retval"))

                if not header_output:
                    header_output = True

                    if no_hosts_matched:
                        ansithemeprint([ANSIThemeString("[No hosts matched]", "error")])
                    elif unreachable:
                        ansithemeprint([ANSIThemeString(f"[{host}]", "error")])
                    elif skipped:
                        ansithemeprint([ANSIThemeString(f"[{host}]", "skip")])
                    elif not retval:
                        ansithemeprint([ANSIThemeString(f"[{host}]", "success")])
                    else:
                        ansithemeprint([ANSIThemeString(f"[{host}]", "error")])
                if no_hosts_matched:
                    count_no_hosts_match += 1
                elif unreachable:
                    count_unreachable += 1
                elif skipped:
                    count_skip += 1
                elif not retval:
                    count_success += 1
                else:
                    count_fail += 1

                if not no_hosts_matched:
                    msg_lines = deep_get(play, DictPath("msg_lines"), "")
                    stdout_lines = deep_get(play, DictPath("stdout_lines"), "")
                    stderr_lines = deep_get(play, DictPath("stderr_lines"), "")
                    ansible_print_task_results(task,
                                               msg_lines,
                                               stdout_lines,
                                               stderr_lines,
                                               retval,
                                               unreachable=unreachable,
                                               skipped=skipped,
                                               verbose=verbose)

                if not skipped or verbose:
                    print()

                # Only show no hosts matched and unreachable once
                if unreachable:
                    break

    if verbose:
        successful_formatting = "default"
        failed_formatting = "skip"
        unreachable_formatting = "skip"
        no_hosts_matched_formatting = "skip"
        if count_success > 0:
            successful_formatting = "success"
        if count_fail > 0:
            failed_formatting = "error"
        if count_unreachable > 0:
            unreachable_formatting = "error"
        if count_no_hosts_match > 0:
            no_hosts_matched_formatting = "error"

        ansithemeprint([ANSIThemeString("Summary:", "default")])
        ansithemeprint([ANSIThemeString("Total Plays: ", "phase"),
                        ANSIThemeString(f"{count_total}", "numerical"),
                        ANSIThemeString(" / ", "separator"),
                        ANSIThemeString("Tasks: ", "phase"),
                        ANSIThemeString(f"{count_task_total}", "numerical"),
                        ANSIThemeString(", ", "separator"),
                        ANSIThemeString("Successful: ", successful_formatting),
                        ANSIThemeString(f"{count_success}", "numerical"),
                        ANSIThemeString(", ", "separator"),
                        ANSIThemeString("Failed: ", failed_formatting),
                        ANSIThemeString(f"{count_fail}", "numerical"),
                        ANSIThemeString(", ", "separator"),
                        ANSIThemeString("Skipped: ", "skip"),
                        ANSIThemeString(f"{count_skip}", "numerical"),
                        ANSIThemeString(", ", "separator"),
                        ANSIThemeString("Unreachable: ", unreachable_formatting),
                        ANSIThemeString(f"{count_unreachable}", "numerical"),
                        ANSIThemeString(", ", "separator"),
                        ANSIThemeString("No hosts matched: ", no_hosts_matched_formatting),
                        ANSIThemeString(f"{count_no_hosts_match}\n", "numerical")])


# pylint: disable-next=too-many-locals
def ansible_run_playbook(playbook: FilePath, **kwargs: Any) -> Tuple[int, Dict]:
    """
    Run a playbook

        Parameters:
            playbook (FilePath): The playbook to run
            **kwargs (dict[str, Any]): Keyword arguments
                inventory (dict): An inventory dict with selection as the list of hosts to run on
                verbose (bool): Output status updates for every new Ansible event
                quiet (bool): Disable console output
        Returns:
            (int, dict):
                (int): The return value
                (dict): The results of the run
    """
    inventory: Optional[Dict] = deep_get(kwargs, DictPath("inventory"), None)
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)
    quiet: bool = deep_get(kwargs, DictPath("quiet"), True)

    forks = deep_get(ansible_configuration, DictPath("ansible_forks"))

    ansible_results: Dict = {}

    inventories: Union[Dict, List[FilePath]] = []

    if inventory is None:
        inventories = [ANSIBLE_INVENTORY]
    else:
        inventories = inventory

    start_date = datetime.now()

    event_handler = None
    if verbose:
        event_handler = __ansible_run_event_handler_verbose_cb
    elif not quiet:
        event_handler = __ansible_run_event_handler_cb

    # We need to run with ANSIBLE_JINJA2_NATIVE=False
    # to be compatible with Ubuntu 22.04 LTS
    runner = ansible_runner.interface.run(json_mode=True,
                                          quiet=True,
                                          playbook=playbook,
                                          inventory=inventories,
                                          forks=forks,
                                          event_handler=event_handler,
                                          envvars={"ANSIBLE_JINJA2_NATIVE": False})

    retval = 0
    if runner is not None:
        for event in runner.events:
            host = deep_get(event, DictPath("event_data#host"))
            if host is None:
                continue
            retval_, d = ansible_results_extract(event)
            if not retval and retval_:
                retval = retval_
            if d:
                if host not in ansible_results:
                    ansible_results[host] = []
                ansible_results[host].append(d)
        ansible_write_log(start_date, playbook, runner.events)

    return retval, ansible_results


def ansible_run_playbook_on_selection(playbook: FilePath,
                                      selection: List[str], **kwargs: Any) -> Tuple[int, Dict]:
    """
    Run a playbook on selected nodes

        Parameters:
            playbook (FilePath): The playbook to run
            selection (list[str]): The hosts to run the play on
            kwargs (dict):
                values (dict): Extra values to set for the hosts
                verbose (bool): Output status updates for every new Ansible event
                quiet (bool): Disable console output
        Returns:
            (int, dict):
                (int): The result from ansible_run_playbook();
                       -errno.ENOENT if the inventory is missing or empty
                (dict): The results of the run
    """
    # If ansible_ssh_pass system variable is not set, and ansible_sudo_pass is set,
    # we set ansible_ssh_pass to ansible_become_pass; on systems where we already have a host key
    # this will be ignored; the same goes for groups or hosts where ansible_ssh_pass is set,
    # since group and host vars take precedence over system vars.
    #
    # This is mainly for the benefit of making the prepare_host task possible to run without
    # encouraging permanent use of ansible_{ssh,sudo,become}_pass.
    # Ideally these variables should only be needed once; when preparing the host; after that
    # we will use passwordless sudo and ssh hostkeys.
    #
    # Also, if ansible_user is not set ansible will implicitly use the local user. Pass this
    # as ansible user to make scripts that tries to access ansible_user function properly.
    d = ansible_get_inventory_dict()

    if not d:
        return -errno.ENOENT, {}

    values: Dict[str, Any] = deep_get(kwargs, DictPath("values"), {})
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)
    quiet: bool = deep_get(kwargs, DictPath("quiet"), True)

    if values is None:
        values = {}

    if "ansible_sudo_pass" in values and "ansible_become_pass" not in values:
        values["ansible_become_pass"] = values["ansible_sudo_pass"]
    if "ansible_become_pass" in values and "ansible_ssh_pass" not in d["all"]["vars"]:
        values["ansible_ssh_pass"] = values["ansible_become_pass"]
    if "ansible_user" not in d["all"]["vars"]:
        values["ansible_user"] = deep_get(ansible_configuration, DictPath("ansible_user"))

    for key, value in values.items():
        d["all"]["vars"][key] = value

    d["selection"] = {
        "hosts": {}
    }

    for host in selection:
        d["selection"]["hosts"][host] = {}

    return ansible_run_playbook(playbook, inventory=d, verbose=verbose, quiet=quiet)


def ansible_ping(selection: List[str]) -> List[Tuple[str, str]]:
    """
    Ping all selected hosts

        Parameters:
            selection ([str]): A list of hostnames
        Returns:
            [(str, str)]: The status of the pinged hosts
    """
    save_logs_tmp = deep_get(ansible_configuration, DictPath("save_logs"), False)
    ansible_configuration["save_logs"] = False

    host_status = []

    if selection is None:
        selection = ansible_get_hosts_by_group(ANSIBLE_INVENTORY, "all")
    else:
        validate_args(kwargs_spec={"__allof": ("selection",), "selection": {"types": (list,)}},
                      kwargs={"selection": selection})

    playbook_path = FilePath(os.path.join(ANSIBLE_PLAYBOOK_DIR, "ping.yaml"))
    _retval, ansible_results = ansible_run_playbook_on_selection(playbook_path,
                                                                 selection=selection, quiet=False)

    for host in ansible_results:
        for task in deep_get(ansible_results, DictPath(host), []):
            unreachable = deep_get(task, DictPath("unreachable"))
            skipped = deep_get(task, DictPath("skipped"))
            stderr_lines = deep_get(task, DictPath("stderr_lines"))
            retval = deep_get(task, DictPath("retval"))
            status = ansible_extract_failure(retval,
                                             stderr_lines,
                                             skipped=skipped, unreachable=unreachable)
            host_status.append((host, status))
    ansible_configuration["save_logs"] = save_logs_tmp

    return host_status


def __ansible_run_event_handler_cb(data: Dict) -> bool:
    if deep_get(data, DictPath("event"), "") in ("runner_on_failed", "runner_on_async_failed"):
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeString("  • ", "separator"),
                        ANSIThemeString("Task", "action"),
                        ANSIThemeString(": ", "default"),
                        ANSIThemeString(f"{task}", "play"),
                        ANSIThemeString(" ", "default"),
                        ANSIThemeString("failed", "error"),
                        ANSIThemeString(" on ", "default"),
                        ANSIThemeString(f"{host}", "hostname")])
        for res in deep_get(data, DictPath("event_data#res#results"), []):
            msg = deep_get(res, DictPath("msg"), "")
            if msg:
                ansithemeprint([ANSIThemeString("    ", "default"),
                                ANSIThemeString("Error", "error"),
                                ANSIThemeString(":", "default")])
                ansithemeprint([ANSIThemeString(f"      {msg}", "default")])
    elif deep_get(data, DictPath("event"), "") == "runner_on_unreachable":
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeString("  • ", "separator"),
                        ANSIThemeString("Task", "action"),
                        ANSIThemeString(": ", "default"),
                        ANSIThemeString(f"{task}", "play"),
                        ANSIThemeString(" ", "default"),
                        ANSIThemeString("failed", "error"),
                        ANSIThemeString("; ", "default"),
                        ANSIThemeString(f"{host}", "hostname"),
                        ANSIThemeString(" unreachable", "default")])
    return True


def __ansible_run_event_handler_verbose_cb(data: Dict) -> bool:
    if deep_get(data, DictPath("event"), "") == "runner_on_start":
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeString("  • ", "separator"),
                        ANSIThemeString("Task", "action"),
                        ANSIThemeString(": ", "default"),
                        ANSIThemeString(f"{task}", "play"),
                        ANSIThemeString(" ", "default"),
                        ANSIThemeString("started", "phase"),
                        ANSIThemeString(" on ", "default"),
                        ANSIThemeString(f"{host}", "hostname")])
    elif deep_get(data, DictPath("event"), "") in ("runner_on_ok", "runner_on_async_ok"):
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeString("  • ", "separator"),
                        ANSIThemeString("Task", "action"),
                        ANSIThemeString(": ", "default"),
                        ANSIThemeString(f"{task}", "play"),
                        ANSIThemeString(" ", "default"),
                        ANSIThemeString("succeeded", "success"),
                        ANSIThemeString(" on ", "default"),
                        ANSIThemeString(f"{host}", "hostname")])
    elif deep_get(data, DictPath("event"), "") in ("runner_on_failed", "runner_on_async_failed"):
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeString("  • ", "separator"),
                        ANSIThemeString("Task", "action"),
                        ANSIThemeString(": ", "default"),
                        ANSIThemeString(f"{task}", "play"),
                        ANSIThemeString(" ", "default"),
                        ANSIThemeString("failed", "error"),
                        ANSIThemeString(" on ", "default"),
                        ANSIThemeString(f"{host}", "hostname")])
        for res in deep_get(data, DictPath("event_data#res#results"), []):
            msg = deep_get(res, DictPath("msg"), "")
            if msg:
                ansithemeprint([ANSIThemeString("    ", "default"),
                                ANSIThemeString("Error", "error"),
                                ANSIThemeString(":", "default")])
                ansithemeprint([ANSIThemeString(f"      {msg}", "default")])
    elif deep_get(data, DictPath("event"), "") == "runner_on_unreachable":
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeString("  • ", "separator"),
                        ANSIThemeString("Task", "action"),
                        ANSIThemeString(": ", "default"),
                        ANSIThemeString(f"{task}", "play"),
                        ANSIThemeString(" ", "default"),
                        ANSIThemeString("failed", "error"),
                        ANSIThemeString("; ", "default"),
                        ANSIThemeString(f"{host}", "hostname"),
                        ANSIThemeString(" unreachable", "default")])
    elif deep_get(data, DictPath("event"), "") == "runner_on_skipped":
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeString("  • ", "separator"),
                        ANSIThemeString("Task", "action"),
                        ANSIThemeString(": ", "default"),
                        ANSIThemeString(f"{task}", "play"),
                        ANSIThemeString(" ", "default"),
                        ANSIThemeString("skipped", "none"),
                        ANSIThemeString(" on ", "default"),
                        ANSIThemeString(f"{host}", "hostname")])
    return True
