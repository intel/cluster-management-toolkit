#! /usr/bin/env python3
# Requires: python3 (>= 3.8)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
This file contains custom types used to define types used by CMT
"""

from datetime import datetime
from enum import auto, Enum, IntEnum
from functools import reduce
import os
import sys
import traceback
from typing import Any, Dict, List, NewType, Optional, Union

FilePath = NewType("FilePath", str)
DictPath = NewType("DictPath", str)

class UnknownError(Exception):
	"""
	Exception raised when an error occurs that we have no further information about
	Note: severity and formatted_msg use Any as type to avoid recursive imports,
	but they are typically LogLevel and List[ANSIThemeString], respectively

		Attributes:
			message (str): Additional information about the error
			severity (any): The severity
			facility (str): A facility
			formatted_msg (any); A formatted version of the message
			timestamp (datetime): A timestamp (optional; normally taken from datetime.now())
			file (str): The file the error occurred in (optional; normally taken from the frame)
			function (str): The function the error occurred in (optional; normally taken from the frame)
			lineno (str): The line the error occurred on (optional; normally taken from the frame)
			ppid (str): The parent pid of the process (optional; normally taken from os.getppid())
	"""

	traceback: Optional[str] = None

	def __init__(self,
		     message: str,
		     severity: Optional[Any] = None,
		     facility: Optional[str] = None,
		     formatted_msg: Optional[Any] = None,
		     timestamp: Optional[datetime] = None,
		     file: Optional[str] = None,
		     function: Optional[str] = None,
		     lineno: Optional[int] = None,
		     ppid: Optional[int] = None) -> None:
		try:
			# This is to get the necessary stack info
			raise UserWarning
		except UserWarning:
			frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
			self.file = str(frame.f_code.co_filename)  # type: ignore
			self.function = str(frame.f_code.co_name)  # type: ignore
			self.lineno = int(frame.f_lineno)  # type: ignore

		self.exception = __class__.__name__  # type: ignore
		self.message = message
		self.severity = severity
		self.facility = facility
		self.formatted_msg = formatted_msg
		if timestamp is None:
			self.timestamp = datetime.now()
		else:
			self.timestamp = timestamp
		if file is not None:
			self.file = file
		if function is not None:
			self.function = function
		if lineno is not None:
			self.lineno = lineno
		if ppid is not None:
			self.ppid = ppid
		else:
			self.ppid = os.getppid()
		self.traceback = ''.join(traceback.format_stack())

		super().__init__(message)

	def __str__(self) -> str:
		"""
		Return a string representation of the exception

			Returns:
				(str): The string representation of the exception
		"""

		if len(self.message) == 0:
			message = "No further details were provided"
		else:
			message = self.message

		return message

	def exception_dict(self) -> Dict:
		"""
		Return a dictionary containing structured information about the exception

			Returns:
				(dict): A dictionary with structured information
		"""

		return {
			"exception": self.exception,
			"message": self.message,
			"severity": self.severity,
			"facility": self.facility,
			"formatted_msg": self.formatted_msg,
			"timestamp": self.timestamp,
			"file": self.file,
			"function": self.function,
			"lineno": self.lineno,
			"ppid": self.ppid,
			"traceback": self.traceback,
		}

class ProgrammingError(Exception):
	"""
	Exception raised when a condition occured that is most likely caused by a programming error
	Note: severity and formatted_msg use Any as type to avoid recursive imports,
	but they are typically LogLevel and List[ANSIThemeString], respectively

		Attributes:
			message (str): Additional information about the error
			subexception (Exception): Related standard exception
			severity (any): The severity
			facility (str): A facility
			formatted_msg (any); A formatted version of the message
			timestamp (datetime): A timestamp (optional; normally taken from datetime.now())
			file (str): The file the error occurred in (optional; normally taken from the frame)
			function (str): The function the error occurred in (optional; normally taken from the frame)
			lineno (str): The line the error occurred on (optional; normally taken from the frame)
			ppid (str): The parent pid of the process (optional; normally taken from os.getppid())
	"""

	traceback: Optional[str] = None

	def __init__(self,
		     message: str,
		     subexception: Exception = None,
		     severity: Optional[Any] = None,
		     facility: Optional[str] = None,
		     formatted_msg: Optional[Any] = None,
		     timestamp: Optional[datetime] = None,
		     file: Optional[str] = None,
		     function: Optional[str] = None,
		     lineno: Optional[int] = None,
		     ppid: Optional[int] = None) -> None:
		try:
			# This is to get the necessary stack info
			raise UserWarning
		except UserWarning:
			frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
			self.file = str(frame.f_code.co_filename)  # type: ignore
			self.function = str(frame.f_code.co_name)  # type: ignore
			self.lineno = int(frame.f_lineno)  # type: ignore

		self.exception = __class__.__name__  # type: ignore
		self.subexception = subexception
		self.message = message
		self.severity = severity
		self.facility = facility
		self.formatted_msg = formatted_msg
		if timestamp is None:
			self.timestamp = datetime.now()
		else:
			self.timestamp = timestamp
		if file is not None:
			self.file = file
		if function is not None:
			self.function = function
		if lineno is not None:
			self.lineno = lineno
		if ppid is not None:
			self.ppid = ppid
		else:
			self.ppid = os.getppid()
		self.traceback = ''.join(traceback.format_stack())

		super().__init__(message)

	def __str__(self) -> str:
		"""
		Return a string representation of the exception

			Returns:
				(str): The string representation of the exception
		"""

		if self.subexception is None:
			message = ""
		else:
			message = f"({self.subexception}): "

		if len(self.message) == 0:
			message += "No further details were provided"
		else:
			message += f"{self.message}"

		return message

	def exception_dict(self) -> Dict:
		"""
		Return a dictionary containing structured information about the exception

			Returns:
				(dict): A dictionary with structured information
		"""

		return {
			"exception": self.exception,
			"subexception": self.subexception,
			"message": self.message,
			"severity": self.severity,
			"facility": self.facility,
			"formatted_msg": self.formatted_msg,
			"timestamp": self.timestamp,
			"file": self.file,
			"function": self.function,
			"lineno": self.lineno,
			"ppid": self.ppid,
			"traceback": self.traceback,
		}

class FilePathAuditError(Exception):
	"""
	Exception raised when a security check fails on a FilePath
	Note: severity and formatted_msg use Any as type to avoid recursive imports,
	but they are typically LogLevel and List[ANSIThemeString], respectively

		Attributes:
			message (str): Additional information about the error
			path (FilePath): The path being audited
			severity (any): The severity
			facility (str): A facility
			formatted_msg (any); A formatted version of the message
			timestamp (datetime): A timestamp (optional; normally taken from datetime.now())
			file (str): The file the error occurred in (optional; normally taken from the frame)
			function (str): The function the error occurred in (optional; normally taken from the frame)
			lineno (str): The line the error occurred on (optional; normally taken from the frame)
			ppid (str): The parent pid of the process (optional; normally taken from os.getppid())
	"""

	traceback: Optional[str] = None

	def __init__(self,
	             message: str,
		     path: Optional[FilePath] = None,
		     severity: Optional[Any] = None,
		     facility: Optional[str] = None,
		     formatted_msg: Optional[Any] = None,
		     timestamp: Optional[datetime] = None,
		     file: Optional[str] = None,
		     function: Optional[str] = None,
		     lineno: Optional[int] = None,
		     ppid: Optional[int] = None) -> None:
		try:
			# This is to get the necessary stack info
			raise UserWarning
		except UserWarning:
			frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
			self.file = str(frame.f_code.co_filename)  # type: ignore
			self.function = str(frame.f_code.co_name)  # type: ignore
			self.lineno = int(frame.f_lineno)  # type: ignore

		self.exception = __class__.__name__  # type: ignore
		self.message = message
		self.path = path
		self.severity = severity
		self.facility = facility
		self.formatted_msg = formatted_msg
		if timestamp is None:
			self.timestamp = datetime.now()
		else:
			self.timestamp = timestamp
		if file is not None:
			self.file = file
		if function is not None:
			self.function = function
		if lineno is not None:
			self.lineno = lineno
		if ppid is not None:
			self.ppid = ppid
		else:
			self.ppid = os.getppid()
		self.traceback = ''.join(traceback.format_stack())

		super().__init__(message)

	def __str__(self) -> str:
		"""
		Return a string representation of the exception

			Returns:
				(str): The string representation of the exception
		"""

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

	def exception_dict(self) -> Dict:
		"""
		Return a dictionary containing structured information about the exception

			Returns:
				(dict): A dictionary with structured information
		"""

		return {
			"exception": self.exception,
			"message": self.message,
			"path": self.path,
			"severity": self.severity,
			"facility": self.facility,
			"formatted_msg": self.formatted_msg,
			"timestamp": self.timestamp,
			"file": self.file,
			"function": self.function,
			"lineno": self.lineno,
			"ppid": self.ppid,
			"traceback": self.traceback,
		}

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
	DNS_TLD_INVALID = auto()

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
	CAN_READ_IF_EXISTS = auto()
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
		raise ValueError(f"deep_set: dictionary {dictionary} or path {path} invalid/unset")

	ref = dictionary
	pathsplit = path.split("#")

	for i in range(0, len(pathsplit)):
		if ref is None or not isinstance(ref, dict):
			raise ValueError(f"Path {path} does not exist in dictionary {dictionary} or is the wrong type {type(ref)}")

		if pathsplit[i] not in ref or ref[pathsplit[i]] is None:
			if create_path:
				ref[pathsplit[i]] = {}

		if i == len(pathsplit) - 1:
			ref[pathsplit[i]] = value
			break

		ref = deep_get(ref, DictPath(pathsplit[i]))

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

		if result is not None and not (type(result) in (list, str, dict) and len(result) == 0 and fallback_on_empty):
			break
	if result is None or type(result) in (list, str, dict) and len(result) == 0 and fallback_on_empty:
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
		if result is not None and not (type(result) in (list, str, dict) and len(result) == 0 and fallback_on_empty):
			break
	if result is None or type(result) in (list, str, dict) and len(result) == 0 and fallback_on_empty:
		result = default
	return result
