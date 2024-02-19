#! /usr/bin/env python3
# Requires: python3 (>= 3.8)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Ansible-related helpers
"""

from datetime import datetime
import errno
from pathlib import Path, PurePath
import re
import sys
from typing import Any, cast, Dict, List, Optional, Set, Tuple, Union
try:
	import yaml
except ModuleNotFoundError:  # pragma: no cover
	# This is acceptable; we don't benefit from a backtrace or log message
	sys.exit("ModuleNotFoundError: Could not import yaml; you may need to (re-)run `cmt-install` or `pip3 install PyYAML`; aborting.")

import cmtlib
from cmtio import check_path, join_securitystatus_set, secure_mkdir, secure_rm, secure_rmdir
from cmtio_yaml import secure_read_yaml, secure_write_yaml
from cmtpaths import HOMEDIR
from cmtpaths import ANSIBLE_DIR, ANSIBLE_PLAYBOOK_DIR, ANSIBLE_LOG_DIR
from cmtpaths import ANSIBLE_INVENTORY
from ansithemeprint import ANSIThemeString, ansithemeprint
from cmttypes import deep_get, deep_set, DictPath, FilePath, FilePathAuditError, SecurityChecks, SecurityStatus, ProgrammingError

ansible_results: Dict = {}

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
	sys.exit("ModuleNotFoundError: Could not import ansible_runner; you may need to (re-)run `cmt-install` or `pip3 install ansible-runner`; aborting.")

# Exit if the ansible directory does not exist
if not Path(ANSIBLE_DIR).exists():
	# This is acceptable; we don't benefit from a backtrace or log message
	sys.exit(f"{ANSIBLE_DIR} not found; try (re-)running cmt-install")

# Exit if the ansible log directory does not exist
if not Path(ANSIBLE_LOG_DIR).exists():
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
			path (FilePath): The playbook path with the highest priority
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
def populate_playbooks_from_paths(paths: List[FilePath]) -> List[Tuple[List[ANSIThemeString], FilePath]]:
	"""
	Populate a playbook list

		Parameters:
			paths (list[FilePath]): A list of paths to playbooks
		Returns:
			list[(description, playbookpath)]: A playbook list for use with run_playbooks()
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
		tmp = yaml_regex.match(pathname)
		if tmp is None:
			raise ValueError(f"The playbook filename “{pathname}“ does not end with .yaml or .yml; this is most likely a programming error.")

		playbookname = tmp[1]

		# The playbook directory itself may be a symlink. This is expected behaviour when installing from a git repo,
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

		violations = check_path(playbook_dir, checks = checks)
		if violations != [SecurityStatus.OK]:
			violations_joined = join_securitystatus_set(",", set(violations))
			raise FilePathAuditError(f"Violated rules: {violations_joined}", path = playbook_dir)

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

		d = secure_read_yaml(playbookpath, checks = checks)
		description = None
		t_description = deep_get(d[0], DictPath("vars#metadata#description"), "")
		if t_description:
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

	if not (isinstance(playbooks[0], tuple) and len(playbooks[0]) == 2 and isinstance(playbooks[0][0], list) and isinstance(playbooks[0][1], str)):
		raise TypeError(f"playbooks[] is wrong type; expected: [([{ANSIThemeString}], {FilePath})]")

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
		playbook_data = secure_read_yaml(FilePath(playbook_path), checks = checks)

		ansithemeprint(playbook_string +
			       [ANSIThemeString(" (path: ", "default"),
				ANSIThemeString(f"{playbook_path}", "path"),
			        ANSIThemeString(")", "default")])
		# None of our playbooks have more than one play per file
		summary = deep_get(playbook_data[0], DictPath("vars#metadata#summary"), {})
		if not summary:
			ansithemeprint([ANSIThemeString("      Error", "error"),
					ANSIThemeString(": playbook lacks a summary; please file a bug report if this isn't a locally modified playbook!", "default")],
				       stderr = True)
		for section_description, section_data in summary.items():
			ansithemeprint([ANSIThemeString(f"      {section_description}:", "emphasis")])
			for section_item in section_data:
				description = deep_get(section_item, DictPath("description"), "")
				ansithemeprint([ANSIThemeString(f"        {description}", "default")])

def ansible_get_inventory_dict() -> Dict:
	"""
        Get the Ansible inventory and return it as a dict

		Returns:
			d (dict): A dictionary with an Ansible inventory
	"""

	if not Path(ANSIBLE_INVENTORY).exists():
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

def ansible_get_inventory_pretty(groups: Optional[List[str]] = None, highlight: bool = False,
				 include_groupvars: bool = False, include_hostvars: bool = False,
				 include_hosts: bool = True) -> Union[List[str], List[List[ANSIThemeString]]]:
	"""
        Get the Ansible inventory and return it neatly formatted

		Parameters:
			groups (list[str]): What groups to include
			highlight (bool): Apply syntax highlighting?
			include_groupvars (bool): Should group variables be included
			include_hostvars (bool): Should host variables be included
			include_hosts (bool): Should hosts be included
		Returns:
			dump (list[str]): An unformatted list of strings or formatted list of themearrays
	"""

	tmp = {}

	if not Path(ANSIBLE_INVENTORY).exists():
		return []

	d = secure_read_yaml(ANSIBLE_INVENTORY)

	# We want the entire inventory
	if groups is None or not groups:
		tmp = d
	else:
		if not (isinstance(groups, list) and len(groups) > 0 and isinstance(groups[0], str)):
			raise TypeError(f"groups is type: {type(groups)}, expected {list}")
		for group in groups:
			item = d.pop(group, None)
			if item is not None:
				tmp[group] = item

	# OK, now we have a dict with only the groups we are interested in;
	# time for further post-processing

	# do we want groupvars?
	if not include_groupvars:
		for group in tmp:
			tmp[group].pop("vars", None)
	else:
		for group in tmp:
			if tmp[group].get("vars") is None or tmp[group].get("vars") == {}:
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

	dump: List[Union[List[ANSIThemeString], str]] = \
		yaml.safe_dump(tmp, default_flow_style = False).replace(r"''", "").replace("null", "").replace("{}", "").splitlines()

	if highlight and len(dump) > 0:
		i = 0
		list_regex = re.compile(r"^(\s*)((- )+)(.*)")
		key_value_regex = re.compile(r"^(.*?)(:)(.*)")
		for i, data in enumerate(dump):
			# Is it a list?
			tmp2 = list_regex.match(data)
			if tmp2 is not None:
				indent = tmp2[1]
				listmarker = tmp2[2]
				item = tmp2[4]
				dump[i] = [ANSIThemeString(indent, "default"),
					   ANSIThemeString(listmarker, "yaml_list"),
					   ANSIThemeString(item, "yaml_value")]
				continue

			# Is it key: value?
			tmp2 = key_value_regex.match(data)
			if tmp2 is not None:
				key = tmp2[1]
				separator = tmp2[2]
				value = tmp2[3]
				dump[i] = [ANSIThemeString(key, "yaml_key"),
					   ANSIThemeString(separator, "yaml_key_separator"),
					   ANSIThemeString(value, "yaml_value")]
				continue

			# Nope, then we will use default format
			dump[i] = [ANSIThemeString(dump[i], "default")]

	return dump

