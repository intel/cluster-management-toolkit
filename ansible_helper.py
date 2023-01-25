#! /usr/bin/env python3
# Requires: python3 (>= 3.8)

"""
Ansible-related helpers
"""

from datetime import datetime
from pathlib import Path, PurePath
import re
import sys
from typing import cast, Dict, List, Optional, Set, Tuple, Union
import yaml

import cmtlib
from cmtio import check_path, secure_mkdir, secure_rm, secure_rmdir
from cmtio_yaml import secure_read_yaml, secure_write_yaml
from cmtpaths import HOMEDIR
from cmtpaths import ANSIBLE_DIR, ANSIBLE_PLAYBOOK_DIR, ANSIBLE_LOG_DIR
from cmtpaths import ANSIBLE_INVENTORY
from ansithemeprint import ANSIThemeString, ansithemeprint
from cmttypes import deep_get, DictPath, FilePath, FilePathAuditError, SecurityChecks, SecurityStatus

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
	import ansible_runner # type: ignore
except ModuleNotFoundError:
	sys.exit("ansible_runner not available; try (re-)running cmt-install")

# Exit if the ansible directory does not exist
if not Path(ANSIBLE_DIR).exists():
	sys.exit(f"{ANSIBLE_DIR} not found; try (re-)running cmt-install")

# Exit if the ansible log directory does not exist
if not Path(ANSIBLE_LOG_DIR).exists():
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
		if Path(f"{playbook_path}/{playbook}").is_file() == True:
			path = f"{playbook_path}/{playbook}"
			break
	if len(path) == 0:
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

	# Safe
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
			raise Exception(f"The playbook filename “{pathname}“ does not end with .yaml or .yml; this is most likely a programming error.")

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
			violation_strings = []
			for violation in violations:
				violation_strings.append(str(violation))
			violations_joined = ",".join(violation_strings)
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
		description = [ANSIThemeString(deep_get(d[0], DictPath("vars#metadata#description")), "play")]

		if description is None or len(description) == 0:
			description = [ANSIThemeString("Running “", "play"),
				       ANSIThemeString(playbookname, "programname"),
				       ANSIThemeString("“", "play")]

		# If there's no description we fallback to just using the filename
		playbooks.append(([ANSIThemeString("  • ", "separator")] + description, playbookpath))

	return playbooks

def ansible_get_inventory_dict() -> Dict:
	"""
        Get the Ansible inventory and return it as a dict

		Returns:
			d (dict): A dictionary with an Ansible inventory
	"""

	if not Path(ANSIBLE_INVENTORY).exists():
		return {}

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
				 include_groupvars: bool = False, include_hostvars: bool = False, include_hosts: bool = True) -> List[List[ANSIThemeString]]:
	"""
        Get the Ansible inventory and return it neatly formatted

		Parameters:
			groups (list[str]): What groups to include
			highlight (bool): Apply syntax highlighting?
			include_groupvars (bool): Should group variables be included
			include_hostvars (bool): Should host variables be included
			include_hosts (bool): Should hosts be included
		Returns:
			dump (list[themearray]): A list of themearrays
	"""

	tmp = {}

	if not Path(ANSIBLE_INVENTORY).exists():
		return []

	d = secure_read_yaml(ANSIBLE_INVENTORY)

	# We want the entire inventory
	if groups is None or groups == []:
		tmp = d
	else:
		for group in groups:
			item = d.pop(group, None)
			if item is not None:
				tmp[group] = item

	# OK, now we have a dict with only the groups we are interested in;
	# time for further post-processing

	# do we want groupvars?
	if include_groupvars == False:
		for group in tmp:
			tmp[group].pop("vars", None)
	else:
		for group in tmp:
			if tmp[group].get("vars") is None or tmp[group].get("vars") == {}:
				tmp[group].pop("vars", None)

	# Do we want hosts?
	if include_hosts == False:
		for group in tmp:
			tmp[group].pop("hosts", None)
	else:
		for group in tmp:
			if tmp[group].get("hosts") is None or tmp[group].get("hosts") == {}:
				tmp[group].pop("hosts", None)

		# OK, but do we want hostvars?
		if include_hostvars == False:
			for group in tmp:
				if tmp[group].get("hosts") is not None:
					for host in tmp[group]["hosts"]:
						tmp[group]["hosts"][host] = None

	dump = yaml.safe_dump(tmp, default_flow_style = False).replace(r"''", '').replace("null", "").replace("{}", "").splitlines()

	if highlight == True and len(dump) > 0:
		i = 0
		# Safe
		list_regex = re.compile(r"^(\s*)((- )+)(.*)")
		# Safe
		key_value_regex = re.compile(r"^(.*?)(:)(.*)")
		for i in range(0, len(dump)): # pylint: disable=consider-using-enumerate
			# Is it a list?
			tmp2 = list_regex.match(dump[i])
			if tmp2 is not None:
				indent = tmp2[1]
				listmarker = tmp2[2]
				item = tmp2[4]
				dump[i] = [ANSIThemeString(indent, "default"),
					   ANSIThemeString(listmarker, "yaml_list"),
					   ANSIThemeString(item, "yaml_value")]
				continue

			# Is it key: value?
			tmp2 = key_value_regex.match(dump[i])
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

	for group in inventory_dict:
		if inventory_dict[group].get("hosts") and host in inventory_dict[group]["hosts"]:
			groups.append(group)

	return groups

