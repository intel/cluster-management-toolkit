#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
# Requires: python3 (>= 3.9)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Ansible-related helpers
"""

# pylint: disable=too-many-lines

from datetime import datetime
import errno
from pathlib import Path, PurePath
import re
import sys
from typing import Any, cast, Optional, Union
from collections.abc import Sequence

from clustermanagementtoolkit import cmtlib

from clustermanagementtoolkit.cmtio import check_path, join_securitystatus_set
from clustermanagementtoolkit.cmtio import secure_mkdir, secure_rm, secure_rmdir

from clustermanagementtoolkit.cmtio_yaml import ruyaml_dump_to_string
from clustermanagementtoolkit.cmtio_yaml import secure_read_yaml, secure_write_yaml

from clustermanagementtoolkit.cmtpaths import HOMEDIR
from clustermanagementtoolkit.cmtpaths import SYSTEM_ANSIBLE_PLAYBOOK_DIR
from clustermanagementtoolkit.cmtpaths import ANSIBLE_DIR, ANSIBLE_PLAYBOOK_DIR, ANSIBLE_LOG_DIR
from clustermanagementtoolkit.cmtpaths import ANSIBLE_INVENTORY

from clustermanagementtoolkit.ansithemeprint import ANSIThemeStr, ansithemeprint

from clustermanagementtoolkit.cmttypes import deep_get, deep_set, DictPath
from clustermanagementtoolkit.cmttypes import FilePath, FilePathAuditError
from clustermanagementtoolkit.cmttypes import SecurityChecks, SecurityStatus, validate_args

try:
    import ruyaml
    ryaml = ruyaml.YAML()
    sryaml = ruyaml.YAML(typ="safe")
except ModuleNotFoundError:  # pragma: no cover
    try:
        import ruamel.yaml as ruyaml  # type: ignore
        ryaml = ruyaml.YAML()
        sryaml = ruyaml.YAML(typ="safe")
    except ModuleNotFoundError:  # pragma: no cover
        sys.exit("ModuleNotFoundError: Could not import ruyaml/ruamel.yaml; "
                 "you may need to (re-)run `cmt-install` or `pip3 install ruyaml/ruamel.yaml`; "
                 "aborting.")

ansible_configuration: dict = {
    "ansible_forks": 10,
    "ansible_password": None,
    "ansible_user": None,
    "disable_strict_host_key_checking": False,
    "save_logs": False,
}

# Used by Ansible
try:
    import ansible_runner
except ModuleNotFoundError:  # pragma: no cover
    # This is acceptable; we don't benefit from a backtrace or log message
    sys.exit("ModuleNotFoundError: Could not import ansible_runner; "
             "you may need to (re-)run `cmt-install` or `pip3 install ansible-runner`; aborting.")


def get_playbook_path(playbook: Union[FilePath, str]) -> FilePath:
    """
    Pass in the name of a playbook that exists in either
    {SYSTEM_PLAYBOOK_DIR} or {ANSIBLE_PLAYBOOK_DIR};
    returns the path to the drop-in playbook with the highest priority
    (or the same playbook in case there is no override).

        Parameters:
            playbook (FilePath): The name of the playbook to get the path to
        Returns:
            (FilePath): The playbook path with the highest priority
        Raises:
            FilePathAuditError: No usable match playbook was found
    """
    path = ""

    if not isinstance(playbook, (FilePath, str)):
        raise TypeError(f"playbook is type: {type(playbook)}, expected FilePath | str")
    if not playbook:
        raise ValueError("len(playbook) == 0; expected a filename")

    # Check if there's a local playbook overriding this one
    playbook_dirs = deep_get(cmtlib.cmtconfig, DictPath("Ansible#local_playbooks"), [])
    playbook_dirs.append(ANSIBLE_PLAYBOOK_DIR)
    playbook_dirs.append(SYSTEM_ANSIBLE_PLAYBOOK_DIR)

    for playbook_path in playbook_dirs:
        # Substitute {HOME}/ for {HOMEDIR}
        if playbook_path.startswith("{HOME}/"):
            playbook_path = f"{HOMEDIR}/{playbook_path[len('{HOME}/'):]}"
        playbook_path_entry = Path(playbook_path)
        # Skip non-existing playbook paths
        if not playbook_path_entry.is_dir():
            continue
        # We can have multiple directories with playbooks;
        # the first match wins
        if Path(f"{playbook_path}/{playbook}").is_file():
            path = f"{playbook_path}/{playbook}"
            break
    if not path:
        raise FilePathAuditError(f"Could not find a usable match for playbook `{playbook}`",
                                 path=playbook)
    return FilePath(path)


# Add all playbooks in the array
def populate_playbooks_from_paths(paths: list[FilePath]) -> list[tuple[list[ANSIThemeStr],
                                                                       FilePath]]:
    """
    Populate a list of playbook paths.

        Parameters:
            paths ([FilePath]): A list of paths to playbooks
        Returns:
            [([ANSIThemeStr], FilePath)]:
                ([ANSIThemeStr]): An ansithemearray with the name of the playbook
                (FilePath): The path to the playbook
        Raises:
            FilePathAuditError: The playbook exists but violates path constraints
    """
    playbooks = []

    yaml_regex = re.compile(r"^(.*)\.ya?ml$")

    for playbookpath in paths:
        pathname = PurePath(playbookpath).name
        playbook_dir = FilePath(PurePath(playbookpath).parent)

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

        try:
            dl = list(secure_read_yaml(playbookpath, checks=checks))
        except TypeError:
            dl = []
        description = None
        if (t_description := deep_get(dl[0], DictPath("vars#metadata#description"), "")):
            description = [ANSIThemeStr(t_description, "play")]

        if description is None or not description:
            description = [ANSIThemeStr("Running “", "play"),
                           ANSIThemeStr(playbookname, "programname"),
                           ANSIThemeStr("“", "play")]

        # If there's no description we fallback to just using the filename
        playbooks.append(([ANSIThemeStr("  • ", "separator")] + description, playbookpath))
    return playbooks


# Add all playbooks in the array
def populate_playbooks_from_filenames(playbooks: list[FilePath]) -> list[tuple[list[ANSIThemeStr],
                                                                               FilePath]]:
    """
    Given a list of playbook names, populate a list of playbook paths.

        Parameters:
            paths ([FilePath]): A list of playbook names
        Returns:
            [([ANSIThemeStr], FilePath)]:
                ([ANSIThemeStr]): An ansithemearray with the name of the playbook
                (FilePath): The path to the playbook
        Raises:
            FilePathAuditError: The playbook exists but violates path constraints,
                                or no valid playbook was found.
    """
    playbook_paths = []

    for playbook in playbooks:
        playbook_paths.append(get_playbook_path(playbook))
    return populate_playbooks_from_paths(playbook_paths)


def ansible_print_action_summary(playbooks: list[tuple[list[ANSIThemeStr], FilePath]]) -> None:
    """
    Given a list of playbook paths, print a summary of the actions that will be performed.

        Parameters:
            playbook (str): The name of the playbook to print a summary for
    """
    if not isinstance(playbooks, list):
        raise TypeError(f"playbooks is type: {type(playbooks)}, expected: {list}")

    if not playbooks:
        raise ValueError("playbooks is empty")

    if not (isinstance(playbooks[0], tuple) and len(playbooks[0]) == 2
            and isinstance(playbooks[0][0], list) and isinstance(playbooks[0][1], (FilePath, str))):
        raise TypeError("playbooks[] is wrong type; "
                        f"expected: [([{ANSIThemeStr}], {FilePath})]")

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

    ansithemeprint([ANSIThemeStr("\n• ", "separator"),
                    ANSIThemeStr("Playbooks to be executed:", "action")])
    for playbook in playbooks:
        playbook_string, playbook_path = playbook
        playbook_data = secure_read_yaml(FilePath(playbook_path), checks=checks)

        ansithemeprint(playbook_string + [ANSIThemeStr(" (path: ", "default"),
                                          ANSIThemeStr(f"{playbook_path}", "path"),
                                          ANSIThemeStr(")", "default")])
        # None of our playbooks have more than one play per file
        summary = deep_get(playbook_data[0], DictPath("vars#metadata#summary"), {})
        if not summary:
            ansithemeprint([ANSIThemeStr("      Error", "error"),
                            ANSIThemeStr(": playbook lacks a summary; "
                                         "please file a bug report unless it's a "
                                         "locally modified playbook!", "default")],
                           stderr=True)
        for section_description, section_data in summary.items():
            ansithemeprint([ANSIThemeStr(f"      {section_description}:", "emphasis")])
            for section_item in section_data:
                description = deep_get(section_item, DictPath("description"), "")
                ansithemeprint([ANSIThemeStr(f"        {description}", "default")])


def ansible_get_inventory_dict() -> Union[dict[str, Any], ruyaml.comments.CommentedMap]:
    """
        Get the Ansible inventory and return it as a dict.

        Returns:
            (dict): A dictionary with an Ansible inventory
    """
    d: Union[dict[str, Any], ruyaml.comments.CommentedMap] = {
        "all": {
            "hosts": {},
            "vars": {},
        },
    }

    if not Path(ANSIBLE_INVENTORY).is_file():
        return d

    tmp_d: Any = secure_read_yaml(ANSIBLE_INVENTORY)
    if isinstance(tmp_d, (dict, ruyaml.comments.CommentedMap)):
        deep_set(tmp_d, DictPath("all#hosts"),
                 deep_get(tmp_d, DictPath("all#hosts"), {}), create_path=True)
        deep_set(tmp_d, DictPath("all#vars"),
                 deep_get(tmp_d, DictPath("all#vars"), {}), create_path=True)
        d = tmp_d

    return d


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def ansible_get_inventory_pretty(**kwargs: Any) -> list[Union[list[ANSIThemeStr], str]]:
    """
        Get the Ansible inventory and return it neatly formatted.

        Parameters:
            **kwargs (dict[str, Any]): Keyword arguments
                groups ([str]): What groups to include
                highlight (bool): Apply syntax highlighting?
                include_groupvars (bool): Should group variables be included
                include_hostvars (bool): Should host variables be included
                include_hosts (bool): Should hosts be included
        Returns:
            ([str|[ANSIThemeStr]]): An unformatted list of strings
                                       or a formatted list of themearrays
    """
    groups: list[str] = deep_get(kwargs, DictPath("groups"), [])
    highlight: bool = deep_get(kwargs, DictPath("highlight"), False)
    include_groupvars: bool = deep_get(kwargs, DictPath("include_groupvars"), False)
    include_hostvars: bool = deep_get(kwargs, DictPath("include_hostvars"), False)
    include_hosts: bool = deep_get(kwargs, DictPath("include_hosts"), True)

    tmp: Union[dict[str, Any], ruyaml.comments.CommentedMap] = {}

    if not Path(ANSIBLE_INVENTORY).is_file():
        return []

    try:
        d = dict(secure_read_yaml(ANSIBLE_INVENTORY))
    except TypeError:
        d = {}

    # We want the entire inventory
    if not groups:
        tmp = dict(d)
    else:
        if not (isinstance(groups, list) and groups and isinstance(groups[0], str)):
            raise TypeError(f"groups is type: {type(groups)}, expected {list}")
        for group in groups:
            if (item := deep_get(d, DictPath(group))) is not None:
                tmp[group] = item

    # OK, now we have a dict with only the groups we are interested in;
    # time for further post-processing.

    # do we want groupvars?
    if not include_groupvars:
        for group in tmp:
            tmp[group].pop("vars", None)
    else:
        for group in tmp:
            if not deep_get(tmp, DictPath(f"{group}#vars"), {}):
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

    tmp_dump = ruyaml_dump_to_string(tmp, replace_null=True, replace_empty=True,
                                     replace_empty_dict=True)
    dump: list[Union[list[ANSIThemeStr], str]] = []

    if highlight and tmp_dump:
        list_regex = re.compile(r"^(\s*)((- )+)(.*)")
        key_value_regex = re.compile(r"^(.*?)(:)(.*)")
        for data in tmp_dump.splitlines():
            # Is it a list?
            tmp2 = list_regex.match(data)
            if tmp2 is not None:
                indent = tmp2[1]
                listmarker = tmp2[2]
                item = tmp2[4]
                dump.append([ANSIThemeStr(indent, "default"),
                             ANSIThemeStr(listmarker, "yaml_list"),
                             ANSIThemeStr(item, "yaml_value")])
                continue

            # Is it key: value?
            tmp2 = key_value_regex.match(data)
            if tmp2 is not None:
                key = tmp2[1]
                separator = tmp2[2]
                value = tmp2[3]
                dump.append([ANSIThemeStr(key, "yaml_key"),
                             ANSIThemeStr(separator, "yaml_key_separator"),
                             ANSIThemeStr(value, "yaml_value")])
                continue

            # Nope, then we will use default format
            dump.append([ANSIThemeStr(data, "default")])
    else:
        dump = list(tmp_dump.splitlines())

    return dump


def ansible_get_hosts_by_group(inventory: FilePath, group: str) -> list[str]:
    """
    Get the list of hosts belonging to a group.

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

    for host in deep_get(d, DictPath(f"{group}#hosts"), []):
        hosts.append(host)

    return hosts