def ansible_get_hosts_by_group(inventory: FilePath, group: str) -> List[str]:
	"""
	Get the list of hosts belonging to a group

		Parameters:
			inventory (FilePath): The inventory to use
			group (str): The group to return hosts for
		Returns:
			hosts (list[str]): A list of hosts
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
			groups (list[str]): A list of groups
	"""

	groups = []

	if not Path(inventory).exists():
		return []

	d = secure_read_yaml(inventory)

	for group in d:
		groups.append(group)

	return groups

def ansible_get_groups_by_host(inventory_dict: Dict, host: str) -> List[str]:
	"""
	Given an inventory, returns the groups a host belongs to

		Parameters:
			inventory_dict (dict): An Ansible inventory
			host (str): The host to return groups for
		Returns:
			groups (list[str]): A list of groups
	"""

	groups = []

	if not isinstance(inventory_dict, dict):
		raise TypeError(f"inventory dict is type: {type(inventory_dict)}, expected {dict}")

	if not isinstance(host, str):
		raise TypeError(f"host is type: {type(host)}, expected str")

	for group in inventory_dict:
		if inventory_dict[group].get("hosts") and host in inventory_dict[group]["hosts"]:
			groups.append(group)

	return groups

def __ansible_create_inventory(inventory: FilePath, overwrite: bool = False, temporary: bool = False) -> bool:
	"""
	Create a new inventory at the path given if no inventory exists

		Parameters:
			inventory (FilePath): A path where to create a new inventory (if non-existing)
			overwrite (bool): True: Overwrite the existing inventory
			temporary (bool): Is the file a tempfile? If so we need to disable the check for parent permissions
		Return:
			(bool): True if inventory was created, False if nothing was done
	"""

	if not isinstance(inventory, str):
		raise TypeError(f"inventory is type: {type(inventory)}, expected str")
	if not isinstance(overwrite, bool):
		raise TypeError(f"inventory is type: {type(overwrite)}, expected bool")

	# Do not create anything if the inventory exists;
	# unless overwrite is set
	if Path(inventory).exists() and not overwrite:
		return False

	# If the ansible directory does not exist, create it
	secure_mkdir(ANSIBLE_DIR, permissions = 0o755, exit_on_failure = True)

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
		deep_set(d, DictPath("all#vars#ansible_user"), ansible_user, create_path = True)

	if (ansible_password := deep_get(ansible_configuration, DictPath("ansible_password"))) is not None:
		deep_set(d, DictPath("all#vars#ansible_ssh_pass"), ansible_password, create_path = True)

	if deep_get(ansible_configuration, DictPath("disable_strict_host_key_checking"), False):
		deep_set(d, DictPath("ansible_ssh_common_args"), "-o StrictHostKeyChecking=no", create_path = True)

	secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, temporary = temporary)

	return True

def ansible_create_groups(inventory: FilePath, groups: List[str], temporary: bool = False) -> bool:
	"""
	Create new groups

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The groups to create
			temporary (bool): Is the file a tempfile? If so we need to disable the check for parent permissions
		Returns:
			(bool): True on success, False on failure
		Raises:
			TypeError: group is not a str
	"""

	changed: bool = False

	if groups is None or not groups:
		return True

	if not Path(inventory).is_file():
		__ansible_create_inventory(inventory, overwrite = False, temporary = temporary)

	d = secure_read_yaml(inventory, temporary = temporary)

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
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True, temporary = temporary)

	return True

