#! /usr/bin/env python3

"""
Helpers used by various components of iKT
"""

from datetime import datetime, timezone, timedelta, date
from functools import reduce
from pathlib import Path, PurePath
import re
import subprocess
from subprocess import PIPE, STDOUT
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from ikttypes import DictPath, FilePath, SecurityPolicy
from iktpaths import IKT_CONFIG_FILE, IKT_CONFIG_FILE_DIR
import iktio

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-natsort")

iktconfig = {}

def clamp(value: int, minval: int, maxval: int) -> int:
	"""
	Clamp value inside the range minval, maxval

		Parameters:
			value (int): The value to clamp
			minval (int): The minimum allowed value
			maxval (int): The maximum allowed value
		Returns:
			int: The clamped value
	"""

	return min(maxval, max(minval, value))

def none_timestamp() -> datetime:
	"""
	Return the timestamp used to represent None

		Returns:
			timestamp (datetime): A "None" timestamp
	"""

	return (datetime.combine(date.min, datetime.min.time()) + timedelta(days = 1)).astimezone()

def disksize_to_human(size: int) -> str:
	"""
	Given a disksize in bytes, convert it to a more readable format with size suffix

		Parameters:
			size (int): The disksize in bytes
		Returns:
			disksize (str): The human readable disksize with size suffix
	"""

	size_suffixes = [
		" bytes",
		"kiB",
		"MiB",
		"GiB",
		"TiB",
		"PiB",
	]

	for suffix in size_suffixes:
		if size < 1024:
			break
		size = size // 1024
	return f"{size}{suffix}"

def split_msg(rawmsg: str) -> List[str]:
	"""
	Split a string into a list of strings, strip NUL-bytes, and convert newlines

		Parameters:
			rawmsg (str): The string to split
		Returns:
			list[str]: A list of split strings
	"""

	# We only want "\n" to represent newlines
	tmp = rawmsg.replace("\r\n", "\n")
	# We also replace all \x00 with <NUL>
	tmp = rawmsg.replace("\x00", "<NUL>")
	return list(map(str.rstrip, tmp.splitlines()))

def deep_set(dictionary: Dict, path: DictPath, value: Any, create_path: bool = False) -> None:
	"""
	Given a dictionary, a path into that dictionary, and a value, set the path to that value

a		Parameters:
			dictionary (dict): The dict to set the value in
			path (DictPath): A dict path
			value (any): The value to set
			create_path (bool): If True the path will be created if it doesn't exist
	"""

	if dictionary is None or path is None or len(path) == 0:
		raise Exception(f"deep_set: dictionary {dictionary} or path {path} invalid/unset")

	ref = dictionary
	pathsplit = path.split("#")
	for i in range(0, len(pathsplit)):
		if pathsplit[i] in ref:
			if i == len(pathsplit) - 1:
				ref[pathsplit[i]] = value
				break

			ref = deep_get(ref, DictPath(pathsplit[i]))
			if ref is None or not isinstance(ref, dict):
				raise Exception(f"Path {path} does not exist in dictionary {dictionary} or is the wrong type {type(ref)}")
		elif create_path == True:
			if i == len(pathsplit) - 1:
				ref[pathsplit[i]] = value
			else:
				ref[pathsplit[i]] = {}

def deep_get(dictionary: Dict, path: DictPath, default: Any = None) -> Any:
	"""
	Given a dictionary and a path into that dictionary, get the value

		Parameters:
			dictionary (dict): The dict to get the value from
			path (DictPath): A dict path
			default (Any): The default value to return if the dictionary, path is None, or result is None
		Returns:
			result (Any): The value from the path
	"""

	if dictionary is None:
		return default
	if path is None or len(path) == 0:
		return default
	result = reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, path.split("#"), dictionary)
	if result is None:
		result = default
	return result

