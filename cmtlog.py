#! /usr/bin/env python3
# Requires: python3 (>= 3.8)

"""
Structured log module for CMT
"""

from datetime import datetime
from enum import auto, Enum
import sys
from typing import cast, Dict, List, Optional, Union

from cmtpaths import AUDIT_LOG_FILE, DEBUG_LOG_FILE
from cmttypes import FilePath, LogLevel
from cmtio_yaml import secure_write_yaml

from ansithemeprint import ANSIThemeString

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

	If no timestamp is passed now() will be used.
	"""

	log: List[Dict] = []
	logtype = None
	path: Optional[FilePath] = None

	# pylint: disable-next=too-many-arguments
	def __format_entry(self, message: Union[List[List[ANSIThemeString]], List[str]],
			   severity: LogLevel = LogLevel.INFO, timestamp: Optional[datetime] = None,
			   facility: str = "", file: str = "", function: str = "", lineno: int = 0) -> Dict:
		if timestamp is None:
			timestamp = datetime.now()

		log_entry: Dict = {
			"timestamp": timestamp,
			"severity": str(severity),
			"facility": facility,
			"file": file,
			"function": function,
			"lineno": lineno,
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

	# pylint: disable-next=too-many-arguments
	def __init__(self, path: Union[CMTLogType, FilePath], message: Union[List[List[ANSIThemeString]], List[str]],
		     severity: LogLevel = LogLevel.INFO, timestamp: Optional[datetime] = None, facility: str = ""):
		# Figure out what the caller was
		file = None
		function = None
		lineno = None
		try:
			# This is to get the necessary stack info
			raise UserWarning
		except UserWarning:
			frame = sys.exc_info()[2].tb_frame.f_back # type: ignore
			file = str(frame.f_code.co_filename) # type: ignore
			function = str(frame.f_code.co_name) # type: ignore
			lineno = int(frame.f_lineno) # type: ignore

		if path == CMTLogType.DEBUG:
			self.path = DEBUG_LOG_FILE
		elif path == CMTLogType.AUDIT:
			self.path = AUDIT_LOG_FILE
		else:
			self.path = cast(FilePath, path)

		log_entry = self.__format_entry(message, severity, timestamp, facility, file, function, lineno)
		if isinstance(path, CMTLogType):
			self.logtype = path

		# The audit log is always synchronous
		if path == CMTLogType.AUDIT:
			secure_write_yaml(AUDIT_LOG_FILE, [log_entry], permissions = 0o640, write_mode = "a")
		else:
			self.log.append(log_entry)

	def __del__(self) -> None:
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
			frame = sys.exc_info()[2].tb_frame.f_back # type: ignore
			file = str(frame.f_code.co_filename) # type: ignore
			function = str(frame.f_code.co_name) # type: ignore
			lineno = int(frame.f_lineno) # type: ignore

		log_entry = self.__format_entry(message, severity, timestamp, facility, file, function, lineno)

		# The audit log is always synchronous; calling it like this is incorrect, but we want audit messages to be successful, so we just log an extra message
		if self.logtype == CMTLogType.AUDIT:
			warning_log_entry = {
				"timestamp": timestamp,
				"severity": str(LogLevel.WARNING),
				"facility": facility,
				"file": file,
				"function": function,
				"lineno": lineno,
				"strarray": ["CMTLog.add() called from a synchronous log; this is a programming error."]
			}
			secure_write_yaml(AUDIT_LOG_FILE, [warning_log_entry], permissions = 0o640, write_mode = "a")
			secure_write_yaml(AUDIT_LOG_FILE, [log_entry], permissions = 0o640, write_mode = "a")
		else:
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
				frame = sys.exc_info()[2].tb_frame.f_back # type: ignore
				file = str(frame.f_code.co_filename) # type: ignore
				function = str(frame.f_code.co_name) # type: ignore
				lineno = int(frame.f_lineno) # type: ignore

			warning_log_entry = {
				"timestamp": datetime.now(),
				"severity": str(LogLevel.WARNING),
				"facility": "",
				"file": file,
				"function": function,
				"lineno": lineno,
				"strarray": ["CMTLog.flush() called from a synchronous log; this is a programming error."]
			}
			secure_write_yaml(AUDIT_LOG_FILE, [warning_log_entry], permissions = 0o640, write_mode = "a")
		elif len(self.log) > 0:
			secure_write_yaml(cast(FilePath, self.path), self.log, permissions = 0o640, write_mode = "a")
			self.log = []

	def close(self) -> None:
		"""
		Close the log; this is not necessary from an I/O-perspective; it is intended to be used to detect logical errors in the code
		"""

		self.path = None
		self.logtype = None
		self.log = []