def ansible_set_vars(inventory: FilePath, group: str, values: Dict, temporary: bool = False) -> bool:
	"""
	Set one or several values for a group

		Parameters:
			inventory (FilePath): The path to the inventory
			group (str): The group to set variables for
			values (dict): The values to set
			temporary (bool): Is the file a tempfile? If so we need to disable the check for parent permissions
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if not (isinstance(inventory, str) and isinstance(group, str) and isinstance(values, dict) and isinstance(temporary, bool)):
		msg = [
			[("ansible_set_vars()", "emphasis"),
			 (" called with invalid argument(s):", "error")],
			[("inventory = ", "default"),
			 (f"“{inventory}“", "argument"),
			 (" (type: ", "default"),
			 (f"{type(inventory)}", "argument"),
			 (", expected: ", "default"),
			 ("FilePath", "argument"),
			 (")", "default")],
			[("group = ", "default"),
			 (f"“{group}“", "argument"),
			 (" (type: ", "default"),
			 (f"{type(group)}", "argument"),
			 (", expected: ", "default"),
			 ("str", "argument"),
			 (")", "default")],
			[("values = ", "default"),
			 (f"{values}", "argument"),
			 (" (type: ", "default"),
			 (f"{type(values)}", "argument"),
			 (", expected: ", "default"),
			 (f"{dict}", "argument"),
			 (")", "default")],
			[("temporary = ", "default"),
			 (f"{temporary}", "argument"),
			 (" (type: ", "default"),
			 (f"{type(temporary)}", "argument"),
			 (", expected: ", "default"),
			 ("bool", "argument"),
			 (")", "default")],
		]

		unformatted_msg, formatted_msg = ANSIThemeString.format_error_msg(msg)

		raise ProgrammingError(unformatted_msg,
				       subexception = TypeError,
				       formatted_msg = formatted_msg)

	if not (len(inventory) > 0 and len(group) > 0 and len(values) > 0):
		msg = [
			[("ansible_set_vars()", "emphasis"),
			 (" called with invalid argument(s):", "error")],
			[("inventory = ", "default"),
			 (f"“{inventory}“", "argument"),
			 (" (len: ", "default"),
			 (f"{len(inventory)}", "argument"),
			 (")", "default")],
			[("group = ", "default"),
			 (f"“{group}“", "argument"),
			 (" (len: ", "default"),
			 (f"{len(group)}", "argument"),
			 (")", "default")],
			[("values = ", "default"),
			 (f"{values}", "argument"),
			 (" (len: ", "default"),
			 (f"{len(values)}", "argument"),
			 (")", "default")],
		]

		unformatted_msg, formatted_msg = ANSIThemeString.format_error_msg(msg)

		raise ProgrammingError(unformatted_msg,
				       subexception = ValueError,
				       formatted_msg = formatted_msg)

	if not Path(inventory).is_file():
		__ansible_create_inventory(inventory, overwrite = False, temporary = temporary)

	d = secure_read_yaml(inventory, temporary = temporary)

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
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True, temporary = temporary)

	return True

def ansible_set_groupvars(inventory: FilePath, groups: List[str], groupvars: List[Tuple[str, Union[str, int]]], temporary: bool = False) -> bool:
	"""
	Set one or several vars for the specified groups

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The groups to set variables for
			groupvars (list[(str, str|int)]): The values to set
			temporary (bool): Is the file a tempfile? If so we need to disable the check for parent permissions
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if not (isinstance(inventory, str) and inventory and
	        isinstance(groups, list) and groups and isinstance(groups[0], str) and
		isinstance(groupvars, list) and groupvars and isinstance(groupvars[0], tuple) and
		len(groupvars[0]) == 2 and isinstance(groupvars[0][0], str) and isinstance(groupvars[0][1], (str, int)) and
		isinstance(temporary, bool)):
		msg = [
			[("ansible_set_groupvars()", "emphasis"),
			 (" called with invalid argument(s):", "error")],
			[("inventory = ", "default"),
			 (f"“{inventory}“", "argument"),
			 (" (type: ", "default"),
			 (f"{type(inventory)}", "argument"),
			 (", expected: ", "default"),
			 ("FilePath", "argument"),
			 (")", "default")],
			[("groups = ", "default"),
			 (f"“{groups}“", "argument"),
			 (" (type: ", "default"),
			 (f"{type(groups)}", "argument"),
			 (", expected: ", "default"),
			 ("{list}", "argument"),
			 (")", "default")],
			[("groupvars = ", "default"),
			 (f"{groupvars}", "argument"),
			 (" (type: ", "default"),
			 (f"{type(groupvars)}", "argument"),
			 (", expected: ", "default"),
			 ("[(str, str|int)]", "argument"),
			 (")", "default")],
			[("temporary = ", "default"),
			 (f"{temporary}", "argument"),
			 (" (type: ", "default"),
			 (f"{type(temporary)}", "argument"),
			 (", expected: ", "default"),
			 ("bool", "argument"),
			 (")", "default")],
		]

		unformatted_msg, formatted_msg = ANSIThemeString.format_error_msg(msg)

		raise ProgrammingError(unformatted_msg,
				       subexception = TypeError,
				       formatted_msg = formatted_msg)

	d = secure_read_yaml(inventory, temporary = temporary)

	for group in groups:
		# Silently ignore non-existing groups
		if not group in d:
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
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True, temporary = temporary)

	return True

# Set one or several vars for hosts in the group all
def ansible_set_hostvars(inventory: FilePath, hosts: List[str], hostvars: List[Tuple[str, Union[str, int]]], temporary: bool = False) -> bool:
	"""
	Set one or several vars for the specified hosts

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The hosts to set variables for
			hostvars (list[(str, str|int)]): The values to set
			temporary (bool): Is the file a tempfile? If so we need to disable the check for parent permissions
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if not (isinstance(inventory, str) and inventory and
		isinstance(hosts, list) and hosts and isinstance(hosts[0], str) and
		isinstance(hostvars, list) and hostvars and isinstance(hostvars[0], tuple) and
		len(hostvars[0]) == 2 and isinstance(hostvars[0][0], str) and isinstance(hostvars[0][1], (str, int)) and
		isinstance(temporary, bool)):
		msg = [
			[("ansible_set_hostvars()", "emphasis"),
			 (" called with invalid argument(s):", "error")],
			[("inventory = ", "default"),
			 (f"“{inventory}“", "argument"),
			 (" (type: ", "default"),
			 (f"{type(inventory)}", "argument"),
			 (", expected: ", "default"),
			 ("FilePath", "argument"),
			 (")", "default")],
			[("hosts = ", "default"),
			 (f"“{hosts}“", "argument"),
			 (" (type: ", "default"),
			 (f"{type(hosts)}", "argument"),
			 (", expected: ", "default"),
			 ("{list}", "argument"),
			 (")", "default")],
			[("hostvars = ", "default"),
			 (f"{hostvars}", "argument"),
			 (" (type: ", "default"),
			 (f"{type(hostvars)}", "argument"),
			 (", expected: ", "default"),
			 ("[(str, str|int)]", "argument"),
			 (")", "default")],
			[("temporary = ", "default"),
			 (f"{temporary}", "argument"),
			 (" (type: ", "default"),
			 (f"{type(temporary)}", "argument"),
			 (", expected: ", "default"),
			 ("bool", "argument"),
			 (")", "default")],
		]

		unformatted_msg, formatted_msg = ANSIThemeString.format_error_msg(msg)

		raise ProgrammingError(unformatted_msg,
				       subexception = TypeError,
				       formatted_msg = formatted_msg)

	d = secure_read_yaml(inventory, temporary = temporary)

	for host in hosts:
		# Silently ignore non-existing hosts
		if not host in d["all"]["hosts"]:
			continue

		if d["all"]["hosts"][host] is None:
			d["all"]["hosts"][host] = {}

		for key, value in hostvars:
			# Set the variable (overwriting previous value)
			d["all"]["hosts"][host][key] = value
			changed = True

	if changed:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True, temporary = temporary)

	return True

# Unset one or several vars in the specified groups
def ansible_unset_groupvars(inventory: FilePath, groups: List[str], groupvars: List[str], temporary: bool = False) -> bool:
	"""
	Unset one or several vars for the specified groups

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The groups to unset variables for
			groupvars (list[(str]): The values to unset
			temporary (bool): Is the file a tempfile? If so we need to disable the check for parent permissions
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if not (isinstance(inventory, str) and inventory and
	        isinstance(groups, list) and groups and isinstance(groups[0], str) and
		isinstance(groupvars, list) and groupvars and isinstance(groupvars[0], str) and groupvars[0] and
		isinstance(temporary, bool)):
		msg = [
			[("ansible_set_groupvars()", "emphasis"),
			 (" called with invalid argument(s):", "error")],
			[("inventory = ", "default"),
			 (f"“{inventory}“", "argument"),
			 (" (type: ", "default"),
			 (f"{type(inventory)}", "argument"),
			 (", expected: ", "default"),
			 ("FilePath", "argument"),
			 (")", "default")],
			[("groups = ", "default"),
			 (f"“{groups}“", "argument"),
			 (" (type: ", "default"),
			 (f"{type(groups)}", "argument"),
			 (", expected: ", "default"),
			 (f"{list}", "argument"),
			 (")", "default")],
			[("groupvars = ", "default"),
			 (f"{groupvars}", "argument"),
			 (" (type: ", "default"),
			 (f"{type(groupvars)}", "argument"),
			 (", expected: ", "default"),
			 (f"{[str]}", "argument"),
			 (")", "default")],
			[("temporary = ", "default"),
			 (f"{temporary}", "argument"),
			 (" (type: ", "default"),
			 (f"{type(temporary)}", "argument"),
			 (", expected: ", "default"),
			 ("bool", "argument"),
			 (")", "default")],
		]

		unformatted_msg, formatted_msg = ANSIThemeString.format_error_msg(msg)

		raise ProgrammingError(unformatted_msg,
				       subexception = TypeError,
				       formatted_msg = formatted_msg)

	d = secure_read_yaml(inventory, temporary = temporary)

	for group in groups:
		# Silently ignore non-existing groups
		if not group in d:
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
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True, temporary = temporary)

	return True

