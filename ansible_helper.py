#! /usr/bin/env python3
# Requires: python3 (>= 3.6)
from datetime import datetime
from functools import partial, reduce
import os
from pathlib import Path
import pwd
import re
import sys
import yaml

from iktlib import deep_get
from iktprint import iktprint

ansible_bin_path = None
ansible_results = {}

active_task = ""
suffix = 0

HOMEDIR = str(Path.home())

# Ansible
ANSIBLE_TMP_GROUP = "selection"

IKTDIR = f"{HOMEDIR}/.ikt"
ANSIBLE_DIR = f"{IKTDIR}/ansible"
ANSIBLE_PLAYBOOK_DIRNAME = "playbooks"
ANSIBLE_PLAYBOOK_DIR = f"{IKTDIR}/{ANSIBLE_PLAYBOOK_DIRNAME}"
ANSIBLE_INVENTORY = f"{ANSIBLE_DIR}/inventory.yaml"
ANSIBLE_LOG_DIR = f"{ANSIBLE_DIR}/logs"
ANSIBLE_TMP_INVENTORY = f"{ANSIBLE_DIR}/tmp_inventory.yaml"

class ansible_configuration:
	ansible_user = None
	ansible_password = None
	save_logs = False

# Behaves roughly as which(1)
def which(commandname):
	global ansible_bin_path

	# Did we get a full path, or just a command name?
	fpath, fname = os.path.split(commandname)

	# If we got a path we just verify whether commandname
	# exists and is executable
	if fpath:
		if os.path.isfile(commandname) and os.access(commandname, os.X_OK):
			ansible_bin_path = commandname
		return

	for path in os.environ["PATH"].split(os.pathsep):
		tmp = os.path.join(path, commandname)
		if os.path.isfile(tmp) and os.access(tmp, os.X_OK):
			ansible_bin_path = tmp
			break
	return

# Used by Ansible
try:
	import ansible_runner
except ModuleNotFoundError:
	sys.exit(f"ansible_runner not available; try (re-)running ikt-install")

# If the ansible directory doesn't exist, create it
if not os.path.exists(ANSIBLE_DIR):
	try:
		os.mkdir(ANSIBLE_DIR)
	except FileNotFoundError:
		sys.exit(f"{ANSIBLE_DIR} not found; did you forget to run ikt-install?")

# If the ansible log directory doesn't exist, create it
if not os.path.exists(ANSIBLE_LOG_DIR):
	os.mkdir(ANSIBLE_LOG_DIR)

def ansible_get_inventory_dict():
	if not os.path.exists(ANSIBLE_INVENTORY):
		return {}

	with open(ANSIBLE_INVENTORY, "r") as f:
		d = yaml.safe_load(f)

	return d

# Returns a formatted version of the inventory
def ansible_get_inventory_pretty(groups = None, highlight = False, include_groupvars = False, include_hostvars = False, include_hosts = True):
	tmp = {}

	if not os.path.exists(ANSIBLE_INVENTORY):
		return {}

	with open(ANSIBLE_INVENTORY, "r") as f:
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
		for i in range(0, len(dump)):
			# Is it a list?
			tmp = re.match(r"^(\s*)((- )+)(.*)", dump[i])
			if tmp is not None:
				indent = tmp[1]
				listmarker = tmp[2]
				item = tmp[4]
				dump[i] = [(indent, "default"), (listmarker, "yaml_list"), (item, "yaml_value")]
				continue

			# Is it key: value?
			tmp = re.match(r"(.*?)(:)(.*)", dump[i])
			if tmp is not None:
				key = tmp[1]
				separator = tmp[2]
				value = tmp[3]
				dump[i] = [(key, "yaml_key"), (separator, "yaml_key_separator"), (value, "yaml_value")]
				continue

			# Nope, then we'll use default format
			dump[i] = [(dump[i], "default")]

	return dump

def ansible_get_hosts_by_group(inventory, group):
	hosts = []

	if not os.path.exists(inventory):
		return []

	with open(inventory, "r") as f:
		d = yaml.safe_load(f)

		if d.get(group) is not None and d[group].get("hosts") is not None:
			for host in d[group]["hosts"]:
				hosts.append(host)

	return hosts