def __ansible_create_inventory(inventory: FilePath, overwrite: bool = False) -> None:
	"""
	Create a new inventory at the path given if no inventory exists

		Parameters:
			inventory (FilePath): A path where to create a new inventory (if non-existing)
			overwrite (bool): True: Overwrite the existing inventory
	"""

	# Do not create anything if the inventory exists;
	# unless overwrite is set
	if Path(inventory).exists() and overwrite == False:
		return

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

	if deep_get(ansible_configuration, DictPath("ansible_user")) is not None:
		d["all"]["vars"]["ansible_user"] = deep_get(ansible_configuration, DictPath("ansible_user"))

	if deep_get(ansible_configuration, DictPath("ansible_password")) is not None:
		d["all"]["vars"]["ansible_ssh_pass"] = deep_get(ansible_configuration, DictPath("ansible_password"))

	if deep_get(ansible_configuration, DictPath("disable_strict_host_key_checking")) is not None:
		d["all"]["vars"]["ansible_ssh_common_args"] = "-o StrictHostKeyChecking=no"

	secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True)

def ansible_create_groups(inventory: FilePath, groups: List[str]) -> bool:
	"""
	Create new groups

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The groups to create
		Returns:
			(bool): True on success, False on failure
	"""

	changed: bool = False

	if groups is None or len(groups) == 0:
		return True

	if not Path(inventory).is_file():
		__ansible_create_inventory(inventory, overwrite = False)

	d = secure_read_yaml(inventory)

	for group in groups:
		# Group already exists; ignore
		if group in d:
			continue

		d[group] = {
			"hosts": "",
		}

		changed = True

	if changed == True:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True)

	return True

def ansible_set_vars(inventory: FilePath, group: str, values: Dict) -> bool:
	"""
	Set one or several values for a group

		Parameters:
			inventory (FilePath): The path to the inventory
			group (str): The group to set variables for
			values (dict): The values to set
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if group is None or group == "":
		sys.exit("ansible_set_vars: group is empty or None; this is a programming error")

	if values is None or values == {}:
		sys.exit("ansible_set_vars: values is empty or None; this is a programming error")

	if not Path(inventory).is_file():
		__ansible_create_inventory(inventory, overwrite = False)

	d = secure_read_yaml(inventory)

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

	if changed == True:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True)

	return True

def ansible_set_groupvars(inventory: FilePath, groups: List[str], groupvars: List[Tuple[str, str]]) -> bool:
	"""
	Set one or several vars for the specified groups

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The groups to set variables for
			groupvars (list[(str, str)]): The values to set
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if groups is None or len(groups) == 0:
		raise Exception("ansible_set_vars: groups is empty or groups; this is a programming error")

	if groupvars is None or groupvars == []:
		raise Exception("ansible_set_vars: groupvars is empty or None; this is a programming error")

	if not Path(inventory).is_file():
		raise Exception("ansible_set_vars: the inventory does not exist; this is a programming error")

	d = secure_read_yaml(inventory)

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

	if changed == True:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True)

	return True

