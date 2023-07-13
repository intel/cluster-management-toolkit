#! /usr/bin/env python3
# Requires: python3 (>= 3.8)

# The parser takes one line of input at a time;
# for messages that need multi-line parsing you need to
# return remnants and if necessary tweak multiline_parser
#
# Log levels are the same as in syslog:
# EMERG		system is unusable <should be irrelevant>
# ALERT		action must be taken immediately
# CRIT		critical conditions
# ERR		error conditions
# WARNING	warning conditions
# NOTICE	normal, but significant, condition
# INFO		informational message
# DEBUG		debug-level message
#
# Return format is timestamp, facility, severity, message

"""
Log parsers for cmu
"""

# pylint: disable=line-too-long

import ast
from collections import namedtuple
from datetime import datetime
import difflib
# ujson is much faster than json,
# but it might not be available
try:
	import ujson as json
	json_is_ujson = True
	# The exception raised by ujson when parsing fails is different
	# from what json raises
	DecodeException = ValueError
except ModuleNotFoundError:
	import json # type: ignore
	json_is_ujson = False
	DecodeException = json.decoder.JSONDecodeError # type: ignore
from pathlib import Path, PurePath
import re
import sys
from typing import cast, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union
try:
	import yaml
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: You probably need to install python3-yaml; did you forget to run cmt-install?")

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: You probably need to install python3-natsort; did you forget to run cmt-install?")

try:
	import validators # type: ignore
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: You probably need to install python3-validators; did you forget to run cmt-install?")

from cmtpaths import HOMEDIR, PARSER_DIR

from cmtlog import CMTLogType, CMTLog
from cmttypes import deep_get, deep_get_with_fallback, DictPath, FilePath, LogLevel, loglevel_mappings, loglevel_to_name

from cmtio_yaml import secure_read_yaml, secure_read_yaml_all

import cmtlib
from cmtlib import none_timestamp
import formatter as formatters # pylint: disable=wrong-import-order,deprecated-module

from curses_helper import themearray_len, themearray_to_string, ThemeAttr, ThemeRef, ThemeString

from ansithemeprint import ANSIThemeString

class logparser_configuration:
	"""
	Various configuration options used by the logparsers
	"""
	# Keep or strip timestamps in structured logs
	pop_ts: bool = True
	# Keep or strip severity in structured logs
	pop_severity: bool = True
	# Keep or strip facility in structured logs
	pop_facility: bool = True
	# msg="foo" or msg=foo => foo
	msg_extract: bool = True
	# If msg_extract is False,
	# this decides whether or not to put msg="foo" first or not
	# this also affects err="foo" and error="foo"
	msg_first: bool = True
	# if msg_extract is True,
	# this decides whether msg="foo\nbar" should be converted to:
	# foo
	# bar
	# This does (currently) not affect "err=" and "error="
	msg_linebreaks: bool = True
	# Should "* " be replaced with real bullets?
	msg_realbullets: bool = True
	# Should override severity rules be applied?
	override_severity: bool = True
	# collector=foo => • foo
	bullet_collectors: bool = True
	# if msg_extract is True,
	# this decides whether should be converted to:
	# msg="Starting foo" version="(version=.*)" => Starting foo (version=.*)
	merge_starting_version: bool = True
	using_bundles: bool = False

if json_is_ujson:
	def json_dumps(obj) -> str:
		"""
		Dump JSON object to text format; ujson version

			Parameters:
				obj (dict): The JSON object to dump
			Returns:
				str: The serialized JSON object
		"""

		indent = 2
		return json.dumps(obj, indent = indent, escape_forward_slashes = False)
else:
	def json_dumps(obj) -> str:
		"""
		Dump JSON object to text format; json version

			Parameters:
				obj (dict): The JSON object to dump
			Returns:
				str: The serialized JSON object
		"""

		indent = 2
		return json.dumps(obj, indent = indent)

def get_loglevel_names() -> List[str]:
	"""
	Ugly way of removing duplicate values from dict

		Returns:
			list[str]: The unique severities
	"""
	return list(dict.fromkeys(list(loglevel_mappings.values())))

def name_to_loglevel(severity: str) -> LogLevel:
	"""
	Given a severity string, return its numerical number

		Parameters:
			name  (int): The corresponding numerical loglevel
		Returns:
			severity (str): A severity string
	"""
	for _severity, _severity_string in loglevel_mappings.items():
		if _severity_string.lower() == severity.lower():
			return _severity
	raise ValueError(f"Programming error! Loglevel {severity} does not exist!")

def month_to_numerical(month: str) -> str:
	"""
	Convert a 3-letter month string to a numerical month string

		Parameters:
			month (str): The month string
		Returns:
			int: The numerical value for the month
	"""

	months = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
	month = str(month.lower()[0:3]).zfill(2)

	y = 1
	for tmp in months:
		if month == tmp:
			return str(y).zfill(2)
		y += 1

	raise TypeError("No matching month")

# Mainly used by glog
def letter_to_severity(letter: str, default: Optional[LogLevel] = None) -> Optional[LogLevel]:
	severities = {
		"F": LogLevel.EMERG,
		"E": LogLevel.ERR,
		"W": LogLevel.WARNING,
		"N": LogLevel.NOTICE,
		"C": LogLevel.NOTICE,	# Used by jupyter for the login token
		"I": LogLevel.INFO,
		"D": LogLevel.DEBUG,
	}

	return severities.get(letter, default)

# Used by Kiali; anything else?
def str_3letter_to_severity(string: str, default: Optional[LogLevel] = None) -> Optional[LogLevel]:
	severities = {
		"ERR": LogLevel.ERR,
		"WRN": LogLevel.WARNING,
		"INF": LogLevel.INFO,
	}
	return severities.get(string.upper(), default)

def str_4letter_to_severity(string: str, default: Optional[LogLevel] = None) -> Optional[LogLevel]:
	severities = {
		"CRIT": LogLevel.CRIT,
		"FATA": LogLevel.CRIT,
		"ERRO": LogLevel.ERR,
		"WARN": LogLevel.WARNING,
		"NOTI": LogLevel.NOTICE,
		"INFO": LogLevel.INFO,
		"DEBU": LogLevel.DEBUG,
	}
	return severities.get(string.upper(), default)

def str_to_severity(string: str, default: Optional[LogLevel] = None) -> Optional[LogLevel]:
	severities = {
		"fatal": LogLevel.CRIT,
		"error": LogLevel.ERR,
		"eror": LogLevel.ERR,
		"warning": LogLevel.WARNING,
		"warn": LogLevel.WARNING,
		"notice": LogLevel.NOTICE,
		"noti": LogLevel.NOTICE,
		"info": LogLevel.INFO,
		"debug": LogLevel.DEBUG,
		"debu": LogLevel.DEBUG,
	}

	return severities.get(string.lower(), default)

def lvl_to_letter_severity(lvl: LogLevel) -> str:
	severities = {
		LogLevel.CRIT: "C",
		LogLevel.ERR: "E",
		LogLevel.WARNING: "W",
		LogLevel.NOTICE: "N",
		LogLevel.INFO: "I",
		LogLevel.DEBUG: "D",
	}

	return severities.get(lvl, "!ERROR IN LOGPARSER!")

def lvl_to_4letter_severity(lvl: LogLevel) -> str:
	severities = {
		LogLevel.CRIT: "CRIT",
		LogLevel.ERR: "ERRO",
		LogLevel.WARNING: "WARN",
		LogLevel.NOTICE: "NOTI",
		LogLevel.INFO: "INFO",
		LogLevel.DEBUG: "DEBU",
	}

	return severities.get(lvl, "!ERROR IN LOGPARSER!")

def lvl_to_word_severity(lvl: LogLevel) -> str:
	severities = {
		LogLevel.CRIT: "CRITICAL",
		LogLevel.ERR: "ERROR",
		LogLevel.WARNING: "WARNING",
		LogLevel.NOTICE: "NOTICE",
		LogLevel.INFO: "INFO",
		LogLevel.DEBUG: "DEBUG",
	}

	return severities.get(lvl, "!ERROR IN LOGPARSER!")

def split_bracketed_severity(message: str, default: LogLevel = LogLevel.INFO) -> Tuple[str, LogLevel]:
	severities = {
		"[fatal]": LogLevel.CRIT,
		# This is for ingress-nginx; while alert is higher than crit in syslog terms,
                # ingress-nginx doesn't seem to use it that way.
		"[alert]": LogLevel.ERR,
		"[error]": LogLevel.ERR,
		"[err]": LogLevel.ERR,
		"[warning]": LogLevel.WARNING,
		"[warn]": LogLevel.WARNING,
		"[notice]": LogLevel.NOTICE,
		"[info]": LogLevel.INFO,
		"[system]": LogLevel.INFO,	# MySQL seems to have its own loglevels
		"[note]": LogLevel.INFO,	# none of which makes every much sense
		"[debug]": LogLevel.DEBUG,
	}

	# Safe
	tmp = re.match(r"^(\[[A-Za-z]+?\]) ?(.*)", message)
	if tmp is not None:
		severity = severities.get(tmp[1].lower())
		if severity is not None:
			message = tmp[2]
		else:
			severity = default
	else:
		severity = default

	return message, severity

def split_colon_severity(message: str, severity: LogLevel = LogLevel.INFO) -> Tuple[str, LogLevel]:
	severities = {
		"CRITICAL:": LogLevel.CRIT,
		"ERROR:": LogLevel.ERR,
		"WARNING:": LogLevel.WARNING,
		"NOTICE:": LogLevel.NOTICE,
		"NOTE:": LogLevel.NOTICE,
		"INFO:": LogLevel.INFO,
		"DEBUG:": LogLevel.DEBUG,
	}

	# Safe
	tmp = re.match(r"^([A-Za-z]+?:) ?(.*)", message)
	if tmp is not None:
		_severity = severities.get(tmp[1].upper())
		if _severity is not None:
			message = tmp[2]
			severity = _severity

	return message, severity