def ansible_get_groups(inventory):
	groups = []

	if not os.path.exists(inventory):
		return []

	with open(inventory, "r") as f:
		d = yaml.safe_load(f)

		for group in d:
			groups.append(group)

	return groups

def ansible_get_groups_by_host(inventory, host):
	groups = []

	#if not os.path.exists(inventory):
	#	return []

	#with open(inventory, "r") as f:
	#	d = yaml.safe_load(f)

	for group in inventory:
		if inventory[group].get("hosts") and host in inventory[group]["hosts"]:
			groups.append(group)
	#	for group in d:
	#		if d[group].get("hosts") and host in d[group]["hosts"]:
	#			groups.append(group)

	return groups

def __ansible_create_inventory(inventory, overwrite = False):
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
			# workaround for Ubuntu 18.04 and various other older operating systems
			# that have python3 installed, but not as default
			"vars": {
				"ansible_python_interpreter": "/usr/bin/python3",
			}
		}
	}

	if ansible_configuration.ansible_user is not None:
		d["all"]["vars"]["ansible_user"] = ansible_configuration.ansible_user

	if ansible_configuration.ansible_password is not None:
		d["all"]["vars"]["ansible_ssh_pass"] = ansible_configuration.ansible_password

	if ansible_configuration.disable_strict_host_key_checking == True:
		d["all"]["vars"]["ansible_ssh_common_args"] = "-o StrictHostKeyChecking=no"

	yaml_str = yaml.safe_dump(d, default_flow_style = False).replace(r"''", '')

	with open(inventory, "w", opener = partial(os.open, mode = 0o640)) as f:
		f.write(yaml_str)

def ansible_create_groups(inventory, groups):
	changed = False

	if groups is None or len(groups) == 0:
		return True

	if os.path.isfile(inventory) == False:
		__ansible_create_inventory(inventory, overwrite = False)

	with open(inventory, "r") as f:
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
		with open(inventory, "w", opener = partial(os.open, mode = 0o640)) as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

def ansible_delete_groups(inventory, group):
	if group == "":
		return True

	# Don't try to remove the "all" group; it's always needed
	if group == "all":
		return False

	if os.path.isfile(inventory) == False:
		__ansible_create_inventory(inventory, overwrite = False)

	with open(inventory, "r") as f:
		d = yaml.safe_load(f)

	if d.get(group) is None:
		return True

	# A group is counted as empty if it has hosts and/or vars as members,
	# but nothing else

	# If the group has more than 2 members,
	# don't delete it, since it contains something unknown
	if len(d[group]) > 2:
		return False
	elif len(d[group]) == 2:
		# The only acceptable groups (when deleting) are hosts and vars
		if "hosts" in d[group] == False or "vars" in d[group] == False:
			return False
	elif len(d[group]) == 1:
		# The only acceptable groups (when deleting) are hosts and vars
		if "hosts" in d[group] is None and "vars" in d[group] is None:
			return False

	if "hosts" in d[group] and d[group].get("hosts") is not None:
		if len(d[group]["hosts"]) > 0:
			return False

	if "vars" in d[group] and d[group].get("vars") is not None:
		if len(d[group]["vars"]) > 0:
			return False

	# At this point we know that the group exists and has at most 2 empty members,
	# those being hosts and vars; thus it's acceptable to delete it

	d[group].pop("hosts", None)
	d[group].pop("vars", None)
	d.pop(group, None)

	with open(inventory, "w", opener = partial(os.open, mode = 0o640)) as f:
		yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
		f.write(yaml_str)

	return True

# Set one or several values for a group
def ansible_set_vars(inventory, group, values):
	changed = False

	if group is None or group == "":
		sys.exit("ansible_set_vars: group is empty or None; this is a programming error")

	if values is None or values == {}:
		sys.exit("ansible_set_vars: values is empty or None; this is a programming error")

	if os.path.isfile(inventory) == False:
		__ansible_create_inventory(inventory, overwrite = False)

	with open(inventory, "r") as f:
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
		with open(inventory, "w", opener = partial(os.open, mode = 0o640)) as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

