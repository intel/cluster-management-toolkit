#! /usr/bin/env python3
# Requires: python3 (>= 3.8)
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Structured log module for CMT
"""

from datetime import datetime, timezone
from enum import auto, Enum
import os
from pathlib import Path, PurePath
import sys
from typing import cast, Dict, List, Optional, Union

try:
	from natsort import natsorted
except ModuleNotFoundError:  # pragma: no cover
	sys.exit("ModuleNotFoundError: Could not import natsort; you may need to (re-)run `cmt-install` or `pip3 install natsort`; aborting.")

from cmtpaths import CMT_LOGS_DIR, AUDIT_LOG_BASENAME, DEBUG_LOG_BASENAME
from cmttypes import FilePath, LogLevel, ProgrammingError
from cmtio_yaml import secure_write_yaml

from ansithemeprint import ANSIThemeString

auditlog = None
debuglog = None

class CMTLogType(Enum):
	"""
	Type of log passed to CMTLog
	"""
	AUDIT = auto()
	DEBUG = auto()

class CMTLog:
	"""
	A structured log format used by CMT that serialises to YAML on disk. To ensure that we can use
	append we use a list; this means that the performance is worse when reading the log,
	but we do not need to read the file to do an append.

	The AUDIT log is always synchronous (flushed immediately).
	All other logs require flush() to be called.

	If no timestamp is passed now(timezone.utc) will be used.

	To avoid logs flooding the system every log file is limited to 1MB,
	and the number of log files limited to 100, hence setting an upper limit to 100MB worth of logs.
	"""

	log: List[Dict] = []
	logtype = None
	basename: Optional[FilePath] = None
	# These two are used for rate limiting
	last_write = None
	writes_last_minute = 0

	def __rate_limit(self, filepath: FilePath, rate_limit: int, exception_on_flood: bool = True) -> bool:
		now = datetime.now()

		if self.last_write is None or (now - self.last_write).seconds > 60:
			self.last_write = now
			self.writes_last_minute = 1
		else:
			self.writes_last_minute += 1

		# More than 10 log messages in a minute is an indication that something is very, very wrong;
		# this should be close to 0
		if self.writes_last_minute > rate_limit:
			if exception_on_flood:
				raise ProgrammingError(f"The log {filepath} is flooded; more than {rate_limit} messages in 60 seconds")
			return False

		return True

	# pylint: disable-next=too-many-arguments
	def __format_entry(self, message: Union[List[List[ANSIThemeString]], List[str]],
			   severity: LogLevel = LogLevel.INFO, timestamp: Optional[datetime] = None,
			   facility: str = "", file: str = "", function: str = "", lineno: int = 0) -> Dict:
		if timestamp is None:
			timestamp = datetime.now(timezone.utc)

		log_entry: Dict = {
			"timestamp": timestamp,
			"severity": str(severity),
			"facility": facility,
			"file": PurePath(file).name,
			"function": function,
			"lineno": lineno,
			"ppid": os.getppid(),
		}

		if not isinstance(message, list):
			raise TypeError(f"CMTLog only accepts log messages as List[str] or List[themearray]; received {type(message)}")

		if isinstance(message[0], str):
			log_entry["strarray"] = cast(List[str], message)
		else:
			loglines = []
			for line in message:
				logline = []
				for linesegment in line:
					linesegment = cast(ANSIThemeString, linesegment)
					logline.append({
						"string": str(linesegment),
						"themeref": linesegment.themeref,
					})
				loglines.append(logline)
			log_entry["themearray"] = loglines
		return log_entry

	def __rotate_filename(self, dirpath: FilePath, basename: str, suffix: str = "", maxsize: int = 1024 ** 3) -> Optional[FilePath]:
		dir_path_entry = Path(dirpath)

		if not dir_path_entry.is_dir():
			return None

		newest = None
		count = 1

		for filename in natsorted(list(dir_path_entry.glob(f"{basename}*{suffix}")), reverse = True):
			if newest is None:
				newest = str(filename)
			count += 1

		if newest is None:
			filename = f"{basename}{count}{suffix}"
		else:
			path_entry = Path(FilePath(PurePath(dirpath).joinpath(newest)))
			fstat = path_entry.stat()
			if fstat.st_size > maxsize:
				count += 1
				filename = f"{basename}{count}{suffix}"
			else:
				filename = newest

		return FilePath(str(PurePath(dirpath).joinpath(filename)))

	# pylint: disable-next=too-many-arguments
	def __init__(self, path: Union[CMTLogType, FilePath],
		     message: Union[List[List[ANSIThemeString]], List[str]] = None,
		     severity: LogLevel = LogLevel.INFO,
		     timestamp: Optional[datetime] = None, facility: str = ""):
		# Figure out what the caller was
		file = None
		function = None
		lineno = None
		try:
			# This is to get the necessary stack info
			raise UserWarning
		except UserWarning:
			frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
			file = str(frame.f_code.co_filename)  # type: ignore
			function = str(frame.f_code.co_name)  # type: ignore
			lineno = int(frame.f_lineno)  # type: ignore

		if path == CMTLogType.DEBUG:
			self.basename = DEBUG_LOG_BASENAME
		elif path == CMTLogType.AUDIT:
			self.basename = AUDIT_LOG_BASENAME
		else:
			self.basename = cast(FilePath, path)

		if isinstance(path, CMTLogType):
			self.logtype = path

		# OK, we're initialising without logging anything
		if message is None:
			return

		log_entry = self.__format_entry(message, severity, timestamp, facility, file, function, lineno)

		# The audit log is always synchronous
		if path == CMTLogType.AUDIT:
			log_path = self.__rotate_filename(dirpath = CMT_LOGS_DIR, basename = AUDIT_LOG_BASENAME, suffix = ".yaml", maxsize = 1024 ** 3)
			if self.__rate_limit(filepath = log_path, rate_limit = 10, exception_on_flood = True):
				secure_write_yaml(log_path, [log_entry], permissions = 0o600, write_mode = "a")
		else:
			log_path = self.__rotate_filename(dirpath = CMT_LOGS_DIR, basename = self.basename, suffix = ".yaml", maxsize = 1024 ** 3)
			if self.__rate_limit(filepath = log_path, rate_limit = 10, exception_on_flood = True):
				self.log.append(log_entry)

	def __del__(self) -> None:
		if self.logtype != CMTLogType.AUDIT:
			self.flush()
		self.close()

	def add(self, message: Union[List[List[ANSIThemeString]], List[str]],
		severity: LogLevel = LogLevel.INFO, timestamp: Optional[datetime] = None, facility: str = "") -> None:
		"""
		Add a new log message to a log

			Parameters:
				message ([str] or [[AnsiThemeString]]): Either a list of unformatted strings or a list of formatted strings
		"""

		# Figure out what the caller was
		file = None
		function = None
		lineno = None
		try:
			# This is to get the necessary stack info
			raise UserWarning
		except UserWarning:
			frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
			file = str(frame.f_code.co_filename)  # type: ignore
			function = str(frame.f_code.co_name)  # type: ignore
			lineno = int(frame.f_lineno)  # type: ignore

		log_entry = self.__format_entry(message, severity, timestamp, facility, file, function, lineno)

		# The audit log is always synchronous; calling it like this is incorrect, but we want audit messages to be successful, so we just log an extra message
		if self.logtype == CMTLogType.AUDIT:
			warning_log_entry = {
				"timestamp": timestamp,
				"severity": str(LogLevel.WARNING),
				"facility": facility,
				"file": PurePath(file).name,
				"function": function,
				"lineno": lineno,
				"ppid": os.getppid(),
				"strarray": ["CMTLog.add() called from a synchronous log; this is a programming error."]
			}
			log_path = self.__rotate_filename(dirpath = CMT_LOGS_DIR, basename = self.basename, suffix = ".yaml", maxsize = 1024 ** 3)
			if self.__rate_limit(filepath = log_path, rate_limit = 10, exception_on_flood = True):
				secure_write_yaml(log_path, [warning_log_entry], permissions = 0o600, write_mode = "a")
				secure_write_yaml(log_path, [log_entry], permissions = 0o600, write_mode = "a")
		else:
			log_path = self.__rotate_filename(dirpath = CMT_LOGS_DIR, basename = self.basename, suffix = ".yaml", maxsize = 1024 ** 3)
			if self.__rate_limit(filepath = log_path, rate_limit = 10, exception_on_flood = True):
				self.log.append(log_entry)

	def flush(self) -> None:
		"""
		Flush the log to storage
		"""

		if self.logtype == CMTLogType.AUDIT:
			# Figure out what the caller was
			file = None
			function = None
			lineno = None
			try:
				# This is to get the necessary stack info
				raise UserWarning
			except UserWarning:
				frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
				file = str(frame.f_code.co_filename)  # type: ignore
				function = str(frame.f_code.co_name)  # type: ignore
				lineno = int(frame.f_lineno)  # type: ignore

			warning_log_entry = {
				"timestamp": datetime.now(timezone.utc),
				"severity": str(LogLevel.WARNING),
				"facility": "",
				"file": PurePath(file).name,
				"function": function,
				"lineno": lineno,
				"ppid": os.getppid(),
				"strarray": ["CMTLog.flush() called from a synchronous log; this is a programming error."]
			}
			log_path = self.__rotate_filename(dirpath = CMT_LOGS_DIR, basename = AUDIT_LOG_BASENAME, suffix = ".yaml", maxsize = 1024 ** 3)
			if self.__rate_limit(filepath = log_path, rate_limit = 10, exception_on_flood = True):
				secure_write_yaml(log_path, [warning_log_entry], permissions = 0o600, write_mode = "a")
		elif len(self.log) > 0:
			log_path = self.__rotate_filename(dirpath = CMT_LOGS_DIR, basename = self.basename, suffix = ".yaml", maxsize = 1024 ** 3)
			if self.__rate_limit(filepath = log_path, rate_limit = 10, exception_on_flood = True):
				secure_write_yaml(log_path, self.log, permissions = 0o600, write_mode = "a")
			self.log = []

	def close(self) -> None:
		"""
		Close the log; this is not necessary from an I/O-perspective; it is intended to be used to detect logical errors in the code
		"""

		self.path = None
		self.logtype = None
		self.log = []