# Will split timestamp from messages that begin with timestamps of the form:
# 2020-02-07T13:12:24.224Z (Z = UTC)
# 2020-02-13T12:06:18.011345 [+-]0000 (+/-timezone)
# 2020-09-23T17:12:32.18396709[+-]03:00
# 2020-02-13T12:06:18[+-]0000 (+/-timezone)
# 2020-02-20 13:47:41,008 (assume UTC)
# 2020-02-20 13:47:41.008416 (assume UTC)
# 2020-02-20 13:47:41.008416Z (Z = UTC)
# 2020-02-20 13:47:41 (assume UTC)
# Technically not in ISO-8601/RFC 3339 format, but close enough;
# at least the order is sensible
# 2020/02/20 13:47:41.008416 (assume UTC)
# 2020/02/20 13:47:41 (assume UTC)
#
# XXX: According to ISO-8601 timestamps that lack timezone should be assumed to be local timezone,
#      NOT UTC. Does this make a difference though? Are these timestamps actually used anywhere?
def split_iso_timestamp(message: str, timestamp: datetime) -> Tuple[str, datetime]:
	old_timestamp = timestamp
	tmp_timestamp = ""

	while True:
		# 2020-02-07 13:12:24.224
		# 2020-02-07 13:12:24,224
		# [2020-02-07 13:12:24.224]
		# [2020-02-07 13:12:24,224]
		# Safe
		tmp = re.match(r"^\[?(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d)(,|\.)(\d+)\]? ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp == "":
				ymd = tmp[1]
				hms = tmp[2]
				_sep = tmp[3]
				ms = tmp[4]
				tmp_timestamp = f"{ymd} {hms}.{ms}+0000"
			message = tmp[5]
			break

		# 2020-02-07T13:12:24.224Z (Z = UTC)
		# Safe
		tmp = re.match(r"^(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d\.\d+)Z ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp == "":
				ymd = tmp[1]
				hmsms = tmp[2][0:len("HH:MM:SS.sss")]
				tmp_timestamp = f"{ymd} {hmsms}+0000"
			message = tmp[3]
			break

		# 2020-02-13T12:06:18.011345 [+-]00:00 (+timezone)
		# 2020-09-23T17:12:32.183967091[+-]03:00
		# Safe
		tmp = re.match(r"^(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d\.\d+) ?([\+-])(\d\d):(\d\d) ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp == "":
				ymd = tmp[1]
				hmsms = tmp[2][0:len("HH:MM:SS.sss")]
				tzsign = tmp[3]
				tzhour = tmp[4]
				tzmin = tmp[5]
				tmp_timestamp = f"{ymd} {hmsms}{tzsign}{tzhour}{tzmin}"
			message = tmp[6]
			break

		# 2020-02-13 12:06:18[+-]00:00 (+timezone)
		# [2020-02-13 12:06:18 [+-]00:00] (+timezone)
		# 2020-02-13T12:06:18[+-]0000 (+timezone)
		# Safe
		tmp = re.match(r"^\[?(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d:\d\d) ?([\+-])(\d\d):?(\d\d)\]? ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp == "":
				ymd = tmp[1]
				hms = tmp[2]
				tzsign = tmp[3]
				tzhour = tmp[4]
				tzmin = tmp[5]
				tmp_timestamp = f"{ymd} {hms}.000{tzsign}{tzhour}{tzmin}"
			message = tmp[6]
			break

		# 2020-02-20 13:47:41.008416 (assume UTC)
		# 2020-02-20 13:47:41.008416: (assume UTC)
		# 2020/02/20 13:47:41.008416 (assume UTC)
		# 2020-02-20 13:47:41.008416Z (Z = UTC)
		# Safe
		tmp = re.match(r"^(\d{4})[-/](\d\d)[-/](\d\d) (\d\d:\d\d:\d\d\.\d+)[Z:]? ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp == "":
				year = tmp[1]
				month = tmp[2]
				day = tmp[3]
				hmsms = tmp[4][0:len("HH:MM:SS.sss")]
				tmp_timestamp = f"{year}-{month}-{day} {hmsms}+0000"
			message = tmp[5]
			break

		# [2021-12-18T20:15:36Z]
		# 2021-12-18T20:15:36Z
		# Safe
		tmp = re.match(r"^\[?(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d)Z\]? ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp == "":
				ymd = tmp[1]
				hms = tmp[2]
				tmp_timestamp = f"{ymd} {hms}.000+0000"
			message = tmp[3]
			break


		# 2020-02-20 13:47:41 (assume UTC)
		# 2020/02/20 13:47:41 (assume UTC)
		# Safe
		tmp = re.match(r"^(\d{4})[-/](\d\d)[-/](\d\d) (\d\d:\d\d:\d\d) ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp == "":
				year = tmp[1]
				month = tmp[2]
				day = tmp[3]
				hms = tmp[4]
				tmp_timestamp = f"{year}-{month}-{day} {hms}.000+0000"
			message = tmp[5]
			break

		break

	if old_timestamp == none_timestamp() and len(tmp_timestamp) > 0:
		timestamp = datetime.strptime(tmp_timestamp, "%Y-%m-%d %H:%M:%S.%f%z")

	# message + either a timestamp or none_timestamp() is passed in, so it is safe just to return it too
	return message, timestamp

def strip_iso_timestamp(message: str) -> str:
	"""
	Given a string with a timestamp, return that string without the timestamp

		Parameters:
			message (str): The message to strip
		Returns:
			stripped_message (str): The stripped message
	"""

	message, _timestamp = split_iso_timestamp(message, none_timestamp())
	return message

# 2020-02-20 13:47:01.531 GMT
def strip_iso_timestamp_with_tz(message: str) -> str:
	"""
	Given a string with a timestamp and timezone, return that string without the timestamp

		Parameters:
			message (str): The message to strip
		Returns:
			stripped_message (str): The stripped message
	"""

	# Safe
	tmp = re.match(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d [A-Z]{3}(\s+?|$)(.*)", message)
	if tmp is not None:
		message = tmp[2]
	return message

# pylint: disable-next=too-many-arguments,unused-argument
def iptables(message: str, remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]],
	     severity: Optional[LogLevel] = LogLevel.INFO, facility: str = "", fold_msg: bool = True) ->\
			Tuple[Sequence[Union[ThemeRef, ThemeString]], LogLevel, str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	"""
	Format output from iptables-save

		Parameters:
			message (str): The message part of the msg to format
			remnants (list[(themearray, severity)]): The remnants part of the msg to format
			severity (LogLevel): The log severity
			facility (str): The log facility
			fold_msg (bool): Should the message be expanded or folded?
			options (dict): Additional, rule specific, options
		Returns:
	"""

	new_message: List[Union[ThemeRef, ThemeString]] = []
	new_remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []

	old_messages: List[str] = []
	if fold_msg and "\\n" in message:
		old_messages = message.split("\\n")
	else:
		old_messages.append(message)

		for themearray, _loglevel in remnants:
			old_messages.append(themearray_to_string(themearray))

	for i, items in enumerate(old_messages):
		tmp_message: List[Union[ThemeRef, ThemeString]] = []
		for j, item in enumerate(items.split(" ")):
			if j == 0:
				if item.startswith("/sbin/iptables"):
					tmp_message.append(ThemeString(item, ThemeAttr("types", "iptables_programname")))
				elif item.startswith("*"):
					tmp_message.append(ThemeString(item, ThemeAttr("types", "iptables_table")))
				elif item.startswith(":"):
					tmp_message.append(ThemeString(item, ThemeAttr("types", "iptables_chain")))
				elif item.startswith("COMMIT"):
					tmp_message.append(ThemeString(item, ThemeAttr("types", "iptables_command")))
				elif item.startswith("#"):
					tmp_message.append(ThemeString(items[j:], ThemeAttr("types", "iptables_comment")))
					break
			elif item.startswith("-"):
				tmp_message.append(ThemeString(f" {item}", ThemeAttr("types", "iptables_option")))
			elif item.startswith("#"):
				tmp_message.append(ThemeString(" ", ThemeAttr("types", "iptables_comment")))
				tmp_message.append(ThemeString(" ".join(item[j:]), ThemeAttr("types", "iptables_comment")))
				break
			else:
				tmp_message.append(ThemeString(f" {item}", ThemeAttr("types", "iptables_argument")))

		if i == 0:
			new_message = tmp_message
		else:
			new_remnants.append((tmp_message, severity))

	if fold_msg and "\\n" in message:
		for remnant, _severity in new_remnants:
			new_message.append(ThemeRef("separators", "newline"))
			new_message += remnant

		new_remnants = []
	return new_message, severity, facility, new_remnants

# http:
# ::ffff:10.217.0.1 - - [06/May/2022 18:50:45] "GET / HTTP/1.1" 200 -
# 10.244.0.1 - - [29/Jan/2022:10:34:20 +0000] "GET /v0/healthz HTTP/1.1" 301 178 "-" "kube-probe/1.23"
# 10.244.0.1 - - [29/Jan/2022:10:33:50 +0000] "GET /v0/healthz/ HTTP/1.1" 200 3 "http://10.244.0.123:8000/v0/healthz" "kube-probe/1.23"
# 10.32.0.1 - - [20/Mar/2023:11:38:13 +0000] "GET /api/v1/series?match%5B%5D=collectd_gpu_sysman_frequency_mhz&start=1679311983&end=1679312283 HTTP/1.1" 200 528 "-" "Grafana/8.3.10" 368 0.002 [monitoring-prometheus-k8s-9090] [] 10.40.0.30:9090 528 0.004 200 5997e385f9f1e248446d28a810c4
# [2022-12-17T21:59:10.447Z] "GET /ready HTTP/1.1" 200 - 0 5 0 - "-" "kube-probe/1.25" "0823108e-89da-41f6-9663-ff0e7003f098" "internalkourier" "-""
# pylint: disable-next=unused-argument
def http(message: str, severity: Optional[LogLevel] = LogLevel.INFO, facility: str = "", fold_msg: bool = True, options: Optional[Dict] = None) ->\
			Tuple[Sequence[Union[ThemeRef, ThemeString]], LogLevel, str]:
	"""
	Format various http log style messages

		Parameters:
			message (str): The message to format
			severity (LogLevel): The log severity
			facility (str): The log facility
			fold_msg (bool): Unused
			options (dict): Additional, rule specific, options
		Returns:
	"""

	reformat_timestamps = deep_get(options, DictPath("reformat_timestamps"), False)

	ipaddress = ""

	# If the message starts with a timestamp without a leading IP-address, skip this
	if not message.startswith("["):
		# First try to check if it's an IP-address
		# Safe
		tmp = re.match(r"^([a-f0-9:][a-f0-9:.]+[a-f0-9])( - - .*)", message)
		if tmp is not None:
			if validators.ipv4(tmp[1]) or validators.ipv6(tmp[1]):
				ipaddress = tmp[1]
				message = tmp[2]

	# Short format
	if len(ipaddress) > 0:
		# Safe
		tmp = re.match(r"( - - )"
			       r"(\[)"
			       r"(\d\d)"
			       r"/"
			       r"([A-Z][a-z][a-z])"
			       r"/"
			       r"(\d{4})"
			       r" "
			       r"(\d\d:\d\d:\d\d)"
			       r"(\])"
			       r"(\s\")"
			       r"([A-Z]*?\s)"
			       r"(\S*?)"
			       r"(\s\S*?)"
			       r"(\"\s)"
			       r"(\d+?)"
			       r"(\s+[\d-]+?$)", message)

		if tmp is not None:
			address1 = ipaddress
			separator1 = tmp[1]
			separator2 = tmp[2]
			day = tmp[3]
			_month = tmp[4]
			month = month_to_numerical(_month)
			year = tmp[5]
			hms = tmp[6]
			if reformat_timestamps == True:
				ts = f"{year}-{month}-{day} {hms}"
			else:
				ts = f"{day}/{_month}/{year}:{hms}"
			separator3 = tmp[7]
			separator4 = tmp[8]
			verb = tmp[9]
			address3 = tmp[10]
			protocol = tmp[11]
			separator5 = tmp[12]
			statuscode = tmp[13]
			_statuscode = int(statuscode)
			if 100 <= _statuscode < 300:
				severity = LogLevel.NOTICE
			elif 300 <= _statuscode < 400:
				severity = LogLevel.WARNING
			else:
				severity = LogLevel.ERR
			separator6 = tmp[14]
			new_message: Sequence[Union[ThemeRef, ThemeString]] = [
				ThemeString(address1, ThemeAttr("logview", "hostname")),
				ThemeString(separator1, ThemeAttr("logview", "severity_info")),
				ThemeString(f"{separator2}{ts}{separator3}", ThemeAttr("logview", "timestamp")),
				ThemeString(separator4, ThemeAttr("logview", "severity_info")),
				ThemeString(verb, ThemeAttr("logview", "protocol")),
				ThemeString(address3, ThemeAttr("logview", "url")),
				ThemeString(protocol, ThemeAttr("logview", "protocol")),
				ThemeString(separator5, ThemeAttr("logview", "severity_info")),
				ThemeString(statuscode, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")),
				ThemeString(separator6, ThemeAttr("logview", "severity_info")),
			]

			return new_message, severity, facility

	if len(ipaddress) > 0:
		# Safe
		tmp = re.match(r"( - - )"
			       r"(\[)"
			       r"(\d\d)"
			       r"/"
			       r"([A-Z][a-z][a-z])"
			       r"/"
			       r"(\d{4})"
			       r":"
			       r"(\d\d:\d\d:\d\d)"
			       r"(\s\+\d{4}|\s-\d{4})"
			       r"(\])"
			       r"(\s\")"
			       r"([A-Z]*?\s)"
			       r"(\S*?)"
			       r"(\s\S*?)"
			       r"(\"\s)"
			       r"(\d+?)"
			       r"(\s+\d+?\s\")"
			       r"([^\"]*)"
			       r"(\")"
			       r"(\s|$)"
			       r"(\"|.*$)"
			       r"([^\"]*|$)"
			       r"(\"|$)"
			       r"(\s.*$|$)", message)

		if tmp is not None:
			address1 = ipaddress
			separator1 = tmp[1]
			separator2 = tmp[2]
			day = tmp[3]
			_month = tmp[4]
			month = month_to_numerical(_month)
			year = tmp[5]
			hms = tmp[6]
			tz = tmp[7]
			if reformat_timestamps == True:
				ts = f"{year}-{month}-{day} {hms}{tz}"
			else:
				ts = f"{day}/{_month}/{year}:{hms}{tz}"
			separator3 = tmp[8]
			separator4 = tmp[9]
			verb = tmp[10]
			address3 = tmp[11]
			protocol = tmp[12]
			separator5 = tmp[13]
			statuscode = tmp[14]
			_statuscode = int(statuscode)
			if 100 <= _statuscode < 300:
				severity = LogLevel.NOTICE
			elif 300 <= _statuscode < 400:
				severity = LogLevel.WARNING
			else:
				severity = LogLevel.ERR
			separator6 = tmp[15]
			address4 = tmp[16]
			separator7 = tmp[17] + tmp[18] + tmp[19]
			address5 = tmp[20]
			separator8 = tmp[21]
			remainder = tmp[22]

			new_message = [
				ThemeString(address1, ThemeAttr("logview", "hostname")),
				ThemeString(separator1, ThemeAttr("logview", "severity_info")),
				ThemeString(f"{separator2}{ts}{separator3}", ThemeAttr("logview", "timestamp")),
				ThemeString(separator4, ThemeAttr("logview", "severity_info")),
				ThemeString(verb, ThemeAttr("logview", "protocol")),
				ThemeString(address3, ThemeAttr("logview", "url")),
				ThemeString(protocol, ThemeAttr("logview", "protocol")),
				ThemeString(separator5, ThemeAttr("logview", "severity_info")),
				ThemeString(statuscode, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")),
				ThemeString(separator6, ThemeAttr("logview", "severity_info")),
				ThemeString(address4, ThemeAttr("logview", "url")),
				ThemeString(separator7, ThemeAttr("logview", "severity_info")),
			]
			if address5 is not None:
				new_message.append(ThemeString(address5, ThemeAttr("logview", "url")))
				new_message.append(ThemeString(separator8, ThemeAttr("logview", "severity_info")))
			if remainder is not None:
				new_message.append(ThemeString(remainder, ThemeAttr("types", "generic")))

			return new_message, severity, facility

	# Alternate formats
	# DoS
	tmp = re.match(r"^\|\s+(\d{3})\s+\|\s+([0-9.]+)([^ ]*)\s+\|\s+([^:]*):(\d+?)\s+\|\s+([A-Z]+)\s+(.*)", message)

	if tmp is not None:
		statuscode = tmp[1]
		_statuscode = int(statuscode)
		if 100 <= _statuscode < 300:
			severity = LogLevel.NOTICE
		elif 300 <= _statuscode < 400:
			severity = LogLevel.WARNING
		else:
			severity = LogLevel.ERR
		duration = tmp[2]
		unit = tmp[3]
		hostname = tmp[4]
		port = tmp[5]
		verb = tmp[6]
		url = tmp[7]
		new_message = [
			ThemeString("| ", ThemeAttr("logview", "severity_info")),
			ThemeString(statuscode, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")),
			ThemeString(" | ", ThemeAttr("logview", "severity_info")),
			ThemeString(duration, ThemeAttr("logview", "severity_info")),
			ThemeString(unit, ThemeAttr("types", "unit")),
			ThemeString(" | ", ThemeAttr("logview", "severity_info")),
			ThemeString(hostname, ThemeAttr("logview", "hostname")),
			ThemeRef("separators", "port"),
			ThemeString(port, ThemeAttr("types", "port")),
			ThemeString(" | ", ThemeAttr("logview", "severity_info")),
			ThemeString(verb, ThemeAttr("logview", "protocol")),
			ThemeString(" ", ThemeAttr("logview", "severity_info")),
			ThemeString(url, ThemeAttr("logview", "url")),
		]
		return new_message, severity, facility

	tmp = re.match(r"^\["
		       r"(\d{4}-\d\d-\d\d)"
		       r"T"
		       r"(\d\d:\d\d:\d\d\.\d\d\d)Z"
		       r"\] \""
		       r"([A-Z]+)"
		       r"\s"
		       r"([^\s]+)"
		       r"\s"
		       r"([^\"]+)"
		       r"\" "
		       r"([\d]+)"
		       r" ([^\s]+)"
		       r" ([^\s]+)"
		       r" ([^\s]+)"
		       r" ([^\s]+)"
		       r" ([^\s]+) "
		       r"\"([^\"]+)\" "
		       r"\"([^\"]+)\" "
		       r"\"([^\"]+)\" "
		       r"\"([^\"]+)\" "
		       r"\"([^\"]+)\"", message)

	if tmp is not None:
		date = tmp[1]
		hmsms = tmp[2]

		if reformat_timestamps == True:
			ts = f"{date} {hmsms} +0000"
		else:
			ts = f"{date}T{hmsms}Z"

		verb = tmp[3]
		address1 = tmp[4]
		protocol = tmp[5]
		statuscode = tmp[6]
		_statuscode = int(statuscode)
		if 100 <= _statuscode < 300:
			severity = LogLevel.NOTICE
		elif 300 <= _statuscode < 400:
			severity = LogLevel.WARNING
		else:
			severity = LogLevel.ERR
		number0 = tmp[7]
		number1 = tmp[8]
		number2 = tmp[9]
		number3 = tmp[10]
		number4 = tmp[11]
		client = tmp[12]
		str0 = tmp[13]
		str1 = tmp[14]
		str2 = tmp[15]
		str3 = tmp[16]

		new_message = [
			ThemeString(f"[{ts}] ", ThemeAttr("logview", "timestamp")),
			ThemeString("\"", ThemeAttr("logview", "severity_info")),
			ThemeString(f"{verb} ", ThemeAttr("logview", "protocol")),
			ThemeString(address1, ThemeAttr("logview", "url")),
			ThemeString(f" {protocol}", ThemeAttr("logview", "protocol")),
			ThemeString("\" ", ThemeAttr("logview", "severity_info")),
			ThemeString(statuscode, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")),
			ThemeString(f" {number0}", ThemeAttr("logview", "severity_info")),
			ThemeString(f" {number1}", ThemeAttr("logview", "severity_info")),
			ThemeString(f" {number2}", ThemeAttr("logview", "severity_info")),
			ThemeString(f" {number3}", ThemeAttr("logview", "severity_info")),
			ThemeString(f" {number4} \"", ThemeAttr("logview", "severity_info")),
			ThemeString(f"{client}", ThemeAttr("logview", "url")),
			ThemeString("\" \"", ThemeAttr("logview", "severity_info")),
			ThemeString(str0, ThemeAttr("logview", "url")),
			ThemeString("\" \"", ThemeAttr("logview", "severity_info")),
			ThemeString(str1, ThemeAttr("logview", "url")),
			ThemeString("\" \"", ThemeAttr("logview", "severity_info")),
			ThemeString(str2, ThemeAttr("logview", "url")),
			ThemeString("\" \"", ThemeAttr("logview", "severity_info")),
			ThemeString(str3, ThemeAttr("logview", "url")),
			ThemeString("\"", ThemeAttr("logview", "severity_info")),
		]
		return new_message, severity, facility

	if severity is None:
		severity = LogLevel.INFO
	return [ThemeString(f"{ipaddress}", ThemeAttr("logview", "hostname")), ThemeString(f"{message}", ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity, facility

# log messages of the format:
# E0514 09:01:55.108028382       1 server_chttp2.cc:40]
# I0511 14:31:10.500543       1 start.go:76]
# XXX: Messages like these have been observed;
# I0417 09:32:43.32022-04-17T09:32:43.343052189Z 41605       1 tlsconfig.go:178]
# they indicate a race condition; hack around them to make the log pretty
def split_glog(message: str, severity: Optional[LogLevel] = None, facility: str = "") ->\
			Tuple[str, LogLevel, str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]], bool]:
	"""
	Extract messages in glog format

		Parameters:
			message (str): The message to reformat
			severity (LogLevel): The current loglevel
			facility (str): The current facility
		Returns:
			(message, severity, facility, remnants, matched)
	"""

	matched = False
	loggingerror = None
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []

	# Workaround a bug in use of glog; to make the logged message useful
	# we separate it from the warning about glog use; this way we can get the proper severity
	if message.startswith("ERROR: logging before flag.Parse: "):
		loggingerror = message[0:len("ERROR: logging before flag.Parse")]
		message = message[len("ERROR: logging before flag.Parse: "):]

	# Safe
	tmp = re.match(r"^([A-Z]\d{4} \d\d:\d\d:\d\d\.\d)\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{9}Z (.*)", message)
	if tmp is not None:
		message = f"{tmp[1]}{tmp[2]}"

	# Safe
	tmp = re.match(r"^([A-Z])\d\d\d\d \d\d:\d\d:\d\d\.\d+\s+(\d+)\s(.+?:\d+)\](.*)", message)
	if tmp is not None:
		severity = letter_to_severity(tmp[1])

		# We do not use PID, but it is assigned here just to document the meaning of the field
		_pid = tmp[2]

		facility = f"{(tmp[3])}"
		message = f"{(tmp[4])}"
		# The first character is always whitespace unless this is an empty line
		if len(message) > 0:
			message = message[1:]
		matched = True
	else:
		if severity is None:
			severity = LogLevel.INFO

	# If we have a logging error we return that as message and the rest as remnants
	if loggingerror is not None:
		severity = LogLevel.ERR
		remnants.insert(0, ([ThemeString(message, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity))
		message = loggingerror

	return message, severity, facility, remnants, matched

# 2022-12-13T22:23:45.808Z\tINFO\tcontroller-runtime.metrics\tMetrics server is starting to listen\t{"addr": ":8080"}
# 2022-12-13T22:23:45.808Z\tINFO\tsetup\tstarting manager
# 1.677757754464991e+09\tINFO\tcontroller-runtime.metrics\tMetrics server is starting to listen\t{"addr": ":8080"}
# Assumption: datetime\tSEVERITY\t{facility if lowercase, else message}[\tjson]
# or
#             secondssinceepoch\tSEVERITY\t{facility if lowercase, else message}[\tjson]
def tab_separated(message: str, severity: Optional[LogLevel] = LogLevel.INFO, facility: str = "", fold_msg: bool = True) ->\
				Tuple[str, Optional[LogLevel], str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	"""
	Extract messages of the format datetime\tSEVERITY\t[facility\t]message[\tjson]

		Parameters:
			message (str): The message to reformat
			severity (LogLevel): The current loglevel
			facility (str): The current facility
			fold_msg (bool): Should the message be expanded or folded?
		Returns:
			(message, severity, facility, remnants)
	"""

	remnants = []

	fields = message.split("\t")
	# If the first field is not a timestamp we cannot trust the rest of the message to be what we hope for
	if len(fields) < 4 or len(fields[0]) != 24 and not fields[0].endswith("e+09"):
		return message, severity, facility, remnants

	severity = str_to_severity(fields[1], severity)
	message_index = 2
	if fields[2][0].islower():
		facility = fields[2]
		message_index += 1

	message = fields[message_index]
	remnants_index = message_index + 1

	if not fold_msg and remnants_index < len(fields) and fields[remnants_index].startswith("{") and fields[remnants_index].endswith("}"):
		try:
			d = json.loads(fields[remnants_index])
			json_strs = json_dumps(d)
			for remnant in formatters.format_yaml(json_strs):
				remnants.append((remnant, severity))
		except DecodeException:
			message = " ".join(fields[message_index:])
	else:
		message = " ".join(fields[message_index:])

	return message, severity, facility, remnants

# \tINFO\tcontrollers.Reaper\tstarting reconciliation\t{"reaper": "default/k8ssandra-cluster-a-reaper-k8ssandra"}
def __split_severity_facility_style(message: str, severity: Optional[LogLevel] = LogLevel.INFO, facility: str = "") -> Tuple[str, Optional[LogLevel], str]:
	# Safe
	tmp = re.match(r"^\s*([A-Z]+)\s+([a-zA-Z-\.]+)\s+(.*)", message)
	if tmp is not None:
		severity = str_to_severity(tmp[1], default = severity)
		facility = tmp[2]
		message = tmp[3]

	return message, severity, facility

def split_json_style(message: str, severity: Optional[LogLevel] = LogLevel.INFO, facility: str = "", fold_msg: bool = True, options: Optional[Dict] = None) ->\
				Tuple[Union[str, Sequence[Union[ThemeRef, ThemeString]]], LogLevel, str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	logentry = None

	messages = deep_get(options, DictPath("messages"), ["msg", "message"])
	errors = deep_get(options, DictPath("errors"), ["err", "error"])
	error_tags = deep_get(options, DictPath("error_tags"), {})
	timestamps = deep_get(options, DictPath("timestamps"), ["ts", "time", "timestamp"])
	severities = deep_get(options, DictPath("severities"), ["level"])
	msg_severity_overrides = deep_get(options, DictPath("msg#severity#overrides"), [])
	facilities = deep_get(options, DictPath("facilities"), ["logger", "caller", "filename"])
	versions = deep_get(options, DictPath("versions"), [])

	message = message.replace("\x00", "")

	try:
		logentry = json.loads(message)
	except DecodeException:
		pass

	# Unfold Python dicts
	if logentry is None:
		d = None
		try:
			d = ast.literal_eval(message)
		except (ValueError, TypeError, SyntaxError, RecursionError):
			pass

		if d is not None:
			try:
				logentry = json_dumps(d)
			except ValueError:
				pass

	if logentry is not None and isinstance(logentry, dict):
		# If msg_first we reorder the dict
		if logparser_configuration.msg_first == True:
			_d = {}
			for key in messages + errors:
				value = logentry.get(key, None)
				if value is not None:
					_d[key] = value
			for key in logentry:
				if key not in messages + errors:
					value = logentry.get(key, "")
					if value is not None:
						_d[key] = value
			logentry = _d

		msg = deep_get_with_fallback(logentry, messages, "")
		level = deep_get_with_fallback(logentry, severities, None)
		if logparser_configuration.pop_severity == True:
			for _sev in severities:
				logentry.pop(_sev, None)
		if logparser_configuration.pop_ts == True:
			for _ts in timestamps:
				logentry.pop(_ts, None)

		if facility == "":
			for _fac in facilities:
				if isinstance(_fac, str):
					facility = deep_get(logentry, DictPath(_fac), "")
					break

				if isinstance(_fac, dict):
					_facilities = deep_get(_fac, DictPath("keys"), [])
					_separators = deep_get(_fac, DictPath("separators"), [])
					for i, _fac in enumerate(_facilities):
						# this is to allow prefixes/suffixes
						if _fac != "":
							if _fac not in logentry:
								break
							facility += str(deep_get(logentry, DictPath(_fac), ""))
						if i < len(_separators):
							facility += _separators[i]

		if logparser_configuration.pop_facility == True:
			for _fac in facilities:
				if isinstance(_fac, str):
					logentry.pop(_fac, None)
				elif isinstance(_fac, dict):
					# This is a list, since the order of the facilities matter when outputting
					# it does not matter when popping though
					for __fac in deep_get(_fac, DictPath("keys"), []):
						if __fac == "":
							continue

						logentry.pop(__fac, None)

		if level is not None:
			severity = cast(LogLevel, str_to_severity(level))

		# If the message is folded, append the rest
		if fold_msg:
			if severity is not None:
				msgseverity = severity
			else:
				msgseverity = LogLevel.INFO
			# Append all remaining fields to message
			if msg == "":
				message = str(logentry)
			else:
				if logparser_configuration.msg_extract == True:
					# pop the first matching _msg
					for _msg in messages:
						if _msg in logentry:
							logentry.pop(_msg, None)
							break
					if len(logentry) > 0:
						message = f"{msg} {logentry}"
					else:
						message = msg
				else:
					message = str(logentry)
		# else return an expanded representation
		else:
			if severity is not None and severity == LogLevel.DEBUG:
				structseverity = severity
			else:
				structseverity = LogLevel.INFO

			if "err" not in logentry and "error" not in logentry:
				if severity is not None:
					msgseverity = severity
				else:
					msgseverity = LogLevel.INFO
			else:
				msgseverity = structseverity
			if severity is not None:
				errorseverity = severity
			else:
				errorseverity = LogLevel.ERR

			if logparser_configuration.msg_extract == True:
				message = msg
				# Pop the first matching _msg
				for _msg in messages:
					if _msg in logentry:
						logentry.pop(_msg, None)
						break
			else:
				message = ""

			override_formatting: Union[ThemeAttr, Dict] = {}
			formatted_message = None
			remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []

			if len(logentry) > 0:
				if structseverity == LogLevel.DEBUG:
					override_formatting = ThemeAttr("logview", "severity_debug")
				else:
					override_formatting = {}
					for _msg in versions:
						override_formatting[f"\"{_msg}\""] = {
							"key": ThemeAttr("types", "yaml_key"),
							"value": ThemeAttr("logview", "severity_notice")
						}
					for _msg in messages:
						override_formatting[f"\"{_msg}\""] = {
							"key": ThemeAttr("types", "yaml_key"),
							"value": ThemeAttr("logview", f"severity_{loglevel_to_name(msgseverity).lower()}")
						}
					for _err in errors:
						override_formatting[f"\"{_err}\""] = {
							"key": ThemeAttr("types", "yaml_key_error"),
							"value": ThemeAttr("logview", f"severity_{loglevel_to_name(errorseverity).lower()}"),
						}
					tagseverity = None
					for tag, tag_values in error_tags.items():
						for tag_key, tag_severity in tag_values.items():
							if tag_key in deep_get(logentry, DictPath(tag), []):
								tagseverity = str_to_severity(tag_severity, msgseverity)
								break
						if tagseverity is not None:
							break
				if tagseverity is not None:
					override_formatting[f"\"{_msg}\""] = {
						"key": ThemeAttr("types", "yaml_key"),
						"value": ThemeAttr("logview", f"severity_{loglevel_to_name(tagseverity).lower()}")
					}
					severity = tagseverity

				dump = json_dumps(logentry)
				tmp = formatters.format_yaml([dump], override_formatting = override_formatting)

				if len(message) == 0:
					formatted_message = tmp[0]
					tmp.pop(0)
					msgseverity = structseverity
				for line in tmp:
					remnants.append((line, severity))

			if formatted_message is not None:
				return formatted_message, severity, facility, remnants

			if isinstance(message, str):
				_message, severity = custom_override_severity(message, severity, msg_severity_overrides)
			return message, severity, facility, remnants

	return message, severity, facility, []

def merge_message(message: Union[str, List[Union[ThemeRef, ThemeString]]],
		  remnants: Optional[List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]] = None, severity: LogLevel = LogLevel.INFO) ->\
			Tuple[str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	"""
	Given message + remnants, merge the message into the remnants and return an empty message

		Parameters:
			message (str|themearray): The string to merge into remnants
			remnants (list[(themearray, LogLevel)]): The list of remnants
			severity (LogLevel): The severity for message
		Returns:
			(message, remnants):
				message (str): The newly emptied message
				remnants (list[(themearray, LogLevel)]): Remnants with message preprended
	"""

	# This is a ThemeArray
	if isinstance(message, List):
		if remnants is not None:
			remnants = [(message, severity)] + remnants
		else:
			remnants = message
	else:
		if remnants is not None:
			remnants.insert(0, ([ThemeString(message, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity))
		else:
			remnants = [([ThemeString(message, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity)]
	message = ""

	return message, remnants

# pylint: disable-next=too-many-arguments
def split_json_style_raw(message: str, severity: LogLevel = LogLevel.INFO, facility: str = "", fold_msg: bool = True, options: Optional[Dict] = None, merge_msg: bool = False) ->\
				Tuple[str, LogLevel, str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	# This warning seems incorrect
	# pylint: disable-next=global-variable-not-assigned
	global logparser_configuration

	tmp_msg_first = logparser_configuration.msg_first
	tmp_msg_extract = logparser_configuration.msg_extract
	tmp_pop_severity = logparser_configuration.pop_severity
	tmp_pop_ts = logparser_configuration.pop_ts
	tmp_pop_facility = logparser_configuration.pop_facility

	logparser_configuration.msg_first = False
	logparser_configuration.msg_extract = False
	logparser_configuration.pop_severity = False
	logparser_configuration.pop_ts = False
	logparser_configuration.pop_facility = False

	_message, _severity, _facility, _remnants = split_json_style(message = message, severity = severity, facility = facility, fold_msg = fold_msg, options = options)

	logparser_configuration.msg_first = tmp_msg_first
	logparser_configuration.msg_extract = tmp_msg_extract
	logparser_configuration.pop_severity = tmp_pop_severity
	logparser_configuration.pop_ts = tmp_pop_ts
	logparser_configuration.pop_facility = tmp_pop_facility

	if merge_msg == True:
		message, remnants = merge_message(message, _remnants, severity)
	else:
		remnants = _remnants

	if severity is None:
		severity = _severity
	if facility == "":
		facility = _facility

	return message, severity, facility, remnants

def json_event(message: str, severity: LogLevel = LogLevel.INFO, facility: str = "", fold_msg: bool = True, options: Optional[Dict] = None) ->\
			Tuple[Union[str, List[Union[ThemeRef, ThemeString]]], LogLevel, str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []
	tmp = message.split(" ", 2)

	if not message.startswith("EVENT ") or len(tmp) < 3:
		return message, severity, facility, remnants

	event = tmp[1]

	if event in ("AddPod", "DeletePod", "AddNamespace", "AddNetworkPolicy", "DeleteNamespace") or (event in ("UpdatePod", "UpdateNamespace") and not "} {" in tmp[2]):
		msg = tmp[2]
		_message, _severity, _facility, remnants = split_json_style_raw(message = msg, severity = severity, facility = facility, fold_msg = fold_msg, options = options, merge_msg = True)
		new_message = [ThemeString(f"{tmp[0]} {event}", ThemeAttr("logview", "severity_info"))]
		if event in ("UpdatePod", "UpdateNamespace"):
			new_message = [ThemeString(f"{tmp[0]} {event}", ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")),
				       ThemeString(" [No changes]", ThemeAttr("logview", "unchanged"))]
	elif event in ("UpdatePod", "UpdateNamespace"):
		# Safe
		tmp2 = re.match(r"^({.*})\s*({.*})", tmp[2])
		if tmp2 is not None:
			try:
				old = json.loads(tmp2[1])
			except DecodeException:
				new_message = [ThemeString(f"{tmp[1]} {event}", ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")),
					       ThemeString(" [error: could not parse json]", ThemeAttr("logview", "severity_error"))]
				remnants = [([ThemeString(tmp[2], ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity)]
				return new_message, severity, facility, remnants

			old_str = json_dumps(old)
			try:
				new = json.loads(tmp2[2])
			except DecodeException:
				new_message = [ThemeString(f"{tmp[0]} {event}", ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")),
					       ThemeString(" [error: could not parse json]", ThemeAttr("logview", "severity_error"))]
				remnants = [([ThemeString(tmp[2], ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity)]
				return new_message, severity, facility, remnants
			new_str = json_dumps(new)

			y = 0
			for el in difflib.unified_diff(old_str.split("\n"), new_str.split("\n"), n = sys.maxsize, lineterm = ""):
				y += 1
				if y < 4:
					continue
				if el.startswith("+"):
					remnants.append(([ThemeString(el, ThemeAttr("logview", "severity_diffplus"))], LogLevel.DIFFPLUS))
				elif el.startswith("-"):
					remnants.append(([ThemeString(el, ThemeAttr("logview", "severity_diffminus"))], LogLevel.DIFFMINUS))
				else:
					remnants.append(([ThemeString(el, ThemeAttr("logview", "severity_diffsame"))], LogLevel.DIFFSAME))
			new_message = [ThemeString(f"{tmp[0]} {event}", ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")),
				       ThemeString(" [State modified]", ThemeAttr("logview", "modified"))]
	else:
		CMTLog(CMTLogType.DEBUG, [
				[ANSIThemeString("Unknown EVENT type: ", "default"),
				 ANSIThemeString(f"{event}", "argument")],
		       ], severity = LogLevel.ERR, facility = "logparser.py:json_event()")
		return message, severity, facility, remnants

	return new_message, severity, facility, remnants

def split_angle_bracketed_facility(message: str, facility: str = "") -> Tuple[str, str]:
	# Safe
	tmp = re.match(r"^<(.+?)>\s?(.*)", message)
	if tmp is not None:
		facility = tmp[1]
		message = tmp[2]
	return message, facility

def split_colon_facility(message: str, facility: str = "") -> Tuple[str, str]:
	# Safe
	tmp = re.match(r"^(\S+?):\s?(.*)", message)
	if tmp is not None:
		facility = tmp[1]
		message = tmp[2]
	return message, facility

def strip_ansicodes(message: str) -> str:
	message = message.replace("\\x1b", "\x1b")
	# Safe
	tmp = re.findall(r"("
	                 r"\x1b\[\d+m|"
	                 r"\x1b\[\d+;\d+m|"
			 r"\x1b\[\d+;\d+;\d+m|"
			 r".*?)", message)
	if tmp is not None:
		message = "".join(item for item in tmp if not item.startswith("\x1b"))

	return message

def split_bracketed_timestamp_severity_facility(message: str, default: LogLevel = LogLevel.INFO) -> Tuple[str, LogLevel, str]:
	severity = default
	facility = ""

	# DoS
	tmp = re.match(r"\[(.*?) (.*?) (.*?)\]: (.*)", message)

	if tmp is not None:
		severity = str_to_severity(tmp[2])
		facility = tmp[3]
		message = tmp[4]

	return message, severity, facility

def custom_override_severity(message: Union[str, List], severity: Optional[LogLevel], overrides: Dict) -> Tuple[Union[str, List], LogLevel]:
	if not logparser_configuration.override_severity:
		return message, severity

	if isinstance(message, list):
		tmp_message = themearray_to_string(message)
	else:
		tmp_message = message
	override_message = message

	for override in overrides:
		override_type = deep_get(override, DictPath("matchtype"), "")
		override_pattern = deep_get(override, DictPath("matchkey"), "")
		override_loglevel = name_to_loglevel(deep_get(override, DictPath("loglevel"), ""))

		if override_type == "startswith":
			if not tmp_message.startswith(override_pattern):
				continue
		elif override_type == "endswith":
			if not tmp_message.endswith(override_pattern):
				continue
		elif override_type == "contains":
			if override_pattern not in tmp_message:
				continue
		elif override_type == "regex":
			tmp = override_pattern.match(tmp_message)
			if tmp is None:
				continue
		else:
			raise ValueError(f"Unknown override_type '{override_type}'; this is a programming error.")

		severity = override_loglevel

		if isinstance(message, list):
			override_message = []
			for substring in message:
				override_message.append(ThemeString(substring.string, ThemeAttr("logview", f"severity_{loglevel_to_name(override_loglevel).lower()}")))
		break

	return override_message, severity

def expand_event_objectmeta(message: str, severity: LogLevel, remnants: Optional[List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]] = None, fold_msg: bool = True) ->\
					Tuple[LogLevel, str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	# pylint: disable=unused-argument
	raw_message = message
	curlydepth = 0

	# This just makes sure that the indentation matches up
	for i in range(0, len(raw_message)):
		if message[i] == "{":
			curlydepth += 1
		elif message[i] == "}":
			curlydepth -= 1
			if curlydepth < 0:
				# Abort parsing; assume that this message is either malformed
				# or that the parser is flawed
				return severity, message, remnants

	message = None
	remnants = []
	indent = 2
	depth = 0
	escaped = False
	quoted = False # pylint: disable=unused-variable
	tmp = ""

	for i, raw_msg in enumerate(raw_message):
		if raw_msg == "\"" and escaped == False:
			quoted = True
		elif raw_msg == "\\":
			escaped = not escaped
		elif raw_msg in ("{", ",", "}"):
			if raw_msg != "}":
				tmp += raw_msg
			else:
				if tmp == "":
					tmp += raw_msg
					depth -= 1
					if i < len(raw_msg) - 1:
						continue

			# OK, this is not an escaped curly brace or comma,
			# so it is time to flush the buffer
			if message is None:
				if ":" in tmp:
					key, value = tmp.split(":", 1)
					message = [ThemeString("".ljust(indent * depth) + key, ThemeAttr("types", "yaml_key")),
						   ThemeRef("separators", "yaml_key_separator"),
						   ThemeString(f"{value}", ThemeAttr("types", "yaml_value"))]
				else:
					message = [ThemeString("".ljust(indent * depth) + tmp, ThemeAttr("types", "yaml_value"))]
			else:
				if ":" in tmp:
					key, value = tmp.split(":", 1)
					remnants.append(([ThemeString("".ljust(indent * depth) + key, ThemeAttr("types", "yaml_key")),
							  ThemeRef("separators", "yaml_key_separator"),
							  ThemeString(f"{value}", ThemeAttr("types", "yaml_value"))], severity))
				else:
					remnants.append(([ThemeString("".ljust(indent * depth) + tmp, ThemeAttr("types", "yaml_value"))], severity))
			tmp = ""
			if raw_msg == "{":
				depth += 1
			elif raw_msg == "}":
				tmp += raw_msg
				depth -= 1
			continue
		tmp += raw_msg
	return severity, message, remnants

def expand_event(message: str, severity: LogLevel, remnants: Optional[List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]] = None, fold_msg: bool = True) ->\
			Tuple[LogLevel, str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	if fold_msg or (remnants is not None and len(remnants) > 0):
		return severity, message, remnants

	raw_message = message
	parendepth = 0
	curlydepth = 0
	eventstart = None
	eventend = None
	refstart = None
	refend = None

	for i in range(0, len(raw_message)):
		if message[i] == "(":
			parendepth += 1
			if eventstart is None:
				eventstart = i + 1
		elif message[i] == "{":
			curlydepth += 1
			if refstart is None:
				refstart = i + 1
		elif message[i] == "}":
			curlydepth -= 1
			if curlydepth < 0:
				# Abort parsing; assume that this message is either malformed
				# or that the parser is flawed
				return message, remnants
			refend = i
		elif message[i] == ")":
			parendepth -= 1
			if parendepth == 0:
				if curlydepth > 0:
					# Abort parsing; assume that this message is either malformed
					# or that the parser is flawed
					return message, remnants

				eventend = i
				break

	remnants = []
	message = raw_message[0:eventstart]
	indent = 2
	# Try to extract an embedded severity; use it if higher than severity
	# DoS
	tmp = re.match(r".*type: '([A-Z][a-z]+)' reason:.*", raw_message)
	if tmp is not None:
		if tmp[1] == "Normal":
			_severity = LogLevel.INFO
		elif tmp[1] == "Warning":
			_severity = LogLevel.WARNING
		if _severity < severity:
			severity = _severity
	remnants.append(([ThemeString(" ".ljust(indent) + raw_message[eventstart:refstart], ThemeAttr("types", "yaml_reference"))], severity))
	for _key_value in raw_message[refstart:refend].split(", "):
		key, value = _key_value.split(":", 1)
		remnants.append(([ThemeString(" ".ljust(indent * 2) + key, ThemeAttr("types", "yaml_key")),
				  ThemeRef("separators", "yaml_key_separator"),
				  ThemeString(f" {value}", ThemeAttr("types", "yaml_value"))], severity))
	remnants.append(([ThemeString(" ".ljust(indent * 1) + raw_message[refend:eventend], ThemeAttr("types", "yaml_reference"))], severity))
	remnants.append(([ThemeString(raw_message[eventend:eventend + 3], ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")),
			  ThemeString(raw_message[eventend + 3:len(raw_message)], ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity))

	return severity, message, remnants

def format_key_value(key: str, value: str, severity: LogLevel, force_severity: bool = False) -> List[Union[ThemeRef, ThemeString]]:
	if key in ("error", "err"):
		tmp = [ThemeString(f"{key}", ThemeAttr("types", "key_error")),
		       ThemeRef("separators", "keyvalue_log"),
		       ThemeString(f"{value}", ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
	elif force_severity == True:
		tmp = [ThemeString(f"{key}", ThemeAttr("types", "key")),
		       ThemeRef("separators", "keyvalue_log"),
		       ThemeString(f"{value}", ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
	else:
		tmp = [ThemeString(f"{key}", ThemeAttr("types", "key")),
		       ThemeRef("separators", "keyvalue_log"),
		       ThemeString(f"{value}", ThemeAttr("types", "value"))]
	return tmp

# pylint: disable-next=unused-argument
def sysctl(message: str, severity: Optional[LogLevel] = LogLevel.INFO, facility: str = "", fold_msg: bool = True, options: Optional[Dict] = None) ->\
			Tuple[str, LogLevel, str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	"""
	Format output from sysctl

		Parameters:
			message (str): The string to format
			severity (LogLevel): The log severity
			facility (str): The log facility
			fold_msg (bool): Should the message be expanded or folded?
			options (dict): Additional, rule specific, options
		Returns:
	"""

	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []
	new_message: List[Union[ThemeRef, ThemeString]] = []

	kv = message.split(" = ")
	if len(kv) == 2:
		key, value = kv
		keyparts = key.split(".")
		for i, part in enumerate(keyparts):
			new_message.append(ThemeString(part, ThemeAttr("types", "key")))
			if i < len(keyparts) - 1:
				new_message.append(ThemeRef("separators", "sysctl_key_components"))
		new_message.append(ThemeRef("separators", "sysctl_keyvalue"))
		new_message.append(ThemeString(value, ThemeAttr("types", "value")))
	return facility, severity, new_message, remnants

# Severity: lvl=|level=
# Timestamps: t=|ts=|time= (all of these are ignored)
# Facility: subsys|caller|logger|source
def key_value(message: str, severity: Optional[LogLevel] = LogLevel.INFO, facility: str = "", fold_msg: bool = True, options: Optional[Dict] = None) ->\
			Tuple[str, LogLevel, str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []

	messages = deep_get(options, DictPath("messages"), ["msg"])
	errors = deep_get(options, DictPath("errors"), ["err", "error"])
	timestamps = deep_get(options, DictPath("timestamps"), ["t", "ts", "time"])
	severities = deep_get(options, DictPath("severities"), ["level", "lvl"])
	severity_overrides = deep_get(options, DictPath("severity#overrides"), [])
	facilities = deep_get(options, DictPath("facilities"), ["source", "subsys", "caller", "logger", "Topic"])
	versions = deep_get(options, DictPath("versions"), [])
	substitute_bullets = deep_get(options, DictPath("substitute_bullets"), True)
	collector_bullets = deep_get(options, DictPath("collector_bullets"), False)

	# Replace embedded quotes with fancy quotes
	message = message.replace("\\\"", "”")

	# split all key=value pairs
	# Safe
	key_value_regex = re.compile(r"^(.*?)=(.*)")
	# Safe
	tmp = re.findall(r"(?:\".*?\"|\S)+", message)
	# pylint: disable-next=too-many-nested-blocks
	if tmp is not None:
		d = {}
		for item in tmp:
			tmp2 = key_value_regex.match(item)
			if tmp2 is None:
				# Give up; this line cannot be parsed as a set of key=value
				return facility, severity, message, remnants
			if tmp2 is not None:
				key = tmp2[1]
				value = tmp2[2]
				if key not in d:
					d[key] = value
				else:
					# Give up; this line cannot be parsed as a set of key=value
					break
			# XXX: Instead of just giving up we should probably do something with the leftovers...

		if logparser_configuration.pop_ts == True:
			for _ts in timestamps:
				d.pop(_ts, None)
		level = deep_get_with_fallback(d, severities)
		if logparser_configuration.pop_severity == True:
			for _sev in severities:
				d.pop(_sev, None)
		if level is not None:
			severity = str_to_severity(level)
		if severity is None:
			severity = LogLevel.INFO

		msg = deep_get_with_fallback(d, messages, "")
		if msg.startswith("\"") and msg.endswith("\""):
			msg = msg[1:-1]
		version = deep_get_with_fallback(d, versions, "").strip("\"")

		if facility == "":
			for _fac in facilities:
				if isinstance(_fac, str):
					facility = deep_get(d, DictPath(_fac), "")
					break

				if isinstance(_fac, dict):
					_facilities = deep_get(_fac, DictPath("keys"), [])
					_separators = deep_get(_fac, DictPath("separators"), [])
					for i, _fac in enumerate(_facilities):
						# This is to allow prefixes/suffixes
						if _fac != "":
							if _fac not in d:
								break
							facility += str(deep_get(d, DictPath(_fac), ""))
						if i < len(_separators):
							facility += _separators[i]
		if logparser_configuration.pop_facility == True:
			for _fac in facilities:
				if isinstance(_fac, str):
					d.pop(_fac, None)
				elif isinstance(_fac, dict):
					# This is a list, since the order of the facilities matter when outputting
					# it does not matter when popping though
					for __fac in deep_get(_fac, DictPath("keys"), []):
						if __fac == "":
							continue

						d.pop(__fac)

		# pylint: disable-next=too-many-boolean-expressions
		if not fold_msg and len(d) == 2 and logparser_configuration.merge_starting_version == True and "msg" in d and msg.startswith("Starting") and "version" in d and version.startswith("(version="):
			message, severity = custom_override_severity(msg, severity, overrides = severity_overrides)
			message = f"{msg} {version}"
		elif "err" in d and ("errors occurred:" in d["err"] or "error occurred:" in d["err"]) and fold_msg == False:
			err = d["err"]
			if err.startswith("\"") and err.endswith("\""):
				err = err[1:-1]
			message = f"{msg}"
			# DoS
			tmp = re.match(r"(\d+ errors? occurred:)(.*)", err)
			if tmp is not None:
				remnants.append(([ThemeString(tmp[1], ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity))
				s = tmp[2].replace("\\t", "").split("\\n")
				for line in s:
					if len(line) > 0:
						# Real bullets look so much nicer
						if line.startswith("* ") and substitute_bullets == True and logparser_configuration.msg_realbullets == True:
							remnants.append(([ThemeRef("separators", "logbullet"),
									  ThemeString(f"{line[2:]}", ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity))
						else:
							remnants.append(([ThemeString(f"{line}", ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity))
		else:
			tmp = []
			# If we are extracting msg we always want msg first
			if logparser_configuration.msg_extract == True and fold_msg == False and len(msg) > 0:
				tmp.append(msg)
				# Pop the first matching _msg
				for _msg in messages:
					if _msg in d:
						d.pop(_msg, "")
						break
				for key in errors:
					value = d.pop(key, "")
					if len(value) > 0:
						tmp.append(format_key_value(key, value, severity))
			else:
				if logparser_configuration.msg_first == True:
					if fold_msg:
						for key in messages + errors:
							value = d.pop(key, "")
							if len(value) > 0:
								if logparser_configuration.msg_extract == True and key in messages:
									# We already have the message extracted
									tmp.append(msg)
								else:
									tmp.append(f"{key}={value}")
					else:
						msg = deep_get_with_fallback(d, messages, "")
						if len(msg) > 0:
							force_severity = False
							if not any(key in errors for key in d):
								force_severity = True
							tmp.append(format_key_value("msg", msg, severity, force_severity = force_severity))
						# Pop the first matching _msg
						for _msg in messages:
							if _msg in d:
								d.pop(_msg, "")
								break
						for key in errors:
							value = d.pop(key, "")
							if len(value) > 0:
								tmp.append(format_key_value(key, value, severity))

			for d_key, d_value in d.items():
				if not fold_msg:
					if d_key == "collector" and collector_bullets == True and logparser_configuration.bullet_collectors == True:
						tmp.append(f"• {d_value}")
					elif d_key in versions:
						tmp.append(format_key_value(d_key, d_value, LogLevel.NOTICE, force_severity = True))
					else:
						d_value, __severity = custom_override_severity(d_value, severity, overrides = severity_overrides)
						# pylint: disable-next=superfluous-parens
						tmp.append(format_key_value(d_key, d_value, __severity, force_severity = (__severity != severity)))
				else:
					tmp.append(f"{d_key}={d_value}")

			if fold_msg:
				message = " ".join(tmp)
			else:
				if len(tmp) > 0:
					message = tmp.pop(0)
				else:
					message = ""
				if len(tmp) > 0:
					remnants = (tmp, severity)

	if logparser_configuration.msg_linebreaks and "\\n" in message and isinstance(message, str) and not fold_msg:
		lines = message.split("\\n")
		message = lines[0]
		_remnants = []
		if len(lines) > 1:
			for line in lines[1:]:
				_remnants.append(([ThemeString(f"{line}", ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity))
			if isinstance(remnants, tuple):
				for remnant in remnants[0]:
					_remnants.append(([ThemeString(remnant, ThemeAttr("logview", f"severity_{loglevel_to_name(remnants[1]).lower()}"))], remnants[1]))
				remnants = _remnants
			elif isinstance(remnants, list):
				remnants = _remnants + remnants

	if facility.startswith("\"") and facility.endswith("\""):
		facility = facility[1:-1]
	return facility, severity, message, remnants

# For messages along the lines of:
# "Foo" "key"="value" "key"="value"
# Foo key=value key=value
def key_value_with_leading_message(message: str, severity: Optional[LogLevel] = LogLevel.INFO, facility: str = "", fold_msg: bool = True, options: Optional[Dict] = None) ->\
						Tuple[str, LogLevel, str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	# This warning seems incorrect
	# pylint: disable-next=global-variable-not-assigned
	global logparser_configuration
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []

	if fold_msg:
		return facility, severity, message, remnants

	# Split into substrings based on spaces
	tmp = re.findall(r"(?:\".*?\"|\S)+", message)
	if tmp is not None and len(tmp) > 0:
		if "=" in tmp[0]:
			# Try parsing this as regular key_value
			facility, severity, new_message, remnants = key_value(message, fold_msg = fold_msg, severity = severity, facility = facility, options = options)
			if not isinstance(new_message, str):
				new_message = themearray_to_string(new_message)
			return facility, severity, new_message, remnants

		for item in tmp[1:]:
			# we could not parse this as "msg key=value"; give up
			if "=" not in item:
				return facility, severity, message, remnants
		rest = message[len(tmp[0]):].lstrip()
		new_message = tmp[0]
		tmp_msg_extract = logparser_configuration.msg_extract
		logparser_configuration.msg_extract = False
		facility, severity, first_message, tmp_new_remnants = key_value(rest, fold_msg = fold_msg, severity = severity, facility = facility, options = options)
		logparser_configuration.msg_extract = tmp_msg_extract
		if tmp_new_remnants is not None and len(tmp_new_remnants) > 0:
			new_remnants_strs, new_remnants_severity = tmp_new_remnants
			new_remnants = ([first_message] + new_remnants_strs, new_remnants_severity)
		else:
			new_remnants = ([first_message], severity)
		return facility, severity, new_message, new_remnants
	return facility, severity, message, remnants

# Messages on the format:
# <key>:<whitespace>...<value>
# pylint: disable-next=unused-argument
def modinfo(message: str, fold_msg: bool = True) ->\
			Tuple[str, LogLevel, str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	facility = ""
	severity = LogLevel.INFO
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []

	# Safe
	tmp = re.match(r"^([a-z][\S]*?):(\s+)(.+)", message)
	if tmp is not None:
		key = tmp[1]
		whitespace = tmp[2]
		value = tmp[3]
		new_message: List[Union[ThemeRef, ThemeString]] = [
			ThemeString(key, ThemeAttr("types", "key")),
			ThemeRef("separators", "keyvalue"),
			ThemeString(whitespace, ThemeAttr("types", "generic")),
			ThemeString(value, ThemeAttr("types", "value")),
		]
		return facility, severity, new_message, remnants
	return facility, severity, message, remnants

# Messages on the format:
# [timestamp] [severity] message
# pylint: disable-next=unused-argument
def bracketed_timestamp_severity(message: str, fold_msg: bool = True) ->\
					Tuple[str, LogLevel, str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	facility = ""
	severity = LogLevel.INFO
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []

	# Some messages have double timestamps...
	message, _timestamp = split_iso_timestamp(message, none_timestamp())
	message, severity = split_bracketed_severity(message, default = LogLevel.WARNING)

	if message.startswith(("XPU Manager:", "Build:", "Level Zero:")):
		severity = LogLevel.NOTICE

	return facility, severity, message, remnants

# pylint: disable-next=unused-argument
def directory(message: str, fold_msg: bool = True, severity: Optional[LogLevel] = LogLevel.INFO, facility: str = "") ->\
					Tuple[Union[str, List[Union[ThemeRef, ThemeString]]], LogLevel, Union[str, List[Union[ThemeRef, ThemeString]]], List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []

	# Safe
	tmp = re.match(r"^(total)\s+(\d+)$", message)
	if tmp is not None:
		return facility, severity, message, remnants

	# DoS
	tmp = re.match(r"^(.)(.........)(\s+)(\d+)(\s+)(.*?)(\s+)(\*?)(\s+)(\d+)(,\s+\d+|)(\s+)(.+?)(\s+)(\d+)(\s+)(.*?)(\s+)(.+?)(=|\||/|)$", message)
	if tmp is None:
		# This is unlikely to be a directory match
		return facility, severity, message, remnants

	etype = tmp[1]
	permissions = tmp[2]
	space1 = tmp[3]
	linkcount = tmp[4]
	space2 = tmp[5]
	owner = tmp[6]
	space3 = tmp[7]
	group = tmp[8]
	space4 = tmp[9]
	size = tmp[10] + tmp[11]
	space5 = tmp[12]
	month = tmp[13]
	space6 = tmp[14]
	day = tmp[15]
	space7 = tmp[16]
	yearortime = tmp[17]
	space8 = tmp[18]
	name = tmp[19]
	suffix = tmp[20]

	_message: List[Union[ThemeRef, ThemeString]] = [
		ThemeString(f"{etype}", ThemeAttr("types", "dir_type")),
		ThemeString(f"{permissions}", ThemeAttr("types", "dir_permissions")),
		ThemeString(f"{space1}", ThemeAttr("types", "generic")),
		ThemeString(f"{linkcount}", ThemeAttr("types", "dir_linkcount")),
		ThemeString(f"{space2}", ThemeAttr("types", "generic")),
		ThemeString(f"{owner}", ThemeAttr("types", "dir_owner")),
		ThemeString(f"{space3}", ThemeAttr("types", "generic")),
		ThemeString(f"{group}", ThemeAttr("types", "dir_group")),
		ThemeString(f"{space4}", ThemeAttr("types", "generic")),
		ThemeString(f"{size}", ThemeAttr("types", "dir_size")),
		ThemeString(f"{space5}", ThemeAttr("types", "generic")),
		ThemeString(f"{month}", ThemeAttr("types", "dir_date")),
		ThemeString(f"{space6}", ThemeAttr("types", "generic")),
		ThemeString(f"{day}", ThemeAttr("types", "dir_date")),
		ThemeString(f"{space7}", ThemeAttr("types", "generic")),
		ThemeString(f"{yearortime}", ThemeAttr("types", "dir_date")),
		ThemeString(f"{space8}", ThemeAttr("types", "generic")),
	]
	# regular file
	if etype == "-":
		_message += [
			ThemeString(f"{name}", ThemeAttr("types", "dir_file"))
		]
	# block device
	elif etype == "b":
		_message += [
			ThemeString(f"{name}", ThemeAttr("types", "dir_dev"))
		]
	# character device
	elif etype == "c":
		_message += [
			ThemeString(f"{name}", ThemeAttr("types", "dir_dev"))
		]
	# sticky bit has precedence over the regular directory type
	elif permissions.endswith("t"):
		_message += [
			ThemeString(f"{name}", ThemeAttr("types", "dir_socket"))
		]
	# directory
	elif etype == "d":
		_message += [
			ThemeString(f"{name}", ThemeAttr("types", "dir_dir"))
		]
	# symbolic link
	elif etype == "l":
		tmp2 = re.match(r"(.+?)( -> )(.+)", name)
		if tmp2 is None:
			_message += [
				ThemeString(f"{name}", ThemeAttr("types", "dir_symlink_name"))
			]
		else:
			_message += [
				ThemeString(f"{tmp2[1]}", ThemeAttr("types", "dir_symlink_name")),
				ThemeString(f"{tmp2[2]}", ThemeAttr("types", "dir_symlink_link"))
			]
			# There is no suffix for devices or regular files,
			# but we can distinguish the two based on the file size;
			# the size for devices is not really a size per se,
			# but rather major, minor (a normal size never has a comma)
			if len(suffix) == 0:
				if "," in size:
					_message += [
						ThemeString(f"{tmp2[3]}", ThemeAttr("types", "dir_dev")),
					]
				else:
					_message += [
						ThemeString(f"{tmp2[3]}", ThemeAttr("types", "dir_file")),
					]
			elif suffix == "|":
				_message += [
					ThemeString(f"{tmp2[3]}", ThemeAttr("types", "dir_pipe")),
				]
			elif suffix == "=":
				_message += [
					ThemeString(f"{tmp2[3]}", ThemeAttr("types", "dir_socket")),
				]
			elif suffix == "/":
				_message += [
					ThemeString(f"{tmp2[3]}", ThemeAttr("types", "dir_dir")),
				]
			else:
				raise ValueError(f"Unhandled suffix {suffix} in line {message}")
	# pipe
	elif etype == "p":
		_message += [
			ThemeString(f"{name}", ThemeAttr("types", "dir_pipe"))
		]
	# socket
	elif etype == "s":
		_message += [
			ThemeString(f"{name}", ThemeAttr("types", "dir_socket"))
		]

	if len(suffix) > 0:
		_message += [
			ThemeString(f"{suffix}", ThemeAttr("types", "dir_suffix"))
		]

	return facility, severity, _message, remnants

# input: [     0.000384s]  INFO ThreadId(01) linkerd2_proxy::rt: Using single-threaded proxy runtime
# output:
#   severity: LogLevel.INFO
#   facility: ThreadId(01)
#   msg: [     0.000384s] linkerd2_proxy::rt: Using single-threaded proxy runtime
#   remnants: []
# pylint: disable-next=unused-argument
def seconds_severity_facility(message: str, fold_msg: bool = True) ->\
					Tuple[str, LogLevel, Union[str, List[Union[ThemeRef, ThemeString]]], List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	facility = ""
	severity = LogLevel.INFO
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []

	tmp = re.match(r"(\[\s*?\d+?\.\d+?s\])\s+([A-Z]+?)\s+(\S+?)\s(.*)", message)
	if tmp is not None:
		severity = cast(LogLevel, str_to_severity(tmp[2], default = severity))
		facility = cast(str, tmp[3])
		new_message: List[Union[ThemeRef, ThemeString]] = [ThemeString(f"{tmp[1]} ", ThemeAttr("logview", "timestamp")),
								   ThemeString(f"{tmp[4]}", ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
		return facility, severity, new_message, remnants

	return facility, severity, message, remnants

def substitute_bullets(message: str, prefix: str) -> str:
	"""
	Replace '*' with actual bullet characters

		Parameters:
			message (str): The message to process
			prefix (str): The prefix to use to detect whether or not the bullets should be substituted
		Returns:
			message (str): The message with bullets substituted
	"""

	if message.startswith(prefix):
		# We do not want to replace all "*" in the message with bullet, just prefixes
		message = message[0:len(prefix)].replace("*", "•", 1) + message[len(prefix):]
	return message

def python_traceback_scanner(message: str, fold_msg: bool = True, options: Optional[Dict] = None) ->\
					Tuple[Tuple[str, Optional[Callable], Dict],
					      Tuple[datetime, str, LogLevel, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]]:
	# pylint: disable=unused-argument
	timestamp = none_timestamp()
	facility = ""
	severity = LogLevel.ERR
	message, _timestamp = split_iso_timestamp(message, none_timestamp())
	processor: Tuple[str, Optional[Callable], Dict] = ("block", python_traceback_scanner, {})

	# Default case
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = [
		([ThemeString(message, ThemeAttr("logview", "severity_info"))], severity)
	]

	tmp = re.match(r"^(\s+File \")(.+?)(\", line )(\d+)(, in )(.*)", message)
	if tmp is not None:
		remnants = [
			([ThemeString(tmp[1], ThemeAttr("logview", "severity_info")),
			  ThemeString(tmp[2], ThemeAttr("types", "path")),
			  ThemeString(tmp[3], ThemeAttr("logview", "severity_info")),
			  ThemeString(tmp[4], ThemeAttr("types", "lineno")),
			  ThemeString(tmp[5], ThemeAttr("logview", "severity_info")),
			  ThemeString(tmp[6], ThemeAttr("types", "path"))],
			 severity),
		]
	else:
		tmp = re.match(r"(^\S+?Error:|Exception:|GeneratorExit:|KeyboardInterrupt:|StopIteration:|StopAsyncIteration:|SystemExit:)( .*)", message)
		if tmp is not None:
			remnants = [
				([ThemeString(tmp[1], ThemeAttr("logview", "severity_error")),
				  ThemeString(tmp[2], ThemeAttr("logview", "severity_info"))],
				 severity),
			]
			processor = ("end_block", None, {})
		elif message.lstrip() == message:
			processor = ("break", None, {})

	return processor, (timestamp, facility, severity, remnants)

# pylint: disable-next=unused-argument
def python_traceback(message: str, fold_msg: bool = True) ->\
				Tuple[Union[str, Tuple[str, Optional[Callable], Dict]],
				      List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []

	if message == "Traceback (most recent call last):":
		remnants = [([ThemeString(message, ThemeAttr("logview", "severity_error"))], LogLevel.ERR)]
		processor: Tuple[str, Optional[Callable], Dict] = ("start_block", python_traceback_scanner, {})
		return processor, remnants

	return message, remnants

def json_line_scanner(message: str, fold_msg: bool = True, options: Optional[Dict] = None) ->\
				Tuple[Tuple[str, Optional[Callable], Dict],
				      Tuple[datetime, str, LogLevel, Optional[List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]]]:
	# pylint: disable=unused-argument
	allow_empty_lines = deep_get(options, DictPath("allow_empty_lines"), True)
	timestamp = none_timestamp()
	facility = ""
	severity = LogLevel.INFO
	message, _timestamp = split_iso_timestamp(message, none_timestamp())

	if message == "}".rstrip():
		remnants = formatters.format_yaml_line(message, override_formatting = {})
		processor: Tuple[str, Optional[Callable], Dict] = ("end_block", None, {})
	elif message.lstrip() != message or message == "{":
		remnants = formatters.format_yaml_line(message, override_formatting = {})
		processor = ("block", json_line_scanner, {})
	elif len(message.strip()) == 0 and allow_empty_lines == True:
		remnants = formatters.format_yaml_line(message, override_formatting = {})
		processor = ("block", json_line_scanner, {})
	else:
		remnants = None
		processor = ("break", None, {})

	return processor, (timestamp, facility, severity, remnants)

# pylint: disable-next=unused-argument
def json_line(message: str, fold_msg: bool = True, severity: Optional[LogLevel] = LogLevel.INFO, options: Optional[Dict] = None) ->\
			Tuple[Union[str, Tuple[str, Optional[Callable], Dict]],
			      List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	if options is None:
		options = {}

	remnants: Union[str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]] = []
	matched = False

	block_start = deep_get(options, DictPath("block_start"), [{
		"matchtype": "exact",
		"matchkey": "{",
		"matchline": "any",
		"format_block_start": False,
	}])
	line = deep_get(options, DictPath("__line"), 0)

	for _bs in block_start:
		matchtype = _bs["matchtype"]
		matchkey = _bs["matchkey"]
		matchline = _bs["matchline"]
		format_block_start = deep_get(_bs, DictPath("format_block_start"), False)
		if matchline == "any" or matchline == "first" and line == 0:
			if matchtype == "exact":
				if message == matchkey:
					matched = True
			elif matchtype == "startswith":
				if message.startswith(matchkey):
					matched = True
			elif matchtype == "endswith":
				if message.endswith(matchkey):
					matched = True
			elif matchtype == "regex":
				tmp = re.match(matchkey, message)
				if tmp is not None:
					matched = True

	if matched == True:
		if format_block_start == True:
			remnants = formatters.format_yaml_line(message, override_formatting = {})
		else:
			remnants = [ThemeString(message, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
		processor: Tuple[str, Optional[Callable], Dict] = ("start_block", json_line_scanner, options)
		return processor, remnants

	return message, []

# pylint: disable-next=unused-argument
def yaml_line_scanner(message: str, fold_msg: bool = True, options: Optional[Dict] = None) ->\
				Tuple[Tuple[str, Optional[Callable], Dict],
				      Tuple[datetime, str, LogLevel, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]]:
	if options is None:
		options = {}

	timestamp = none_timestamp()
	facility = ""
	severity = LogLevel.INFO
	message, _timestamp = split_iso_timestamp(message, none_timestamp())
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []
	matched = True

	# If no block end is defined we continue until EOF
	block_end = deep_get(options, DictPath("block_end"))

	format_block_end = False
	process_block_end = True

	for _be in block_end:
		matchtype = deep_get(_be, DictPath("matchtype"))
		matchkey = deep_get(_be, DictPath("matchkey"))
		format_block_end = deep_get(_be, DictPath("format_block_end"), False)
		process_block_end = deep_get(_be, DictPath("process_block_end"), True)
		if matchtype == "empty":
			if len(message.strip()) == 0:
				matched = False
		elif matchtype == "exact":
			if message == matchkey:
				matched = False
		elif matchtype == "startswith":
			if message.startswith(matchkey):
				matched = False
		elif matchtype == "regex":
			tmp = matchkey.match(message)
			if tmp is not None:
				matched = False

	if matched == True:
		remnants = formatters.format_yaml_line(message, override_formatting = {})
		processor: Tuple[str, Optional[Callable], Dict] = ("block", yaml_line_scanner, options)
	else:
		if process_block_end == True:
			if format_block_end == True:
				remnants = formatters.format_yaml_line(message, override_formatting = {})
			else:
				remnants = [ThemeString(message, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
			processor = ("end_block", None, {})
		else:
			processor = ("end_block_not_processed", None, {})

	return processor, (timestamp, facility, severity, remnants)

# pylint: disable-next=unused-argument
def yaml_line(message: str, fold_msg: bool = True, severity: LogLevel = LogLevel.INFO, options: Optional[Dict] = None) ->\
			Tuple[Union[str, Tuple[str, Optional[Callable], Dict]],
			      Union[str, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]]:
	if options is None:
		options = {}

	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []
	matched = False

	block_start = deep_get(options, DictPath("block_start"), [{
		"matchtype": "regex",
		"matchkey": re.compile(r"\S+?: \S.*|\S+?:$"),
		"matchline": "any",
		"format_block_start": False,
	}])
	line = deep_get(options, DictPath("__line"), 0)
	if deep_get(options, DictPath("eof")) is None:
		options["eof"] = "end_block"

	for _bs in block_start:
		matchtype = _bs["matchtype"]
		matchkey = _bs["matchkey"]
		matchline = _bs["matchline"]
		format_block_start = deep_get(_bs, DictPath("format_block_start"), False)
		if matchline == "any" or matchline == "first" and line == 0:
			if matchtype == "exact":
				if message == matchkey:
					matched = True
			elif matchtype == "startswith":
				if message.startswith(matchkey):
					matched = True
			elif matchtype == "regex":
				tmp = re.match(matchkey, message)
				if tmp is not None:
					matched = True

	if matched == True:
		if format_block_start == True:
			remnants = formatters.format_yaml_line(message, override_formatting = {})
		else:
			remnants = [ThemeString(message, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
		processor: Tuple[str, Optional[Callable], Dict] = ("start_block", yaml_line_scanner, options)
		return processor, remnants

	return message, remnants

# pylint: disable-next=unused-argument
def diff_line_scanner(message: str, fold_msg: bool = True, options: Optional[Dict] = None) ->\
				Tuple[Tuple[str, Optional[Callable], Dict],
				      Tuple[datetime, str, LogLevel, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]]:
	timestamp = none_timestamp()
	facility = ""
	severity = LogLevel.INFO
	message, _timestamp = split_iso_timestamp(message, none_timestamp())
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []
	matched = True

	# If no block end is defined we continue until EOF
	block_end = deep_get(options, DictPath("block_end"))

	format_block_end = False
	process_block_end = True

	for _be in block_end:
		matchtype = deep_get(_be, DictPath("matchtype"))
		matchkey = deep_get(_be, DictPath("matchkey"))
		format_block_end = deep_get(_be, DictPath("format_block_end"), False)
		process_block_end = deep_get(_be, DictPath("process_block_end"), True)
		if matchtype == "empty":
			if len(message.strip()) == 0:
				matched = False
		elif matchtype == "exact":
			if message == matchkey:
				matched = False
		elif matchtype == "startswith":
			if message.startswith(matchkey):
				matched = False
		elif matchtype == "regex":
			tmp = matchkey.match(message)
			if tmp is not None:
				matched = False

	if matched == True:
		remnants = formatters.format_diff_line(message, override_formatting = {})
		processor: Tuple[str, Optional[Callable], Dict] = ("block", diff_line_scanner, options)
	else:
		if process_block_end == True:
			if format_block_end == True:
				remnants = formatters.format_diff_line(message, override_formatting = {})
			else:
				remnants = [ThemeString(message, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
			processor = ("end_block", None, {})
		else:
			processor = ("end_block_not_processed", None, {})

	return processor, (timestamp, facility, severity, remnants)

# pylint: disable-next=unused-argument
def diff_line(message: str, fold_msg: bool = True, severity: LogLevel = LogLevel.INFO, options: Optional[Dict] = None) ->\
			Tuple[Tuple[str, Optional[Callable], Dict],
			      List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	if options is None:
		options = {}

	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []
	matched = False

	block_start = deep_get(options, DictPath("block_start"), [{
		"matchtype": "regex",
		"matchkey": re.compile(r"\S+?: \S.*|\S+?:$"),
		"matchline": "any",
		"format_block_start": False,
	}])
	line = deep_get(options, DictPath("__line"), 0)
	if deep_get(options, DictPath("eof")) is None:
		options["eof"] = "end_block"

	for _bs in block_start:
		matchtype = _bs["matchtype"]
		matchkey = _bs["matchkey"]
		matchline = _bs["matchline"]
		format_block_start = deep_get(_bs, DictPath("format_block_start"), False)
		if matchline == "any" or matchline == "first" and line == 0:
			if matchtype == "exact":
				if message == matchkey:
					matched = True
			elif matchtype == "startswith":
				if message.startswith(matchkey):
					matched = True
			elif matchtype == "regex":
				tmp = matchkey.match(message)
				if tmp is not None:
					matched = True

	if matched == True:
		if format_block_start == True:
			remnants = formatters.format_diff_line(message, override_formatting = {})
		else:
			remnants = [ThemeString(message, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
		processor: Tuple[str, Optional[Callable], Dict] = ("start_block", diff_line_scanner, options)
		return processor, remnants

	return message, remnants

# pylint: disable-next=unused-argument
def ansible_line_scanner(message: str, fold_msg: bool = True, options: Optional[Dict] = None) ->\
				Tuple[Tuple[str, Optional[Callable], Dict],
				      Tuple[datetime, str, LogLevel, List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]]:
	timestamp = none_timestamp()
	facility = ""
	severity = LogLevel.INFO
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []
	matched = True
	final_block = deep_get(options, "final_block", False)

	message = strip_iso_timestamp(message)

	if len(message) == 0:
		options["override_formatting"] = None

	# We're approaching the end
	if final_block and len(message) == 0:
		processor = ("end_block", None, {})
	else:
		if "final_block" in options:
			tmp = re.match(r"^.+?:\sok=(\d+)\s+changed=(\d+)\s+unreachable=(\d+)\s+failed=(\d+)\s+skipped=(\d+)\s+rescued=(\d+)\s+ignored=(\d+)", message)
			if tmp is not None:
				ok = int(tmp[1])
				changed = int(tmp[2])
				unreachable = int(tmp[3])
				failed = int(tmp[4])
				skipped = int(tmp[5])
				rescued = int(tmp[6])
				ignored = int(tmp[7])

				# These are sorted in order of severity; "highest" wins
				if ok > 0:
					options["override_formatting"] = ThemeAttr("main", "status_ok")
				if changed > 0:
					options["override_formatting"] = ThemeAttr("logview", "severity_modified")
				if skipped > 0:
					options["override_formatting"] = ThemeAttr("logview", "severity_debug")
				if ignored > 0 or rescued > 0:
					options["override_formatting"] = ThemeAttr("logview", "severity_warn")
				if unreachable > 0 or failed > 0:
					options["override_formatting"] = ThemeAttr("logview", "severity_error")

		if message.startswith("skipping"):
			options["override_formatting"] = ThemeAttr("logview", "severity_debug")
		elif message.startswith("ok"):
			options["override_formatting"] = ThemeAttr("main", "status_ok")
		elif message.startswith("changed"):
			options["override_formatting"] = ThemeAttr("logview", "severity_modified")
		elif message.startswith("fatal"):
			options["override_formatting"] = ThemeAttr("logview", "severity_error")
		remnants = formatters.format_ansible_line(message, override_formatting = deep_get(options, DictPath("override_formatting")))
		if message.startswith("PLAY RECAP"):
			options["final_block"] = True
			processor: Tuple[str, Optional[Callable], Dict] = ("final_block", ansible_line_scanner, options)
		else:
			processor: Tuple[str, Optional[Callable], Dict] = ("block", ansible_line_scanner, options)

	return processor, (timestamp, facility, severity, remnants)

# pylint: disable-next=unused-argument
def ansible_line(message: str, fold_msg: bool = True, severity: LogLevel = LogLevel.INFO, options: Optional[Dict] = None) ->\
			Tuple[Tuple[str, Optional[Callable], Dict],
			      List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	if options is None:
		options = {}

	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []
	matched = False

	if message.startswith("PLAY [") and message.endswith("***"):
		if severity is None:
			severity = LogLevel.INFO
		remnants = [ThemeString(message, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
		options["eof"] = "end_block"
		processor: Tuple[str, Optional[Callable], Dict] = ("start_block", ansible_line_scanner, options)
		return processor, remnants

	return message, remnants

# pylint: disable-next=unused-argument
def raw_formatter(message: str, severity: Optional[LogLevel] = None, facility: str = "", fold_msg: bool = True, options: Optional[Dict] = None) ->\
			Tuple[Union[str, List[Union[ThemeRef, ThemeString]]], Optional[LogLevel], str]:
	assert options is not None

	format_rules = deep_get(options, DictPath("format_rules"), {})

	if len(format_rules) == 0:
		raise ValueError("format_rules is empty")

	# Iterate until first matching rule, if any
	for format_rule in format_rules:
		matchtype = deep_get(format_rule, DictPath("matchtype"), "")
		matchkey = deep_get(format_rule, DictPath("matchkey"), "")
		formatting = deep_get(format_rule, DictPath("formatting"), {})

		if matchtype == "regex":
			tmp = re.match(matchkey, message)
			if tmp is None or len(tmp.groups()) == 0:
				continue
			tmp_msg = []

			field_colors = deep_get(formatting, DictPath("field_colors"), [])
			for color_index, group in enumerate(tmp.groups()):
				if len(field_colors) == 0:
					tmp_msg.append(ThemeString(group, ThemeAttr("types", "generic")))
				elif color_index > len(field_colors):
					tmp_msg.append(ThemeString(group, ThemeAttr(field_colors[-1]["context"], field_colors[-1]["type"])))
				else:
					tmp_msg.append(ThemeString(group, ThemeAttr(field_colors[color_index]["context"], field_colors[color_index]["type"])))
			message = tmp_msg
			break
		else:
			raise TypeError(f"Unsupported matchtype {matchtype}")

	return message, severity, facility

# pylint: disable-next=unused-argument
def custom_splitter(message: str, severity: Optional[LogLevel] = None, facility: str = "", fold_msg: bool = True, options: Optional[Dict] = None) ->\
			Tuple[Union[str, List[Union[ThemeRef, ThemeString]]], Optional[LogLevel], str]:
	assert options is not None

	compiled_regex = deep_get(options, DictPath("regex"), None)
	severity_field = deep_get(options, DictPath("severity#field"), None)
	severity_transform = deep_get(options, DictPath("severity#transform"), None)
	severity_overrides = deep_get(options, DictPath("severity#overrides"), [])
	facility_fields = deep_get_with_fallback(options, [DictPath("facility#fields"), DictPath("facility#field")], None)
	facility_separators = deep_get_with_fallback(options, [DictPath("facility#separators"), DictPath("facility#separator")], "")
	message_field = deep_get(options, DictPath("message#field"), None)

	# This message is already formatted
	if isinstance(message, list):
		return message, severity, facility

	# The bare minimum for these rules is
	if compiled_regex is None or message_field is None:
		raise ValueError("parser rule is missing regex or message field")

	tmp = compiled_regex.match(message)

	if tmp is not None:
		group_count = len(tmp.groups())
		if message_field > group_count:
			sys.exit(f"The parser rule references a non-existing capture group {message_field} for message; the valid range is [1-{group_count}]")
		if severity_field is not None and severity_transform is not None:
			if severity_field > group_count:
				sys.exit(f"The parser rule references a non-existing capture group {severity_field} for severity; the valid range is [1-{group_count}]")
			if severity_transform == "letter":
				severity = letter_to_severity(tmp[severity_field], severity)
			elif severity_transform == "3letter":
				severity = str_3letter_to_severity(tmp[severity_field], severity)
			elif severity_transform == "4letter":
				severity = str_4letter_to_severity(tmp[severity_field], severity)
			elif severity_transform == "str":
				severity = str_to_severity(tmp[severity_field], severity)
			elif severity_transform == "int":
				severity = cast(LogLevel, int(tmp[severity_field]))
			else:
				sys.exit(f"Unknown severity transform rule {severity_transform}; aborting.")
			message, severity = custom_override_severity(tmp[message_field], severity, overrides = severity_overrides)
		else:
			message = tmp[message_field]
		if facility_fields is not None and len(facility) == 0:
			if isinstance(facility_fields, str):
				facility_fields = [facility_fields]
			if isinstance(facility_separators, str):
				facility_separators = [facility_separators]
			i = 0
			facility = ""
			for field in facility_fields:
				if field > group_count:
					sys.exit(f"The parser rule references a non-existing capture group {field} for facility; the valid range is [1-{group_count}]")
				if i > 0:
					facility += facility_separators[min(i - 1, len(facility_separators) - 1)]
				if field != 0:
					facility += tmp[field]
				i += 1

	return message, severity, facility

def custom_parser(message: str, filters: List[Union[str, Tuple]], fold_msg: bool = True, options: Optional[Dict] = None) ->\
				Tuple[str,
				      LogLevel,
				      Union[List[Union[ThemeRef, ThemeString]], Tuple[str, Optional[Callable], Dict]],
				      List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	facility = ""
	severity = None
	remnants: List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]] = []

	if options is None:
		options = {}

	for _filter in filters:
		if isinstance(_filter, str):
			# These parsers CANNOT handle ThemeArrays
			if isinstance(message, str):
				# Multiparsers
				if _filter == "glog":
					message, severity, facility, remnants, _match = split_glog(message, severity = severity, facility = facility)
				elif _filter == "tab_separated":
					message, severity, facility, remnants = tab_separated(message, severity = severity, facility = facility, fold_msg = fold_msg)
				elif _filter == "spaced_severity_facility":
					message, severity, facility = __split_severity_facility_style(message, severity = severity, facility = facility)
				elif _filter == "directory":
					facility, severity, message, remnants = directory(message, fold_msg = fold_msg, severity = severity, facility = facility)
				elif _filter == "seconds_severity_facility":
					facility, severity, message, remnants = seconds_severity_facility(message, fold_msg = fold_msg)
				elif _filter == "expand_event":
					if message.startswith(("Event(v1.ObjectReference{")):
						severity, message, remnants = expand_event(message, severity = severity, remnants = remnants, fold_msg = fold_msg)
					elif message.startswith(("&Event{ObjectMeta:")):
						severity, message, remnants = expand_event_objectmeta(message, severity = severity, remnants = remnants, fold_msg = fold_msg)
				elif _filter == "modinfo":
					facility, severity, message, remnants = modinfo(message, fold_msg = fold_msg)
				elif _filter == "sysctl":
					facility, severity, message, remnants = sysctl(message, severity = severity, facility = facility, fold_msg = fold_msg)
				# Timestamp formats
				elif _filter == "ts_8601": # Anything that resembles ISO-8601 / RFC 3339
					message = strip_iso_timestamp(message)
				# Facility formats
				elif _filter == "colon_facility":
					message, facility = split_colon_facility(message, facility)
				elif _filter == "angle_bracketed_facility":
					message, facility = split_angle_bracketed_facility(message, facility)
				# Severity formats
				elif _filter == "colon_severity":
					message, severity = split_colon_severity(message, severity)
				# Filters
				elif _filter == "strip_ansicodes":
					message = strip_ansicodes(message)
				# Block starters
				elif _filter == "python_traceback":
					message, remnants = python_traceback(message, fold_msg = fold_msg)
		elif isinstance(_filter, tuple):
			# These parsers CANNOT handle ThemeArrays
			if isinstance(message, str):
				# Multiparsers
				if _filter[0] == "bracketed_timestamp_severity_facility":
					message, severity, facility = split_bracketed_timestamp_severity_facility(message, default = _filter[1])
				elif _filter[0] == "raw_formatter":
					_parser_options = _filter[1]
					message, severity, facility = raw_formatter(message, severity = severity, facility = facility, fold_msg = fold_msg, options = _parser_options)
				elif _filter[0] == "custom_splitter":
					_parser_options = _filter[1]
					message, severity, facility = custom_splitter(message, severity = severity, facility = facility, fold_msg = fold_msg, options = _parser_options)
				elif _filter[0] == "http":
					_parser_options = _filter[1]
					message, severity, facility = http(message, severity = severity, facility = facility, fold_msg = fold_msg, options = _parser_options)
				elif _filter[0] == "iptables":
					_parser_options = _filter[1]
					message, severity, facility, remnants = iptables(message, remnants, severity = severity, facility = facility, fold_msg = fold_msg)
				elif _filter[0] == "json" and isinstance(message, str):
					_parser_options = _filter[1]
					_message = message
					if message.startswith(("{\"", "{ \"")):
						message, severity, facility, remnants = split_json_style(message, severity = severity, facility = facility, fold_msg = fold_msg, options = _parser_options)
				elif _filter[0] == "json_with_leading_message" and isinstance(message, str):
					_parser_options = _filter[1]
					parts = message.split("{", 1)
					if len(parts) == 2:
						# No leading message
						if len(parts[0]) == 0:
							message, severity, facility, remnants = split_json_style("{" + parts[1], severity = severity, facility = facility, fold_msg = fold_msg, options = _parser_options)
						elif parts[0].rstrip() != parts[0]:
							parts[0] = parts[0].rstrip()
							# It isn't leading message + JSON unless there's whitespace in-between
							_message, severity, facility, remnants = split_json_style("{" + parts[1], severity = severity, facility = facility, fold_msg = fold_msg, options = _parser_options)
							_severity = severity
							if _severity is None:
								_severity = LogLevel.INFO
							_message, remnants = merge_message(_message, remnants, severity = _severity)
							message = [ThemeString(parts[0], ThemeAttr("logview", f"severity_{loglevel_to_name(_severity).lower()}"))]
				elif _filter[0] == "json_event":
					_parser_options = _filter[1]
					# We do not extract the facility/severity from folded messages, so just skip if fold_msg == True
					if message.startswith("EVENT ") and fold_msg == False:
						message, severity, facility, remnants = json_event(message, fold_msg = fold_msg, options = _parser_options)
				elif _filter[0] == "key_value":
					_parser_options = _filter[1]
					if "=" in message:
						facility, severity, message, remnants = key_value(message, fold_msg = fold_msg, severity = severity, facility = facility, options = _parser_options)
				elif _filter[0] == "key_value_with_leading_message":
					_parser_options = _filter[1]
					if "=" in message:
						facility, severity, message, remnants = key_value_with_leading_message(message, fold_msg = fold_msg, severity = severity, facility = facility, options = _parser_options)
				# Severity formats
				elif _filter[0] == "bracketed_severity":
					message, severity = split_bracketed_severity(message, default = _filter[1])
				# Filters
				elif _filter[0] == "substitute_bullets":
					message = substitute_bullets(message, _filter[1])
				# Block starters; these are treated as parser loop terminators if a match is found
				elif _filter[0] == "json_line":
					_parser_options = {**_filter[1], **options}
					message, remnants = json_line(message, fold_msg = fold_msg, severity = severity, options = _parser_options)
				elif _filter[0] == "yaml_line":
					_parser_options = {**_filter[1], **options}
					message, remnants = yaml_line(message, fold_msg = fold_msg, severity = severity, options = _parser_options)
				elif _filter[0] == "diff_line":
					_parser_options = {**_filter[1], **options}
					message, remnants = diff_line(message, fold_msg = fold_msg, severity = severity, options = _parser_options)
				elif _filter[0] == "ansible_line":
					_parser_options = {**_filter[1], **options}
					message, remnants = ansible_line(message, fold_msg = fold_msg, severity = severity, options = _parser_options)
			# These parsers CAN handle ThemeArrays
			# Severity formats
			if _filter[0] == "override_severity":
				message, severity = custom_override_severity(message, severity, _filter[1])

		if isinstance(message, tuple) and message[0] == "start_block":
			break

	if severity is None:
		severity = LogLevel.INFO

	# As a step towards always using ThemeString, convert all regular strings
	if isinstance(message, str):
		rmessage = [ThemeString(message, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
	else:
		rmessage = message

	return facility, severity, rmessage, remnants

Parser = namedtuple("Parser", "parser_name show_in_selector match_rules parser_rules")
parsers = []

def init_parser_list():
	"""
	Initialise the list of parsers
	"""

	# This pylint warning seems incorrect--does it not handle namedtuple.append()?
	# pylint: disable-next=global-variable-not-assigned
	global parsers

	# Get a full list of parsers from all parser directories
	# Start by adding files from the parsers directory

	parser_dirs = []
	parser_dirs += deep_get(cmtlib.cmtconfig, DictPath("Pod#local_parsers"), [])
	parser_dirs.append(PARSER_DIR)

	parser_files = []

	for parser_dir in parser_dirs:
		if parser_dir.startswith("{HOME}"):
			parser_dir = parser_dir.replace("{HOME}", HOMEDIR, 1)

		if not Path(parser_dir).is_dir():
			continue

		parser_dir = FilePath(parser_dir)

		if Path(parser_dir).joinpath("BUNDLE.yaml").is_file():
			path = FilePath(str(PurePath(parser_dir).joinpath("BUNDLE.yaml")))
			parser_files.append(path)
			continue

		for path in natsorted(Path(parser_dir).iterdir()):
			filename = PurePath(str(path)).name

			if filename.startswith(("~", ".")):
				continue
			if not filename.endswith((".yaml", ".yml")):
				continue

			parser_files.append(FilePath(str(path)))

	for parser_file in parser_files:
		if parser_file.endswith("BUNDLE.yaml"):
			temp_dl = secure_read_yaml_all(parser_file, directory_is_symlink = True)
			try:
				# This validates everything in one go
				dl = list(temp_dl)
			except yaml.composer.ComposerError as e:
				raise yaml.composer.ComposerError(f"{parser_file} is not valid YAML; aborting.") from e
			except yaml.parser.ParserError as e:
				raise yaml.parser.ParserError(f"{parser_file} is not valid YAML; aborting.") from e
			logparser_configuration.using_bundles = True
		else:
			try:
				d = secure_read_yaml(parser_file, directory_is_symlink = True)
			except yaml.composer.ComposerError as e:
				raise yaml.composer.ComposerError(f"{parser_file} is not valid YAML; aborting.") from e
			except yaml.parser.ParserError as e:
				raise yaml.parser.ParserError(f"{parser_file} is not valid YAML; aborting.") from e
			dl = [d]

		for parser_dict in dl:
			for parser in parser_dict:
				parser_name = parser.get("name", "")
				if len(parser_name) == 0:
					continue
				show_in_selector = parser.get("show_in_selector", False)
				matchrules = []
				for matchkey in parser.get("matchkeys"):
					pod_name = matchkey.get("pod_name", "")
					container_name = matchkey.get("container_name", "")
					image_name = matchkey.get("image_name", "")
					image_regex_raw = matchkey.get("image_regex", "")
					if len(image_regex_raw) > 0:
						image_regex = re.compile(image_regex_raw)
					else:
						image_regex = None
					container_type = matchkey.get("container_type", "container")
					# We need at least one way of matching
					if len(pod_name) == 0 and len(container_name) == 0 and len(image_name) == 0:
						continue
					matchrule = (pod_name, container_name, image_name, container_type, image_regex)
					matchrules.append(matchrule)

				if len(matchrules) == 0:
					continue

				parser_rules = parser.get("parser_rules")
				if parser_rules is None or len(parser_rules) == 0:
					continue

				rules = []
				for rule in parser_rules:
					if isinstance(rule, dict):
						rule_name = rule.get("name")
						if rule_name in ("angle_bracketed_facility",
								 "colon_facility",
								 "colon_severity",
								 "directory",
								 "expand_event",
								 "glog",
								 "modinfo",
								 "python_traceback",
								 "seconds_severity_facility",
								 "spaced_severity_facility",
								 "strip_ansicodes",
								 "sysctl",
								 "tab_separated",
								 "ts_8601"):
							rules.append(rule_name)
						elif rule_name in ("ansible_line",
								   "custom_splitter",
								   "diff_line",
								   "http",
								   "iptables",
								   "json",
								   "json_event",
								   "json_line",
								   "json_with_leading_message",
								   "key_value",
								   "key_value_with_leading_message",
								   "raw_formatter",
								   "yaml_line"):
							options = {}
							for key, value in deep_get(rule, DictPath("options"), {}).items():
								if key == "regex":
									regex = deep_get(rule, DictPath("options#regex"), "")
									value = re.compile(regex)
								options[key] = value
							rules.append((rule_name, options))
						elif rule_name == "substitute_bullets":
							prefix = rule.get("prefix", "* ")
							rules.append((rule_name, prefix))
						elif rule_name == "override_severity":
							overrides = []
							for override in deep_get(rule, DictPath("overrides"), []):
								matchtype = deep_get(override, DictPath("matchtype"))
								matchkey = deep_get(override, DictPath("matchkey"))
								_loglevel = deep_get(override, DictPath("loglevel"))

								if matchtype is None or matchkey is None or _loglevel is None:
									raise ValueError(f"Incorrect override rule in Parser {parser_file}; every override must define matchtype, matchkey, and loglevel")

								if matchtype == "regex":
									regex = deep_get(override, DictPath("matchkey"), "")
									matchkey = re.compile(regex)
								overrides.append({
									"matchtype": matchtype,
									"matchkey": matchkey,
									"loglevel": _loglevel,
								})
							rules.append((rule_name, overrides))
						elif rule_name in ("bracketed_severity", "bracketed_timestamp_severity_facility"):
							_loglevel = rule.get("default_loglevel", "info")
							try:
								default_loglevel = name_to_loglevel(_loglevel)
							except ValueError:
								sys.exit(f"Parser {parser_file} contains an invalid loglevel {_loglevel}; aborting.")
							rules.append((rule_name, default_loglevel))
						else:
							sys.exit(f"Parser {parser_file} has an unknown rule-type {rule}; aborting.")
					else:
						rules.append(rule)

				parsers.append(Parser(parser_name = parser_name, show_in_selector = show_in_selector, match_rules = matchrules, parser_rules = rules))

	# Fallback entries
	parsers.append(Parser(parser_name = "basic_8601_raw", show_in_selector = True, match_rules = [("raw", "", "", "container", None)], parser_rules = []))
	# This should always be last
	parsers.append(Parser(parser_name = "basic_8601", show_in_selector = True, match_rules = [("raw", "", "", "container", None)], parser_rules = ["ts_8601"]))

def get_parser_list() -> Set[Parser]:
	_parsers = set()
	for parser in parsers:
		if parser.show_in_selector == False:
			continue
		_parsers.add(parser.parser_name)

	return _parsers

# We've already defined the parser, so no need to do it again
def logparser_initialised(parser: Optional[Parser] = None, message: str = "", fold_msg: bool = True, line: int = 0) ->\
				Tuple[datetime,
				      str,
				      LogLevel,
				      Union[List[Union[ThemeRef, ThemeString]], Tuple[str, Optional[Callable], Dict]],
				      List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]]]:
	"""
	This is used when the parser is already initialised.

		Parameters:
			parser (Parser): The parser to use
			message (str): A line to parse
			fold_msg (bool): Should the message be folded (unmodified) or unfolded (expanded to multiple lines where possible)
			line (int): The line number
		Returns:
			(timestamp, facility, severity, message, remnants):
				timestamp (datetime): A timestamp
				facility (str): The log facility
				severity (int): Loglevel
				message (rstr): An unformatted string
				remnants ([(ThemeArray, LogLevel)]): Formatted remainders with severity
	"""

	# First extract the Kubernetes timestamp
	message, timestamp = split_iso_timestamp(message, none_timestamp())

	if parser is None:
		raise ValueError("logparser_initialised() called with parser == None")

	options = {
		"__line": line,
	}
	facility, severity, rmessage, remnants = custom_parser(message, filters = parser.parser_rules, fold_msg = fold_msg, options = options)

	max_untruncated_len = 16384
	if isinstance(rmessage, list) and themearray_len(cast(List[Union[ThemeRef, ThemeString]], rmessage)) > max_untruncated_len - 1:
		remnants = [([ThemeString(message[0:max_untruncated_len - 1], ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity)]
		severity = LogLevel.ERR
		rmessage = [ThemeString(f"Line too long ({len(message)} bytes); truncated to {max_untruncated_len} bytes (Use line wrapping to see the entire message)",
					ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]

	return timestamp, facility, severity, rmessage, remnants

# pylint: disable-next=too-many-arguments
def logparser(pod_name: str, container_name: str, image_name: str, message: str, fold_msg: bool = True,
	      override_parser: Optional[Parser] = None, container_type: str = "container", line: int = 0) ->\
			Tuple[datetime,
			      str,
			      LogLevel,
			      Union[List[Union[ThemeRef, ThemeString]], Tuple[str, Optional[Callable], Dict]],
			      List[Tuple[List[Union[ThemeRef, ThemeString]], LogLevel]],
			      Tuple[Optional[str], str],
			      Parser]:
	"""
	This (re-)initialises the parser; it will identify what parser rules to use
	helped by pod_name, container_name, and image_name;
	this allows for different containers in the same pod to use different parsers,
	and different versions of a pod to use different parsers

		Parameters:
			pod_name (str): The name of the pod
			container_name (str): The name of the container
			image_name (str): The name of the image
			message (str): A line to parse
			fold_msg (bool): Should the message be folded (unmodified) or unfolded (expanded to multiple lines where possible)
			override_parser (opaque): A reference to the parser rules to use instead of the autodetected parser
			container_type (str): container or init_container
			line (int): The line number
		Returns:
			(timestamp, facility, severity, message, remnants, (lparser, uparser), parser):
				timestamp (datetime): A timestamp
				facility (str): The log facility
				severity (int): Loglevel
				rmessage (ThemeArray): An unformatted string
				remnants ([tuple[ThemeArray, LogLevel]]): Formatted remainders with severity
				lparser (str): Subidentifiers to help explain what rules in the parser file are used
				uparser (str): Name of the parser file used
				parser (opaque): A reference to the parser rules that are used
	"""

	# First extract the Kubernetes timestamp
	message, timestamp = split_iso_timestamp(message, none_timestamp())

	if len(parsers) == 0:
		init_parser_list()

	rmessage = None

	if override_parser is not None:
		# Any other timestamps (as found in the logs) are ignored
		parser = None
		for parser in parsers:
			if parser.parser_name == override_parser:
				options = {
					"__line": line,
				}
				facility, severity, rmessage, remnants = custom_parser(message, filters = parser.parser_rules, fold_msg = fold_msg, options = options)
		# As a step towards always using ThemeString, convert all regular strings
		if rmessage is None:
			rmessage = [ThemeString(message, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
		return timestamp, facility, severity, rmessage, remnants, ("<override>", str(override_parser)), parser

	if image_name.startswith("docker-pullable://"):
		image_name = image_name[len("docker-pullable://"):]

	for parser in parsers:
		uparser = None
		lparser = None

		for pod_prefix, container_prefix, image_prefix, _container_type, image_regex in parser.match_rules:
			_image_name = image_name
			if image_prefix.startswith("/"):
				tmp = image_name.split("/", 1)
				if len(tmp) == 2:
					_image_name = f"/{tmp[1]}"

			if image_regex is None:
				regex_match = True
			else:
				tmp = image_regex.match(_image_name)
				regex_match = tmp is not None

			if pod_name.startswith(pod_prefix) and container_name.startswith(container_prefix) and \
			   _image_name.startswith(image_prefix) and container_type  == _container_type and regex_match == True:
				uparser = parser.parser_name
				options = {
					"__line": line,
				}
				facility, severity, rmessage, remnants = custom_parser(message, filters = parser.parser_rules, fold_msg = fold_msg, options = options)

				_lparser = []
				if len(pod_prefix) > 0:
					_lparser.append(pod_prefix)
				if len(container_prefix) > 0:
					_lparser.append(container_prefix)
				if len(image_prefix) > 0:
					_lparser.append(image_prefix)
				lparser = "|".join(_lparser)
				break

		if lparser is not None:
			break

	if uparser is None and (lparser is None or len(lparser) == 0):
		lparser = "<unknown format>"
		uparser = "basic_8601"
		parser = Parser(parser_name = "basic_8601", show_in_selector = True, match_rules = [("raw", "", "", "container", None)], parser_rules = ["ts_8601"])
		facility, severity, rmessage, remnants = custom_parser(message, filters = parser.parser_rules, fold_msg = fold_msg, options = {})

	if rmessage is None:
		rmessage = [ThemeString(message, ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]

	max_untruncated_len = 16384
	if isinstance(rmessage, list) and themearray_len(cast(List[Union[ThemeRef, ThemeString]], rmessage)) > max_untruncated_len - 1:
		remnants = [([ThemeString(message[0:max_untruncated_len - 1], ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity)]
		severity = LogLevel.ERR
		rmessage = [ThemeString(f"Line too long ({len(message)} bytes); truncated to {max_untruncated_len} bytes (Use line wrapping to see the entire message)",
					ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}"))]

	return timestamp, facility, severity, rmessage, remnants, (lparser, uparser), parser