# Set one or several vars for hosts in the group all
def ansible_set_hostvars(inventory: FilePath, hosts: List[str], hostvars: List[Tuple[str, str]]) -> bool:
	"""
	Set one or several vars for the specified hosts

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The hosts to set variables for
			hostvars (list[(str, str)]): The values to set
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if hosts is None or len(hosts) == 0:
		raise Exception("ansible_set_vars: hosts is empty or None; this is a programming error")

	if hostvars is None or hostvars == []:
		raise Exception("ansible_set_vars: hostvars is empty or None; this is a programming error")

	if not Path(inventory).is_file():
		raise Exception("ansible_set_vars: the inventory does not exist; this is a programming error")

	d = secure_read_yaml(inventory)

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

	if changed == True:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True)

	return True

# Unset one or several vars in the specified groups
def ansible_unset_groupvars(inventory: FilePath, groups: List[str], groupvars: List[str]) -> bool:
	"""
	Unset one or several vars for the specified groups

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The groups to unset variables for
			groupvars (list[(str]): The values to unset
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if groups is None or len(groups) == 0:
		raise Exception("ansible_set_vars: groups is empty or groups; this is a programming error")

	if groupvars is None or groupvars == []:
		raise Exception("ansible_set_vars: groupvars is empty or None; this is a programming error")

	if not Path(inventory).is_file():
		raise Exception("ansible_set_vars: the inventory does not exist; this is a programming error")

	d = secure_read_yaml(inventory)

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
		if len(d[group]["vars"]) == 0:
			d[group].pop("vars", None)

	if changed == True:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True)

	return True

# Unset one or several vars for the specified host in the group all
def ansible_unset_hostvars(inventory: FilePath, hosts: List[str], hostvars: List[str]) -> bool:
	"""
	Unset one or several vars for the specified hosts

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The hosts to unset variables for
			hostvars (list[(str]): The values to unset
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if hosts is None or len(hosts) == 0:
		raise Exception("ansible_set_vars: hosts is empty or None; this is a programming error")

	if hostvars is None or hostvars == []:
		raise Exception("ansible_set_vars: hostvars is empty or None; this is a programming error")

	if not Path(inventory).is_file():
		raise Exception("ansible_set_vars: the inventory does not exist; this is a programming error")

	d = secure_read_yaml(inventory)

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

		if len(d["all"]["hosts"][host]) == 0:
			d["all"]["hosts"][host] = None

	if changed == True:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True)

	return True

def ansible_add_hosts(inventory: FilePath, hosts: List[str], group: str = "", skip_all: bool = False) -> bool:
	"""
	Add hosts to the ansible inventory; if the inventory does not exist, create it

		Parameters:
			inventory (FilePath): The path to the inventory
			hosts (list[str]): The hosts to add to the inventory
			group (str): The group to add the hosts to
			skip_all (bool): If True we do not create a new inventory if it does not exist
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if hosts == []:
		return True

	d: Dict = {}

	# The inventory does not exist; if the user specified skip_all
	# we do not mind, otherwise we need to create it
	if not Path(inventory).is_file():
		if skip_all == True and group != "all":
			changed = True
		else:
			__ansible_create_inventory(inventory, overwrite = False)
			d = secure_read_yaml(inventory)
	else:
		d = secure_read_yaml(inventory)

	for host in hosts:
		# All nodes go into the "hosts" group of the "all" group,
		# no matter if the caller also supplies a group, unless
		# skip_all has been specified; the exception being
		# if the group is all
		#
		# Do not add a host that already exists in all;
		# that will wipe its vars
		if skip_all == False and group != "all":
			if d["all"]["hosts"] is None:
				d["all"]["hosts"] = {}
			if host not in cast(List, d["all"]["hosts"]):
				d = cast(Dict, d)
				d["all"]["hosts"][host] = ""
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
				d[group]["hosts"][host] = ""
				changed = True

	if changed == True:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True)

	return True

