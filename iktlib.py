#! /usr/bin/env python3

"""
Helpers used by various components of iKT
"""

from datetime import datetime, timezone, timedelta, date
from functools import reduce
import os
import re
import subprocess
from subprocess import PIPE, STDOUT
import sys
import yaml

from iktpaths import ANSIBLE_PLAYBOOK_DIR, IKT_CONFIG_FILE_DIR
from iktpaths import IKT_CONFIG_FILE

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-natsort")

iktconfig = {}

def clamp(value, minval, maxval):
	return min(maxval, max(minval, value))

def none_timestamp():
	return (datetime.combine(date.min, datetime.min.time()) + timedelta(days = 1)).astimezone()

def disksize_to_human(size):
	size_suffixes = [
		" bytes",
		"kiB",
		"MiB",
		"GiB",
		"TiB",
		"PiB",
	]
	for i in range(0, len(size_suffixes)):
		if size < 1024:
			break
		size = size // 1024
	suffix = size_suffixes[i]
	return f"{size}{suffix}"

def split_msg(rawmsg):
	# We only want "\n" to represent newlines
	tmp = rawmsg.replace("\r\n", "\n")
	return list(map(str.rstrip, tmp.splitlines()))

def deep_set(dictionary, path, value, create_path = False):
	if dictionary is None or path is None or len(path) == 0:
		raise Exception(f"deep_set: dictionary {dictionary} or path {path} invalid/unset")

	ref = dictionary
	pathsplit = path.split("#")
	for i in range(0, len(pathsplit)):
		if pathsplit[i] in ref:
			if i == len(pathsplit) - 1:
				ref[pathsplit[i]] = value
				break

			ref = ref.get(pathsplit[i])
			if ref is None or not isinstance(ref, dict):
				raise Exception(f"Path {path} does not exist in dictionary {dictionary} or is the wrong type {type(ref)}")
		elif create_path == True:
			if i == len(pathsplit) - 1:
				ref[pathsplit[i]] = value
			else:
				ref[pathsplit[i]] = {}

def deep_get(dictionary, path, default = None):
	if dictionary is None:
		return default
	if path is None or len(path) == 0:
		return default
	result = reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, path.split("#"), dictionary)
	if result is None:
		result = default
	return result

def deep_get_recursive(dictionary, path_fragments, result = None):
	if result is None:
		result = []

	for i in range(0, len(path_fragments)):
		tmp = deep_get(dictionary, path_fragments[i])
		if i + 1 == len(path_fragments):
			if tmp is None:
				return result
			return tmp

		if isinstance(tmp, dict):
			result = deep_get_recursive(tmp, path_fragments[i + 1:len(path_fragments)], result)
		elif isinstance(tmp, list):
			for tmp2 in tmp:
				result = deep_get_recursive(tmp2, path_fragments[i + 1:len(path_fragments)], result)

	return result

def deep_get_list(dictionary, paths, default = None, fallback_on_empty = False):
	for path in paths:
		result = deep_get_recursive(dictionary, path.split("#"))

		if result is not None and not (type(result) in (list, str, dict) and len(result) == 0 and fallback_on_empty == True):
			break
	if result is None or type(result) in (list, str, dict) and len(result) == 0 and fallback_on_empty == True:
		result = default
	return result

def deep_get_with_fallback(obj, paths, default = None, fallback_on_empty = False):
	if paths is None:
		return default

	result = None
	for path in paths:
		result = deep_get(obj, path)
		if result is not None and not (type(result) in (list, str, dict) and len(result) == 0 and fallback_on_empty == True):
			break
	if result is None or type(result) in (list, str, dict) and len(result) == 0 and fallback_on_empty == True:
		result = default
	return result

def read_iktconfig():
	global iktconfig # pylint: disable=global-statement

	if os.path.isfile(IKT_CONFIG_FILE) is False:
		return None

	# Read the base configuration file
	with open(IKT_CONFIG_FILE, encoding = "utf-8") as f:
		iktconfig = yaml.safe_load(f)

	# Now read ikt.yaml.d/* if available
	if os.path.isdir(IKT_CONFIG_FILE_DIR) is False:
		return None

	for item in natsorted(os.listdir(IKT_CONFIG_FILE_DIR)):
		# Only read entries that end with .y{,a}ml
		if item.startswith(("~", ".")):
			continue
		if not item.endswith((".yaml", ".yml")):
			continue

		# Read the conflet files
		with open(f"{IKT_CONFIG_FILE_DIR}/{item}", encoding = "utf-8") as f:
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
		if isinstance(item, tuple):
			_list.append(item)
		else:
			_list.append((item, _tuple))
		if item_suffix is not None:
			_list.append(item_suffix)
		first = False
	return _list

