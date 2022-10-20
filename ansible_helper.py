#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

"""
Helper for iKT to run Ansible playbooks
"""

from datetime import datetime
from functools import partial
import os
import re
import sys
import typing # pylint: disable=unused-import
import yaml

import iktlib # pylint: disable=unused-import
from iktlib import deep_get, iktconfig
from iktpaths import HOMEDIR
from iktpaths import ANSIBLE_DIR, ANSIBLE_PLAYBOOK_DIR, ANSIBLE_LOG_DIR
from iktpaths import ANSIBLE_INVENTORY
from iktprint import iktprint
from ikttypes import FilePath

ansible_results = {} # type: ignore

ansible_configuration = {
	"ansible_forks": 5,
	"ansible_password": None,
	"ansible_user": None,
	"disable_strict_host_key_checking": False,
	"save_logs": False,
}

# Used by Ansible
try:
	import ansible_runner # type: ignore
except ModuleNotFoundError:
	sys.exit("ansible_runner not available; try (re-)running ikt-install")

# If the ansible directory doesn't exist, create it
if not os.path.exists(ANSIBLE_DIR):
	try:
		os.mkdir(ANSIBLE_DIR)
	except FileNotFoundError:
		sys.exit(f"{ANSIBLE_DIR} not found; did you forget to run ikt-install?")

# If the ansible log directory doesn't exist, create it
if not os.path.exists(ANSIBLE_LOG_DIR):
	os.mkdir(ANSIBLE_LOG_DIR)

def get_playbook_path(playbook: FilePath) -> FilePath:
	"""
	Pass in the name of a playbook that exists in {ANSIBLE_PLAYBOOK_DIR};
	returns the path to the drop-in playbook with the highest priority
	(or the same playbook in case there is no override)

		Parameters:
			playbook (str): The name of the playbook to get the path to
		Returns:
			path (str): The playbook path with the highest priority
	"""

	path = ""

	# Check if there's a local playbook overriding this one
	local_playbooks = deep_get(iktconfig, "Ansible#local_playbooks", [])
	for playbook_path in local_playbooks:
		# Substitute {HOME}/ for {HOMEDIR}
		if playbook_path.startswith("{HOME}/"):
			playbook_path = f"{HOMEDIR}/{playbook_path[len('{HOME}/'):]}"
		# Skip non-existing playbook paths
		if not os.path.isdir(playbook_path):
			continue
		# We can have multiple directories with local playbooks;
		# the first match wins
		if os.path.isfile(f"{playbook_path}/{playbook}") == True:
			path = f"{playbook_path}/{playbook}"
			break
	if len(path) == 0:
		path = f"{ANSIBLE_PLAYBOOK_DIR}/{playbook}"
	return FilePath(path)

def ansible_get_inventory_dict():
	"""
        Get the iKT inventory and return it as a dict

		Returns:
			d (dict): A dictionary with an Ansible inventory
	"""

	if not os.path.exists(ANSIBLE_INVENTORY):
		return {}

	with open(ANSIBLE_INVENTORY, "r", encoding = "utf-8") as f:
		d = yaml.safe_load(f)

	return d