# Remove hosts from ansible groups
def ansible_remove_hosts(inventory: FilePath, hosts: List[str], group: Optional[str] = None) -> bool:
	"""
	Remove hosts from the inventory

		Parameters:
			inventory (FilePath): The inventory to use
			hosts (list[str]): The hosts to remove
			group (str): The group to remove the hosts from
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	# Treat empty or zero-length hosts as a programming error
	if hosts is None or len(hosts) == 0:
		raise Exception("None or zero-length hosts; this is a programming error")

	# Treat empty or zero-length group as a programming error
	if group is None or len(group) == 0:
		raise Exception("None or zero-length group; this is a programming error")

	if not Path(inventory).is_file():
		return False

	d = secure_read_yaml(inventory)

	for host in hosts:
		if group in d and d[group].get("hosts") is not None:
			if host in d[group]["hosts"]:
				d[group]["hosts"].pop(host, None)
				changed = True
			if len(d[group]["hosts"]) == 0:
				d[group]["hosts"] = None

	if changed == True:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True)

	return True

def ansible_remove_groups(inventory: FilePath, groups: List[str], force: bool = False) -> bool:
	"""
	Remove groups from the inventory

		Parameters:
			inventory (FilePath): The inventory to use
			groups (list[str]): The groups to remove
			force (bool): Force allows for removal of non-empty groups
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	# Treat empty or zero-length groups as a programming error
	if groups is None or len(groups) == 0:
		raise Exception("None or zero-length group; this is a programming error")

	if not Path(inventory).is_file():
		return False

	d = secure_read_yaml(inventory)

	for group in groups:
		if d.get(group) is None:
			continue

		if d[group].get("hosts") is not None and force == False:
			continue

		d.pop(group)
		changed = True

	if changed == True:
		secure_write_yaml(inventory, d, permissions = 0o600, replace_empty = True, replace_null = True)

	return True

def ansible_get_logs() -> List[Tuple[str, str, FilePath, datetime]]:
	"""
	Returns a list of all available logs

		Returns:
			logs (tuple(full_name, name, date, path)): A list of full name, name, date, and path to logs
	"""

	logs = []

	# Safe
	timestamp_regex = re.compile(r"^(\d{4}-\d\d-\d\d_\d\d:\d\d:\d\d\.\d+)_(.*)")

	for path in Path(ANSIBLE_LOG_DIR).iterdir():
		filename = str(path.name)
		tmp = timestamp_regex.match(filename)
		if tmp is not None:
			date = datetime.strptime(tmp[1], "%Y-%m-%d_%H:%M:%S.%f")
			name = tmp[2]
			logs.append((filename, name, FilePath(str(path)), date))
		else:
			raise Exception(f"Could not parse {filename}")
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

	if unreachable == True:
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
	elif skipped == True:
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

	if unreachable == True:
		__retval: Optional[int] = -1
	elif skipped == True or deep_get(event, DictPath("event"), "") == "runner_on_ok":
		__retval = 0
	elif failed == True:
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
		"unreachable": unreachable,
		"status": "UNKNOWN",
		"skipped": skipped,
		"stdout_lines": [],
		"stderr_lines": [],
		"msg_lines": [],
		"ansible_facts": ansible_facts,
	}

	if unreachable == False and __retval == 0:
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
	global ansible_results # pylint: disable=global-variable-not-assigned

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

	if save_logs == False:
		return

	playbook_name = playbook
	if "/" in playbook_name:
		tmp2 = str(PurePath(playbook_name).name)
		# Safe
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
	secure_write_yaml(metadata_path, d, permissions = 0o600, sort_keys = False)

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

		if unreachable == True:
			retval = -1
		elif skipped == True or deep_get(event, DictPath("event"), "") == "runner_on_ok":
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
		secure_write_yaml(logentry_path, d, permissions = 0o600, sort_keys = False)