def __deep_get_recursive(dictionary: Dict, path_fragments: List[str], result: Union[List, None] = None) -> Optional[List[Any]]:
	if result is None:
		result = []

	for i in range(0, len(path_fragments)):
		path_fragment = DictPath(path_fragments[i])
		tmp = deep_get(dictionary, path_fragment)
		if i + 1 == len(path_fragments):
			if tmp is None:
				return result
			return tmp

		if isinstance(tmp, dict):
			result = __deep_get_recursive(tmp, path_fragments[i + 1:len(path_fragments)], result)
		elif isinstance(tmp, list):
			for tmp2 in tmp:
				result = __deep_get_recursive(tmp2, path_fragments[i + 1:len(path_fragments)], result)

	return result

def deep_get_list(dictionary: Dict, paths: List[DictPath], default: Optional[List[Any]] = None, fallback_on_empty: bool = False) -> Optional[List[Any]]:
	"""
	Given a dictionary and a list of paths into that dictionary, get all values

		Parameters:
			dictionary (dict): The dict to get the values from
			path (List[DictPath]): A list of dict paths
			default (List[Any]): The default value to return if the dictionary, paths, or results are None
			fallback_on_empty (bool): Should "" be treated as None?
		Returns:
			result (List[Any]): The values from the paths
	"""

	for path in paths:
		result = __deep_get_recursive(dictionary, path.split("#"))

		if result is not None and not (type(result) in (list, str, dict) and len(result) == 0 and fallback_on_empty == True):
			break
	if result is None or type(result) in (list, str, dict) and len(result) == 0 and fallback_on_empty == True:
		result = default
	return result

def deep_get_with_fallback(obj: Dict, paths: List[DictPath], default: Optional[Any] = None, fallback_on_empty: bool = False) -> Any:
	"""
	Given a dictionary and a list of paths into that dictionary, get the value from the first path that has a value

		Parameters:
			dictionary (dict): The dict to get the value from
			paths (list[DictPath]): A list of dict paths
			default (any): The default value to return if the dictionary, path is None, or result is None
			fallback_on_empty (bool): Should "" be treated as None?
	"""

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

def read_iktconfig() -> Dict:
	"""
	Read ikt.yaml and ikt.yaml.d/*.yaml and update the global iktconfig dict

		Returns:
			iktconfig (Dict): A reference to the global iktconfig dict
	"""

	global iktconfig # pylint: disable=global-statement

	if not Path(IKT_CONFIG_FILE).is_file():
		return {}

	# Read the base configuration file
	iktconfig = iktio.secure_read_yaml(IKT_CONFIG_FILE)

	# Now read ikt.yaml.d/* if available
	if not Path(IKT_CONFIG_FILE_DIR).is_dir():
		return iktconfig

	for path in natsorted(Path(IKT_CONFIG_FILE_DIR).iterdir()):
		filename = PurePath(str(path)).name

		# Only read entries that end with .y{,a}ml
		if filename.startswith(("~", ".")):
			continue
		if not filename.endswith((".yaml", ".yml")):
			continue

		# Read the conflet files
		moreiktconfig = iktio.secure_read_yaml(FilePath(str(path)))

		# Handle config files without any values defined
		if moreiktconfig is not None:
			iktconfig = {**iktconfig, **moreiktconfig}

	return iktconfig

# Helper functions
def versiontuple(ver: str) -> Tuple[str, ...]:
	"""
	Split a version string into a tuple

		Parameters:
			ver (str): The version string to split
		Returns:
			result (tuple[str, ...]): A variable-length tuple with one string per version component
	"""

	filled = []
	for point in ver.split("."):
		filled.append(point.zfill(8))
	return tuple(filled)

def join_tuple_list(items: List[Union[str, Tuple[str, str]]], _tuple: Union[str, Tuple[str, str]] = "",
		    item_prefix: Optional[Tuple[str, str]] = None, item_suffix: Optional[Tuple[str, str]] = None, separator: Optional[Tuple[str, str]] = None):
	"""
	Given a list of strings or tuples, returns a list of tuples suitable to be used a themearray;
	tuples will be added as is, strings will be paired up with _tuple.

		Parameters:
			items (list[str]): The list of strings to format
			_tuple (str|(str, str)): Either a string or a tuple
			item_prefix (tuple(str, str)|tuple(str, tuple(str, str))): A prefix to apply before each item
			item_suffix (tuple(str, str)|tuple(str, tuple(str, str))): A suffix to apply after each item
			separator (tuple(str, str)|tuple(str, tuple(str, str))): A separator to apply between each item
		Returns:
			(themearray): A list of themearray fragments with all items joined together
	"""

	_list: List[Tuple[str, Union[str, Tuple[str, str]]]] = []
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