# Unset one or several vars for the specified host in the group all
def ansible_unset_hostvars(inventory: FilePath, hosts: List[str], hostvars: List[str], temporary: bool = False) -> bool:
	"""
	Unset one or several vars for the specified hosts

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The hosts to unset variables for
			hostvars (list[(str]): The values to unset
			temporary (bool): Is the file a tempfile? If so we need to disable the check for parent permissions
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if not (isinstance(inventory, str) and inventory and
		isinstance(hosts, list) and hosts and isinstance(hosts[0], str) and
		isinstance(hostvars, list) and hostvars and isinstance(hostvars[0], str) and hostvars[0] and
		isinstance(temporary, bool)):
		msg = [
			[("ansible_set_hostvars()", "emphasis"),
			 (" called with invalid argument(s):", "error")],
			[("inventory = ", "default"),
			 (f"“{inventory}“", "argument"),
			 (" (type: ", "default"),
			 (f"{type(inventory)}", "argument"),
			 (", expected: ", "default"),
			 ("FilePath", "argument"),
			 (")", "default")],
			[("hosts = ", "default"),
			 (f"“{hosts}“", "argument"),
			 (" (type: ", "default"),
			 (f"{type(hosts)}", "argument"),
			 (", expected: ", "default"),
			 (f"{list}", "argument"),
			 (")", "default")],
			[("hostvars = ", "default"),
			 (f"{hostvars}", "argument"),
			 (" (type: ", "default"),
			 (f"{type(hostvars)}", "argument"),
			 (", expected: ", "default"),
			 (f"{[str]}", "argument"),
			 (")", "default")],
			[("temporary = ", "default"),
			 (f"{temporary}", "argument"),
			 (" (type: ", "default"),
			 (f"{type(temporary)}", "argument"),
			 (", expected: ", "default"),
			 ("bool", "argument"),
			 (")", "default")],
		]

		unformatted_msg, formatted_msg = ANSIThemeString.format_error_msg(msg)

		raise ProgrammingError(unformatted_msg,
				       subexception = TypeError,
				       formatted_msg = formatted_msg)

	d = secure_read_yaml(inventory, temporary = temporary)

	for host in hosts:
		# Silently ignore non-existing hosts
		if not host in d["all"]["hosts"]:
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
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True, temporary = temporary)

	return True

def ansible_add_hosts(inventory: FilePath, hosts: List[str], group: str = "", skip_all: bool = False, temporary: bool = False) -> bool:
	"""
	Add hosts to the ansible inventory; if the inventory does not exist, create it

		Parameters:
			inventory (FilePath): The path to the inventory
			hosts (list[str]): The hosts to add to the inventory
			group (str): The group to add the hosts to
			skip_all (bool): If True we do not create a new inventory if it does not exist
			temporary (bool): Is the file a tempfile? If so we need to disable the check for parent permissions
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if not hosts:
		return True

	d: Dict = {}

	# The inventory does not exist; if the user specified skip_all
	# we do not mind, otherwise we need to create it
	if not Path(inventory).is_file():
		if skip_all and group != "all":
			changed = True
		else:
			__ansible_create_inventory(inventory, overwrite = False)
			d = secure_read_yaml(inventory, temporary = temporary)
	else:
		d = secure_read_yaml(inventory, temporary = temporary)

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

			if not host in d[group]["hosts"]:
				d[group]["hosts"][host] = {}
				changed = True

	if changed:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True, temporary = temporary)

	return True