def ansible_get_groups(inventory: FilePath) -> list[str]:
    """
    Get the list of groups in the inventory.

        Parameters:
            inventory (FilePath): The inventory to use
        Returns:
            ([str]): A list of groups
    """
    if not Path(inventory).exists():
        return []

    try:
        d = dict(secure_read_yaml(inventory))
    except TypeError:
        d = {}
    return list(d.keys())


def ansible_get_groups_by_host(inventory_dict: dict, host: str) -> list[str]:
    """
    Given an inventory, returns the groups a host belongs to.

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
        if host in deep_get(inventory_dict, DictPath(f"{group}#hosts"), {}):
            groups.append(group)

    return groups


def __ansible_create_inventory(inventory: FilePath, **kwargs: Any) -> bool:
    """
    Create a new inventory at the path given if no inventory exists.

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

    if not isinstance(inventory, (FilePath, str)):
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
    d: dict = {
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


def ansible_create_groups(inventory: FilePath, groups: list[str], **kwargs: Any) -> bool:
    """
    Create new groups.

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


def ansible_set_vars(inventory: FilePath, group: str, values: dict, **kwargs: Any) -> bool:
    """
    Set one or several values for a group.

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
    changed: bool = False

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
    deep_set(d, DictPath(f"{group}#vars"),
             deep_get(d, DictPath(f"{group}#vars"), {}), create_path=True)

    for key in values:
        value_key = deep_get(values, DictPath(key))
        if key in deep_get(d, DictPath(f"{group}#vars"), {}) \
                and deep_get(d, DictPath(f"{group}#vars#{key}"), {}) == value_key:
            continue

        # Set the variable (overwriting previous value)
        deep_set(d, DictPath(f"{group}#vars#{key}"), value_key)
        changed = True

    if changed:
        secure_write_yaml(inventory, d, permissions=0o600,
                          replace_empty=True, replace_null=True, temporary=temporary)

    return True


def ansible_set_groupvars(inventory: FilePath,
                          groups: list[str],
                          groupvars: Sequence[tuple[str, Union[str, int]]], **kwargs: Any) -> bool:
    """
    Set one or several vars for the specified groups.

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
                         hosts: list[str],
                         hostvars: Sequence[tuple[str, Union[str, int]]], **kwargs: Any) -> bool:
    """
    Set one or several vars for the specified hosts.

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
                            groups: list[str], groupvars: list[str], **kwargs: Any) -> bool:
    """
    Unset one or several vars for the specified groups.

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
                           hosts: list[str], hostvars: list[str], **kwargs: Any) -> bool:
    """
    Unset one or several vars for the specified hosts.

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