def age_to_seconds(age: str) -> int:
	"""
	Given a time in X1dX2hX3mX4s, convert it to seconds

		Parameters:
			age (str): A string in age format
		Returns:
			seconds (int): The number of seconds
	"""

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

def seconds_to_age(seconds: int, negative_is_skew: bool = False) -> str:
	"""
	Given a time in seconds, convert it to X1dX2hX3mX4s

		Parameters:
			seconds (int): The number of seconds
			negative_is_skew (bool): Should a negative timestamp return a clock skew warning (default: -age)
		Returns:
			age (str): The age string
	"""

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

def get_since(timestamp: Optional[Union[int, datetime]]) -> int:
	"""
	Given either a datetime, or an integer, returns how old that
	timestamp is in seconds

		Parameters:
			timestamp (Union[datetime, int]): A time in the past
		Returns:
			since (int): The number of seconds, 0 if timestamp is None, or -1 if the none_timestamp() was provided
	"""

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
def datetime_to_timestamp(timestamp: datetime) -> str:
	"""
	Given a timestamp in datetime format,
	convert it to a string

		Parameters:
			timestamp (datetime): The timestamp in datetime
		Returns:
			string (str): The timestamp in string format
	"""

	if timestamp is None or timestamp == none_timestamp():
		string = ""
	elif timestamp == datetime.fromtimestamp(0).astimezone():
		string = "".ljust(len(str(datetime.fromtimestamp(0).astimezone())))
	else:
		string = timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
	return string

def reformat_timestamp(timestamp: str) -> str:
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
def timestamp_to_datetime(timestamp: str, default: datetime = none_timestamp()) -> datetime:
	"""
	Takes a timestamp and converts it to datetime

		Parameters:
			timestamp (str): The timestamp string to convert
			default (datetime): The value to return if timestamp is None, 0, "", or "None"
		Returns:
			timestamp (Union[int, datetime]): -1 if the timestamp was -1, datetime otherwise
	"""

	if timestamp is None or isinstance(timestamp, int) and timestamp == 0 or isinstance(timestamp, str) and timestamp in ("", "None"):
		return default

	if timestamp == -1:
		return none_timestamp()

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
def execute_command(args: List[Union[FilePath, str]], env: Dict = None, comparison: int = 0) -> bool:
	"""
	Executes a command

		Parameters:
			args (list[str]): The commandline
			env (dict): Environment variables to set
			comparison (int): The value to compare retval to
		Returns:
			retval.returncode == comparison (bool): True if retval.returncode == comparison, False otherwise
	"""

	if env is None:
		retval = subprocess.run(args, check = False)
	else:
		retval = subprocess.run(args, env = env, check = False)
	return retval.returncode == comparison

# This executes a command with the output captured
def execute_command_with_response(args: List[str]) -> str:
	"""
	Executes a command and returns stdout

		Parameters:
			args (list[str]): The commandline
		Returns:
			stdout (str): The stdout from the execution
	"""
	result = subprocess.run(args, stdout = PIPE, stderr = STDOUT, check = False)
	return result.stdout.decode("utf-8")

def make_set_expression_list(expression_list: Dict) -> List[Tuple[str, str, str]]:
	"""
	Create a list of set expressions (key, operator, values)

		Parameters:
			expression_list (dict): The dict to extract the data from
		Returns:
			expressions (list[(key, operator, values)])
	"""

	expressions = []

	if expression_list is not None:
		for expression in expression_list:
			operator = deep_get(expression, DictPath("operator"), "")
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
			key = deep_get_with_fallback(expression, [DictPath("key"), DictPath("scopeName")], "")

			tmp = deep_get(expression, DictPath("values"), [])
			values = ",".join(tmp)
			if len(values) > 0 and operator not in ("Gt", "Lt"):
				values = f"[{values}]"

			expressions.append((str(key), str(operator), values))
	return expressions