# Remove hosts from ansible groups
def ansible_remove_hosts(inventory: FilePath, hosts: List[str], group: Optional[str] = None, temporary: bool = False) -> bool:
	"""
	Remove hosts from the inventory

		Parameters:
			inventory (FilePath): The inventory to use
			hosts (list[str]): The hosts to remove
			group (str): The group to remove the hosts from
			temporary (bool): Is the file a tempfile? If so we need to disable the check for parent permissions
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	# Treat empty or zero-length hosts as a programming error
	if hosts is None or len(hosts) == 0:
		raise ValueError("None or zero-length hosts; this is a programming error")

	# Treat empty or zero-length group as a programming error
	if group is None or len(group) == 0:
		raise ValueError("None or zero-length group; this is a programming error")

	if not Path(inventory).is_file():
		return False

	d = secure_read_yaml(inventory, temporary = temporary)

	for host in hosts:
		if group in d and d[group].get("hosts") is not None:
			if host in d[group]["hosts"]:
				d[group]["hosts"].pop(host, None)
				changed = True

	if changed:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True, temporary = temporary)

	return True

def ansible_remove_groups(inventory: FilePath, groups: List[str], force: bool = False, temporary: bool = False) -> bool:
	"""
	Remove groups from the inventory

		Parameters:
			inventory (FilePath): The inventory to use
			groups (list[str]): The groups to remove
			force (bool): Force allows for removal of non-empty groups
			temporary (bool): Is the file a tempfile? If so we need to disable the check for parent permissions
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	# Treat empty or zero-length groups as a programming error
	if groups is None or len(groups) == 0:
		raise ValueError("None or zero-length group; this is a programming error")

	if not Path(inventory).is_file():
		return False

	d = secure_read_yaml(inventory, temporary = temporary)

	for group in groups:
		if d.get(group) is None:
			continue

		if d[group].get("hosts") is not None and not force:
			continue

		d.pop(group)
		changed = True

	if changed:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True, temporary = temporary)

	return True

def ansible_get_logs() -> List[Tuple[str, str, FilePath, datetime]]:
	"""
	Returns a list of all available logs

		Returns:
			logs (tuple(full_name, name, date, path)): A list of full name, name, date, and path to logs
	"""

	logs = []

	timestamp_regex = re.compile(r"^(\d{4}-\d\d-\d\d_\d\d:\d\d:\d\d\.\d+)_(.*)")

	for path in Path(ANSIBLE_LOG_DIR).iterdir():
		filename = str(path.name)
		tmp = timestamp_regex.match(filename)
		if tmp is not None:
			date = datetime.strptime(tmp[1], "%Y-%m-%d_%H:%M:%S.%f")
			name = tmp[2]
			logs.append((filename, name, FilePath(str(path)), date))
		else:
			raise ValueError(f"Could not parse {filename}")
	return logs

def ansible_extract_failure(retval: int, error_msg_lines: List[str], skipped: bool = False, unreachable: bool = False) -> str:
	"""
	Given error information from an ansible run, return a suitable error message

		Parameters:
			retval (int): The retval from the run
			error_msg_lines (list[str]): A list of error messages
			skipped (bool): Was the task skipped?
			unreachable (bool): Was the target unreachable?
		Returns:
			status (str): A status string
	"""

	status = ""

	if unreachable:
		for line in error_msg_lines:
			if "Name or service not known" in line:
				status = "COULD NOT RESOLVE"
				break
			if "Permission denied" in line:
				status = "PERMISSION DENIED"
				break
			if "The module failed to execute correctly" in line:
				status = "MISSING INTERPRETER?"
				break
			if "No route to host" in line:
				status = "NO ROUTE TO HOST"
				break
			if "Connection timed out" in line:
				status = "CONNECTION TIMED OUT"
				break
		if len(status) == 0:
			status = "UNREACHABLE (unknown reason)"
	elif skipped:
		status = "SKIPPED"
	else:
		if retval != 0:
			status = "FAILED"
		else:
			status = "SUCCESS"

	return status

