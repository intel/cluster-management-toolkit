#! /usr/bin/env python3
# Requires: python3 (>= 3.6)
from datetime import datetime
from functools import partial, reduce
import os
from pathlib import Path
import pwd
import re
import subprocess
from subprocess import PIPE
import shutil
import sys
import yaml

from iktlib import deep_get

ansible_support = False
ansible_bin_path = None
ansible_results = {}

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
	from ansible import context
	import ansible.constants as ansibleC
	from ansible.executor.playbook_executor import PlaybookExecutor
	from ansible.inventory.host import Host
	from ansible.inventory.manager import InventoryManager
	from ansible.module_utils.common.collections import ImmutableDict
	from ansible.parsing.dataloader import DataLoader
	from ansible.plugins.callback import CallbackBase
	from ansible.utils.unsafe_proxy import AnsibleUnsafeText
	from ansible.vars.manager import VariableManager
	ansible_support = True
except:
	ansible_support = False

def ansible_ping(inventory, selection = "all"):
	host_status = []

	# FIXME: ansible bin path
	forks = ansible_configuration.ansible_forks

	# "-o" => one line result; makes parsing easier
	ansible_command = [ "/usr/bin/ansible", "-o", f"--forks={forks}", f"--inventory={inventory}", selection, "-m", "ping" ]
	result = subprocess.run(ansible_command, stdout = PIPE, stderr = PIPE, universal_newlines = True)

	for line in result.stdout.splitlines():
		tmp = re.match(r"^(.*?) \| (.*?):? (.*)", line)
		if tmp is not None:
			host = tmp[1]
			status = tmp[2]
			output = tmp[3]
			if "Permission denied" in output:
				status = "PERMISSION DENIED"
			elif "The module failed to execute correctly" in output:
				status = "MISSING INTERPRETER?"
			elif "Name or service not known" in output:
				status = "COULD NOT RESOLVE"
			host_status.append((host, status))

	return result.returncode, host_status

# If ansible support is available, ensure that the directories are there
if ansible_support == True:
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

	if not os.path.exists(ANSIBLE_INVENTORY):
		return []

	with open(ANSIBLE_INVENTORY, "r") as f:
		d = yaml.safe_load(f)

		for group in d:
			if d[group].get("hosts") and host in d[group]["hosts"]:
				groups.append(group)

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

def ansible_delete_log(log):
	if os.path.exists(f"{ANSIBLE_LOG_DIR}/{log}"):
		for filename in os.listdir(f"{ANSIBLE_LOG_DIR}/{log}"):
			os.remove(f"{ANSIBLE_LOG_DIR}/{log}/{filename}")
		os.rmdir(f"{ANSIBLE_LOG_DIR}/{log}")

