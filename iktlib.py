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
	result = reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, path.split("#"), dictionary)
	if result is None:
		result = default
	return result

def deep_get_with_fallback(obj, paths, default = None):
	result = None
	for path in paths:
		result = deep_get(obj, path)
		if result is not None:
			break
	if result is None:
		result = default
	return result

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

def __str_representer(dumper, data):
	if "\n" in data:
		return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
	return dumper.represent_scalar("tag:yaml.org,2002:str", data)

def format_yaml_line(line, override_formatting = {}):
	if type(override_formatting) == dict:
		generic_format = ("types", "generic")
		comment_format = ("types", "yaml_comment")
		key_format = ("types", "yaml_key")
		value_format = ("types", "yaml_value")
		list_format = ("separators", "yaml_list")
		separator_format = ("types", "generic")
		reference_format = ("types", "yaml_reference")
	elif type(override_formatting) == tuple:
		generic_format = override_formatting
		comment_format = override_formatting
		key_format = override_formatting
		value_format = override_formatting
		list_format = ("- ", override_formatting)
		separator_format = override_formatting
		reference_format = override_formatting

	tmpline = []
	if line.lstrip(" ").startswith("#"):
		tmpline += [
			(line, comment_format),
		]
		return tmpline
	if line.lstrip(" ").startswith("- "):
		tmp = re.match("^(\s*?)- (.*)", line)
		tmpline += [
			(f"{tmp[1]}", generic_format),
			list_format,
		]
		line = tmp[2]
		if len(line) == 0:
			return tmpline

	if line.endswith(":"):
		if type(override_formatting) == dict:
			_key_format = deep_get(override_formatting, f"{line[:-1]}#key", key_format)
		else:
			_key_format = key_format
		tmpline += [
			(f"{line[:-1]}", _key_format),
			(":", separator_format),
		]
	else:
		tmp = re.match(r"^(.*?)(:\s*?)(&|\.|)(.*)", line)
		if tmp is not None and (tmp[1].strip().startswith("\"") and tmp[1].strip().endswith("\"") or (not tmp[1].strip().startswith("\"") and not tmp[1].strip().endswith("\""))):
			key = tmp[1]
			reference = tmp[2]
			separator = tmp[3]
			value = tmp[4]
			if type(override_formatting) == dict:
				_key_format = deep_get(override_formatting, f"{key.strip()}#key", key_format)
				if value.strip() in ["{", "["]:
					_value_format = value_format
				else:
					_value_format = deep_get(override_formatting, f"{key.strip()}#value", value_format)
			else:
				_key_format = key_format
				_value_format = value_format
			tmpline += [
				(f"{key}", _key_format),
				(f"{separator}", separator_format),
				(f"{reference}", reference_format),
				(f"{value}", _value_format),
			]
		else:
			if type(override_formatting) == dict:
				_value_format = deep_get(override_formatting, f"{line}#value", value_format)
			else:
				_value_format = value_format
			tmpline += [
				(f"{line}", _value_format),
			]

	return tmpline

# Takes a list of yaml dictionaries and returns a single list of themearray
def format_yaml(objects, override_formatting = {}):
	dumps = []
	indent = 4 #deep_get(iktconfig, "Global#indent", 4)

	yaml.add_representer(str, __str_representer)

	for i in range(0, len(objects)):
		obj = objects[i]
		if type(obj) == dict:
			split_dump = yaml.dump(obj, default_flow_style = False, indent = indent, width = sys.maxsize).splitlines()
		else:
			split_dump = obj.splitlines()
		first = True
		if len(split_dump) > 0 and "\n" not in obj and split_dump[0].startswith("'") and split_dump[0].endswith("'"):
			split_dump[0] = split_dump[0][1:-1]

		for line in split_dump:
			# This allows us to use the yaml formatter for json too
			if first == True:
				first = False
				if line in ["|", "|-"]:
					continue
			if len(line) == 0:
				continue

			tmpline = format_yaml_line(line, override_formatting = override_formatting)
			dumps.append(tmpline)

		if i < len(objects) - 1:
			dumps.append([("", generic_format)])
			dumps.append([("", generic_format)])
			dumps.append([("", generic_format)])

	return dumps
