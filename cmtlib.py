#! /usr/bin/env python3
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Helpers used by various components of CMT
"""

from datetime import datetime, timezone, timedelta, date
import errno
from pathlib import Path, PurePath
import re
import sys
from typing import Any, cast, Dict, Generator, List, Optional, Tuple, Union

import about
from ansithemeprint import ANSIThemeString, ansithemeprint
from cmttypes import deep_get, deep_get_with_fallback, DictPath, FilePath, SecurityPolicy
from cmtpaths import CMT_CONFIG_FILE, CMT_CONFIG_FILE_DIR
import cmtio

cmtconfig = {}

def substitute_string(string: str, substitutions: Dict) -> str:
	"""
	Substitutes substrings in a string

		Parameters:
			string (str): The string to perform substitutions on
			substitutions (dict): A dict where key is the substring to match against, and value is the replacement for that substring
		Returns:
			string (str): The string with substitutions performed
	"""

	for key, value in substitutions.items():
		if string is None or value is None:
			continue
		string = string.replace(key, value)
	return string

def substitute_list(strlist: List[str], substitutions: Dict) -> List[str]:
	"""
	Substitutes substrings in all strings in a list

		Parameters:
			string (list[str]): A list with the strings to perform substitutions on
			substitutions (dict): A dict where key is the substring to match against, and value is the replacement for that substring
		Returns:
			list[str]: The list of strings with substitutions performed
	"""

	if strlist is not None:
		for key, value in substitutions.items():
			strlist = [s.replace(key, value) if (s is not None and value is not None) else s for s in strlist]
	return strlist

def lstrip_count(string: str, prefix: str) -> Tuple[str, int]:
	"""
	Given a string remove prefix and return the stripped string and the count of stripped characters

		Parameters:
			string (str): The string to strip
			prefix (str): The prefix to strip
		Returns:
			(string (str), count (int)): The stripped string and the count of stripped characters
	"""

	stripped = string.lstrip(prefix)
	return stripped, len(string) - len(stripped)

def rstrip_count(string: str, suffix: str) -> Tuple[str, int]:
	"""
	Given a string remove suffix and return the stripped string and the count of stripped characters

		Parameters:
			string (str): The string to strip
			suffix (str): The suffix to strip
		Returns:
			(string (str), count (int)): The stripped string and the count of stripped characters
	"""

	stripped = string.rstrip(suffix)
	return stripped, len(string) - len(stripped)

def chunk_list(items: List[Any], chunksize: int) -> Generator[List, None, None]:
	"""
	Split a list into sublists, each up to chunksize elements long

		Parameters:
			items ([Any]): The list to split
			chunksize (int): The chunksize
		Returns:
			chunk ([Any]): A generator for the chunked list
		Raises:
			TypeError: items is not a list or chunksize is not an integer
			ValueError: chunksize is < 1
	"""
	if not isinstance(items, list):
		raise TypeError("items must be a list")
	if not isinstance(chunksize, int):
		raise TypeError("chunksize must by an integer > 0")
	if chunksize < 1:
		raise ValueError(f"Invalid chunksize {chunksize}; chunksize must be > 0")
	for i in range(0, len(items), chunksize):
		yield items[i:i + chunksize]

def clamp(value: Union[int, float], minval: Union[int, float], maxval: Union[int, float]) -> Union[int, float]:
	"""
	Clamp value inside the range minval, maxval

		Parameters:
			value (int): The value to clamp
			minval (int): The minimum allowed value
			maxval (int): The maximum allowed value
		Returns:
			int: The clamped value
	"""

	if not isinstance(value, (int, float)):
		raise TypeError("value must be an integer or float")
	if not isinstance(minval, (int, float)) or not isinstance(maxval, (int, float)):
		raise TypeError("maxval and minval must be integers or floats")
	if minval > maxval:
		raise ValueError(f"maxval ({maxval}) must be >= minval ({minval})")
	return min(maxval, max(minval, value))

def none_timestamp() -> datetime:
	"""
	Return the timestamp used to represent None

		Returns:
			timestamp (datetime): A "None" timestamp
	"""

	return (datetime.combine(date.min, datetime.min.time()) + timedelta(days = 1)).astimezone()

def normalise_cpu_usage_to_millicores(cpu_usage: str) -> float:
	"""
	Given CPU usage information, convert it to CPU usage in millicores

		Parameters:
			cpu_usage(union(int, str)): The CPU usage
		Returns:
			cpu_usage_millicores (float): CPU usage in millicores
	"""

	cpu_usage_millicores: float = 0

	if not isinstance(cpu_usage, str):
		raise TypeError("cpu_usage must be a str")

	if cpu_usage.isnumeric():
		cpu_usage_millicores = int(cpu_usage) * 1000 ** 1
	elif cpu_usage.endswith("m"):
		cpu_usage_millicores = int(cpu_usage[0:-1])
	elif cpu_usage.endswith("u"):
		cpu_usage_millicores = int(cpu_usage[0:-1]) / 1000 ** 1
	elif cpu_usage.endswith("n"):
		cpu_usage_millicores = int(cpu_usage[0:-1]) / 1000 ** 2
	else:
		raise ValueError(f"Unknown unit for CPU usage in {cpu_usage}")
	return cpu_usage_millicores

def normalise_mem_to_bytes(mem_usage: str) -> int:
	"""
	Given a memory usage string, normalise it to bytes

		Parameters:
			mem_usage (str): The amount of memory used
		Returns:
			mem_usage_bytes (int): The amount of memory used in bytes
	"""

	mem = 0

	unit_lookup = {
		"Ki": 1024 ** 1,
		"Mi": 1024 ** 2,
		"Gi": 1024 ** 3,
		"Ti": 1024 ** 4,
		"Pi": 1024 ** 5,
		"Ei": 1024 ** 6,
		"Zi": 1024 ** 7,
		"Yi": 1024 ** 8,
	}

	if not isinstance(mem_usage, (int, str)):
		raise TypeError(f"mem_usage must be an integer-string (optionally with a valid unit) or int")

	if isinstance(mem_usage, int) or isinstance(mem_usage, str) and mem_usage.isnumeric():
		mem = int(mem_usage)
	else:
		for key, value in unit_lookup.items():
			if mem_usage.endswith(key):
				mem = int(mem_usage[0:-len(key)]) * value
				break
		else:
			raise ValueError(f"Unknown unit for memory usage in {mem_usage}")

	return mem

def normalise_mem_bytes_to_str(mem_usage_bytes: int, fmt: str = "float") -> str:
	"""
	Given memory usage in bytes, convert it to a normalised string

		Parameters:
			mem_usage_bytes (int): The memory size in bytes
			fmt (str): Format as float or integer
		Returns:
			(str): The human readable mem usage with size suffix
		Raises:
			TypeError: size is not an integer
			ValueError: size is not >= 0
	"""

	suffix = ""
	mem_usage: float = 0

	suffixes = (
		"",	# 1024 ** 1
		"Ki",	# 1024 ** 2
		"Mi",	# 1024 ** 3
		"Gi",	# 1024 ** 4
		"Ti",	# 1024 ** 5
		"Pi",	# 1024 ** 6
		"Ei",	# 1024 ** 7
		"Zi",	# 1024 ** 8
		"Yi",	# 1024 ** 9
	)

	if not isinstance(mem_usage_bytes, int):
		raise TypeError("mem_usage_bytes must be an int")

	mem_usage = float(mem_usage_bytes)

	if mem_usage < 0:
		raise ValueError("mem_usage_bytes must be >= 0")

	for i, suffix in enumerate(suffixes):
		if mem_usage < 1024 or i >= len(suffixes) - 1:
			break
		mem_usage /= 1024 ** 1

	if fmt == "int":
		return f"{int(mem_usage)}{suffix}B"
	return f"{mem_usage:0.1f}{suffix}B"

def disksize_to_human(size: int) -> str:
	"""
	Given a disksize in bytes, convert it to a more readable format with size suffix

		Parameters:
			size (int): The disksize in bytes
		Returns:
			disksize (str): The human readable disksize with size suffix
		Raises:
			TypeError: size is not an integer
			ValueError: size is not >= 0
	"""

	tmp = normalise_mem_bytes_to_str(size, fmt = "int")
	if tmp[:-1].isnumeric():
		tmp = f"{tmp[:-1]} bytes"
	return tmp

def split_msg(rawmsg: str) -> List[str]:
	"""
	Split a string into a list of strings, strip NUL-bytes, and convert newlines

		Parameters:
			rawmsg (str): The string to split
		Returns:
			list[str]: A list of split strings
	"""

	if not isinstance(rawmsg, str):
		raise TypeError(f"rawmsg is type {type(rawmsg)}, expected str")
	# We only want "\n" to represent newlines
	tmp = rawmsg.replace("\r\n", "\n")
	# We also replace all \x00 with <NUL>
	tmp = tmp.replace("\x00", "<NUL>")
	# We also replace non-breaking space with space
	tmp = tmp.replace("\xa0", " ")
	# And remove almost all control characters
	tmp = re.sub(r"[\x00-\x08\x0b-\x1a\x1c-\x1f\x7f-\x9f]", "\uFFFD", tmp)

	return list(map(str.rstrip, tmp.splitlines()))

def strip_ansicodes(message: str) -> str:
	"""
	Strip all ANSI-formatting from a string

		Parameters:
			message (str): The string to strip
		Returns:
			(str): The stripped string
		Raises:
			TypeError: The input was not a string
	"""
	if not isinstance(message, str):
		raise TypeError(f"message is type {type(message)}, expected str")

	message = message.replace("\\x1b", "\x1b").replace("\\u001b", "\x1b")
	tmp = re.findall(r"("
	                 r"\x1b\[\d+m|"
	                 r"\x1b\[\d+;\d+m|"
			 r"\x1b\[\d+;\d+;\d+m|"
			 r".*?)", message)
	message = "".join(item for item in tmp if not item.startswith("\x1b"))

	return message

def read_cmtconfig() -> Dict:
	"""
	Read cmt.yaml and cmt.yaml.d/*.yaml and update the global cmtconfig dict

		Returns:
			cmtconfig (Dict): A reference to the global cmtconfig dict
	"""

	# This is for the benefit of avoiding dependency cycles
	# pylint: disable-next=import-outside-toplevel
	import cmtio_yaml

	try:
		# This is for the benefit of avoiding dependency cycles
		# pylint: disable-next=import-outside-toplevel
		from natsort import natsorted
	except ModuleNotFoundError:  # pragma: no cover
		sys.exit("ModuleNotFoundError: Could not import natsort; you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

	global cmtconfig  # pylint: disable=global-statement

	if not Path(CMT_CONFIG_FILE).is_file():
		return {}

	# Read the base configuration file
	cmtconfig = cmtio_yaml.secure_read_yaml(CMT_CONFIG_FILE)

	# Now read cmt.yaml.d/* if available
	if not Path(CMT_CONFIG_FILE_DIR).is_dir():
		return cmtconfig

	for path in natsorted(Path(CMT_CONFIG_FILE_DIR).iterdir()):
		filename = PurePath(str(path)).name

		# Only read entries that end with .y{,a}ml
		if filename.startswith(("~", ".")):
			continue
		if not filename.endswith((".yaml", ".yml")):
			continue

		# Read the conflet files
		morecmtconfig = cmtio_yaml.secure_read_yaml(FilePath(str(path)))

		# Handle config files without any values defined
		if morecmtconfig is not None:
			cmtconfig = {**cmtconfig, **morecmtconfig}

	return cmtconfig

# Helper functions
def versiontuple(ver: str) -> Tuple[str, ...]:
	"""
	Split a version string into a tuple

		Parameters:
			ver (str): The version string to split
		Returns:
			result (tuple[str, ...]): A variable-length tuple with one string per version component
		Raises:
			TypeError: The input was not a string
	"""

	filled = []

	if not isinstance(ver, str):
		raise TypeError(f"ver is type {type(ver)}, expected str")

	for point in ver.split("."):
		filled.append(point.zfill(8))
	return tuple(filled)

def age_to_seconds(age: str) -> int:
	"""
	Given a time in X1dX2hX3mX4s, convert it to seconds

		Parameters:
			age (str): A string in age format
		Returns:
			seconds (int): The number of seconds
		Raises:
			TypeError: The input was not a string
			ValueError: The input could not be parsed as an age string
	"""

	seconds = 0

	if not isinstance(age, str):
		raise TypeError(f"age is type {type(age)}, expected str")

	if len(age) == 0:
		return -1
	tmp = re.match(r"^(\d+d)?(\d+h)?(\d+m)?(\d+s)?", age)
	if tmp.span() != (0, 0):
		d = 0 if tmp[1] is None else int(tmp[1][:-1])
		h = 0 if tmp[2] is None else int(tmp[2][:-1])
		m = 0 if tmp[3] is None else int(tmp[3][:-1])
		s = 0 if tmp[4] is None else int(tmp[4][:-1])
		seconds = d * 24 * 60 * 60 + h * 60 * 60 + m * 60 + s
	else:
		raise ValueError(f"age regex did not match; age: {age}")

	return seconds

def seconds_to_age(seconds: int, negative_is_skew: bool = False) -> str:
	"""
	Given a time in seconds, convert it to X1dX2hX3mX4s

		Parameters:
			seconds (int): The number of seconds
			negative_is_skew (bool): Should a negative timestamp return a clock skew warning (default: -age)
		Returns:
			age (str): The age string
		Raises:
			TypeError: The input was not an integer
	"""

	if not isinstance(seconds, int):
		raise TypeError(f"age is type {type(seconds)}, expected int")

	age = ""
	fields = 0

	if seconds < -1:
		sign = "-"
	else:
		sign = ""

	if seconds < -1 and negative_is_skew:
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
		return 0

	if not isinstance(timestamp, (int, datetime)):
		raise TypeError(f"timestamp is type {type(timestamp)}, expected int or datetime")

	if timestamp == -1 or timestamp == none_timestamp():
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
	tmp = re.match(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{6})\d* ([+-]\d{4}) [A-Z]{3}$", timestamp)
	if tmp is not None:
		timestamp = f"{tmp[1]}{tmp[2]}"

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

def make_set_expression_list(expression_list: Dict, key: str = "") -> List[Tuple[str, str, str]]:
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
			operator = deep_get_with_fallback(expression, [DictPath("operator"), DictPath("op")], "")
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
			key = deep_get_with_fallback(expression, [DictPath("key"), DictPath("scopeName")], key)

			tmp = deep_get_with_fallback(expression, [DictPath("values"), DictPath("value")], [])
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

	# pylint: disable-next=unused-import,import-outside-toplevel
	import ansible_helper  # noqa
	from ansible_helper import ansible_run_playbook_on_selection, get_playbook_path  # pylint: disable=import-outside-toplevel

	get_versions_path = get_playbook_path(FilePath("get_versions.yaml"))
	retval, ansible_results = ansible_run_playbook_on_selection(get_versions_path, selection = [hostname])

	if len(ansible_results) == 0:
		raise ValueError(f"Error: Failed to get package versions from {hostname} (retval: {retval}); aborting.")

	tmp = []

	for result in deep_get(ansible_results, DictPath(hostname), []):
		if deep_get(result, DictPath("task"), "") == "Package versions":
			tmp = deep_get(result, DictPath("msg_lines"), [])
			break

	if len(tmp) == 0:
		raise ValueError(f"Error: Received empty version data from {hostname} (retval: {retval}); aborting.")

	package_versions = []

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
		raise ValueError("Error: Failed to extract a version; this is (most likely) a programming error.")
	return tmp[1].strip()

def check_versions_apt(packages: List[str]) -> List[Tuple[str, str, str, List[str]]]:
	"""
	Given a list of packages, return installed, candidate, and all available versions

		Parameters:
			packages (list[str]): A list of packages to get versions for
		Returns:
			versions (list[(package, installed_version, candidate_version, all_versions)]): A list of package versions
	"""

	try:
		# This is for the benefit of avoiding dependency cycles
		# pylint: disable-next=import-outside-toplevel
		from natsort import natsorted
	except ModuleNotFoundError:  # pragma: no cover
		sys.exit("ModuleNotFoundError: Could not import natsort; you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

	versions = []

	apt_cache_path = cmtio.secure_which(FilePath("apt-cache"), fallback_allowlist = ["/bin", "/usr/bin"],
					    security_policy = SecurityPolicy.ALLOWLIST_STRICT)
	args = [apt_cache_path, "policy"] + packages
	response = cmtio.execute_command_with_response(args)
	split_response = response.splitlines()
	installed_regex = re.compile(r"^\s*Installed: (.*)")
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
			apt_cache_path = cmtio.secure_which(FilePath("apt-cache"), fallback_allowlist = ["/bin", "/usr/bin"],
							    security_policy = SecurityPolicy.ALLOWLIST_STRICT)
			_args = [apt_cache_path, "madison", package]
			_response = cmtio.execute_command_with_response(_args)
			_split_response = _response.splitlines()
			all_versions = []
			for version in _split_response:
				if version.endswith(" Packages"):
					all_versions.append(__extract_version(version))
			natsorted_versions = []
			for natsorted_version in natsorted(all_versions, reverse = True):
				natsorted_versions.append(str(natsorted_version))
			versions.append((package, installed_version, candidate_version, natsorted_versions))

	return versions

def check_versions_yum(packages: List[str]) -> List[Tuple[str, str, str, List[str]]]:
	"""
	Given a list of packages, return installed, candidate, and all available versions

		Parameters:
			packages (list[str]): A list of packages to get versions for
		Returns:
			versions (list[(package, installed_version, candidate_version, all_versions)]): A list of package versions
	"""

	versions = []
	versions_dict: Dict[str, Dict] = {}

	yum_path = cmtio.secure_which(FilePath("/usr/bin/yum"), fallback_allowlist = ["/usr/bin"],
				      security_policy = SecurityPolicy.ALLOWLIST_RELAXED)
	args = [yum_path, "--showduplicates", "-y", "-q", "list"] + packages
	response = cmtio.execute_command_with_response(args)
	split_response = response.splitlines()

	package_version = re.compile(r"^([^.]+)[^\s]+[\s]+([^\s]+).*")

	section = ""

	for line in split_response:
		if line == "Installed Packages":
			section = "installed"
			continue
		if line == "Available Packages":
			section = "available"
			continue
		tmp = package_version.match(line)
		if tmp is not None:
			package = tmp[1]
			version = tmp[2]

			if package not in versions_dict:
				versions_dict[package] = {
					"installed": "<none>",
					"candidate": "<none>",
					"available": [],
				}

			if section == "installed":
				versions_dict[package]["installed"] = version
			elif section == "available":
				versions_dict[package]["available"].append(version)

	# Now summarise
	for package, data in versions_dict.items():
		candidate = "<none>"
		if len(data["available"]) > 0:
			candidate = data["available"][-1]
			if data["installed"] == candidate:
				candidate = ""
		versions.append((package, data["installed"], candidate, list(reversed(data["available"]))))

	return versions

def check_versions_zypper(packages: List[str]) -> List[Tuple[str, str, str, List[str]]]:
	"""
	Given a list of packages, return installed, candidate, and all available versions

		Parameters:
			packages (list[str]): A list of packages to get versions for
		Returns:
			versions (list[(package, installed_version, candidate_version, all_versions)]): A list of package versions
	"""

	versions = []
	versions_dict: Dict[str, Dict] = {}

	zypper_path = cmtio.secure_which(FilePath("/usr/bin/zypper"), fallback_allowlist = ["/usr/bin"],
					 security_policy = SecurityPolicy.ALLOWLIST_RELAXED)
	args = [zypper_path, "search", "-s", "-x"] + packages
	response = cmtio.execute_command_with_response(args)
	split_response = response.splitlines()

	# il | kubernetes1.28-kubeadm | package | 1.28.3-150400.5.1 | x86_64 | kubic
	# i | kubernetes1.28-kubeadm | package | 1.28.3-150400.5.1 | x86_64 | kubic
	package_version = re.compile(r"^(.).? \| (\S+) +\| package +\| (\S+) +\|.*")

	for line in split_response:
		if (tmp := package_version.match(line)):
			if tmp is not None:
				package = tmp[2]
				version = tmp[3]

				if package not in versions_dict:
					versions_dict[package] = {
						"installed": "<none>",
						"candidate": "<none>",
						"available": [],
					}

				if tmp[1] == "i":
					versions_dict[package]["installed"] = version
				versions_dict[package]["available"].append(version)

	# Now summarise
	for package, data in versions_dict.items():
		installed = data["installed"]
		available = data["available"]
		if len(available) > 0:
			candidate = available[0]
		if candidate == installed:
			candidate = ""
		versions.append((package, data["installed"], candidate, list(reversed(data["available"]))))

	return versions

def identify_k8s_distro() -> str:
	"""
	Identify what Kubernetes distro (kubeadm, minikube, OpenShift, etc.) is in use

		Returns:
			k8s_distro (str): The identified Kubernetes distro; empty if no distro could be identified
	"""

	k8s_distro = None

	# This will only work for running clusters
	from kubernetes_helper import KubernetesHelper  # pylint: disable=import-outside-toplevel
	kh = KubernetesHelper(about.PROGRAM_SUITE_NAME, about.PROGRAM_SUITE_VERSION, None)

	vlist, status = kh.get_list_by_kind_namespace(("Node", ""), "")
	if status != 200:
		ansithemeprint([ANSIThemeString("Error", "error"),
				ANSIThemeString(": API-server returned ", "default"),
				ANSIThemeString(f"{status}", "errorvalue"),
				ANSIThemeString("; aborting.", "default")], stderr = True)
		sys.exit(errno.EINVAL)
	if vlist is None:
		ansithemeprint([ANSIThemeString("Error", "error"),
				ANSIThemeString(": API-server did not return any data", "default")], stderr = True)
		sys.exit(errno.EINVAL)

	tmp_k8s_distro = None
	for node in vlist:
		node_roles = kh.get_node_roles(cast(Dict, node))
		labels = deep_get(node, DictPath("metadata#labels"), {})
		if "control-plane" in node_roles or "master" in node_roles:
			cri = deep_get(node, DictPath("status#nodeInfo#containerRuntimeVersion"), "")
			if cri is not None:
				cri = cri.split(":")[0]
			ipaddresses = []
			for address in deep_get(node, DictPath("status#addresses")):
				if deep_get(address, DictPath("type"), "") == "InternalIP":
					ipaddresses.append(deep_get(address, DictPath("address")))
			tmp_k8s_distro = None
			minikube_name = deep_get(node, DictPath("metadata#labels#minikube.k8s.io/name"), "")
			os_image = deep_get(node, DictPath("status#nodeInfo#osImage"), "")
			images = deep_get(node, DictPath("status#images"), [])
			for image in images:
				names = deep_get(image, DictPath("names"), [])
				for name in names:
					if "openshift-crc-cluster" in name:
						tmp_k8s_distro = "crc"
						break
				if tmp_k8s_distro is not None:
					break
			if minikube_name != "":
				tmp_k8s_distro = "minikube"
			elif deep_get(labels, DictPath("microk8s.io/cluster"), False):
				tmp_k8s_distro = "microk8s"
			elif deep_get(node, DictPath("spec#providerID"), "").startswith("kind://"):
				tmp_k8s_distro = "kind"
			elif os_image.startswith("Talos"):
				tmp_k8s_distro = "talos"
			else:
				managed_fields = deep_get(node, DictPath("metadata#managedFields"), [])
				for managed_field in managed_fields:
					manager = deep_get(managed_field, DictPath("manager"), "")
					if manager == "rke2":
						tmp_k8s_distro = "rke2"
						break
					if manager == "k0s":
						tmp_k8s_distro = "k0s"
						break
					if manager.startswith("deploy@k3d"):
						tmp_k8s_distro = "k3d"
						break
					if manager == "k3s":
						tmp_k8s_distro = "k3s"
						break
					if manager == "kubeadm":
						tmp_k8s_distro = "kubeadm"
						break
			if tmp_k8s_distro is None:
				# Older versions of Kubernetes doesn't have managedFields;
				# fall back to checking whether the annotation
				# kubeadm.alpha.kubernetes.io/cri-socket exists if we cannot
				# find any managedFields
				if len(deep_get(node, DictPath("metadata#annotations#kubeadm.alpha.kubernetes.io/cri-socket"), "")) > 0:
					tmp_k8s_distro = "kubeadm"
			if tmp_k8s_distro is not None:
				if k8s_distro is not None:
					ansithemeprint([ANSIThemeString("Critical", "critical"),
							ANSIThemeString(": The control planes are reporting conflicting Kubernetes distros; aborting.", "default")], stderr = True)
					sys.exit(errno.EINVAL)
				else:
					k8s_distro = tmp_k8s_distro
		else:
			# This isn't a control plane; but this might still be vcluster
			if deep_get(labels, DictPath("vcluster.loft.sh/fake-node"), 'false') == 'true':
				if k8s_distro is None and tmp_k8s_distro is None:
					tmp_k8s_distro = "vcluster"
	if k8s_distro is None and tmp_k8s_distro is not None:
		k8s_distro = tmp_k8s_distro

	if k8s_distro is None:
		k8s_distro = "<unknown>"

	return k8s_distro

def identify_distro() -> str:
	"""
	Identify what distro (Debian, Red Hat, SUSE, etc.) is in use

		Returns:
			distro (str): The identified distro; empty if no distro could be identified
	"""

	# Find out what distro this is run on
	try:
		distro_path = cmtio.secure_which(FilePath("/etc/os-release"),
						 fallback_allowlist = ["/usr/lib", "/lib"],
						 security_policy = SecurityPolicy.ALLOWLIST_STRICT,
						 executable = False)
	except FileNotFoundError:
		ansithemeprint([ANSIThemeString("Error:", "error"),
				ANSIThemeString(" Cannot find an “", "default"),
				ANSIThemeString("os-release", "path"),
				ANSIThemeString("“ file to determine OS distribution; aborting.", "default")])
		sys.exit(errno.ENOENT)

	distro = None

	distro_id_like = ""
	distro_id = ""

	with open(distro_path, "r", encoding = "utf-8") as f:
		lines = f.readlines()
		for line in lines:
			line = line.strip()
			key, value = line.split("=")
			value = value.strip("\"'")
			if key == "ID_LIKE":
				distro_id_like = value
				# If there's an ID_LIKE in the file we're done
				break
			if key == "ID":
				distro_id = value
				# But if we've only found an ID we cannot be sure
				# that there won't be an ID_LIKE later on

	if len(distro_id_like) > 0:
		distro = distro_id_like
	else:
		distro = distro_id

	if distro is None or len(distro) == 0:
		ansithemeprint([ANSIThemeString("Error:", "error"),
				ANSIThemeString(" Cannot read ID / ID_LIKE from “", "default"),
				ANSIThemeString("os-release", "path"),
				ANSIThemeString("“ file to determine OS distribution; aborting.", "default")])
		sys.exit(errno.ENOENT)

	if distro == "suse opensuse":
		distro = "suse"

	return distro