def ansible_get_inventory_pretty(groups = None, highlight: bool = False, include_groupvars: bool = False, include_hostvars: bool = False, include_hosts: bool = True): # pylint: disable=line-too-long
	"""
        Get the iKT inventory and return it neatly formatted

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

	if not os.path.exists(ANSIBLE_INVENTORY):
		return {}

	with open(ANSIBLE_INVENTORY, "r", encoding = "utf-8") as f:
		d = yaml.safe_load(f)

	# We want the entire inventory
	if groups is None or groups == []:
		tmp = d
	else:
		tmp = {}
		for group in groups:
			item = d.pop(group, None)
			if item is not None:
				tmp[group] = item

	# OK, now we have a dict with only the groups we're interested in;
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
				dump[i] = [(indent, "default"), (listmarker, "yaml_list"), (item, "yaml_value")]
				continue

			# Is it key: value?
			tmp2 = key_value_regex.match(dump[i])
			if tmp2 is not None:
				key = tmp2[1]
				separator = tmp2[2]
				value = tmp2[3]
				dump[i] = [(key, "yaml_key"), (separator, "yaml_key_separator"), (value, "yaml_value")]
				continue

			# Nope, then we'll use default format
			dump[i] = [(dump[i], "default")]

	return dump

def ansible_get_hosts_by_group(inventory: FilePath, group: str):
	"""
	Get the list of hosts belonging to a group

		Parameters:
			inventory (FilePath): The inventory to use
			group (str): The group to return hosts for
		Returns:
			hosts (list[str]): A list of hosts
	"""

	hosts = []

	if not os.path.exists(inventory):
		return []

	with open(inventory, "r", encoding = "utf-8") as f:
		d = yaml.safe_load(f)

		if d.get(group) is not None and d[group].get("hosts") is not None:
			for host in d[group]["hosts"]:
				hosts.append(host)

	return hosts

def ansible_get_groups(inventory: FilePath):
	"""
	Get the list of groups in the inventory

		Parameters:
			inventory (FilePath): The inventory to use
		Returns:
			groups (list[str]): A list of groups
	"""

	groups = []

	if not os.path.exists(inventory):
		return []

	with open(inventory, "r", encoding = "utf-8") as f:
		d = yaml.safe_load(f)

		for group in d:
			groups.append(group)

	return groups

def ansible_get_groups_by_host(inventory_dict, host: str):
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

def __ansible_create_inventory(inventory: FilePath, overwrite: bool = False):
	"""
	Create a new inventory at the path given if no inventory exists

		Parameters:
			inventory (FilePath): A path where to create a new inventory (if non-existing)
			overwrite (bool): True: Overwrite the existing inventory
	"""

	# Don't create anything if the inventory exists;
	# unless overwrite is set
	if os.path.exists(inventory) and overwrite == False:
		return

	# If the ansible directory doesn't exist, create it
	if not os.path.exists(ANSIBLE_DIR):
		os.mkdir(ANSIBLE_DIR)

	# Create the basic yaml structure that we'll write later on
	d = {
		"all": {
			"hosts": {},
			# Workaround for Ubuntu 18.04 and various other older operating systems
			# that have python3 installed, but not as default.
			"vars": {
				"ansible_python_interpreter": "/usr/bin/python3",
			}
		}
	}

	if deep_get(ansible_configuration, "ansible_user") is not None:
		d["all"]["vars"]["ansible_user"] = deep_get(ansible_configuration, "ansible_user") # type: ignore

	if deep_get(ansible_configuration, "ansible_password") is not None:
		d["all"]["vars"]["ansible_ssh_pass"] = deep_get(ansible_configuration, "ansible_password") # type: ignore

	if deep_get(ansible_configuration, "disable_strict_host_key_checking") is not None:
		d["all"]["vars"]["ansible_ssh_common_args"] = "-o StrictHostKeyChecking=no" # type: ignore

	yaml_str = yaml.safe_dump(d, default_flow_style = False).replace(r"''", '')

	with open(inventory, "w", opener = partial(os.open, mode = 0o600), encoding = "utf-8") as f:
		f.write(yaml_str)

def ansible_create_groups(inventory: FilePath, groups):
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

	if os.path.isfile(inventory) == False:
		__ansible_create_inventory(inventory, overwrite = False)

	with open(inventory, "r", encoding = "utf-8") as f:
		d = yaml.safe_load(f)

	for group in groups:
		# Group already exists; ignore
		if group in d:
			continue

		d[group] = {
			"hosts": "",
		}

		changed = True

	if changed == True:
		with open(inventory, "w", opener = partial(os.open, mode = 0o600), encoding = "utf-8") as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

def ansible_set_vars(inventory: FilePath, group: str, values):
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

	if os.path.isfile(inventory) == False:
		__ansible_create_inventory(inventory, overwrite = False)

	with open(inventory, "r", encoding = "utf-8") as f:
		d = yaml.safe_load(f)

	# If the group doesn't exist we create it
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
		with open(inventory, "w", opener = partial(os.open, mode = 0o600), encoding = "utf-8") as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

def ansible_set_groupvars(inventory: FilePath, groups, groupvars):
	"""
	Set one or several vars for the specified groups

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The groups to set variables for
			groupvars (dict): The values to set
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if groups is None or len(groups) == 0:
		raise Exception("ansible_set_vars: groups is empty or groups; this is a programming error")

	if groupvars is None or groupvars == []:
		raise Exception("ansible_set_vars: groupvars is empty or None; this is a programming error")

	if os.path.isfile(inventory) == False:
		raise Exception("ansible_set_vars: the inventory doesn't exist; this is a programming error")

	with open(inventory, "r", encoding = "utf-8") as f:
		d = yaml.safe_load(f)

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
		with open(inventory, "w", opener = partial(os.open, mode = 0o600), encoding = "utf-8") as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