def age_to_seconds(age):
	seconds = 0

	# Safe
	tmp = re.match(r"^(\d+d)?(\d+h)?(\d+m)?(\d+s)?", age)
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

def seconds_to_age(seconds, negative_is_skew = False):
	age = ""
	fields = 0

	if not isinstance(seconds, int):
		return ""

	if seconds < -1:
		sign = "-"
	else:
		sign = ""

	if seconds < -1 and negative_is_skew == True:
		return "<clock skew detected>"

	seconds = abs(seconds)

	if seconds == 0:
		return "<unset>"
	if seconds >= 24 * 60 * 60:
		days = seconds // (24 * 60 * 60)
		seconds -= days * 24 * 60 * 60
		age += f"{days}d"
		if days >= 7:
			return f"{sign}{age}"
		fields += 1
	if seconds >= 60 * 60:
		hours = seconds // (60 * 60)
		seconds -= hours * 60 * 60
		age += f"{hours}h"
		if hours >= 12:
			return f"{sign}{age}"
		fields += 1
	if seconds >= 60 and fields < 2:
		minutes = seconds // 60
		seconds -= minutes * 60
		age += f"{minutes}m"
		fields += 1
	if seconds > 0 and fields < 2:
		age += f"{seconds}s"

	return f"{sign}{age}"

def get_since(timestamp):
	if timestamp is None:
		since = 0
	elif timestamp == -1 or timestamp == none_timestamp():
		since = -1
	# If the timestamp is an integer we assume it to already be in seconds
	elif isinstance(timestamp, int):
		since = timestamp
	else:
		timediff = datetime.now(timezone.utc) - timestamp
		since = timediff.days * 24 * 60 * 60 + timediff.seconds

	return since

# Will take datetime and convert it to a timestamp
def datetime_to_timestamp(timestamp):
	if timestamp is None or timestamp == none_timestamp():
		string = ""
	elif timestamp == datetime.fromtimestamp(0).astimezone():
		string = "".ljust(len(str(datetime.fromtimestamp(0).astimezone())))
	else:
		string = timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
	return string

def reformat_timestamp(timestamp):
	"""
	Takes a timestamp in various formats and formats it the proper(tm) way; ISO-8601

		Parameters:
			timestamp (str): A timestamp str
		Returns:
			(str): A timestamp str in YYYY-MM-DD HH:MM:SS format
	"""

	if timestamp is not None:
		for fmt in ("%Y-%m-%d %H:%M:%S.%f%z",
			    "%Y-%m-%d %H:%M:%S%z",
			    "%Y-%m-%dT%H:%M:%S.%f%z",
			    "%Y-%m-%dT%H:%M:%S%z"):

			try:
				return datetime.strptime(timestamp, fmt).astimezone().strftime("%Y-%m-%d %H:%M:%S")
			except ValueError:
				pass

	raise ValueError(f"Could not parse timestamp: {timestamp}")

# Will take a timestamp and convert it to datetime
def timestamp_to_datetime(timestamp, default = none_timestamp()):
	if timestamp is None or isinstance(timestamp, int) and timestamp == 0 or isinstance(timestamp, str) and timestamp in ("", "None"):
		return default

	if timestamp == -1:
		return -1

	# Timestamps that end with Z are already in UTC; strip that
	if timestamp.endswith("Z"):
		timestamp = timestamp[:-1]

	rtimestamp = timestamp

	# Some timestamps are weird
	# Safe
	tmp = re.match(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{6})\d* ([+-]\d{4}) [A-Z]{3}$", timestamp)
	if tmp is not None:
		timestamp = f"{tmp[1]}{tmp[2]}"

	# Safe
	tmp = re.match(r"^(.+?) ?([+-]\d{4})$", timestamp)
	if tmp is not None:
		timestamp = f"{tmp[1]}{tmp[2]}"
	else:
		# For timestamp without timezone add one; all timestamps are assumed to be UTC
		timestamp += "+0000"

	for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z",
	            "%Y-%m-%d %H:%M:%S.%f%z",
		    "%Y-%m-%dT%H:%M:%S%z",
		    "%Y-%m-%d %H:%M:%S%z"):
		try:
			return datetime.strptime(timestamp, fmt)
		except ValueError:
			pass
	raise ValueError(f"Could not parse timestamp: {rtimestamp}")

# This executes a command without capturing the output
def execute_command(args, env = None, comparison = 0):
	if env is None:
		retval = subprocess.run(args, check = False)
	else:
		retval = subprocess.run(args, env = env, check = False)
	return retval.returncode == comparison