# pylint: disable-next=too-many-arguments
def ansible_print_task_results(task: str, msg_lines: List[str], stdout_lines: List[str], stderr_lines: List[str], retval: int,
			       unreachable: bool = False, skipped: bool = False) -> None:
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
	"""

	if unreachable == True:
		ansithemeprint([ANSIThemeString("• ", "separator"),
				ANSIThemeString(f"{task}", "error")], stderr = True)
	elif skipped == True:
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

def ansible_print_play_results(retval: int, __ansible_results: Dict) -> None:
	"""
	Pretty-print the result of an Ansible play

		Parameters:
			retval (int): The return value from the play
			__ansible_results (opaque): The data from a playbook run
	"""

	if retval != 0 and len(__ansible_results) == 0:
		ansithemeprint([ANSIThemeString("Failed to execute playbook; retval: ", "error"),
				ANSIThemeString(f"{retval}", "errorvalue")], stderr = True)
	else:
		for host in __ansible_results:
			plays = __ansible_results[host]
			header_output = False

			for play in plays:
				task = deep_get(play, DictPath("task"))

				unreachable = deep_get(play, DictPath("unreachable"), False)
				skipped = deep_get(play, DictPath("skipped"), False)
				retval = deep_get(play, DictPath("retval"))

				if header_output == False:
					header_output = True

					if unreachable == True:
						ansithemeprint([ANSIThemeString(f"[{host}]", "error")])
					elif retval == 0:
						ansithemeprint([ANSIThemeString(f"[{host}]", "success")])
					else:
						ansithemeprint([ANSIThemeString(f"[{host}]", "error")])

				msg_lines = deep_get(play, DictPath("msg_lines"), "")
				stdout_lines = deep_get(play, DictPath("stdout_lines"), "")
				stderr_lines = deep_get(play, DictPath("stderr_lines"), "")
				ansible_print_task_results(task, msg_lines, stdout_lines, stderr_lines, retval, unreachable, skipped)
				print()

				# Only show unreachable once
				if unreachable == True:
					break

def ansible_run_playbook(playbook: FilePath, inventory: Optional[Dict] = None) -> Tuple[int, Dict]:
	"""
	Run a playbook

		Parameters:
			playbook (FilePath): The playbook to run
			inventory (dict): An inventory dict with selection as the list of hosts to run on
		Returns:
			(retval(bool), ansible_results(dict)): The return value and results from the run
	"""

	global ansible_results # pylint: disable=global-statement

	forks = deep_get(ansible_configuration, DictPath("ansible_forks"))

	# Flush previous results
	ansible_results = {}

	inventories: Union[Dict, List[FilePath]] = []

	if inventory is None:
		inventories = [ANSIBLE_INVENTORY]
	else:
		inventories = inventory

	start_date = datetime.now()

	runner = ansible_runner.interface.run(json_mode = True, quiet = True, playbook = playbook, inventory = inventories, forks = forks)

	retval = 0
	if runner is not None:
		for event in runner.events:
			_retval = ansible_results_add(event)
			if retval == 0 and _retval != 0:
				retval = _retval
		ansible_write_log(start_date, playbook, runner.events)

	return retval, ansible_results

def ansible_run_playbook_async(playbook: FilePath, inventory: Dict) -> ansible_runner.runner.Runner:
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
							     forks = forks, finished_callback = __ansible_run_async_finished_cb)

	return runner

def ansible_run_playbook_on_selection(playbook: FilePath, selection: List[str], values: Optional[Dict] = None) -> Tuple[int, Dict]:
	"""
	Run a playbook on selected nodes

		Parameters:
			playbook (FilePath): The playbook to run
			selection (list[str]): The hosts to run the play on
			values (dict): Extra values to set for the hosts
		Returns:
			The result from ansible_run_playbook()
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
		d["selection"]["hosts"][host] = ""

	return ansible_run_playbook(playbook, d)

def ansible_run_playbook_on_selection_async(playbook: FilePath, selection: List[str], values: Optional[Dict] = None) -> ansible_runner.runner.Runner:
	"""
	Run a playbook on selected nodes

		Parameters:
			playbook (FilePath): The playbook to run
			selection (list[str]): The hosts to run the play on
			values (dict): Extra values to set for the hosts
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
	d = ansible_get_inventory_dict()

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
		d["selection"]["hosts"][host] = ""

	return ansible_run_playbook_async(playbook, d)

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

def ansible_ping_async(selection: Optional[List[str]]) -> ansible_runner.runner.Runner:
	"""
	Ping all selected hosts asynchronously

		Parameters:
			selection (list[str]): A list of hostnames
		Returns:
			The result from ansible_run_playbook_async()
	"""

	if selection is None:
		selection = ansible_get_hosts_by_group(ANSIBLE_INVENTORY, "all")

	return ansible_run_playbook_on_selection_async(FilePath(str(PurePath(ANSIBLE_PLAYBOOK_DIR).joinpath("ping.yaml"))), selection = selection)

def __ansible_run_async_finished_cb(runner_obj: ansible_runner.runner.Runner, **kwargs: Dict) -> None:
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

	if async_cookie is None or async_cookie not in finished_runs:
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