def ansible_write_log(start_date, playbook, ansible_results):
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


	for host in ansible_results:
		i = 0
		for task in ansible_results[host]:
			taskname = task
			if taskname.startswith("TASK: debug"):
				continue
			elif taskname.startswith("TASK: "):
				taskname = taskname[len("TASK: "):]
			elif taskname.startswith("output"):
				tmp = re.match(r"output.*?_(.*)", taskname)
				if tmp:
					taskname = tmp[1].replace("_", " ")
			elif taskname == "":
				taskname = "<unnamed>"
			i += 1

			filename = f"{i:02d}-{host}_{taskname}.yaml".replace(" ", "_").replace("/", "_")
			hostname = f"{str(host)}"
			retval = ansible_results[host][task].get("rc", 0)
			msg = str(ansible_results[host][task].get("msg", ""))
			msg_lines = []
			if len(msg) > 0:
				msg_lines = str(ansible_results[host][task].get("msg", "")).split("\n")
			start_date_timestamp = str(ansible_results[host][task].get("start"))
			end_date_timestamp = str(ansible_results[host][task].get("end"))
			stdout = str(ansible_results[host][task].get("stdout", ""))
			stderr = str(ansible_results[host][task].get("stderr", ""))
			stdout_lines = [str(f) for f in ansible_results[host][task].get("stdout_lines", "")]
			stderr_lines = [str(f) for f in ansible_results[host][task].get("stderr_lines", "")]

			if len(stdout_lines) == 0 and len(stdout) > 0:
				stdout_lines = stdout.split("\n")
			if len(stderr_lines) == 0 and len(stderr) > 0:
				stderr_lines = stderr.split("\n")

			d = {
				"playbook": playbook_name,
				"playbook_file": playbook,
				"task": taskname,
				"host": hostname,
				"start_date": start_date_timestamp,
				"end_date": end_date_timestamp,
				"retval": retval,
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
					d["msg_lines"] = msg_lines
			else:
				d["stdout_lines"] = ["<no output>"]

			with open(f"{ANSIBLE_LOG_DIR}/{directory_name}/{filename}", "w", opener = partial(os.open, mode = 0o640)) as f:
				f.write(yaml.dump(d, default_flow_style = False, sort_keys = False))

if ansible_support == True:
	active_task = ""
	suffix = 0

	def ansible_clean_results(item):
		newitem = None
		if item is None:
			return None
		elif isinstance(item, AnsibleUnsafeText):
			newitem = str(item)
		elif isinstance(item, Host):
			newitem = str(item)
		elif type(item) == list or type(item) == tuple:
			if newitem is None:
				newitem = []
			for i in item:
				newitem.append(ansible_clean_results(i))
			if type(item) == tuple:
				newitem = tuple(newitem)
		elif type(item) == dict:
			if newitem is None:
				newitem = {}
			for key in item:
				newitem[ansible_clean_results(key)] = ansible_clean_results(item[key])
		elif type(item) in [str, int, bool]:
			newitem = item
		else:
			raise Exception(f"unhandled type: {type(item)} for item: {item}")
		return newitem

	# Ansible callback
	class ResultCallback(CallbackBase):
		def v2_runner_on_ok(self, result, **kwargs):
			global ansible_results
			global active_task
			global suffix

			host = result._host
			output = result._result

			if active_task == "":
				sys.exit("v2_runner_on_ok: active_task is empty; this should never happen!")

			if active_task == "TASK: Gathering Facts":
				return

			key = f"{active_task}"
			if ansible_results.get(host) is None:
				ansible_results[host] = { active_task: result._result }
			else:
				newkey = key
				if ansible_results[host].get(key) is not None:
					newkey = f"{key}#{suffix}"
					suffix += 1
				ansible_results[host][newkey] = result._result

		def v2_runner_on_failed(self, result, **kwargs):
			global ansible_results
			global active_task
			global suffix

			host = result._host

			if active_task == "":
				sys.exit("v2_runner_on_failed: active_task is empty; this should never happen!")

			# While we ignore the Gathering Facts task when the return value is OK,
			# we need to process it on failure
			key = f"{active_task}"
			if ansible_results.get(host) is None:
				ansible_results[host] = { active_task: result._result }
			else:
				newkey = key
				if ansible_results[host].get(key) is not None:
					newkey = f"{key}#{suffix}"
					suffix += 1
				ansible_results[host][newkey] = result._result

		#def v2_runner_on_unreachable(self, result, **kwargs):
		#	sys.exit(f"host {result._host} unreachable")

		def v2_runner_on_skipped(self, result, **kwargs):
			global ansible_results
			global active_task
			global suffix

			host = result._host

			if active_task == "":
				sys.exit("v2_runner_on_skipped: active_task is empty; this should never happen!")

			# While we ignore the Gathering Facts task when the return value is OK,
			# we need to process it on failure
			key = f"{active_task}"
			if ansible_results.get(host) is None:
				ansible_results[host] = { active_task: result._result }
			else:
				newkey = key
				if ansible_results[host].get(key) is not None:
					newkey = f"{key}#{suffix}"
					suffix += 1
				ansible_results[host][newkey] = result._result

		#def v2_playbook_on_notify(self, task, is_conditional):
		#def v2_playbook_on_include(self, task, is_conditional):
		#def v2_playbook_on_no_hosts_remaining(self, task, is_conditional):

		def v2_playbook_on_task_start(self, task, is_conditional):
			global active_task

			active_task = str(task)

	def ansible_run_playbook(playbook):
		global ansible_results
		global active_task
		global suffix

		forks = ansible_configuration.ansible_forks

		# Flush previous results
		ansible_results = {}
		active_task = ""
		suffix = 0

		context.CLIARGS = ImmutableDict(
			connection = "smart",		# The python ssh method
			module_path = [],		# We don't have any custom modules
			forks = forks,			# Override the number of forks
			become = None,			# This is provided by the playbooks
			become_method = "sudo",		# If we need to become root, use sudo
			become_user = None,		# This is provided by the playbooks
			check = False,			# We don't want to do a dummy run
			diff = False,			# We don't want a diff of modified files
			syntax = False,
			start_at_task = None,
			verbosity = 0,
		)

		passwords = dict(vault_pass = "")

		results_callback = ResultCallback()
		loader = DataLoader()
		sources = [ANSIBLE_INVENTORY]
		if os.path.exists(ANSIBLE_TMP_INVENTORY):
			sources.append(ANSIBLE_TMP_INVENTORY)
		inventory = InventoryManager(loader = loader, sources = sources)
		variable_manager = VariableManager(loader = loader, inventory = inventory)

		pbex = PlaybookExecutor(
			playbooks = [playbook],
			inventory = inventory,
			variable_manager = variable_manager,
			loader = loader,
			passwords = passwords)
		pbex._tqm._stdout_callback = results_callback

		start_date = datetime.now()

		result = pbex.run()

		ansible_write_log(start_date, playbook, ansible_results)

		# Remove old temporary inventory
		if os.path.isfile(ANSIBLE_TMP_INVENTORY):
			os.remove(ANSIBLE_TMP_INVENTORY)

		return result, ansible_results

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
