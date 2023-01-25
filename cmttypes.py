#! /usr/bin/env python3
# Requires: python3 (>= 3.8)

"""
This file contains custom types used to define types used by CMT
"""

from enum import auto, Enum, IntEnum
from functools import reduce
from typing import Any, Dict, List, NewType, Optional, Union

FilePath = NewType("FilePath", str)
DictPath = NewType("DictPath", str)

class FilePathAuditError(Exception):
	"""
	Exception raised when a security check fails on a FilePath

		Attributes:
			path: The path being audited
			message: Additional information about the error
	"""

	def __init__(self, message: str, path: Optional[FilePath] = None) -> None:
		self.path = path
		self.message = message
		super().__init__(message)

	def __str__(self) -> str:
		if self.path is None:
			path = "<omitted>"
		else:
			path = self.path
		if len(self.message) == 0:
			message = "No further details were provided"
		else:
			message = self.message

		msg = f"Security policy violation for path {path}.  {message}"

		return msg

class HostNameStatus(Enum):
	"""
	Return values from validate_hostname()
	"""

	OK = auto()
	DNS_SUBDOMAIN_EMPTY = auto()
	DNS_SUBDOMAIN_TOO_LONG = auto()
	DNS_SUBDOMAIN_WRONG_CASE = auto()
	DNS_SUBDOMAIN_INVALID_FORMAT = auto()
	DNS_LABEL_STARTS_WITH_IDNA = auto()
	DNS_LABEL_INVALID_FORMAT = auto()
	DNS_LABEL_TOO_LONG = auto()
	DNS_LABEL_PUNYCODE_TOO_LONG = auto()
	DNS_LABEL_INVALID_CHARACTERS = auto()

class SecurityStatus(IntEnum):
	"""
	Return values from check_path()
	"""

	OK = auto()
	# Critical
	PERMISSIONS = auto()
	PARENT_PERMISSIONS = auto()
	OWNER_NOT_IN_ALLOWLIST = auto()
	PARENT_OWNER_NOT_IN_ALLOWLIST = auto()
	PATH_NOT_RESOLVING_TO_SELF = auto()
	PARENT_PATH_NOT_RESOLVING_TO_SELF = auto()
	# Error
	DOES_NOT_EXIST = auto()
	PARENT_DOES_NOT_EXIST = auto()
	IS_NOT_FILE = auto()
	IS_NOT_DIR = auto()
	IS_NOT_SYMLINK = auto()
	IS_EXECUTABLE = auto()
	IS_NOT_EXECUTABLE = auto()
	PARENT_IS_NOT_DIR = auto()
	DIR_NOT_EMPTY = auto()
	EXISTS = auto()

class SecurityChecks(Enum):
	"""
	Checks that can be performed by check_path()
	"""

	PARENT_RESOLVES_TO_SELF = auto()
	RESOLVES_TO_SELF = auto()
	OWNER_IN_ALLOWLIST = auto()
	PARENT_OWNER_IN_ALLOWLIST = auto()
	PERMISSIONS = auto()
	PARENT_PERMISSIONS = auto()
	EXISTS = auto()
	IS_FILE = auto()
	IS_DIR = auto()
	IS_SYMLINK = auto()
	IS_EXECUTABLE = auto()
	IS_NOT_EXECUTABLE = auto()

class SecurityPolicy(Enum):
	"""
	Security policies used by CMT
	"""
	# Only allows exact matches
	STRICT = auto()
	# Only allows exact matches from any path in the allowlist
	ALLOWLIST_STRICT = auto()
	# Allows exact matches from any path in the allowlist,
	# but path elements can be symlinks
	ALLOWLIST_RELAXED = auto()

class LogLevel(IntEnum):
	"""
	Loglevels used by CMT
	"""
	EMERG = 0
	ALERT = 1
	CRIT = 2
	ERR = 3
	WARNING = 4
	NOTICE = 5
	INFO = 6
	DEBUG = 7
	DIFFPLUS = 8
	DIFFMINUS = 9
	DIFFSAME = 10
	ALL = 255

loglevel_mappings = {
	LogLevel.EMERG: "Emergency",
	LogLevel.ALERT: "Alert",
	LogLevel.CRIT: "Critical",
	LogLevel.ERR: "Error",
	LogLevel.WARNING: "Warning",
	LogLevel.NOTICE: "Notice",
	LogLevel.INFO: "Info",
	LogLevel.DEBUG: "Debug",
	LogLevel.DIFFPLUS: "Diffplus",
	LogLevel.DIFFMINUS: "Diffminus",
	LogLevel.DIFFSAME: "Diffsame",
	LogLevel.ALL: "Debug",
}

def loglevel_to_name(loglevel: LogLevel) -> str:
	"""
	Given a numerical loglevel, return its severity string

		Parameters:
			loglevel (int): The corresponding numerical loglevel
		Returns:
			severity (str): A severity string
	"""
	return loglevel_mappings[min(LogLevel.DIFFSAME, loglevel)]

class Retval(Enum):
	"""
	Return values from the UI functions
	"""

	NOMATCH = 0	# No keypress matched/processed; further checks needed (if any)
	MATCH = 1	# keypress matched/processed; no further action
	RETURNONE = 2	# keypress matched/processed; return up one level
	RETURNFULL = 3	# keypress matched/processed, callback called; return up entire callstack
	RETURNDONE = 4	# We've done our Return One

class StatusGroup(IntEnum):
	"""
	Status groups used by CMT
	"""
	NEUTRAL = 8
	DONE = 7
	OK = 6
	PENDING = 5
	WARNING = 4
	ADMIN = 3
	NOT_OK = 2
	UNKNOWN = 1
	CRIT = 0

stgroup_mapping = {
	StatusGroup.CRIT: "status_critical",
	StatusGroup.UNKNOWN: "status_unknown",
	StatusGroup.NOT_OK: "status_not_ok",
	StatusGroup.ADMIN: "status_admin",
	StatusGroup.WARNING: "status_warning",
	StatusGroup.OK: "status_ok",
	StatusGroup.PENDING: "status_pending",
	StatusGroup.DONE: "status_done",
}

def deep_set(dictionary: Dict, path: DictPath, value: Any, create_path: bool = False) -> None:
	"""
	Given a dictionary, a path into that dictionary, and a value, set the path to that value

		Parameters:
			dictionary (dict): The dict to set the value in
			path (DictPath): A dict path
			value (any): The value to set
			create_path (bool): If True the path will be created if it does not exist
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

def deep_get(dictionary: Optional[Dict], path: DictPath, default: Any = None) -> Any:
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