def ansible_add_hosts(inventory: FilePath, hosts: list[str], **kwargs: Any) -> bool:
    """
    Add hosts to the ansible inventory; if the inventory does not exist, create it.

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

    d: Union[dict[str, Any], ruyaml.comments.CommentedMap] = {}

    tmp_d: Any = None

    # The inventory does not exist; if the user specified skip_all
    # we do not mind, otherwise we need to create it
    if not Path(inventory).is_file():
        if skip_all and group != "all":
            changed = True
        else:
            __ansible_create_inventory(inventory, overwrite=False)
            tmp_d = secure_read_yaml(inventory, temporary=temporary)
    else:
        tmp_d = secure_read_yaml(inventory, temporary=temporary)
    if isinstance(tmp_d, (dict, ruyaml.comments.CommentedMap)):
        d = tmp_d

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
            if host not in cast(list, d["all"]["hosts"]):
                d = cast(dict, d)
                d["all"]["hosts"][host] = {}
                changed = True

        # If the group does not exist,
        # create it--we currently do not support
        # nested groups, node vars or anything like that
        #
        # We do not want to overwrite groups
        if group not in ("", "all"):
            if host not in deep_get(d, DictPath(f"{group}#hosts"), {}):
                deep_set(d, DictPath(f"{group}#hosts#{host}"), {}, create_path=True)
                changed = True

    if changed:
        secure_write_yaml(inventory, d, permissions=0o600,
                          replace_empty=True, replace_null=True, temporary=temporary)

    return True


# Remove hosts from ansible groups
def ansible_remove_hosts(inventory: FilePath, hosts: list[str], **kwargs: Any) -> bool:
    """
    Remove hosts from the inventory.

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