# Set one or several vars for hosts in the group all
def ansible_set_hostvars(inventory: FilePath, hosts, hostvars):
	"""
	Set one or several vars for the specified hosts

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The hosts to set variables for
			hostvars (dict): The values to set
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if hosts is None or len(hosts) == 0:
		raise Exception("ansible_set_vars: hosts is empty or None; this is a programming error")

	if hostvars is None or hostvars == []:
		raise Exception("ansible_set_vars: hostvars is empty or None; this is a programming error")

	if os.path.isfile(inventory) == False:
		raise Exception("ansible_set_vars: the inventory doesn't exist; this is a programming error")

	with open(inventory, "r", encoding = "utf-8") as f:
		d = yaml.safe_load(f)

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
		with open(inventory, "w", opener = partial(os.open, mode = 0o600), encoding = "utf-8") as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

# Unset one or several vars in the specified groups
def ansible_unset_groupvars(inventory: FilePath, groups, groupvars):
	"""
	Unset one or several vars for the specified groups

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The groups to unset variables for
			groupvars (dict): The values to set
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if groups is None or len(groups) == 0:
		raise Exception("ansible_set_vars: groups is empty or groups; this is a programming error")

	if groupvars is None or groupvars == []:
		raise Exception("ansible_set_vars: groupvars is empty or None; this is a programming error")

	if os.path.isfile(inventory) == False:
		raise Exception("ansible_set_vars: the inventory doesn't exist; this is a programming error")

	with open(inventory, "r", encoding = "utf-8") as f:
		d = yaml.safe_load(f)

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
		with open(inventory, "w", opener = partial(os.open, mode = 0o600), encoding = "utf-8") as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