def ansible_results_extract(event: Dict) -> Tuple[int, Dict]:
	"""
	Extract a result from an Ansible play

		Parameters:
			event (dict): The output from the run
		Returns:
			(retval(int), result(dict)):
				retval: 0 on success, -1 if host is unreachable, retval on other failure,
				result: A dict
	"""

	__retval: Optional[int] = -1

	# Special events
	if deep_get(event, DictPath("event"), "") == "playbook_on_no_hosts_matched":
		d: Dict = {
			"task": "",
			"start_date": "",
			"end_date": "",
			"retval": __retval,
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

	host = deep_get(event, DictPath("event_data#host"), "")
	if len(host) == 0:
		return 0, {}

	task = deep_get(event, DictPath("event_data#task"), "")
	if len(task) == 0:
		return 0, {}

	ansible_facts = deep_get(event, DictPath("event_data#res#ansible_facts"), {})

	skipped = deep_get(event, DictPath("event"), "") == "runner_on_skipped"
	failed = deep_get(event, DictPath("event"), "") == "runner_on_failed"
	unreachable = deep_get(event, DictPath("event_data#res#unreachable"), False)

	if unreachable:
		__retval = -1
	elif skipped or deep_get(event, DictPath("event"), "") == "runner_on_ok":
		__retval = 0
	elif failed:
		__retval = -1
	else:
		__retval = deep_get(event, DictPath("event_data#res#rc"))

	if task.startswith("hide_on_ok: "):
		if __retval == 0:
			__retval = None
		else:
			task = task[len("hide_on_ok: "):]
	elif task == "Gathering Facts" and __retval == 0:
		__retval = None

	if __retval is None:
		return 0, {}

	msg = deep_get(event, DictPath("event_data#res#msg"), "")
	msg_lines = []
	if len(msg) > 0:
		msg_lines = msg.split("\n")

	start_date_timestamp = deep_get(event, DictPath("event_data#start"))
	end_date_timestamp = deep_get(event, DictPath("event_data#end"))

	stdout = deep_get(event, DictPath("event_data#res#stdout"), "")
	stderr = deep_get(event, DictPath("event_data#res#stderr"), "")
	stdout_lines = deep_get(event, DictPath("event_data#res#stdout_lines"), [])
	stderr_lines = deep_get(event, DictPath("event_data#res#stderr_lines"), [])

	if len(stdout_lines) == 0 and len(stdout) > 0:
		stdout_lines = stdout.split("\n")
	if len(stderr_lines) == 0 and len(stderr) > 0:
		stderr_lines = stderr.split("\n")

	d = {
		"task": task,
		"start_date": start_date_timestamp,
		"end_date": end_date_timestamp,
		"retval": __retval,
		"no_hosts_matched": False,
		"unreachable": unreachable,
		"status": "UNKNOWN",
		"skipped": skipped,
		"stdout_lines": [],
		"stderr_lines": [],
		"msg_lines": [],
		"ansible_facts": ansible_facts,
	}

	if not unreachable and __retval == 0:
		d["status"] = "SUCCESS"

	if len(msg_lines) > 0 or len(stdout_lines) > 0 or len(stderr_lines) > 0:
		if len(stdout_lines) > 0:
			d["stdout_lines"] = stdout_lines
		if len(stderr_lines) > 0:
			d["stderr_lines"] = stderr_lines
		# We do not want msg unless stdout_lines and stderr_lines are empty
		# XXX: Or can it be used to get a sequential log when there's both
		# stdout and stderr?
		if len(stdout_lines) == 0 and len(stderr_lines) == 0 and len(msg_lines) > 0:
			if __retval != 0:
				d["stderr_lines"] = msg_lines
			else:
				d["msg_lines"] = msg_lines
	else:
		d["stdout_lines"] = ["<no output>"]

	error_msg_lines = stderr_lines
	if len(error_msg_lines) == 0:
		error_msg_lines = msg_lines
	d["status"] = ansible_extract_failure(__retval, error_msg_lines, skipped = skipped, unreachable = unreachable)

	return __retval, d

def ansible_results_add(event: Dict) -> int:
	"""
	Add the result of an Ansible play to the ansible results

		Parameters:
			event (dict): The output from the run
		Returns:
			(int): 0 on success, -1 if host is unreachable, retval on other failure
	"""
	global ansible_results  # pylint: disable=global-variable-not-assigned

	host = deep_get(event, DictPath("event_data#host"), "")
	__retval, d = ansible_results_extract(event)

	if len(d) > 0:
		if host not in ansible_results:
			ansible_results[host] = []
		ansible_results[host].append(d)

	return __retval

def ansible_delete_log(log: str) -> None:
	"""
	Delete a log file

		Parameters:
			log (str): The name of the log to delete
	"""

	logpath = Path(f"{ANSIBLE_LOG_DIR}/{log}")
	if logpath.exists():
		for file in logpath.iterdir():
			secure_rm(FilePath(str(file)))
		secure_rmdir(FilePath(str(logpath)))

def ansible_write_log(start_date: datetime, playbook: str, events: List[Dict]) -> None:
	"""
	Save an Ansible log entry to a file

		Parameters:
			start_date (date): A timestamp in the format YYYY-MM-DD_HH:MM:SS.ssssss
			playbook (str): The name of the playbook
			events (list[dict]): The list of Ansible runs
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
	secure_mkdir(FilePath(f"{ANSIBLE_LOG_DIR}/{directory_name}"), exit_on_failure = True)

	# Start by creating a file with metadata about the whole run
	d = {
		"playbook_path": playbook,
		"created_at": start_date,
	}

	metadata_path = FilePath(f"{ANSIBLE_LOG_DIR}/{directory_name}/metadata.yaml")
	secure_write_yaml(metadata_path, d, permissions = 0o600, sort_keys = False, temporary = temporary)

	i = 0

	for event in events:
		host = deep_get(event, DictPath("event_data#host"), "")
		if len(host) == 0:
			continue

		task = deep_get(event, DictPath("event_data#task"), "")
		if len(task) == 0:
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
		if len(msg) > 0:
			msg_lines = msg.split("\n")

		start_date_timestamp = deep_get(event, DictPath("event_data#start"))
		end_date_timestamp = deep_get(event, DictPath("event_data#end"))

		stdout = deep_get(event, DictPath("event_data#res#stdout"), "")
		stderr = deep_get(event, DictPath("event_data#res#stderr"), "")
		stdout_lines = deep_get(event, DictPath("event_data#res#stdout_lines"), "")
		stderr_lines = deep_get(event, DictPath("event_data#res#stderr_lines"), "")

		if len(stdout_lines) == 0 and len(stdout) > 0:
			stdout_lines = stdout.split("\n")
		if len(stderr_lines) == 0 and len(stderr) > 0:
			stderr_lines = stderr.split("\n")

		error_msg_lines = stderr_lines
		if len(error_msg_lines) == 0:
			error_msg_lines = msg_lines
		status = ansible_extract_failure(retval, error_msg_lines, skipped = skipped, unreachable = unreachable)

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

		if len(msg_lines) > 0 or len(stdout_lines) > 0 or len(stderr_lines) > 0:
			if len(stdout_lines) > 0:
				d["stdout_lines"] = stdout_lines
			if len(stderr_lines) > 0:
				d["stderr_lines"] = stderr_lines
			# We do not want msg unless stdout_lines and stderr_lines are empty
			# XXX: Or can it be used to get a sequential log when there's both
			# stdout and stderr?
			if len(stdout_lines) == 0 and len(stderr_lines) == 0 and len(msg_lines) > 0:
				if retval != 0:
					d["stderr_lines"] = msg_lines
				else:
					d["msg_lines"] = msg_lines
		else:
			d["stdout_lines"] = ["<no output>"]

		logentry_path = FilePath(f"{ANSIBLE_LOG_DIR}/{directory_name}/{filename}")
		secure_write_yaml(logentry_path, d, permissions = 0o600, sort_keys = False, temporary = temporary)

# pylint: disable-next=too-many-arguments
def ansible_print_task_results(task: str, msg_lines: List[str], stdout_lines: List[str], stderr_lines: List[str], retval: int,
			       unreachable: bool = False, skipped: bool = False, verbose: bool = False) -> None:
	"""
	Pretty-print the result of an Ansible task run

		Parameters:
			task (str): The name of the task
			msg_lines (list[str]): msg from tasks that does not split the output into stdout & stderr
			stdout_lines (list[str]): output from stdout
			stderr_lines (list[str]): output from stderr
			retval (int): The return value from the task
			unreachable (bool): Was the host unreachable?
			skipped (bool): Was the task skipped?
			verbose (bool): Should skipped tasks be outputted?
	"""

	if unreachable:
		ansithemeprint([ANSIThemeString("• ", "separator"),
				ANSIThemeString(f"{task}", "error")], stderr = True)
	elif skipped:
		if verbose:
			ansithemeprint([ANSIThemeString("• ", "separator"),
					ANSIThemeString(f"{task} [skipped]", "skip")], stderr = True)
			ansithemeprint([ANSIThemeString("", "default")])
		return
	elif retval != 0:
		ansithemeprint([ANSIThemeString("• ", "separator"),
				ANSIThemeString(f"{task}", "error"),
				ANSIThemeString(" (retval: ", "default"),
				ANSIThemeString(f"{retval}", "errorvalue"),
				ANSIThemeString(")", "default")], stderr = True)
	else:
		ansithemeprint([ANSIThemeString("• ", "separator"),
				ANSIThemeString(f"{task}", "success")])

	if len(msg_lines) > 0:
		ansithemeprint([ANSIThemeString("msg:", "header")])
		for line in msg_lines:
			ansithemeprint([ANSIThemeString(line.replace("\x00", "<NUL>"), "default")])
		ansithemeprint([ANSIThemeString("", "default")])

	if len(stdout_lines) > 0 or len(msg_lines) == 0 and len(stderr_lines) == 0:
		ansithemeprint([ANSIThemeString("stdout:", "header")])
		for line in stdout_lines:
			ansithemeprint([ANSIThemeString(line.replace("\x00", "<NUL>"), "default")])
		if len(stdout_lines) == 0:
			ansithemeprint([ANSIThemeString("<no output>", "none")])
		ansithemeprint([ANSIThemeString("", "default")])

	# If retval is not 0 we do not really care if stderr is empty
	if len(stderr_lines) > 0 or retval != 0:
		ansithemeprint([ANSIThemeString("stderr:", "header")])
		for line in stderr_lines:
			ansithemeprint([ANSIThemeString(line.replace("\x00", "<NUL>"), "default")], stderr = True)
		if len(stderr_lines) == 0:
			ansithemeprint([ANSIThemeString("<no output>", "none")])
		ansithemeprint([ANSIThemeString("", "default")])

def ansible_print_play_results(retval: int, __ansible_results: Dict, verbose: bool = False) -> None:
	"""
	Pretty-print the result of an Ansible play

		Parameters:
			retval (int): The return value from the play
			__ansible_results (opaque): The data from a playbook run
			verbose (bool): Should skipped tasks be outputted?
	"""

	count_total = 0
	count_task_total = 0
	count_no_hosts_match = 0
	count_unreachable = 0
	count_skip = 0
	count_success = 0
	count_fail = 0

	if retval != 0 and len(__ansible_results) == 0:
		ansithemeprint([ANSIThemeString("Failed to execute playbook; retval: ", "error"),
				ANSIThemeString(f"{retval}", "errorvalue")], stderr = True)
	else:
		for host in __ansible_results:
			count_total += 1

			plays = __ansible_results[host]
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
					elif retval == 0:
						ansithemeprint([ANSIThemeString(f"[{host}]", "success")])
					else:
						ansithemeprint([ANSIThemeString(f"[{host}]", "error")])
				if no_hosts_matched:
					count_no_hosts_match += 1
				elif unreachable:
					count_unreachable += 1
				elif skipped:
					count_skip += 1
				elif retval == 0:
					count_success += 1
				else:
					count_fail += 1

				if not no_hosts_matched:
					msg_lines = deep_get(play, DictPath("msg_lines"), "")
					stdout_lines = deep_get(play, DictPath("stdout_lines"), "")
					stderr_lines = deep_get(play, DictPath("stderr_lines"), "")
					ansible_print_task_results(task, msg_lines, stdout_lines, stderr_lines, retval, unreachable, skipped, verbose)

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
				ANSIThemeString(f"{count_no_hosts_match}\n", "numerical"),
				])

def ansible_run_playbook(playbook: FilePath, inventory: Optional[Dict] = None, verbose: bool = False) -> Tuple[int, Dict]:
	"""
	Run a playbook

		Parameters:
			playbook (FilePath): The playbook to run
			inventory (dict): An inventory dict with selection as the list of hosts to run on
			verbose (bool): Output status updates for every new Ansible event
		Returns:
			(retval(int), ansible_results(dict)): The return value and results from the run
	"""

	global ansible_results  # pylint: disable=global-statement

	forks = deep_get(ansible_configuration, DictPath("ansible_forks"))

	# Flush previous results
	ansible_results = {}

	inventories: Union[Dict, List[FilePath]] = []

	if inventory is None:
		inventories = [ANSIBLE_INVENTORY]
	else:
		inventories = inventory

	start_date = datetime.now()

	event_handler = None
	if verbose:
		event_handler = __ansible_run_event_handler_cb

	runner = ansible_runner.interface.run(json_mode = True, quiet = True, playbook = playbook, inventory = inventories, forks = forks,
					      event_handler = event_handler, envvars = { "ANSIBLE_JINJA2_NATIVE": True })

	retval = 0
	if runner is not None:
		for event in runner.events:
			_retval = ansible_results_add(event)
			if retval == 0 and _retval != 0:
				retval = _retval
		ansible_write_log(start_date, playbook, runner.events)

	return retval, ansible_results

# pylint: disable-next=unused-argument
def ansible_run_playbook_async(playbook: FilePath, inventory: Dict, verbose: bool = False) -> ansible_runner.runner.Runner:
	"""
	Run a playbook asynchronously

		Parameters:
			playbook (FilePath): The playbook to run
			inventory (dict): An inventory dict with selection as the list of hosts to run on

		Returns:
			runner: An ansible_runner.runner.Runner object
	"""

	forks = deep_get(ansible_configuration, DictPath("ansible_forks"))

	_thread, runner = ansible_runner.interface.run_async(json_mode = True, quiet = True, playbook = playbook, inventory = inventory,
							     forks = forks, finished_callback = __ansible_run_async_finished_cb, envvars = { "ANSIBLE_JINJA2_NATIVE": True })

	return runner

def ansible_run_playbook_on_selection(playbook: FilePath, selection: List[str], values: Optional[Dict] = None, verbose: bool = False) -> Tuple[int, Dict]:
	"""
	Run a playbook on selected nodes

		Parameters:
			playbook (FilePath): The playbook to run
			selection (list[str]): The hosts to run the play on
			values (dict): Extra values to set for the hosts
			verbose (bool): Output status updates for every new Ansible event
		Returns:
			The result from ansible_run_playbook()
			retval = -errno.ENOENT if the inventory is missing or empty
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

	if len(d) == 0:
		return -errno.ENOENT, {}

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

	return ansible_run_playbook(playbook, d, verbose)

def ansible_run_playbook_on_selection_async(playbook: FilePath, selection: List[str], values: Optional[Dict] = None,
					    inventory: Optional[Dict] = None, verbose: bool = False) -> ansible_runner.runner.Runner:
	"""
	Run a playbook on selected nodes

		Parameters:
			playbook (FilePath): The playbook to run
			selection (list[str]): The hosts to run the play on
			values (dict): Extra values to set for the hosts
			verbose (bool): Output status updates for every new Ansible event
		Returns:
			The result from ansible_run_playbook_async()
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
	if inventory is None:
		d = ansible_get_inventory_dict()
	else:
		d = inventory

	if len(d) == 0:
		return -errno.ENOENT, {}

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

	return ansible_run_playbook_async(playbook, d, verbose)

def ansible_ping(selection: List[str]) -> List[Tuple[str, str]]:
	"""
	Ping all selected hosts

		Parameters:
			selection (list[str]): A list of hostnames
		Returns:
			list[(hostname, status)]: The status of the pinged hosts
	"""

	save_logs_tmp = deep_get(ansible_configuration, DictPath("save_logs"), False)
	ansible_configuration["save_logs"] = False

	host_status = []

	if selection is None:
		selection = ansible_get_hosts_by_group(ANSIBLE_INVENTORY, "all")

	_retval, __ansible_results = ansible_run_playbook_on_selection(FilePath(str(PurePath(ANSIBLE_PLAYBOOK_DIR).joinpath("ping.yaml"))), selection = selection)

	for host in __ansible_results:
		for task in deep_get(__ansible_results, DictPath(host), []):
			unreachable = deep_get(task, DictPath("unreachable"))
			skipped = deep_get(task, DictPath("skipped"))
			stderr_lines = deep_get(task, DictPath("stderr_lines"))
			retval = deep_get(task, DictPath("retval"))
			status = ansible_extract_failure(retval, stderr_lines, skipped = skipped, unreachable = unreachable)
			host_status.append((host, status))
	ansible_configuration["save_logs"] = save_logs_tmp

	return host_status

def ansible_ping_async(selection: Optional[List[str]], inventory: Optional[Dict] = None) -> ansible_runner.runner.Runner:
	"""
	Ping all selected hosts asynchronously

		Parameters:
			selection (list[str]): A list of hostnames
		Returns:
			The result from ansible_run_playbook_async()
	"""

	if inventory is None:
		if selection is None:
			selection = ansible_get_hosts_by_group(ANSIBLE_INVENTORY, "all")
	else:
		selection = list(deep_get(inventory, DictPath("all#hosts"), {}))

	return ansible_run_playbook_on_selection_async(FilePath(str(PurePath(ANSIBLE_PLAYBOOK_DIR).joinpath("ping.yaml"))),
						       selection = selection, inventory = inventory)

def __ansible_run_event_handler_cb(data: Dict) -> bool:
	if deep_get(data, DictPath("event"), "") == "runner_on_start":
		host = deep_get(data, DictPath("event_data#host"), "<unset>")
		task = deep_get(data, DictPath("event_data#task"), "<unset>")
		ansithemeprint([ANSIThemeString("• ", "separator"),
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
		ansithemeprint([ANSIThemeString("• ", "separator"),
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
		ansithemeprint([ANSIThemeString("• ", "separator"),
				ANSIThemeString("Task", "action"),
				ANSIThemeString(": ", "default"),
				ANSIThemeString(f"{task}", "play"),
				ANSIThemeString(" ", "default"),
				ANSIThemeString("failed", "error"),
				ANSIThemeString(" on ", "default"),
				ANSIThemeString(f"{host}", "hostname")])
	elif deep_get(data, DictPath("event"), "") == "runner_on_unreachable":
		host = deep_get(data, DictPath("event_data#host"), "<unset>")
		task = deep_get(data, DictPath("event_data#task"), "<unset>")
		ansithemeprint([ANSIThemeString("• ", "separator"),
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
		ansithemeprint([ANSIThemeString("• ", "separator"),
				ANSIThemeString("Task", "action"),
				ANSIThemeString(": ", "default"),
				ANSIThemeString(f"{task}", "play"),
				ANSIThemeString(" ", "default"),
				ANSIThemeString("skipped", "none"),
				ANSIThemeString(" on ", "default"),
				ANSIThemeString(f"{host}", "hostname")])
	return True

def __ansible_run_async_finished_cb(runner_obj: ansible_runner.runner.Runner, **kwargs: Any) -> None:
	# pylint: disable-next=global-variable-not-assigned
	global finished_runs
	finished_runs.add(runner_obj)

finished_runs: Set[ansible_runner.runner.Runner] = set()

def ansible_async_get_data(async_cookie: ansible_runner.runner.Runner) -> Optional[Dict]:
	"""
	Get the result from an asynchronous ansible play

		Parameters:
			async_cookie (ansible_runner.runner.Runner): The return value from ansible_run_playbook_async
		Returns:
			data (dict): The result of the run (in a format suitable for passing to ansible_print_play_results)
	"""

	if async_cookie is None or not isinstance(async_cookie, ansible_runner.runner.Runner) or async_cookie not in finished_runs:
		return None

	finished_runs.discard(async_cookie)

	async_results: Dict = {}
	data = None

	if async_cookie is not None:
		for event in async_cookie.events:
			host = deep_get(event, DictPath("event_data#host"), "")

			__retval, d = ansible_results_extract(event)

			if len(d) > 0:
				if host not in async_results:
					async_results[host] = []
				async_results[host].append(d)
		if len(async_results) > 0:
			data = async_results

	return data
