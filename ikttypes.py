#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

"""
This file contains custom types used to define types used by iKT
"""

from enum import auto, Enum, IntEnum
from typing import NewType

FilePath = NewType("FilePath", str)

class SecurityPolicy(Enum):
	"""
	Security policies used by iKT
	"""
	STRICT = auto()
	ALLOWLIST_STRICT = auto()
	ALLOWLIST_RELAXED = auto()
	RELAXED = auto()

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