def ansible_remove_groups(inventory: FilePath, groups: list[str], **kwargs: Any) -> bool:
    """
    Remove groups from the inventory.

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

    d: Union[dict[str, Any], ruyaml.comments.CommentedMap] = {}
    tmp_d: Any = secure_read_yaml(inventory, temporary=temporary)
    if isinstance(tmp_d, (dict, ruyaml.comments.CommentedMap)):
        d = tmp_d

    for group in groups:
        if deep_get(d, DictPath(group)) is None:
            continue

        if deep_get(d, DictPath(f"{group}#hosts")) is not None and not force:
            continue

        d.pop(group)
        changed = True

    if changed:
        secure_write_yaml(inventory, d, permissions=0o600,
                          replace_empty=True, replace_null=True, temporary=temporary)

    return True


def ansible_get_logs() -> list[tuple[str, str, FilePath, datetime]]:
    """
    Returns a list of all available logs.

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
        logs.append((filename, name, FilePath(path), date))
    return logs


# pylint: disable-next=too-many-branches
def ansible_extract_failure(retval: int, error_msg_lines: list[str], **kwargs: Any) -> str:
    """
    Given error information from an ansible run, return a suitable error message.

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
def ansible_results_extract(event: dict) -> tuple[int, dict]:
    """
    Extract a result from an Ansible play.

        Parameters:
            event (dict): The output from the run
        Returns:
            ((int, dict)):
                (int): 0 on success, -1 if host is unreachable, retval on other failure
                (dict): A dict
    """
    retval_: Optional[int] = -1

    # Special events
    if deep_get(event, DictPath("event"), "") == "playbook_on_no_hosts_matched":
        d: dict = {
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
            task = task.removeprefix("hide_on_ok: ")
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


def ansible_delete_log(log: str, **kwargs: Any) -> None:
    """
    Delete a log file.
    FIXME: This should be moved elsewhere since it's used by other components
    than just Ansible logs.

        Parameters:
            log (str): The name of the log to delete
            **kwargs (dict[str, Any]): Keyword arguments
                dirpath (str): The path to the logs
    """
    dirpath: str = deep_get(kwargs, DictPath("dirpath"), ANSIBLE_LOG_DIR)
    logpath: str = Path(f"{dirpath}/{log}")
    if logpath.exists():
        if logpath.is_dir():
            for file in logpath.iterdir():
                secure_rm(FilePath(file))
            secure_rmdir(FilePath(logpath))
        else:
            secure_rm(FilePath(logpath))


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def ansible_write_log(start_date: datetime, playbook: FilePath, events: list[dict]) -> None:
    """
    Save an Ansible log entry to a file.

        Parameters:
            start_date (date): A timestamp in the format YYYY-MM-DD_HH:MM:SS.ssssss
            playbook (str): The name of the playbook
            events ([dict]): The list of Ansible runs
    """
    save_logs: bool = deep_get(ansible_configuration, DictPath("save_logs"), False)

    if not save_logs:
        return

    playbook_name = str(playbook)
    if "/" in playbook_name:
        tmp2 = str(PurePath(playbook_name).name)
        tmp = re.match(r"^(.*)\.ya?ml$", tmp2)
        if tmp is not None:
            playbook_name = tmp[1]

    directory_name = f"{start_date}_{playbook_name}".replace(" ", "_")
    secure_mkdir(FilePath(f"{ANSIBLE_LOG_DIR}/{directory_name}"), exit_on_failure=True)

    # Start by creating a file with metadata about the whole run
    d = {
        "playbook_path": str(playbook),
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
        stdout_lines = deep_get(event, DictPath("event_data#res#stdout_lines"), [])
        stderr_lines = deep_get(event, DictPath("event_data#res#stderr_lines"), [])

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
            "playbook_file": str(playbook),
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


# pylint: disable-next=too-many-branches
def ansible_print_task_results(task: str,
                               msg_lines: list[str],
                               stdout_lines: list[str],
                               stderr_lines: list[str], retval: int, **kwargs: Any) -> None:
    """
    Pretty-print the result of an Ansible task run.

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
        ansithemeprint([ANSIThemeStr("• ", "separator"),
                        ANSIThemeStr(f"{task}", "error")], stderr=True)
    elif skipped:
        if verbose:
            ansithemeprint([ANSIThemeStr("• ", "separator"),
                            ANSIThemeStr(f"{task} [skipped]", "skip")], stderr=True)
            ansithemeprint([ANSIThemeStr("", "default")])
        return
    elif retval:
        ansithemeprint([ANSIThemeStr("• ", "separator"),
                        ANSIThemeStr(f"{task}", "error"),
                        ANSIThemeStr(" (retval: ", "default"),
                        ANSIThemeStr(f"{retval}", "errorvalue"),
                        ANSIThemeStr(")", "default")], stderr=True)
    else:
        ansithemeprint([ANSIThemeStr("• ", "separator"),
                        ANSIThemeStr(f"{task}", "success")])

    if msg_lines:
        ansithemeprint([ANSIThemeStr("msg:", "header")])
        for line in msg_lines:
            ansithemeprint([ANSIThemeStr(line.replace("\x00", "<NUL>"), "default")])
        ansithemeprint([ANSIThemeStr("", "default")])

    if stdout_lines or not msg_lines and not stderr_lines:
        ansithemeprint([ANSIThemeStr("stdout:", "header")])
        for line in stdout_lines:
            ansithemeprint([ANSIThemeStr(line.replace("\x00", "<NUL>"), "default")])
        if not stdout_lines:
            ansithemeprint([ANSIThemeStr("<no output>", "none")])
        ansithemeprint([ANSIThemeStr("", "default")])

    # If retval is not 0 we do not really care if stderr is empty
    if stderr_lines or retval:
        ansithemeprint([ANSIThemeStr("stderr:", "header")])
        for line in stderr_lines:
            ansithemeprint([ANSIThemeStr(line.replace("\x00", "<NUL>"), "default")],
                           stderr=True)
        if not stderr_lines:
            ansithemeprint([ANSIThemeStr("<no output>", "none")])
        ansithemeprint([ANSIThemeStr("", "default")])


# pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
def ansible_print_play_results(retval: int, ansible_results: dict, **kwargs: Any) -> None:
    """
    Pretty-print the result of an Ansible play.

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
        ansithemeprint([ANSIThemeStr("Failed to execute playbook; retval: ", "error"),
                        ANSIThemeStr(f"{retval}", "errorvalue")], stderr=True)
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
                        ansithemeprint([ANSIThemeStr("[No hosts matched]", "error")])
                    elif unreachable:
                        ansithemeprint([ANSIThemeStr(f"[{host}]", "error")])
                    elif skipped:
                        ansithemeprint([ANSIThemeStr(f"[{host}]", "skip")])
                    elif not retval:
                        ansithemeprint([ANSIThemeStr(f"[{host}]", "success")])
                    else:
                        ansithemeprint([ANSIThemeStr(f"[{host}]", "error")])
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
                    stdout_lines = deep_get(play, DictPath("stdout_lines"), [])
                    stderr_lines = deep_get(play, DictPath("stderr_lines"), [])
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
        if count_success:
            successful_formatting = "success"
        if count_fail:
            failed_formatting = "error"
        if count_unreachable:
            unreachable_formatting = "error"
        if count_no_hosts_match:
            no_hosts_matched_formatting = "error"

        ansithemeprint([ANSIThemeStr("Summary:", "default")])
        ansithemeprint([ANSIThemeStr("Total Plays: ", "phase"),
                        ANSIThemeStr(f"{count_total}", "numerical"),
                        ANSIThemeStr(" / ", "separator"),
                        ANSIThemeStr("Tasks: ", "phase"),
                        ANSIThemeStr(f"{count_task_total}", "numerical"),
                        ANSIThemeStr(", ", "separator"),
                        ANSIThemeStr("Successful: ", successful_formatting),
                        ANSIThemeStr(f"{count_success}", "numerical"),
                        ANSIThemeStr(", ", "separator"),
                        ANSIThemeStr("Failed: ", failed_formatting),
                        ANSIThemeStr(f"{count_fail}", "numerical"),
                        ANSIThemeStr(", ", "separator"),
                        ANSIThemeStr("Skipped: ", "skip"),
                        ANSIThemeStr(f"{count_skip}", "numerical"),
                        ANSIThemeStr(", ", "separator"),
                        ANSIThemeStr("Unreachable: ", unreachable_formatting),
                        ANSIThemeStr(f"{count_unreachable}", "numerical"),
                        ANSIThemeStr(", ", "separator"),
                        ANSIThemeStr("No hosts matched: ", no_hosts_matched_formatting),
                        ANSIThemeStr(f"{count_no_hosts_match}\n", "numerical")])


# pylint: disable-next=too-many-locals
def ansible_run_playbook(playbook: FilePath, **kwargs: Any) -> tuple[int, dict]:
    """
    Run a playbook.

        Parameters:
            playbook (FilePath): The playbook to run
            **kwargs (dict[str, Any]): Keyword arguments
                inventory (dict): An inventory dict with selection as the list of hosts to run on
                verbose (bool): Output status updates for every new Ansible event
                quiet (bool): Disable console output
        Returns:
            ((int, dict)):
                (int): The return value
                (dict): The results of the run
    """
    inventory: Optional[dict] = deep_get(kwargs, DictPath("inventory"), None)
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)
    quiet: bool = deep_get(kwargs, DictPath("quiet"), True)

    forks = deep_get(ansible_configuration, DictPath("ansible_forks"))

    ansible_results: dict = {}

    inventories: Union[dict, list[FilePath]] = []

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
                                      selection: list[str], **kwargs: Any) -> tuple[int, dict]:
    """
    Run a playbook on selected nodes.

        Parameters:
            playbook (FilePath): The playbook to run
            selection ([str]): The hosts to run the play on
            kwargs (dict):
                values (dict): Extra values to set for the hosts
                verbose (bool): Output status updates for every new Ansible event
                quiet (bool): Disable console output
        Returns:
            ((int, dict)):
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

    values: dict[str, Any] = deep_get(kwargs, DictPath("values"), {})
    verbose: bool = deep_get(kwargs, DictPath("verbose"), False)
    quiet: bool = deep_get(kwargs, DictPath("quiet"), True)

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