# Unset one or several vars for the specified host in the group all
def ansible_unset_hostvars(inventory: FilePath, hosts, hostvars):
	"""
	Unset one or several vars for the specified hosts

		Parameters:
			inventory (FilePath): The path to the inventory
			groups (list[str]): The hosts to unset variables for
			hostvars (dict): The values to set
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if hosts is None or len(hosts) == 0:
		raise Exception("ansible_set_vars: hosts is empty or None; this is a programming error")

	if hostvars is None or hostvars == []:
		raise Exception("ansible_set_vars: hostvars is empty or None; this is a programming error")

	if os.path.isfile(inventory) == False:
		raise Exception("ansible_set_vars: the inventory doesn't exist; this is a programming error")

	with open(inventory, "r", encoding = "utf-8") as f:
		d = yaml.safe_load(f)

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
		with open(inventory, "w", opener = partial(os.open, mode = 0o600), encoding = "utf-8") as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

def ansible_add_hosts(inventory: FilePath, hosts, group: str = "", skip_all: bool = False):
	"""
	Add hosts to the ansible inventory; if the inventory doesn't exist, create it

		Parameters:
			inventory (FilePath): The path to the inventory
			hosts (list[str]): The hosts to add to the inventory
			group (str): The group to add the hosts to
			skip_all (bool): If True we don't create a new inventory if it doesn't exist
		Returns:
			(bool): True on success, False on failure
	"""

	changed = False

	if hosts == []:
		return True

	# The inventory doesn't exist; if the user specified skip_all
	# we don't mind, otherwise we need to create it
	if os.path.isfile(inventory) == False:
		if skip_all == True and group != "all":
			d = {}
			changed = True
		else:
			__ansible_create_inventory(inventory, overwrite = False)

			with open(inventory, "r", encoding = "utf-8") as f:
				d = yaml.safe_load(f)
	else:
		with open(inventory, "r", encoding = "utf-8") as f:
			d = yaml.safe_load(f)

	for host in hosts:
		# All nodes go into the "hosts" group of the "all" group,
		# no matter if the caller also supplies a group, unless
		# skip_all has been specified; the exception being
		# if the group is all
		#
		# Don't add a host that already exists in all;
		# that will wipe its vars
		if skip_all == False and group != "all":
			if d["all"]["hosts"] is None:
				d["all"]["hosts"] = {}
			if host not in d["all"]["hosts"]: # type: ignore
				d["all"]["hosts"][host] = "" # type: ignore
				changed = True

		# If the group doesn't exist,
		# create it--we currently don't support
		# nested groups, node vars or anything like that
		#
		# We don't want to overwrite groups
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
		with open(inventory, "w", opener = partial(os.open, mode = 0o600), encoding = "utf-8") as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

# Remove hosts from ansible groups
def ansible_remove_hosts(inventory: FilePath, hosts, group: str = None):
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

	if os.path.isfile(inventory) == False:
		return False

	with open(inventory, "r", encoding = "utf-8") as f:
		d = yaml.safe_load(f)

	for host in hosts:
		if d[group].get("hosts") is not None:
			if host in d[group]["hosts"]:
				d[group]["hosts"].pop(host, None)
				changed = True
			if len(d[group]["hosts"]) == 0:
				d[group]["hosts"] = None

	if changed == True:
		with open(inventory, "w", opener = partial(os.open, mode = 0o600), encoding = "utf-8") as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

def ansible_remove_groups(inventory: FilePath, groups, force: bool = False):
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

	if os.path.isfile(inventory) == False:
		return False

	with open(inventory, "r", encoding = "utf-8") as f:
		d = yaml.safe_load(f)

	for group in groups:
		if d.get(group) is None:
			continue

		if d[group].get("hosts") is not None and force == False:
			continue

		d.pop(group)
		changed = True

	if changed == True:
		with open(inventory, "w", opener = partial(os.open, mode = 0o600), encoding = "utf-8") as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

def ansible_get_logs():
	"""
	Returns a list of all available logs

		Returns:
			logs (tuple(full_name, name, date, path)): A list of full name, name, date, and path to logs
	"""

	logs = []

	# Safe
	timestamp_regex = re.compile(r"^(\d{4}-\d\d-\d\d_\d\d:\d\d:\d\d\.\d+)_(.*)")

	for item in os.listdir(ANSIBLE_LOG_DIR):
		#if os.path.isdir(item) == False:
		#	continue

		tmp = timestamp_regex.match(item)
		if tmp is not None:
			date = datetime.strptime(tmp[1], "%Y-%m-%d_%H:%M:%S.%f")
			#full_name = item
			name = tmp[2]
			logs.append((item, name, f"{ANSIBLE_LOG_DIR}/{item}", date))
		else:
			raise Exception(f"Could not parse {item}")
	return logs

def ansible_extract_failure(retval: int, error_msg_lines, skipped: bool = False, unreachable: bool = False) -> str:
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

def ansible_results_extract(event):
	"""
	Extract a result from an Ansible play

		Parameters:
			event (dict): The output from the run
		Returns:
			(retval(int), result(dict)):
				retval: 0 on success, -1 if host is unreachable, retval on other failure,
				result: A dict
	"""

	host = deep_get(event, "event_data#host", "")
	if len(host) == 0:
		return 0, {}

	task = deep_get(event, "event_data#task", "")
	if len(task) == 0:
		return 0, {}

	ansible_facts = deep_get(event, "event_data#res#ansible_facts", {})

	skipped = deep_get(event, "event", "") == "runner_on_skipped"
	unreachable = deep_get(event, "event_data#res#unreachable", False)

	if unreachable == True:
		__retval = -1
	elif skipped == True or deep_get(event, "event", "") == "runner_on_ok":
		__retval = 0
	else:
		__retval = deep_get(event, "event_data#res#rc")

	if __retval is None:
		return 0, {}

	msg = deep_get(event, "event_data#res#msg", "")
	msg_lines = []
	if len(msg) > 0:
		msg_lines = msg.split("\n")

	start_date_timestamp = deep_get(event, "event_data#start")
	end_date_timestamp = deep_get(event, "event_data#end")

	stdout = deep_get(event, "event_data#res#stdout", "")
	stderr = deep_get(event, "event_data#res#stderr", "")
	stdout_lines = deep_get(event, "event_data#res#stdout_lines", "")
	stderr_lines = deep_get(event, "event_data#res#stderr_lines", "")

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
		# We don't want msg unless stdout_lines and stderr_lines are empty
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

def ansible_results_add(event) -> int:
	"""
	Add the result of an Ansible play to the ansible results

		Parameters:
			event (dict): The output from the run
		Returns:
			(int): 0 on success, -1 if host is unreachable, retval on other failure
	"""

	host = deep_get(event, "event_data#host", "")
	__retval, d = ansible_results_extract(event)

	if len(d) > 0:
		if host not in ansible_results:
			ansible_results[host] = []
		ansible_results[host].append(d)

	return __retval

def ansible_delete_log(log: str):
	"""
	Delete a log file

		Parameters:
			log (str): The name of the log to delete
	"""

	if os.path.exists(f"{ANSIBLE_LOG_DIR}/{log}"):
		for filename in os.listdir(f"{ANSIBLE_LOG_DIR}/{log}"):
			os.remove(f"{ANSIBLE_LOG_DIR}/{log}/{filename}")
		os.rmdir(f"{ANSIBLE_LOG_DIR}/{log}")

def ansible_write_log(start_date, playbook: str, events):
	"""
	Save an Ansible log entry to a file

		Parameters:
			start_date (date): A timestamp in the format YYYY-MM-DD_HH:MM:SS.ssssss
			playbook (str): The name of the playbook
			events (list[dict]): The list of Ansible runs
	"""

	save_logs: bool = deep_get(ansible_configuration, "save_logs", False)

	if save_logs == False:
		return

	playbook_name = playbook
	if "/" in playbook_name:
		tmp2 = os.path.basename(playbook_name)
		# Safe
		tmp = re.match(r"^(.*)\.ya?ml$", tmp2)
		if tmp is not None:
			playbook_name = tmp[1]

	directory_name = f"{start_date}_{playbook_name}".replace(" ", "_")
	os.mkdir(f"{ANSIBLE_LOG_DIR}/{directory_name}")

	# Start by creating a file with metadata about the whole run
	d = {
		"playbook_path": playbook,
		"created_at": start_date,
	}

	with open(f"{ANSIBLE_LOG_DIR}/{directory_name}/metadata.yaml", "w", opener = partial(os.open, mode = 0o600), encoding = "utf-8") as f:
		f.write(yaml.dump(d, default_flow_style = False, sort_keys = False))

	i = 0

	for event in events:
		host = deep_get(event, "event_data#host", "")
		if len(host) == 0:
			continue

		task = deep_get(event, "event_data#task", "")
		if len(task) == 0:
			continue

		skipped = deep_get(event, "event", "") == "runner_on_skipped"
		unreachable = deep_get(event, "event_data#res#unreachable", False)

		if unreachable == True:
			retval = -1
		elif skipped == True or deep_get(event, "event", "") == "runner_on_ok":
			retval = 0
		else:
			retval = deep_get(event, "event_data#res#rc")

		if retval is None:
			continue

		taskname = task
		i += 1

		filename = f"{i:02d}-{host}_{taskname}.yaml".replace(" ", "_").replace("/", "_")
		msg = deep_get(event, "event_data#res#msg", "")
		msg_lines = []
		if len(msg) > 0:
			msg_lines = msg.split("\n")

		start_date_timestamp = deep_get(event, "event_data#start")
		end_date_timestamp = deep_get(event, "event_data#end")

		stdout = deep_get(event, "event_data#res#stdout", "")
		stderr = deep_get(event, "event_data#res#stderr", "")
		stdout_lines = deep_get(event, "event_data#res#stdout_lines", "")
		stderr_lines = deep_get(event, "event_data#res#stderr_lines", "")

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
			# We don't want msg unless stdout_lines and stderr_lines are empty
			# XXX: Or can it be used to get a sequential log when there's both
			# stdout and stderr?
			if len(stdout_lines) == 0 and len(stderr_lines) == 0 and len(msg_lines) > 0:
				if retval != 0:
					d["stderr_lines"] = msg_lines
				else:
					d["msg_lines"] = msg_lines
		else:
			d["stdout_lines"] = ["<no output>"]

		with open(f"{ANSIBLE_LOG_DIR}/{directory_name}/{filename}", "w", opener = partial(os.open, mode = 0o600), encoding = "utf-8") as f:
			f.write(yaml.dump(d, default_flow_style = False, sort_keys = False))

# pylint: disable-next=too-many-arguments
def ansible_print_task_results(task: str, msg_lines, stdout_lines, stderr_lines, retval: int, unreachable: bool = False, skipped: bool = False):
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
		iktprint([("• ", "separator"), (f"{task}", "error")], stderr = True)
	elif skipped == True:
		iktprint([("• ", "separator"), (f"{task} [skipped]", "skip")], stderr = True)
		iktprint([("", "default")])
		return
	elif retval != 0:
		iktprint([("• ", "separator"), (f"{task}", "error"), (" (retval: ", "default"), (retval, "errorvalue"), (")", "default")], stderr = True)
	else:
		iktprint([("• ", "separator"), (f"{task}", "success")])

	if len(msg_lines) > 0:
		iktprint([("msg:", "header")])
		for line in msg_lines:
			iktprint([(line, "default")])
		iktprint([("", "default")])

	if len(stdout_lines) > 0 or len(msg_lines) == 0 and len(stderr_lines) == 0:
		iktprint([("stdout:", "header")])
		for line in stdout_lines:
			iktprint([(f"{line}", "default")])
		if len(stdout_lines) == 0:
			iktprint([("<no output>", "none")])
		iktprint([("", "default")])

	# If retval isn't 0 we don't really care if stderr is empty
	if len(stderr_lines) > 0 or retval != 0:
		iktprint([("stderr:", "header")])
		for line in stderr_lines:
			iktprint([(f"{line}", "default")], stderr = True)
		if len(stderr_lines) == 0:
			iktprint([("<no output>", "none")])
		iktprint([("", "default")])

def ansible_print_play_results(retval: int, __ansible_results):
	"""
	Pretty-print the result of an Ansible play

		Parameters:
			retval (int): The return value from the play
			__ansible_results (opaque): The data from a playbook run
	"""

	if retval != 0 and len(__ansible_results) == 0:
		iktprint([("Failed to execute playbook; retval: ", "error"), (f"{retval}", "errorvalue")], stderr = True)
	else:
		for host in __ansible_results:
			plays = __ansible_results[host]
			header_output = False

			for play in plays:
				task = deep_get(play, "task")

				unreachable = deep_get(play, "unreachable", False)
				skipped = deep_get(play, "skipped", False)
				retval = deep_get(play, "retval")

				if header_output == False:
					header_output = True

					if unreachable == True:
						iktprint([(f"[{host}]", "error")])
					elif retval == 0:
						iktprint([(f"[{host}]", "success")])
					else:
						iktprint([(f"[{host}]", "error")])

				msg_lines = deep_get(play, "msg_lines", "")
				stdout_lines = deep_get(play, "stdout_lines", "")
				stderr_lines = deep_get(play, "stderr_lines", "")
				ansible_print_task_results(task, msg_lines, stdout_lines, stderr_lines, retval, unreachable, skipped)
				print()

				# Only show unreachable once
				if unreachable == True:
					break

def ansible_run_playbook(playbook: FilePath, inventory = None):
	"""
	Run a playbook

		Parameters:
			playbook (FilePath): The playbook to run
			inventory (dict): An inventory dict with selection as the list of hosts to run on
		Returns:
			(retval(bool), ansible_results(dict)): The return value and results from the run
	"""

	global ansible_results # pylint: disable=global-statement

	forks = deep_get(ansible_configuration, "ansible_forks")

	# Flush previous results
	ansible_results = {}

	if inventory is None:
		inventory = [ANSIBLE_INVENTORY]

	start_date = datetime.now()

	runner = ansible_runner.interface.run(json_mode = True, quiet = True, playbook = playbook, inventory = inventory, forks = forks)
	retval = 0
	if runner is not None:
		for event in runner.events:
			_retval = ansible_results_add(event)
			if retval == 0 and _retval != 0:
				retval = _retval
		ansible_write_log(start_date, playbook, runner.events)

	return retval, ansible_results

def ansible_run_playbook_async(playbook: FilePath, inventory):
	"""
	Run a playbook asynchronously

		Parameters:
			playbook (FilePath): The playbook to run
			inventory (dict): An inventory dict with selection as the list of hosts to run on

		Returns:
			runner: An ansible_runner.runner.Runner object
	"""

	forks = deep_get(ansible_configuration, "ansible_forks")

	_thread, runner = ansible_runner.interface.run_async(json_mode = True, quiet = True, playbook = playbook, inventory = inventory,
							     forks = forks, finished_callback = __ansible_run_async_finished_cb)

	return runner

def ansible_run_playbook_on_selection(playbook: FilePath, selection, values = None):
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
	# we'll use passwordless sudo and ssh hostkeys.
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
		values["ansible_user"] = deep_get(ansible_configuration, "ansible_user")

	for key, value in values.items():
		d["all"][key] = value

	d["selection"] = {
		"hosts": {}
	}

	for host in selection:
		d["selection"]["hosts"][host] = ""

	return ansible_run_playbook(playbook, d)

def ansible_run_playbook_on_selection_async(playbook: FilePath, selection, values = None):
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
	# we'll use passwordless sudo and ssh hostkeys.
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
		values["ansible_user"] = deep_get(ansible_configuration, "ansible_user")

	for key, value in values.items():
		d["all"][key] = value

	d["selection"] = {
		"hosts": {}
	}

	for host in selection:
		d["selection"]["hosts"][host] = ""

	return ansible_run_playbook_async(playbook, d)

def ansible_ping(selection):
	"""
	Ping all selected hosts

		Parameters:
			selection (list[str]): A list of hostnames
		Returns:
			list[(hostname, status)]: The status of the pinged hosts
	"""

	save_logs_tmp = deep_get(ansible_configuration, "save_logs", False)
	ansible_configuration["save_logs"] = False

	host_status = []

	if selection is None:
		selection = ansible_get_hosts_by_group(ANSIBLE_INVENTORY, "all")

	_retval, __ansible_results = ansible_run_playbook_on_selection(f"{ANSIBLE_PLAYBOOK_DIR}/ping.yaml", selection = selection)

	for host in __ansible_results:
		for task in deep_get(__ansible_results, host, []):
			unreachable = deep_get(task, "unreachable")
			skipped = deep_get(task, "skipped")
			stderr_lines = deep_get(task, "stderr_lines")
			retval = deep_get(task, "retval")
			status = ansible_extract_failure(retval, stderr_lines, skipped = skipped, unreachable = unreachable)
			host_status.append((host, status))
	ansible_configuration["save_logs"] = save_logs_tmp

	return host_status

def ansible_ping_async(selection):
	"""
	Ping all selected hosts asynchronously

		Parameters:
			selection (list[str]): A list of hostnames
		Returns:
			list[(hostname, status)]: The status of the pinged hosts
	"""

	if selection is None:
		selection = ansible_get_hosts_by_group(ANSIBLE_INVENTORY, "all")

	return ansible_run_playbook_on_selection_async(f"{ANSIBLE_PLAYBOOK_DIR}/ping.yaml", selection = selection)

def __ansible_run_async_finished_cb(kwargs):
	# pylint: disable=global-variable-not-assigned
	global finished_runs
	finished_runs.add(kwargs)

finished_runs = set() # type: ignore

def ansible_async_get_data(async_cookie):
	"""
	Get the result from an asynchronous ansible play

		Parameters:
			async_cookie (ansible_runner.runner.Runner): The return value from ansible_run_playbook_async
		Returns:
			data (dict): The result of the run (in a format suitable for passing to ansible_print_play_results)
	"""

	if async_cookie is None or async_cookie not in finished_runs:
		return None

	finished_runs.remove(async_cookie)

	async_results = {}
	data = None

	if async_cookie is not None:
		for event in async_cookie.events:
			host = deep_get(event, "event_data#host", "")

			__retval, d = ansible_results_extract(event)

			if len(d) > 0:
				if host not in async_results:
					async_results[host] = []
				async_results[host].append(d)
		if len(async_results) > 0:
			data = async_results

	return data