# Set one or several vars for the specified groups
def ansible_set_groupvars(inventory, groups, groupvars):
	changed = False

	if groups is None or len(groups) == 0:
		raise Exception("ansible_set_vars: groups is empty or groups; this is a programming error")

	if groupvars is None or groupvars == []:
		raise Exception("ansible_set_vars: groupvars is empty or None; this is a programming error")

	if os.path.isfile(inventory) == False:
		raise Exception("ansible_set_vars: the inventory doesn't exist; this is a programming error")

	with open(inventory, "r") as f:
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
		with open(inventory, "w", opener = partial(os.open, mode = 0o640)) as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

# Set one or several vars for hosts in the group all
def ansible_set_hostvars(inventory, hosts, hostvars):
	changed = False

	if hosts is None or len(hosts) == 0:
		raise Exception("ansible_set_vars: hosts is empty or None; this is a programming error")

	if hostvars is None or hostvars == []:
		raise Exception("ansible_set_vars: hostvars is empty or None; this is a programming error")

	if os.path.isfile(inventory) == False:
		raise Exception("ansible_set_vars: the inventory doesn't exist; this is a programming error")

	with open(inventory, "r") as f:
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
		with open(inventory, "w", opener = partial(os.open, mode = 0o640)) as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

# Unset one or several vars in the specified groups
def ansible_unset_groupvars(inventory, groups, groupvars):
	changed = False

	if groups is None or len(groups) == 0:
		raise Exception("ansible_set_vars: groups is empty or groups; this is a programming error")

	if groupvars is None or groupvars == []:
		raise Exception("ansible_set_vars: groupvars is empty or None; this is a programming error")

	if os.path.isfile(inventory) == False:
		raise Exception("ansible_set_vars: the inventory doesn't exist; this is a programming error")

	with open(inventory, "r") as f:
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
		with open(inventory, "w", opener = partial(os.open, mode = 0o640)) as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

# Unset one or several vars for the specified host in the group all
def ansible_unset_hostvars(inventory, hosts, hostvars):
	changed = False

	if hosts is None or len(hosts) == 0:
		raise Exception("ansible_set_vars: hosts is empty or None; this is a programming error")

	if hostvars is None or hostvars == []:
		raise Exception("ansible_set_vars: hostvars is empty or None; this is a programming error")

	if os.path.isfile(inventory) == False:
		raise Exception("ansible_set_vars: the inventory doesn't exist; this is a programming error")

	with open(inventory, "r") as f:
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
		with open(inventory, "w", opener = partial(os.open, mode = 0o640)) as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

# Add hosts to the ansible inventory
# If the inventory doesn't exist, create it
def ansible_add_hosts(inventory, hosts, group = "", skip_all = False):
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

			with open(inventory, "r") as f:
				d = yaml.safe_load(f)
	else:
		with open(inventory, "r") as f:
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
			if not host in d["all"]["hosts"]:
				d["all"]["hosts"][host] = ""
				changed = True

		# If the group doesn't exist,
		# create it--we currently don't support
		# nested groups, node vars or anything like that
		#
		# We don't want to overwrite groups
		if group != "" and group != "all":
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
		with open(inventory, "w", opener = partial(os.open, mode = 0o640)) as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

# Remove hosts from ansible groups
def ansible_remove_hosts(inventory, hosts, group = None):
	changed = False

	# Treat empty or zero-length hosts as a programming error
	if hosts is None or len(hosts) == 0:
		raise Exception("None or zero-length hosts; this is a programming error")

	# Treat empty or zero-length group as a programming error
	if group is None or len(group) == 0:
		raise Exception("None or zero-length group; this is a programming error")

	if os.path.isfile(inventory) == False:
		return False

	with open(inventory, "r") as f:
		d = yaml.safe_load(f)

	for host in hosts:
		if d[group].get("hosts") is not None:
			if host in d[group]["hosts"]:
				d[group]["hosts"].pop(host, None)
				changed = True
			if len(d[group]["hosts"]) == 0:
				d[group]["hosts"] = None

	if changed == True:
		with open(inventory, "w", opener = partial(os.open, mode = 0o640)) as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

