#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

"""
This file contains custom types used to define types used by iKT
"""

from enum import auto, Enum, IntEnum
from typing import NamedTuple, NewType, Optional

# A reference to text formatting
class ThemeAttr(NamedTuple):
	context: str
	attr_ref: str

# A reference to preformatted string;
class ThemeRef(NamedTuple):
	context: str
	attr_ref: str

class ThemeString(NamedTuple):
	string: str
	# Once all callsites have been modified this should be ThemeAttr, not ThemeRef
	themeref: ThemeRef
	selected: bool = False

# Note: A ThemeArray is Sequence[Union[ThemeRef, ThemeString]]

class ANSIThemeString(NamedTuple):
	string: str
	themeref: str

FilePath = NewType("FilePath", str)
DictPath = NewType("DictPath", str)

class FilePathAuditError(Exception):
	"""
	Exception raised when a security check fails on a FilePath

		Attributes:
			path: The path being audited
			message: Additional information about the error
	"""

	def __init__(self, message: str, path: FilePath = None) -> None:
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

class SecurityStatus(Enum):
	"""
	Return values from check_path()
	"""

	OK = auto()
	# Critical
	WORLD_WRITABLE = auto()
	PARENT_WORLD_WRITABLE = auto()
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
	IS_NOT_EXECUTABLE = auto()
	PARENT_IS_NOT_DIR = auto()

class SecurityChecks(Enum):
	"""
	Checks that can be performed by check_path()
	"""

	PARENT_RESOLVES_TO_SELF = auto()
	RESOLVES_TO_SELF = auto()
	WORLD_WRITABLE = auto()
	PARENT_WORLD_WRITABLE = auto()
	OWNER_IN_ALLOWLIST = auto()
	PARENT_OWNER_IN_ALLOWLIST = auto()
	PERMISSIONS = auto()
	PARENT_PERMISSIONS = auto()
	EXISTS = auto()
	IS_FILE = auto()
	IS_DIR = auto()
	IS_SYMLINK = auto()
	IS_EXECUTABLE = auto()

class SecurityPolicy(Enum):
	"""
	Security policies used by iKT
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
	Loglevels used by iKT
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
	Status groups used by iKT
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
