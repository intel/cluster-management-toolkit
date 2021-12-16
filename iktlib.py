#! /usr/bin/env python3
from functools import reduce
from pathlib import Path
import os
import re
import sys
import yaml

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-natsort")

HOMEDIR = str(Path.home())
IKTDIR = f"{HOMEDIR}/.ikt"
IKT_CONFIG_FILENAME = "ikt.yaml"
IKT_CONFIG_FILE = f"{IKTDIR}/{IKT_CONFIG_FILENAME}"
IKT_CONFIG_FILE_DIR = f"{IKTDIR}/{IKT_CONFIG_FILENAME}.d"

class stgroup:
	DONE = 7
	OK = 6
	PENDING = 5
	WARNING = 4
	ADMIN = 3
	NOT_OK = 2
	UNKNOWN = 1
	CRIT = 0

stgroup_mapping = {
	stgroup.CRIT: "status_critical",
	stgroup.UNKNOWN: "status_unknown",
	stgroup.NOT_OK: "status_not_ok",
	stgroup.ADMIN: "status_admin",
	stgroup.WARNING: "status_warning",
	stgroup.OK: "status_ok",
	stgroup.PENDING: "status_pending",
	stgroup.DONE: "status_done",
}

def deep_get(dictionary, path, default = None):
	if dictionary is None:
		return default
	if path is None or len(path) == 0:
		return default
	return reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, path.split("#"), dictionary)

def read_iktconfig():
	if os.path.isfile(IKT_CONFIG_FILE) is False:
		return

	# Read the base configuration file
	with open(IKT_CONFIG_FILE) as f:
		iktconfig = yaml.safe_load(f)

	# Now read ikt.yaml.d/* if available
	if os.path.isdir(IKT_CONFIG_FILE_DIR) is False:
		return

	for item in natsorted(os.listdir(IKT_CONFIG_FILE_DIR)):
		# Only read entries that end with .y{,a}ml
		if not (item.endswith(".yml") or item.endswith(".yaml")):
			continue

		# Read the conflet files
		with open(f"{IKT_CONFIG_FILE_DIR}/{item}") as f:
			moreiktconfig = yaml.safe_load(f)

		# Handle config files without any values defined
		if moreiktconfig is not None:
			iktconfig = {**iktconfig, **moreiktconfig}

	return iktconfig

# Helper functions
def versiontuple(ver):
	filled = []
	for point in ver.split("."):
		filled.append(point.zfill(8))
	return tuple(filled)

def join_tuple_list(items, _tuple = "", item_prefix = None, item_suffix = None, separator = None):
	_list = []
	first = True

	for item in items:
		if first == False and separator is not None:
			_list.append(separator)
		if item_prefix is not None:
			_list.append(item_prefix)
		if type(item) == tuple:
			_list.append(item)
		else:
			_list.append((item, _tuple))
		if item_suffix is not None:
			_list.append(item_suffix)
		first = False
	return _list

def age_to_seconds(age):
	seconds = 0

	tmp = re.match("^(\d+d)?(\d+h)?(\d+m)?(\d+s)?", age)
	if tmp is not None:
		if len(tmp[0]) == 0:
			seconds = -1
		else:
			d = 0 if tmp[1] is None else int(tmp[1][:-1])
			h = 0 if tmp[2] is None else int(tmp[2][:-1])
			m = 0 if tmp[3] is None else int(tmp[3][:-1])
			s = 0 if tmp[4] is None else int(tmp[4][:-1])
			seconds = d * 24 * 60 * 60 + h * 60 * 60 + m * 60 + s
	else:
		raise Exception(f"age regex did not match; age: {age}")

	return seconds

def seconds_to_age(seconds):
	age = ""
	fields = 0

	if seconds == 0:
		return "<unset>"
	if seconds >= 24 * 60 * 60:
		days = seconds // (24 * 60 * 60)
		seconds -= days * 24 * 60 * 60
		age += f"{days}d"
		if days >= 7:
			return age
		fields += 1
	if seconds >= 60 * 60:
		hours = seconds // (60 * 60)
		seconds -= hours * 60 * 60
		age += f"{hours}h"
		if hours >= 12:
			return age
		fields += 1
	if seconds >= 60 and fields < 2:
		minutes = seconds // 60
		seconds -= minutes * 60
		age += f"{minutes}m"
		fields += 1
	if seconds > 0 and fields < 2:
		age += f"{seconds}s"

	return age