def make_set_expression(expression_list: Dict) -> str:
	"""
	Join set expressions data into one single string

		Parameters:
			expression_list (dict): The dict to extract the data from
		Returns:
			string (str): The set expressions joined into one string
	"""

	vlist = make_set_expression_list(expression_list)
	xlist = []
	for key, operator, values in vlist:
		xlist.append(f"{key} {operator}{values}")
	return ", ".join(xlist)

def get_package_versions(hostname: str) -> List[Tuple[str, str]]:
	"""
	Returns a list of predefined packages for a host

		Parameters:
			hostname (str): The host to get package versions for
		Returns:
			package_versions (list[tuple(package (str), version (str))]): The list of package versions
	"""

	import ansible_helper # pylint: disable=unused-import,import-outside-toplevel
	from ansible_helper import ansible_run_playbook_on_selection, get_playbook_path # pylint: disable=import-outside-toplevel

	get_versions_path = get_playbook_path(FilePath("get_versions.yaml"))
	retval, ansible_results = ansible_run_playbook_on_selection(get_versions_path, selection = [hostname])

	if len(ansible_results) == 0:
		raise ValueError(f"Error: Failed to get package versions from {hostname} (retval: {retval}); aborting.")

	tmp = []

	for result in deep_get(ansible_results, DictPath(hostname), []):
		if deep_get(result, DictPath("task"), "") == "package versions":
			tmp = deep_get(result, DictPath("msg_lines"), [])
			break

	if len(tmp) == 0:
		raise ValueError(f"Error: Received empty version data from {hostname} (retval: {retval}); aborting.")

	package_versions = []

	# Safe
	package_version_regex = re.compile(r"^(.*?): (.*)")

	for line in tmp:
		tmp2 = package_version_regex.match(line)
		if tmp2 is None:
			continue
		package = tmp2[1]
		version = tmp2[2]
		package_versions.append((package, version))

	return package_versions

def __extract_version(line: str) -> str:
	"""
	Extract a version from an apt-cache madison entry

		Parameters:
			line (str): A package info line from apt-cache madison
		Returns:
			(str): A version number
	"""

	tmp = line.split("|")
	if len(tmp) != 3:
		raise Exception("Error: Failed to extract a version; this is (most likely) a programming error.")
	return tmp[1].strip()

def check_deb_versions(deb_packages: List[str]) -> List[Tuple[str, str, str, List[str]]]:
	"""
	Given a list of packages, return installed, candidate, and all available versions

		Parameters:
			deb_packages (list[str]): A list of packages to get versions for
		Returns:
			deb_versions (list[(package, installed_version, candidate_version, all_versions)]): A list of package versions
	"""

	deb_versions = []

	apt_cache_path = iktio.secure_which(FilePath("apt-cache"), fallback_allowlist = ["/bin", "/usr/bin"], security_policy = SecurityPolicy.ALLOWLIST_STRICT)
	args = [apt_cache_path, "policy"] + deb_packages
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
			apt_cache_path = iktio.secure_which(FilePath("apt-cache"), fallback_allowlist = ["/bin", "/usr/bin"], security_policy = SecurityPolicy.ALLOWLIST_STRICT)
			_args = [apt_cache_path, "madison", package]
			_response = execute_command_with_response(_args)
			_split_response = _response.splitlines()
			all_versions = []
			for version in _split_response:
				if "amd64 Packages" in version:
					all_versions.append(__extract_version(version))
			natsorted_versions = []
			for natsorted_version in natsorted(all_versions, reverse = True):
				natsorted_versions.append(str(natsorted_version))
			deb_versions.append((package, installed_version, candidate_version, natsorted_versions))

	return deb_versions