def ansible_ping(selection: Optional[list[str]] = None) -> list[tuple[str, str]]:
    """
    Ping all selected hosts.

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

    playbook_path = get_playbook_path(FilePath("ping.yaml"))
    _retval, ansible_results = ansible_run_playbook_on_selection(playbook_path,
                                                                 selection=selection, quiet=False)

    for host in ansible_results:
        for task in deep_get(ansible_results, DictPath(host), []):
            unreachable = deep_get(task, DictPath("unreachable"))
            skipped = deep_get(task, DictPath("skipped"))
            stderr_lines: list[str] = deep_get(task, DictPath("stderr_lines"), [])
            retval = deep_get(task, DictPath("retval"))
            status = ansible_extract_failure(retval,
                                             stderr_lines,
                                             skipped=skipped, unreachable=unreachable)
            if stderr_lines:
                status += f" ({'\\n'.join(stderr_lines)})"
            host_status.append((host, status))
    ansible_configuration["save_logs"] = save_logs_tmp

    return host_status


def __ansible_run_event_handler_cb(data: dict) -> bool:
    if deep_get(data, DictPath("event"), "") in ("runner_on_failed", "runner_on_async_failed"):
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeStr("  • ", "separator"),
                        ANSIThemeStr("Task", "action"),
                        ANSIThemeStr(": ", "default"),
                        ANSIThemeStr(f"{task}", "play"),
                        ANSIThemeStr(" ", "default"),
                        ANSIThemeStr("failed", "error"),
                        ANSIThemeStr(" on ", "default"),
                        ANSIThemeStr(f"{host}", "hostname")])
        for res in deep_get(data, DictPath("event_data#res#results"), []):
            msg = deep_get(res, DictPath("msg"), "")
            if msg:
                ansithemeprint([ANSIThemeStr("    ", "default"),
                                ANSIThemeStr("Error", "error"),
                                ANSIThemeStr(":", "default")])
                ansithemeprint([ANSIThemeStr(f"      {msg}", "default")])
    elif deep_get(data, DictPath("event"), "") == "runner_on_unreachable":
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeStr("  • ", "separator"),
                        ANSIThemeStr("Task", "action"),
                        ANSIThemeStr(": ", "default"),
                        ANSIThemeStr(f"{task}", "play"),
                        ANSIThemeStr(" ", "default"),
                        ANSIThemeStr("failed", "error"),
                        ANSIThemeStr("; ", "default"),
                        ANSIThemeStr(f"{host}", "hostname"),
                        ANSIThemeStr(" unreachable", "default")])
    return True


# pylint: disable-next=too-many-branches,too-many-statements
def __ansible_run_event_handler_verbose_cb(data: dict) -> bool:
    if deep_get(data, DictPath("event"), "") == "verbose":
        print(deep_get(data, DictPath("stdout"), ""))
    if deep_get(data, DictPath("event"), "") == "runner_on_start":
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeStr("  • ", "separator"),
                        ANSIThemeStr("Task", "action"),
                        ANSIThemeStr(": ", "default"),
                        ANSIThemeStr(f"{task}", "play"),
                        ANSIThemeStr(" ", "default"),
                        ANSIThemeStr("started", "phase"),
                        ANSIThemeStr(" on ", "default"),
                        ANSIThemeStr(f"{host}", "hostname")])
    elif deep_get(data, DictPath("event"), "") in ("runner_on_ok", "runner_on_async_ok"):
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeStr("  • ", "separator"),
                        ANSIThemeStr("Task", "action"),
                        ANSIThemeStr(": ", "default"),
                        ANSIThemeStr(f"{task}", "play"),
                        ANSIThemeStr(" ", "default"),
                        ANSIThemeStr("succeeded", "success"),
                        ANSIThemeStr(" on ", "default"),
                        ANSIThemeStr(f"{host}", "hostname")])
    elif deep_get(data, DictPath("event"), "") in ("runner_on_failed", "runner_on_async_failed"):
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeStr("  • ", "separator"),
                        ANSIThemeStr("Task", "action"),
                        ANSIThemeStr(": ", "default"),
                        ANSIThemeStr(f"{task}", "play"),
                        ANSIThemeStr(" ", "default"),
                        ANSIThemeStr("failed", "error"),
                        ANSIThemeStr(" on ", "default"),
                        ANSIThemeStr(f"{host}", "hostname")])
        for res in deep_get(data, DictPath("event_data#res#results"), []):
            if "stdout_lines" in res or "stderr_lines" in res:
                item = deep_get(res, DictPath("item"), "")
                ansithemeprint([ANSIThemeStr("    ", "default"),
                                ANSIThemeStr("Item", "header"),
                                ANSIThemeStr(":", "default"),
                                ANSIThemeStr(f"{item}", "default")])
            msg = deep_get(res, DictPath("msg"), "")
            if msg:
                ansithemeprint([ANSIThemeStr("    ", "default"),
                                ANSIThemeStr("Error", "error"),
                                ANSIThemeStr(":", "default")])
                ansithemeprint([ANSIThemeStr(f"      {msg}", "default")])
            if "stdout_lines" in res or "stderr_lines" in res:
                stdout_lines = deep_get(res, DictPath("stdout_lines"), [])
                stderr_lines = deep_get(res, DictPath("stderr_lines"), [])
                if stdout_lines:
                    ansithemeprint([ANSIThemeStr("    ", "default"),
                                    ANSIThemeStr("stdout", "default"),
                                    ANSIThemeStr(":", "default")])
                    for line in stdout_lines:
                        ansithemeprint([ANSIThemeStr("      ", "default"),
                                        ANSIThemeStr(line.replace("\x00", "<NUL>"), "default")])
                if stderr_lines:
                    ansithemeprint([ANSIThemeStr("    ", "default"),
                                    ANSIThemeStr("stderr", "error"),
                                    ANSIThemeStr(":", "default")])
                    for line in stderr_lines:
                        ansithemeprint([ANSIThemeStr("      ", "default"),
                                        ANSIThemeStr(line.replace("\x00", "<NUL>"), "default")])

        msg_lines = deep_get(data, DictPath("event_data#res#msg"), "").splitlines()
        if msg_lines:
            ansithemeprint([ANSIThemeStr("    ", "default"),
                            ANSIThemeStr("Error", "error"),
                            ANSIThemeStr(":", "default")])
            for line in msg_lines:
                ansithemeprint([ANSIThemeStr("      ", "default"),
                                ANSIThemeStr(line.replace("\x00", "<NUL>"), "default")])
        stdout_lines = deep_get(data, DictPath("event_data#res#stdout_lines"), [])
        stderr_lines = deep_get(data, DictPath("event_data#res#stderr_lines"), [])
        if stdout_lines:
            ansithemeprint([ANSIThemeStr("    ", "default"),
                            ANSIThemeStr("stdout", "default"),
                            ANSIThemeStr(":", "default")])
            for line in stdout_lines:
                ansithemeprint([ANSIThemeStr("      ", "default"),
                                ANSIThemeStr(line.replace("\x00", "<NUL>"), "default")])
        if stderr_lines:
            ansithemeprint([ANSIThemeStr("    ", "default"),
                            ANSIThemeStr("stderr", "error"),
                            ANSIThemeStr(":", "default")])
            for line in stderr_lines:
                ansithemeprint([ANSIThemeStr("      ", "default"),
                                ANSIThemeStr(line.replace("\x00", "<NUL>"), "default")])
    elif deep_get(data, DictPath("event"), "") == "runner_on_unreachable":
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeStr("  • ", "separator"),
                        ANSIThemeStr("Task", "action"),
                        ANSIThemeStr(": ", "default"),
                        ANSIThemeStr(f"{task}", "play"),
                        ANSIThemeStr(" ", "default"),
                        ANSIThemeStr("failed", "error"),
                        ANSIThemeStr("; ", "default"),
                        ANSIThemeStr(f"{host}", "hostname"),
                        ANSIThemeStr(" unreachable", "default")])
    elif deep_get(data, DictPath("event"), "") == "runner_on_skipped":
        host = deep_get(data, DictPath("event_data#host"), "<unset>")
        task = deep_get(data, DictPath("event_data#task"), "<unset>")
        ansithemeprint([ANSIThemeStr("  • ", "separator"),
                        ANSIThemeStr("Task", "action"),
                        ANSIThemeStr(": ", "default"),
                        ANSIThemeStr(f"{task}", "play"),
                        ANSIThemeStr(" ", "default"),
                        ANSIThemeStr("skipped", "none"),
                        ANSIThemeStr(" on ", "default"),
                        ANSIThemeStr(f"{host}", "hostname")])
    return True