# Remove groups from the ansible inventory
# force is needed to remove non-empty groups
def ansible_remove_groups(inventory, groups, force = False):
	changed = False

	# Treat empty or zero-length groups as a programming error
	if groups is None or len(groups) == 0:
		raise Exception("None or zero-length group; this is a programming error")

	if os.path.isfile(inventory) == False:
		return False

	with open(inventory, "r") as f:
		d = yaml.safe_load(f)

	for group in groups:
		if d.get(group) is None:
			continue

		if d[group].get("hosts") is not None and force == False:
			continue

		d.pop(group)
		changed = True

	if changed == True:
		with open(inventory, "w", opener = partial(os.open, mode = 0o640)) as f:
			yaml_str = yaml.safe_dump(d, default_flow_style = False).replace("''", "").replace("null", "")
			f.write(yaml_str)

	return True

# Returns a list of all available logs
# (full_name, name, date, path)
def ansible_get_logs():
	logs = []

	for item in os.listdir(ANSIBLE_LOG_DIR):
		#if os.path.isdir(item) == False:
		#	continue

		tmp = re.match(r"^(\d\d\d\d-\d\d-\d\d_\d\d:\d\d:\d\d\.\d+)_(.*)", item)
		if tmp is not None:
			date = datetime.strptime(tmp[1], "%Y-%m-%d_%H:%M:%S.%f")
			full_name = item
			name = tmp[2]
			logs.append((item, name, f"{ANSIBLE_LOG_DIR}/{item}", date))
		else:
			raise Exception(f"Could not parse {item}")
	return logs

def ansible_extract_failure(retval, error_msg_lines, skipped = False, unreachable = False):
	status = ""

	if unreachable == True:
		for line in error_msg_lines:
			if "Name or service not known" in line:
				status = "COULD NOT RESOLVE"
				break
			elif "Permission denied" in line:
				status = "PERMISSION DENIED"
				break
			elif "The module failed to execute correctly" in line:
				status = "MISSING INTERPRETER?"
				break
			elif "No route to host" in line:
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

def ansible_results_add(event):
	host = deep_get(event, "event_data#host", "")
	if len(host) == 0:
		return 0

	task = deep_get(event, "event_data#task", "")
	if len(task) == 0:
		return 0

	ansible_facts = deep_get(event, "event_data#res#ansible_facts", {})

	skipped = deep_get(event, "event", "") == "runner_on_skipped"
	unreachable = deep_get(event, "event_data#res#unreachable", False)

	if unreachable == True:
		retval = -1
	elif skipped == True or deep_get(event, "event", "") == "runner_on_ok":
		retval = 0
	else:
		retval = deep_get(event, "event_data#res#rc")

	if retval is None:
		return 0

	taskname = task

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
		"retval": retval,
		"unreachable": unreachable,
		"status": "UNKNOWN",
		"skipped": skipped,
		"stdout_lines": [],
		"stderr_lines": [],
		"msg_lines": [],
		"ansible_facts": ansible_facts,
	}

	if unreachable == False and retval == 0:
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
			if retval != 0:
				d["stderr_lines"] = msg_lines
			else:
				d["msg_lines"] = msg_lines
	else:
		d["stdout_lines"] = ["<no output>"]

	error_msg_lines = stderr_lines
	if len(error_msg_lines) == 0:
		error_msg_lines = msg_lines
	d["status"] = ansible_extract_failure(retval, error_msg_lines, skipped = skipped, unreachable = unreachable)

	if host not in ansible_results:
		ansible_results[host] = []
	ansible_results[host].append(d)

	return retval

def ansible_delete_log(log):
	if os.path.exists(f"{ANSIBLE_LOG_DIR}/{log}"):
		for filename in os.listdir(f"{ANSIBLE_LOG_DIR}/{log}"):
			os.remove(f"{ANSIBLE_LOG_DIR}/{log}/{filename}")
		os.rmdir(f"{ANSIBLE_LOG_DIR}/{log}")