# This executes a command with the output captured
def execute_command_with_response(args):
	result = subprocess.run(args, stdout = PIPE, stderr = STDOUT, check = False)
	return result.stdout.decode("utf-8")

def make_set_expression_list(expression_list):
	expressions = []

	if expression_list is not None:
		for expression in expression_list:
			operator = deep_get(expression, "operator", "")
			if operator == "In":
				operator = "In "
			elif operator == "NotIn":
				operator = "Not In "
			elif operator == "Exists":
				operator = "Exists"
			elif operator == "DoesNotExist":
				operator = "Does Not Exist"
			elif operator == "Gt":
				operator = "> "
			elif operator == "Lt":
				operator = "< "
			key = deep_get_with_fallback(expression, ["key", "scopeName"], "")

			tmp = deep_get(expression, "values", [])
			values = ",".join(tmp)
			if len(values) > 0 and operator not in ("Gt", "Lt"):
				values = f"[{values}]"

			expressions.append((key, operator, values))
	return expressions

def make_set_expression(expression_list):
	vlist = make_set_expression_list(expression_list)
	xlist = []
	for key, operator, values in vlist:
		xlist.append(f"{key} {operator}{values}")
	return ", ".join(xlist)

def get_package_versions(hostname):
	import ansible_helper # pylint: disable=unused-import,import-outside-toplevel
	from ansible_helper import ansible_run_playbook_on_selection, get_playbook_path # pylint: disable=import-outside-toplevel

	if not os.path.isdir(ANSIBLE_PLAYBOOK_DIR):
		return []

	get_versions_path = get_playbook_path("get_versions.yaml")
	retval, ansible_results = ansible_run_playbook_on_selection(get_versions_path, selection = [hostname])

	if len(ansible_results) == 0:
		raise ValueError(f"Error: Failed to get package versions from {hostname} (retval: {retval}); aborting.")

	tmp = []

	for result in deep_get(ansible_results, hostname, []):
		if deep_get(result, "task", "") == "package versions":
			tmp = deep_get(result, "msg_lines", [])
			break

	if len(tmp) == 0:
		raise ValueError(f"Error: Received empty version data from {hostname} (retval: {retval}); aborting.")

	package_versions = []

	# Safe
	package_version_regex = re.compile(r"^(.*?): (.*)")

	for line in tmp:
		tmp = package_version_regex.match(line)
		if tmp is None:
			continue
		package = tmp[1]
		version = tmp[2]
		package_versions.append((package, version))

	return package_versions

def __extract_version(line):
	"""
	Extract a version from an apt-cache madison entry

		Parameters:
			line (str): A package info line from apt-cache madison
		Returns:
			A version number
	"""

	tmp = line.split("|")
	if len(tmp) != 3:
		raise Exception("Error: Failed to extract a version; this is (most likely) a programming error.")
	return tmp[1].strip()

def check_deb_versions(deb_packages):
	"""
	Given a list of packages, return installed, candidate, and all available versions

		Parameters:
			deb_packages (list[str]): A list of packages to get versions for
		Returns:
			deb_versions (list[(package, installed_version, candidate_version, all_versions)]): A list of package versions
	"""

	deb_versions = []

	args = ["/usr/bin/apt-cache", "policy"] + deb_packages
	response = execute_command_with_response(args)
	split_response = response.splitlines()
	# Safe
	installed_regex = re.compile(r"^\s*Installed: (.*)")
	# Safe
	candidate_regex = re.compile(r"^\s*Candidate: (.*)")
	for line in split_response:
		if line.endswith(":"):
			package = line[:-1]
		elif line.startswith("  Installed: "):
			tmp = installed_regex.match(line)
			if tmp is not None:
				if tmp[1] == "(none)":
					installed_version = "<none>"
				else:
					installed_version = tmp[1]
			else:
				installed_version = "<none>"
		elif line.startswith("  Candidate: "):
			tmp = candidate_regex.match(line)
			if tmp is not None and tmp[1] != installed_version:
				if tmp[1] == "(none)":
					if installed_version == "<none>":
						continue
					candidate_version = "<none>"
				else:
					candidate_version = tmp[1]
			else:
				candidate_version = ""
			# We have the current and candidate version now; get all the other versions of the same package
			_args = ["/usr/bin/apt-cache", "madison", package]
			_response = execute_command_with_response(_args)
			_split_response = _response.splitlines()
			all_versions = natsorted([__extract_version(line) for line in _split_response], reverse = True)
			deb_versions.append((package, installed_version, candidate_version, all_versions))

	return deb_versions

read_iktconfig()
