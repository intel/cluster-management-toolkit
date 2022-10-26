#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

"""
This file contains helpers that provide an obj for use in info views,
for cases where the obj provided from the list view isn't sufficient
"""

import os
from pathlib import PurePath
import sys

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-natsort")

from ikttypes import DictPath, FilePath, FilePathAuditError, SecurityChecks
from ansible_helper import ansible_run_playbook_on_selection, get_playbook_path
from iktlib import deep_get
from iktio import check_path, secure_read_yaml

def objgetter_ansible_facts(obj):
	"""
	Get an obj by using ansible facts

		Parameters:
			obj (dict): The obj to use as reference
		Returns:
			obj (dict): An ansible facts object
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

	return ar

def objgetter_ansible_log(obj):
	"""
	Get an obj from an ansible log entry

		Parameters:
			obj (dict): The obj to use as reference
		Returns:
			obj (dict): An ansible log entry
	"""

	tmpobj = {}

	tmpobj = secure_read_yaml(FilePath(f"{obj}/metadata.yaml"))
	tmpobj["log_path"] = obj

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
		SecurityChecks.IS_SYMLINK,
	]

	playbook_path = FilePath(tmpobj["playbook_path"])
	playbook_dir = FilePath(str(PurePath(playbook_path).parent))

	violations = check_path(playbook_dir, checks = checks)
	if len(violations) > 0:
		violation_strings = []
		for violation in violations:
			violation_strings.append(str(violation))
		violations_joined = ",".join(violation_strings)
		raise FilePathAuditError(f"Violated rules: {violations_joined}", path = playbook_dir)

	# We don't want to check that parent resolves to itself,
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
		playbook = secure_read_yaml(playbook_path, checks = checks)
		tmpobj["name"] = deep_get(playbook, DictPath("vars#metadata#description"))
		tmpobj["playbook_types"] = deep_get(playbook, DictPath("vars#metadata#playbook_types"), ["<any>"])
		tmpobj["category"] = deep_get(playbook, DictPath("vars#metadata#category"), "Uncategorized")
	except FileNotFoundError:
		tmpobj["name"] = "File not found"
		tmpobj["playbook_types"] = ["Unavailable"]
		tmpobj["category"] = "Unavailable"

	logs = []
	for path in natsorted(os.listdir(obj)):
		if path == "metadata.yaml":
			continue
		log = secure_read_yaml(FilePath(f"{obj}/{path}"))
		logs.append({
			"index": path.split("-")[0],
			"log": log
		})
	tmpobj["logs"] = logs

	return tmpobj

# Objgetters acceptable for direct use in view files
objgetter_allowlist = {
	"objgetter_ansible_facts": objgetter_ansible_facts,
	"objgetter_ansible_log": objgetter_ansible_log,
}