def ansible_write_log(start_date, playbook, events):
	save_logs = ansible_configuration.save_logs
	if save_logs == False:
		return

	playbook_name = playbook
	if "/" in playbook_name:
		tmp = re.match(r".*/(.*).yaml", playbook)
		playbook_name = tmp[1]

	directory_name = f"{start_date}_{playbook_name}".replace(" ", "_")
	os.mkdir(f"{ANSIBLE_LOG_DIR}/{directory_name}")

	# Start by creating a file with metadata about the whole run
	d = {
		"playbook_path": playbook,
		"created_at": start_date,
	}

	with open(f"{ANSIBLE_LOG_DIR}/{directory_name}/metadata.yaml", "w", opener = partial(os.open, mode = 0o640)) as f:
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

		with open(f"{ANSIBLE_LOG_DIR}/{directory_name}/{filename}", "w", opener = partial(os.open, mode = 0o640)) as f:
			f.write(yaml.dump(d, default_flow_style = False, sort_keys = False))

def ansible_print_task_results(task, msg_lines, stdout_lines, stderr_lines, retval, unreachable = False, skipped = False):
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

def ansible_print_play_results(retval, ansible_results):
	if retval != 0 and len(ansible_results) == 0:
		iktprint([("Failed to execute playbook; retval: ", "error"), (f"{retval}", "errorvalue")], stderr = True)
	else:
		for host in ansible_results:
			plays = ansible_results[host]
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

def ansible_run_playbook(playbook, override_inventory = False):
	global ansible_results
	global active_task
	global suffix

	forks = ansible_configuration.ansible_forks

	# Flush previous results
	ansible_results = {}

	if override_inventory == True:
		inventory = []
	else:
		inventory = [ANSIBLE_INVENTORY]
	if os.path.exists(ANSIBLE_TMP_INVENTORY):
		inventory.append(ANSIBLE_TMP_INVENTORY)

	start_date = datetime.now()

	runner = ansible_runner.interface.run(json_mode = True, quiet = True, playbook = playbook, inventory = inventory)
	retval = 0
	if runner is not None:
		for event in runner.events:
			_retval = ansible_results_add(event)
			if retval == 0 and _retval != 0:
				retval = _retval
		ansible_write_log(start_date, playbook, runner.events)

	# Remove old temporary inventory
	if os.path.isfile(ANSIBLE_TMP_INVENTORY):
		os.remove(ANSIBLE_TMP_INVENTORY)

	return retval, ansible_results

# Execute a playbook on a list of hosts
# by creating a temporary inventory
def ansible_run_playbook_on_host_list(playbook, hosts, values = None):
	# Remove old temporary inventory
	if os.path.isfile(ANSIBLE_TMP_INVENTORY):
		os.remove(ANSIBLE_TMP_INVENTORY)

	ansible_add_hosts(ANSIBLE_TMP_INVENTORY, hosts, group = "selection", skip_all = False)

	if values is not None and len(values) > 0:
		ansible_set_vars(ANSIBLE_TMP_INVENTORY, group = "all", values = values)

	return ansible_run_playbook(playbook, override_inventory = True)

# Execute a playbook using ansible
def ansible_run_playbook_on_selection(playbook, selection, values = None):
	# Remove old temporary inventory
	if os.path.isfile(ANSIBLE_TMP_INVENTORY):
		os.remove(ANSIBLE_TMP_INVENTORY)

	ansible_add_hosts(ANSIBLE_TMP_INVENTORY, selection, group = "selection", skip_all = True)

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
		values["ansible_user"] = ansible_configuration.ansible_user

	if len(values) > 0:
		ansible_set_vars(ANSIBLE_TMP_INVENTORY, group = "all", values = values)

	return ansible_run_playbook(playbook)

def ansible_ping(inventory, selection = []):
	save_logs_tmp = ansible_configuration.save_logs
	ansible_configuration.save_logs = False

	host_status = []

	if len(selection) == 0:
		selection = ansible_get_hosts_by_group(ANSIBLE_INVENTORY, "all")

	_retval, ansible_results = ansible_run_playbook_on_selection(f"{ANSIBLE_PLAYBOOK_DIR}/ping.yaml", selection = selection)

	for host in ansible_results:
		for task in deep_get(ansible_results, host, []):
			unreachable = deep_get(task, "unreachable")
			skipped = deep_get(task, "skipped")
			stderr_lines = deep_get(task, "stderr_lines")
			retval = deep_get(task, "retval")
			status = ansible_extract_failure(retval, stderr_lines, skipped = skipped, unreachable = unreachable)
			host_status.append((host, status))
	ansible_configuration.save_logs = save_logs_tmp
	return host_status
