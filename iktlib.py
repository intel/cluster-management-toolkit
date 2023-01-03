#! /usr/bin/env python3

"""
Helpers used by various components of iKT
"""

from datetime import datetime, timezone, timedelta, date
import os
from pathlib import Path, PurePath
import re
import sys
from typing import Dict, List, Optional, Tuple, Union

from ikttypes import deep_get, deep_get_with_fallback, DictPath, FilePath, SecurityPolicy
from iktpaths import IKT_CONFIG_FILE, IKT_CONFIG_FILE_DIR
import iktio
import iktio_yaml

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-natsort")

iktconfig = {}

def validate_name(rtype: str, name: str) -> bool:
	"""
	Given a name validate whether it is valid for the given type

		Parameters:
			rtype (str): The resource type; valid types are:
				dns-label
				dns-subdomain
				path-segment
				port-name
			name (str): The name to check for validity
		Returns:
			valid (bool): True if valid, False if invalid
	"""

	invalid = False
	tmp = None

	if name is None:
		return False

	# Safe
	name_regex = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
	# Safe
	portname_regex = re.compile(r"^.*[a-z].*")

	if rtype in ("dns-subdomain", "dns-label"):
		if rtype == "dns-label":
			maxlen = 63
			if "." in name:
				invalid = True
		else:
			maxlen = 253

		# A dns-subdomain can be at most 253 characters long
		# and cannot start or end with "-"; it must be made up
		# of valid dns-labels; each of which are separated by "."
		# and have to meet the same standards as a dns-label
		labels = name.lower().split(".")

		for label in labels:
			if len(label) > 63:
				invalid = True
				break

			tmp = name_regex.match(label)
			if tmp is None:
				invalid = True
	elif rtype == "path-segment":
		# XXX: Are there any other requirements? maxlen or similar?
		if name in (".", "..") or "/" in name or "%" in name:
			invalid = True
		maxlen = os.pathconf("/", "PC_NAME_MAX")
	elif rtype == "port-name":
		# Any name containing adjacent "-" is invalid
		if "--" in name:
			invalid = True
		# As is any port-name that does not contain any character in [a-z]
		if portname_regex.match(name.lower()) is None:
			invalid = True
		# A portname can be at most 15 characters long
		# and cannot start or end with "-"
		tmp = name_regex.match(name.lower())
		if tmp is None:
			invalid = True
		maxlen = 15

	return invalid == False and len(name) <= maxlen

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
	iktconfig = iktio_yaml.secure_read_yaml(IKT_CONFIG_FILE)

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
		moreiktconfig = iktio_yaml.secure_read_yaml(FilePath(str(path)))

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
	response = iktio.execute_command_with_response(args)
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
			_response = iktio.execute_command_with_response(_args)
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
