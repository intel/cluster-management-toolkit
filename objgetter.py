#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

import os
import yaml

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-natsort")

from ansible_helper import ansible_run_playbook_on_selection, get_playbook_path
from iktlib import deep_get

def objgetter_ansible_facts(obj):
	hostname = deep_get(obj, "name", "")
	get_facts_path = get_playbook_path("get_facts.yaml")
	retval, ansible_results = ansible_run_playbook_on_selection(get_facts_path, [hostname])
	if retval != 0:
		return {}

	ar = {}

	for result in deep_get(ansible_results, hostname, []):
		if deep_get(result, "task", "") == "Gathering host facts":
			ar = deep_get(result, "ansible_facts")

	return ar

def objgetter_ansible_log(obj):
	tmpobj = {}

	with open(f"{obj}/metadata.yaml", "r") as f:
		tmpobj = yaml.safe_load(f)
		tmpobj["log_path"] = obj

	try:
		with open(tmpobj["playbook_path"], "r") as f:
			playbook = yaml.safe_load(f)[0]
			tmpobj["name"] = deep_get(playbook, "vars#metadata#description")
			tmpobj["playbook_types"] = deep_get(playbook, "vars#metadata#playbook_types", ["<any>"])
			tmpobj["category"] = deep_get(playbook, "vars#metadata#category", "Uncategorized")
	except FileNotFoundError:
		tmpobj["name"] = "File not found"
		tmpobj["playbook_types"] = ["Unavailable"]
		tmpobj["category"] = "Unavailable"
		pass

	logs = []
	for path in natsorted(os.listdir(obj)):
		if path == "metadata.yaml":
			continue
		with open(f"{obj}/{path}", "r") as f:
			logs.append({
				"index": path.split("-")[0],
				"log": yaml.safe_load(f)
			})
	tmpobj["logs"] = logs

	return tmpobj

# Objgetters acceptable for direct use in view files
objgetter_allowlist = {
	"objgetter_ansible_facts": objgetter_ansible_facts,
	"objgetter_ansible_log": objgetter_ansible_log,
}
