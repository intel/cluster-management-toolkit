#! /usr/bin/env python3
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

from collections import namedtuple
from datetime import datetime
import difflib
# ujson is much faster than json,
# but it might not be available
try:
	import ujson as json
	json_is_ujson = True
except ModuleNotFoundError:
	import json
	json_is_ujson = False
import os
from pathlib import Path
import re
import sys
import yaml

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-natsort")

import iktlib
from iktlib import deep_get, deep_get_with_fallback, format_yaml, format_yaml_line

HOMEDIR = str(Path.home())
IKTDIR = os.path.join(HOMEDIR, ".ikt")
PARSER_DIRNAME = "parsers"

class loglevel:
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
	loglevel.EMERG: "Emergency",
	loglevel.ALERT: "Alert",
	loglevel.CRIT: "Critical",
	loglevel.ERR: "Error",
	loglevel.WARNING: "Warning",
	loglevel.NOTICE: "Notice",
	loglevel.INFO: "Info",
	loglevel.DEBUG: "Debug",
	loglevel.DIFFPLUS: "Diffplus",
	loglevel.DIFFMINUS: "Diffminus",
	loglevel.DIFFSAME: "Diffsame",
	loglevel.ALL: "Debug",
}

class logparser_configuration:
	# Keep or strip timestamps in structured logs
	pop_ts = True
	# Keep or strip severity in structured logs
	pop_severity = True
	# Keep or strip facility in structured logs
	pop_facility = True
	# msg="foo" or msg=foo => foo
	msg_extract = True
	# If msg_extract is False,
	# this decides whether or not to put msg="foo" first or not
	# this also affects err="foo" and error="foo"
	msg_first = True
	# if msg_extract is True,
	# this decides whether msg="foo\nbar" should be converted to:
	# foo
	# bar
	# This does (currently) not affect "err=" and "error="
	msg_linebreaks = True
	# Should "* " be replaced with real bullets?
	msg_realbullets = True
	# collector=foo => • foo
	bullet_collectors = True
	# if msg_extract is True,
	# this decides whether should be converted to:
	# msg="Starting foo" version="(version=.*)" => Starting foo (version=.*)
	merge_starting_version = True

def json_dumps(obj):
	indent = 8
	if json_is_ujson:
		string = json.dumps(obj, indent = indent, escape_forward_slashes = False)
	else:
		string = json.dumps(obj, indent = indent)
	return string

def get_loglevel_names():
	# Ugly way of removing duplicate values from dict
	return list(dict.fromkeys(list(loglevel_mappings.values())))

def loglevel_to_name(severity):
	return loglevel_mappings[min(loglevel.DIFFSAME, severity)]

def name_to_loglevel(name):
	for severity in loglevel_mappings:
		if loglevel_mappings[severity].lower() == name.lower():
			return severity
	raise Exception(f"Programming error! Loglevel {name} does not exist!")

def month_to_numerical(month):
	months = [ "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec" ]
	month = str(month.lower()[0:3]).zfill(2)

	y = 1
	for tmp in months:
		if month == tmp:
			return str(y).zfill(2)
		y += 1

	raise TypeError("No matching month")

# Mainly used by glog
def letter_to_severity(letter, default = None):
	severities = {
		"F": loglevel.EMERG,
		"E": loglevel.ERR,
		"W": loglevel.WARNING,
		"N": loglevel.NOTICE,
		"C": loglevel.NOTICE,	# Used by jupyter for the login token
		"I": loglevel.INFO,
		"D": loglevel.DEBUG,
	}

	return severities.get(letter, default)

def str_4letter_to_severity(string, default = None):
	severities = {
		"CRIT": loglevel.CRIT,
		"FATA": loglevel.CRIT,
		"ERRO": loglevel.ERR,
		"WARN": loglevel.WARNING,
		"NOTI": loglevel.NOTICE,
		"INFO": loglevel.INFO,
		"DEBU": loglevel.DEBUG,
	}
	return severities.get(string, default)

def str_to_severity(string, default = None):
	severities = {
		"error": loglevel.ERR,
		"warn": loglevel.WARNING,
		"warning": loglevel.WARNING,
		"notice": loglevel.NOTICE,
		"info": loglevel.INFO,
		"debug": loglevel.DEBUG,
	}

	return severities.get(string.lower(), default)

def level_to_severity(level):
	severities = {
		"fatal": loglevel.CRIT,
		"error": loglevel.ERR,
		"eror": loglevel.ERR,
		"warning": loglevel.WARNING,
		"warn": loglevel.WARNING,
		"notice": loglevel.NOTICE,
		"noti": loglevel.NOTICE,
		"info": loglevel.INFO,
		"debug": loglevel.DEBUG,
		"debu": loglevel.DEBUG,
	}

	severity = severities.get(level, None)
	if severity is None:
		raise Exception(f"Unknown loglevel {level}")

	return severity

def lvl_to_4letter_severity(lvl):
	severities = {
		loglevel.CRIT: "CRIT: ",
		loglevel.ERR: "ERRO: ",
		loglevel.WARNING: "WARN: ",
		loglevel.NOTICE: "NOTI: ",
		loglevel.INFO: "INFO: ",
		loglevel.DEBUG: "DEBU: ",
	}

	return severities.get(lvl, "!ERROR IN LOGPARSER!")

def split_4letter_colon_severity(message, severity = loglevel.INFO):
	severities = {
		"CRIT: ": loglevel.CRIT,
		"FATA: ": loglevel.CRIT,
		"ERRO: ": loglevel.ERR,
		"WARN: ": loglevel.WARNING,
		"NOTI: ": loglevel.NOTICE,
		"INFO: ": loglevel.INFO,
		"DEBU: ": loglevel.DEBUG,
	}

	_severity = severities.get(message[0:len("ERRO: ")], -1)
	if _severity != -1:
		severity = _severity
		message = message[len("ERRO: "):]

	return message, severity

def split_4letter_spaced_severity(message, severity = loglevel.INFO):
	severities = {
		"CRIT": loglevel.CRIT,
		"FATA": loglevel.CRIT,
		"ERRO": loglevel.ERR,
		"WARN": loglevel.WARNING,
		"NOTI": loglevel.NOTICE,
		"INFO": loglevel.INFO,
		"DEBU": loglevel.DEBUG,
	}

	tmp = re.match(r"\s*([a-zA-Z]{4})\s+(.*)", message)
	if tmp is not None:
		severity = severities.get(tmp[1], severity)
		message = tmp[2]

	return message, severity

def split_bracketed_severity(message, default = loglevel.INFO):
	severities = {
		"[FATAL]": loglevel.CRIT,
		"[ERROR]": loglevel.ERR,
		"[error]": loglevel.ERR,
		"[ERR]": loglevel.ERR,
		"[WARNING]": loglevel.WARNING,
		"[Warning]": loglevel.WARNING,
		"[warning]": loglevel.WARNING,
		"[WARN]": loglevel.WARNING,
		"[NOTICE]": loglevel.NOTICE,
		"[notice]": loglevel.NOTICE,
		"[INFO]": loglevel.INFO,
		"[info]": loglevel.INFO,
		"[System]": loglevel.INFO,	# mysql seems to have its own loglevels
		"[Note]": loglevel.INFO,	# none of which makes every much sense
		"[DEBUG]": loglevel.DEBUG,
		"[debug]": loglevel.DEBUG,
	}

	tmp = re.match(r"^(\[[A-Za-z]+?\]) ?(.*)", message)
	if tmp is not None:
		severity = severities.get(tmp[1])
		if severity is not None:
			message = tmp[2]
		else:
			severity = default
	else:
		severity = default

	return message, severity

# Possibly klog style?
def split_tuned_style(message, facility = None, default = loglevel.INFO):
	severities = {
		"FATAL   ": loglevel.CRIT,
		"ERROR   ": loglevel.ERR,
		"WARNING ": loglevel.WARNING,
		"INFO    ": loglevel.INFO,
	}

	tmp = re.match(r"^([A-Za-z ]+) (.*?): (.*)", message)
	if tmp is not None:
		severity = severities.get(tmp[1])
		if severity is not None:
			facility = tmp[2]
			message = tmp[3]
		else:
			severity = default
	else:
		severity = default

	return message, facility, severity

def split_colon_severity(message, severity = loglevel.INFO):
	severities = {
		"CRITICAL:": loglevel.CRIT,
		"ERROR:": loglevel.ERR,
		"WARNING:": loglevel.WARNING,
		"NOTICE:": loglevel.NOTICE,
		"INFO:": loglevel.INFO,
		"DEBUG:": loglevel.DEBUG,
	}

	tmp = re.match(r"^([A-Za-z]+?:) ?(.*)", message)
	if tmp is not None:
		severity = severities.get(tmp[1].upper(), severity)
		message = tmp[2]

	return message, severity

# Will split timestamp from messages that begin with timestamps of the form:
# 2020-02-07T13:12:24.224Z (Z = UTC)
# 2020-02-13T12:06:18.011345 [+-]0000 (+/-timezone)
# 2020-09-23T17:12:32.18396709[+-]03:00
# 2020-02-13T12:06:18[+-]0000 (+/-timezone)
# 2020-02-20 13:47:41,008 (assume UTC)
# 2020-02-20 13:47:41.008416 (assume UTC)
# 2020-02-20 13:47:41.008416Z (Z = UTF)
# 2020-02-20 13:47:41 (assume UTC)
# Technically not in ISO format, but close enough;
# at least the order is sensible
# 2020/02/20 13:47:41.008416 (assume UTC)
# 2020/02/20 13:47:41 (assume UTC)
def split_iso_timestamp(message, timestamp):
	tmp_timestamp = timestamp

	while True:
		# 2020-02-07 13:12:24.224
		# 2020-02-07 13:12:24,224
		# [2020-02-07 13:12:24.224]
		# [2020-02-07 13:12:24,224]
		tmp = re.match(r"^\[?(\d\d\d\d-\d\d-\d\d) (\d\d:\d\d:\d\d)(,|\.)(\d+)\]? ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp is None:
				ymd = tmp[1]
				hms = tmp[2]
				_sep = tmp[3]
				ms = tmp[4]
				tmp_timestamp = f"{ymd} {hms}.{ms}+0000"
			message = tmp[5]
			break

		# 2020-02-07T13:12:24.224Z (Z = UTC)
		tmp = re.match(r"^(\d\d\d\d-\d\d-\d\d)T(\d\d:\d\d:\d\d\.\d+)Z ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp is None:
				ymd = tmp[1]
				hmsms = tmp[2][0:len("HH:MM:SS.sss")]
				tmp_timestamp = f"{ymd} {hmsms}+0000"
			message = tmp[3]
			break

		# 2020-02-13T12:06:18.011345 [+-]00:00 (+timezone)
		# 2020-09-23T17:12:32.183967091[+-]03:00
		tmp = re.match(r"^(\d\d\d\d-\d\d-\d\d)T(\d\d:\d\d:\d\d\.\d+) ?([\+-])(\d\d):(\d\d) ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp is None:
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
		tmp = re.match(r"^\[?(\d\d\d\d-\d\d-\d\d)[ T](\d\d:\d\d:\d\d) ?([\+-])(\d\d):?(\d\d)\]? ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp is None:
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
		tmp = re.match(r"^(\d\d\d\d)[-/](\d\d)[-/](\d\d) (\d\d:\d\d:\d\d\.\d+)[Z:]? ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp is None:
				year = tmp[1]
				month = tmp[2]
				day = tmp[3]
				hmsms = tmp[4][0:len("HH:MM:SS.sss")]
				tmp_timestamp = f"{year}-{month}-{day} {hmsms}+0000"
			message = tmp[5]
			break

		# [2021-12-18T20:15:36Z]
		# 2021-12-18T20:15:36Z
		tmp = re.match(r"^\[?(\d\d\d\d-\d\d-\d\d)T(\d\d:\d\d:\d\d)Z\]? ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp is None:
				ymd = tmp[1]
				hms = tmp[2]
				tmp_timestamp = f"{ymd} {hms}.000+0000"
			message = tmp[3]
			break


		# 2020-02-20 13:47:41 (assume UTC)
		# 2020/02/20 13:47:41 (assume UTC)
		tmp = re.match(r"^(\d\d\d\d)[-/](\d\d)[-/](\d\d) (\d\d:\d\d:\d\d) ?(.*)", message)
		if tmp is not None:
			if tmp_timestamp is None:
				year = tmp[1]
				month = tmp[2]
				day = tmp[3]
				hms = tmp[4]
				tmp_timestamp = f"{year}-{month}-{day} {hms}.000+0000"
			message = tmp[5]
			break

		break

	if timestamp is None and tmp_timestamp is not None:
		timestamp = datetime.strptime(tmp_timestamp, "%Y-%m-%d %H:%M:%S.%f%z")

	# message + either a timestamp or None is passed in, so it's safe just to return it too
	return message, timestamp

def strip_iso_timestamp(message):
	message, _timestamp = split_iso_timestamp(message, None)
	return message

# 2020-02-20 13:47:01.531 GMT
def strip_iso_timestamp_with_tz(message):
	tmp = re.match(r"^\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d [A-Z]{3}(\s+?|$)(.*)", message)
	if tmp is not None:
		message = tmp[2]
	return message

# Will split timestamp from messages that begin with timestamps of the form:
# [10/Feb/2020:23:09:45 [+-]0000]<message>
def split_dd_mmm_yyyy_timestamp(message, timestamp):
	tmp = re.match(r"^\[(\d\d)/([A-Z][a-z][a-z])/(\d+):(\d\d:\d\d:\d\d) ([\+-])(\d\d)(\d\d)\](.*)", message)

	if tmp is not None:
		if timestamp is None:
			year = tmp[3]
			month = month_to_numerical(tmp[2])
			day = tmp[1]
			hms = tmp[4]
			tzsign = tmp[5]
			tzhour = tmp[6]
			tzmin = tmp[7]

			tmp_timestamp = f"{year}-{month}-{day} {hms}.000{tzsign}{tzhour}{tzmin}"
			timestamp = datetime.strptime(tmp_timestamp, "%Y-%m-%d %H:%M:%S.%f%z")

		message = tmp[8]

	return message, timestamp

# Will split timestamp from messages that begin with timestamps of the form:
# Sat Feb 22 00:13:44 2020 <message>
def split_wd_mmm_dd_hh_mm_ss_yyyy_timestamp(message, timestamp):
	tmp = re.match(r"^[A-Z][a-z][a-z] ([A-Z][a-z][a-z]) *(\d*) (\d\d:\d\d:\d\d) (\d\d\d\d) (.*)", message)

	if tmp is not None:
		if timestamp is None:
			year = tmp[4]
			month = month_to_numerical(tmp[1])
			day = tmp[2]
			hms = tmp[3]
			tmp_timestamp = f"{year}-{month}-{day} {hms}.000+0000"
			timestamp = datetime.strptime(tmp_timestamp, "%Y-%m-%d %H:%M:%S.%f%z")
		message = tmp[5]

	return message, timestamp

# Will split messages of the format into ISO-8601 timestamp + message
# 10.32.0.1 - - [22/Feb/2020:16:34:30 +0000] "GET / HTTP/1.1" 200 6 " [...]
# 10.32.0.1 - [10.32.0.1] - - [10/Feb/2020:23:10:25 +0000] [...]
def split_http_style(message, timestamp):
	# For messages of the format
	tmp = re.match(r"^(\d+\.\d+\.\d+\.\d+ - .*?) \[(\d\d)/([A-Z][a-z][a-z])/(\d+).(\d\d:\d\d:\d\d).*?\] (.*)", message)
	if tmp is not None:
		if timestamp is None:
			year = tmp[4]
			month = month_to_numerical(tmp[3])
			day = tmp[2]
			hms = tmp[5]
			if "." in hms:
				tmp_timestamp = f"{year}-{month}-{day} {hms}+0000"
			else:
				tmp_timestamp = f"{year}-{month}-{day} {hms}.000+0000"
			timestamp = datetime.strptime(tmp_timestamp, "%Y-%m-%d %H:%M:%S.%f%z")
		message = "%s %s" % (tmp[1], tmp[6])
	return message, timestamp

# log messages of the format:
# E0514 09:01:55.108028382       1 server_chttp2.cc:40]
# I0511 14:31:10.500543       1 start.go:76]
def split_glog(message, severity = None):
	match = False
	facility = ""
	loggingerror = None
	remnants = []

	# Workaround a bug in use of glog; to make the logged message useful
	# we separate it from the warning about glog use; this way we can get the proper severity
	if message.startswith("ERROR: logging before flag.Parse: "):
		loggingerror = message[0:len("ERROR: logging before flag.Parse")]
		message = message[len("ERROR: logging before flag.Parse: "):]

	tmp = re.match(r"^([A-Z])\d\d\d\d \d\d:\d\d:\d\d\.\d+\s+(\d+)\s(.+?:\d+)\]\s(.*)", message)
	if tmp is not None:
		severity = letter_to_severity(tmp[1])

		# We don't really care about the pid,
		# but let's assign it just to document what it is
		pid = tmp[2]

		facility = "%s" % (tmp[3])
		message = "%s" % (tmp[4])
		match = True
	else:
		if severity is None:
			severity = loglevel.INFO

	# If we have a logging error we return that as message and the rest as remnants
	if loggingerror is not None:
		remnants.insert(0, (message, severity))
		message = loggingerror
		severity = loglevel.ERR

	return message, severity, facility, remnants, match

# \tINFO\tcontrollers.Reaper\tstarting reconciliation\t{"reaper": "default/k8ssandra-cluster-a-reaper-k8ssandra"}
def __split_severity_facility_style(message, severity = loglevel.INFO, facility = ""):
	tmp = re.match(r"^\s*([A-Z]+)\s+([a-zA-Z-\.]+)\s+(.*)", message)
	if tmp is not None:
		severity = str_to_severity(tmp[1], default = severity)
		facility = tmp[2]
		message = tmp[3]

	return message, severity, facility

def split_json_style(message, severity = loglevel.INFO, facility = "", fold_msg = True, options = {}):
	logentry = None
	remnants = None

	messages = options.get("messages", ["msg", "message"])
	errors = options.get("errors", ["err", "error"])
	timestamps = options.get("timestamps", ["ts", "time", "timestamp"])
	severities = options.get("severities", ["level"])
	facilities = options.get("facilities", ["logger", "caller", "filename"])

	try:
		logentry = json.loads(message)
	except ValueError as e:
		pass

	# Unfold Python dicts
	if logentry is None:
		d = None
		try:
			d = eval(message)
		# FIXME: We need a tighter exception here
		except:
			pass

		if d is not None:
			try:
				logentry = json_dumps(d)
			except ValueError as e:
				pass

	if logentry is not None and type(logentry) == dict:
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
			facility = deep_get_with_fallback(logentry, facilities, "")
		if logparser_configuration.pop_facility == True:
			for _fac in facilities:
				logentry.pop(_fac, None)

		if level is not None:
			severity = str_to_severity(level)

		# If the message is folded, append the rest
		if fold_msg == True:
			msgseverity = severity
			# Append all remaining fields to message
			if msg == "":
				message = str(logentry)
			else:
				if logparser_configuration.msg_extract == True:
					# Pop the first matching _msg
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
			if severity == loglevel.DEBUG:
				structseverity = severity
			else:
				structseverity = loglevel.INFO

			if "err" not in logentry and "error" not in logentry:
				msgseverity = severity
			else:
				msgseverity = structseverity
			errorseverity = severity
			if logparser_configuration.msg_extract == True:
				message = msg
				# Pop the first matching _msg
				for _msg in messages:
					if _msg in logentry:
						logentry.pop(_msg, None)
						break
			else:
				message = ""

			if len(logentry) > 0:
				if structseverity == loglevel.DEBUG:
					override_formatting = ("logview", f"severity_{loglevel_to_name(structseverity).lower()}")
				else:
					override_formatting = {
						"\"msg\"": {
							"key": ("types", "yaml_key"),
							"value": ("logview", f"severity_{loglevel_to_name(msgseverity).lower()}")
						},
						"\"err\"": {
							"key": ("types", "yaml_key_error"),
							"value": ("logview", f"severity_{loglevel_to_name(errorseverity).lower()}")
						},
						"\"error\"": {
							"key": ("types", "yaml_key_error"),
							"value": ("logview", f"severity_{loglevel_to_name(errorseverity).lower()}")
						}
					}
				dump = json_dumps(logentry)
				tmp = format_yaml([dump], override_formatting = override_formatting)
				remnants = []
				if len(message) == 0:
					message = tmp[0]
					tmp.pop(0)
					msgseverity = structseverity
				for line in tmp:
					remnants.append((line, severity))
	else:
		msgseverity = severity

	return message, msgseverity, facility, remnants

def split_json_style_raw(message, severity = loglevel.INFO, facility = "", fold_msg = True, options = {}, merge_message = False):
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

	if merge_message == True:
		remnants = [(_message, severity)] + _remnants
		message = ""
	else:
		remnants = _remnants

	return message, severity, facility, remnants

def json_event(message, severity = loglevel.INFO, facility = "", fold_msg = True, options = {}):
	remnants = []
	tmp = message.split(" ", 2)

	# At least events from weave seems to be able to end up with \0; remove them
	message.replace("\0", "")

	if not message.startswith("EVENT ") or len(tmp) < 3:
		return message, severity, facility, remnants

	event = tmp[1]

	if event in ["AddPod", "DeletePod", "AddNamespace", "DeleteNamespace"] or (event in ["UpdatePod", "UpdateNamespace"] and not "} {" in tmp[2]):
		msg = tmp[2]
		_message, _severity, _facility, remnants = split_json_style_raw(message = msg, severity = severity, facility = facility, fold_msg = fold_msg, options = options, merge_message = True)
		message = f"{tmp[0]} {event}"
		if event in ["UpdatePod", "UpdateNamespace"]:
			message = [(f"{tmp[0]} {event}", ("logview", f"severity_{loglevel_to_name(severity).lower()}")), (" [No changes]", ("logview", f"unchanged"))]
	elif event in ["UpdatePod", "UpdateNamespace"]:
		tmp2 = re.match(r"^({.*})\s*({.*})", tmp[2])
		if tmp2 is not None:
			old = json.loads(tmp2[1])
			old_str = json_dumps(old)
			try:
				new = json.loads(tmp2[2])
			except ValueError as e:
				message = [(f"{tmp[0]} {event}", ("logview", f"severity_{loglevel_to_name(severity).lower()}")), (" [Error: could not parse JSON]", ("logview", f"severity_error"))]
				remnants = [(tmp[2], severity)]
				return message, severity, facility, remnants
			new_str = json_dumps(new)

			remnants = []
			y = 0
			for el in difflib.unified_diff(old_str.split("\n"), new_str.split("\n"), n = sys.maxsize, lineterm = ""):
				y += 1
				if y < 4:
					continue
				if el.startswith("+"):
					remnants.append((el, loglevel.DIFFPLUS))
				elif el.startswith("-"):
					remnants.append((el, loglevel.DIFFMINUS))
				else:
					remnants.append((format_yaml_line(el), loglevel.DIFFSAME))
			message = [(f"{tmp[0]} {event}", ("logview", f"severity_{loglevel_to_name(severity).lower()}")), (" [State modified]", ("logview", f"modified"))]
	else:
		sys.exit(f"json_event: Unknown EVENT type:\n{message}")

	return message, severity, facility, remnants

# log messages of the format:
# 2020-05-14 08:25:24.481670: I tensorflow/stream_executor/platform/default/dso_loader.cc:44] Successfully opened dynamic library libcudart.so.10.1
# This also handles facilities that lack a line#
def split_tensorflow_style(message, timestamp, severity = loglevel.INFO, facility = ""):
	tmp = re.match(r"^\d+-\d\d-\d\d \d\d:\d\d:\d\d\.\d+: ([A-Z]) (.+?:?\d*)\] (.*)", message)
	if tmp is not None:
		tmpseverity = letter_to_severity(tmp[1])
		severity = min(tmpseverity, severity)
		facility = tmp[2]
		message = tmp[3]
	return message, timestamp, severity, facility

def split_angle_bracketed_facility(message, facility = ""):
	tmp = re.match(r"^<(.+?)>\s?(.*)", message)
	if tmp is not None:
		facility = tmp[1]
		message = tmp[2]
	return message, facility

def split_colon_facility(message, facility = ""):
	tmp = re.match(r"^(\S+?):\s?(.*)", message)
	if tmp is not None:
		facility = tmp[1]
		message = tmp[2]
	return message, facility

def split_msg(rawmsg):
	# We only want "\n" to represent newlines
	tmp = rawmsg.replace("\r\n", "\n")
	return list(map(str.rstrip, tmp.splitlines()))

def replace_tabs(message):
	if type(message) is str:
		message = message.replace("\t", " ")
	elif type(message) is tuple:
		if type(message[1]) is tuple:
			message = (message[0].replace("\t", " "), message[1])
	elif type(message) is list:
		for i in range(0, len(message)):
			message[i] = replace_tabs(message[i])

	return message

# Basic with colon severity prefix (with ISO8601 timestamps):
# Only split the lines and separate out timestamps
def basic_8601_colon_severity(message, fold_msg = True):
	facility = ""
	remnants = []

	message, severity = split_colon_severity(message)

	return facility, severity, message, remnants

# Basic (with ISO8601 timestamps):
# Only split the lines and separate out timestamps
def basic_8601(message, fold_msg = True):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	# Some messages have double timestamps...
	message, _timestamp = split_iso_timestamp(message, None)

	return facility, severity, message, remnants

# basic_8601 but with no removal of double timestamps
def basic_8601_raw(message, fold_msg = True):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	return facility, severity, message, remnants

def strip_bracketed_pid(message):
	tmp = re.match(r"^\[\d+\]\s*(.*)", message)
	if tmp is not None:
		message = tmp[1]
	return message

def strip_ansicodes(message):
	tmp = re.findall(r"(\x1b\[\d*m|\x1b\[\d+;\d+m|\x1b\[\d+;\d+;\d+m|.*?)", message)
	if tmp is not None:
		message = "".join(item for item in tmp if not item.startswith("\x1b"))

	return message

def split_bracketed_timestamp_severity_facility(message, default = loglevel.INFO):
	severity = default
	facility = ""

	tmp = re.match(r"\[(.*?) (.*?) (.*?)\]: (.*)", message)

	if tmp is not None:
		severity = str_to_severity(tmp[2])
		facility = tmp[3]
		message = tmp[4]

	return message, severity, facility

# kube-app-manager
# 2020-12-27T02:57:49.788Z        INFO    controller-runtime.metrics      metrics server is starting to listen    {"addr": "127.0.0.1:8080"}
# 2020-12-27T02:57:49.789Z        INFO    setup   starting kube-app-manager
# I1227 02:57:49.887903       1 leaderelection.go:242] attempting to acquire leader lease  application-system/controller-leader-election-helper...
# 2020-12-27T02:57:49.887Z        INFO    controller-runtime.manager      starting metrics server {"path": "/metrics"}
# I1227 02:57:49.926209       1 leaderelection.go:252] successfully acquired lease application-system/controller-leader-election-helper
def kube_app_manager(message, fold_msg = True):
	remnants = []

	message, _timestamp = split_iso_timestamp(message, None)
	message, severity, facility, remnants, _match = split_glog(message)
	message, severity, facility = __split_severity_facility_style(message, severity, facility)

	tmp = re.match(r"^(.*?)\s*?({.*})", message)
	if tmp is not None:
		message = tmp[1]
		extra_message, _severity, _facility, remnants = split_json_style(tmp[2], severity = severity, facility = facility, fold_msg = fold_msg)
		if len(extra_message) > 0:
			if remnants is None or len(remnants) == 0:
				message = f"{messsage}  {extra_message}"
			else:
				raise Exception(f"message: {message}\nextra_message: {extra_message}")

	return facility, severity, message, remnants

# katib-controller
# {"level":"info","ts":1586872332.7322807,"logger":"entrypoint","msg":"Registering Components."}
# XXX: Use split_json_style
def kube_parser_json(message, fold_msg = True, glog = False):
	facility = ""
	severity = loglevel.INFO
	remnants = None

	try:
		logentry = json.loads(message)

		msg = logentry.pop("msg", "")
		level = logentry.pop("level", "")
		logentry.pop("ts", None)
		logentry.pop("time", None)
		logentry.pop("timestamp", None)

		logger = logentry.pop("logger", None)
		caller = logentry.pop("caller", None)

		if level is not None:
			tmpseverity = str_to_severity(level)
		else:
			tmpseverity = loglevel.INFO

		# Doesn't this overpromote debug messages?
		severity = min(tmpseverity, severity)

		if facility == "":
			if caller is not None:
				facility = caller
			elif logger is not None:
				facility = logger

		# If the message is folded, append the rest
		if fold_msg == True:
			tmp = ""
			if msg == "":
				message = str(logentry)
			else:
				# Escape newlines
				msg = msg.replace("\n", "\\n")

				if len(logentry) > 0:
					message = f"{msg}  {logentry}"
				else:
					message = msg

			if severity > loglevel.NOTICE and "version" in message:
				severity = loglevel.NOTICE

			message, severity = split_bracketed_severity(message, severity)
		# else return an expanded representation
		else:
			message = msg

			if severity > loglevel.NOTICE and "version" in message:
				severity = loglevel.NOTICE

			message, severity = split_bracketed_severity(message, severity)
			if len(logentry) > 0:
				# Don't make the mistake of setting the loglevel higher than that of the main message
				if severity < loglevel.INFO:
					tmpseverity = loglevel.INFO
				else:
					tmpseverity = severity
				remnants = (json_dumps(logentry), tmpseverity)
			if "\n" in message:
				tmp = message.split("\n")
				message = tmp[0]
				tmpremnants = []
				for remnant in tmp[1:]:
					tmpremnants.append((remnant, tmpseverity))
				if remnants is None:
					remnants = tmpremnants
				elif len(tmpremnants) > 0:
					remnants = tmpremnants + remnants
	# FIXME: We need a tighter exception here
	except Exception as e:
		# We might receive kubernetes style error messages
		if glog == True:
			message, severity, facility, remnants, _match = split_glog(message)
		else:
			e.args = e.args + (f"Original message: {message}",)
			raise e.with_traceback(e.__traceback__)

	return facility, severity, message, remnants

def kube_parser_json_glog(message, fold_msg = True):
	return kube_parser_json(message, fold_msg = fold_msg, glog = True)

def override_severity(message, severity, facility = None):
	if type(message) != str:
		return message, severity

	# Exceptions
	override_notice = (
		"version ",
		"Version: ",
		"\"Version info\"",

		"Kiali: Version: ",
		"Kiali: Console version: ",
		"Kubernetes host: ",
		"NodeName: ",
		"OpenShift Web Console Version",
		"  Release:    ",
		"running version",
		"\"Starting Kubernetes Scheduler\"",
		"\"Starting Prometheus\"",
		"Starting Prometheus Operator version ",
		"Starting Tiller",
		"Starting Weaveworks NPC ",
		"TensorBoard ",
		"Workflow Controller (version: ",
	)
	override_warning = (
		"Aborted connection",
		"failed to ",
		"Flag --insecure-port has been deprecated",
		"Flag --port has been deprecated",
	)
	override_err = (
		"Error checking version: ",
		"http: proxy error",
		"http: TLS handshake error",
	)
	override_alert = (
		"panic: ",
	)

	if message.startswith(override_notice):
		severity = min(severity, loglevel.NOTICE)
	elif message.startswith(override_warning):
		severity = min(severity, loglevel.WARNING)
	elif message.startswith(override_err):
		severity = min(severity, loglevel.ERR)
	elif message.startswith(override_alert):
		severity = min(severity, loglevel.ALERT)
	# Trace messages are annoying, set them to debug severity
	elif message.startswith("Trace["):
		severity = loglevel.DEBUG
	elif facility is not None and facility.startswith("trace.go"):
		severity = loglevel.DEBUG

	return message, severity

def custom_override_severity(message, severity, overrides = []):
	# FIXME: override_severity isn't implemented for strarrays yet
	if type(message) == list:
		return severity

	for override in overrides:
		override_type = override[0]
		override_pattern = override[1]
		override_severity = override[2]

		if override_type == "startswith":
			if not message.startswith(override_pattern):
				continue
		elif override_type == "endswith":
			if not message.endswith(override_pattern):
				continue
		elif override_type == "regex":
			tmp = re.match(override_pattern, message)
			if tmp is None:
				continue
		else:
			raise Exception(f"Unknown override_type '{override_type}'; this is a programming error.")

		severity = override_severity
		break

	return severity

def expand_event(message, severity, remnants = None, fold_msg = True):
	if fold_msg == True or (remnants is not None and len(remnants) > 0):
		return message, remnants

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
			else:
				refend = i
		elif message[i] == ")":
			parendepth -= 1
			if parendepth == 0:
				if curlydepth > 0:
					# Abort parsing; assume that this message is either malformed
					# or that the parser is flawed
					return message, remnants
				else:
					eventend = i
					break

	remnants = []
	message = raw_message[0:eventstart]
	indent = 8
	remnants.append(([(" ".ljust(indent) + raw_message[eventstart:refstart], ("types", "yaml_reference"))], severity))
	for key_value in raw_message[refstart:refend].split(", "):
		key, value = key_value.split(":", 1)
		remnants.append(([(" ".ljust(indent * 2) + key, ("types", "yaml_key")), ("separators", "yaml_key_separator"), (f" {value}", ("types", "yaml_value"))], severity))
	remnants.append(([(" ".ljust(indent * 1) + raw_message[refend:eventend], ("types", "yaml_reference"))], severity))
	remnants.append(([(raw_message[eventend:eventend + 3], ("types", "generic")), (raw_message[eventend + 3:len(raw_message)], ("types", "generic"))], severity))

	return message, remnants

def expand_header_key_value(message, severity, remnants = None, fold_msg = True):
	if fold_msg == True or (remnants is not None and len(remnants) > 0):
		return message, remnants

	header = ""

	# Split into substrings based on spaces
	tmp = re.findall(r"(?:\".*?\"|\S)+", message)

	if tmp is not None and len(tmp) > 0:
		if "=" not in tmp[0]:
			header = f"{tmp[0]}: "
			tmp = tmp[1:]

		res = {}
		for item in tmp:
			# First split into [key, value]
			tmp2 = item.split("=", 1)
			if len(tmp2) < 2:
				# We found a non key=value item; treat the entire string as non-key=value
				res = {}
				break

			# Now add key: value into the dict
			if tmp2[1].startswith("”"):
				if not tmp2[1].endswith("”"):
					raise Exception(f"kube_parser_structured_glog(): unbalanced quotes in item: {item}")
				else:
					res[tmp2[0]] = tmp2[1][1:-1]
			else:
				# Now we restore the quotation marks; fancy quotes should be paired,
				# and since we cannot do that we shouldn't pretend that we did
				res[tmp2[0]] = tmp2[1].replace("”", "\"")

		if len(res) > 0:
			if res.get("msg") is not None:
				message = f"{header}{res['msg']}"
			else:
				message = header

			for entry, value in res.items():
				if severity > loglevel.INFO:
					tmpseverity = loglevel.INFO
				else:
					tmpseverity = severity

				# We have already extracted the message
				if entry == "msg":
					continue
				# We should already have a timestamp
				elif entry in ["ts", "time"]:
					continue
				elif entry == "caller":
					if facility == "":
						facility = value
					continue
				elif entry == "source":
					if facility == "":
						facility = value
					continue
				elif entry == "Topic":
					if facility == "":
						facility = value
					continue
				elif entry == "level":
					# This is used as severity by prometheus
					s = str_to_severity(value, -1)
					if s != -1 and s < severity:
						severity = s
					continue
				elif entry == "err":
					# alertmanager sometimes folds up multiple errors on one line;
					# try to unfold them
					tmpseverity = severity
					tmp = re.match(r"(\d+ errors occurred:)(.*)", value)
					if tmp is not None:
						remnants.append((f"{entry}: {tmp[1]}\n", tmpseverity))
						s = tmp[2].replace("\\t", "").split("\\n")
						for line in s:
							if len(line) > 0:
								if line.startswith("* "):
									remnants.append(("   {line}\n", tmpseverity))
								else:
									remnants.append(("   * {line}\n", tmpseverity))
						continue
				elif entry == "error":
					tmpseverity = severity
				# Should we highlight this too?
				#elif entry == "cluster-version":
				#	tmpseverity = loglevel.NOTICE
				elif entry in ["version", "git-commit"]:
					tmpseverity = loglevel.NOTICE
				elif entry == "Workflow":
					if message.startswith("Syncing Workflow") and value in message:
						continue
				elif entry == "component":
					# this should have loglevel.INFO or lower severity
					tmpseverity = max(loglevel.INFO, severity, tmpseverity)

				remnants.append(([(entry, ("types", "key")), ("separators", "keyvalue_log"), (value, ("types", "value"))], tmpseverity))
			if len(message) == 0:
				message = remnants[0]
				remnants.pop(0)

	return message, remnants

# metrics-server/metrics-server
# Example(s):
# I0221 23:26:05.862399       1 server.go:150] Version: v1.17.3
# E0702 11:03:23.913858859       1 server_chttp2.cc:40]        {"created":
# http-style messages
# [10/Feb/2020:23:09:45 +0000]TCP200000.000
def kube_parser_1(message, fold_msg = True):
	remnants = None

	message, severity, facility, remnants, match = split_glog(message)
	if match == True and remnants is not None:
		# Event(v1.ObjectReference{.*}):
		if message.startswith("Event(v1.ObjectReference{"):
			message, remnants = expand_event(message, severity, remnants = remnants, fold_msg = fold_msg)
		elif message.startswith("\"Event occurred\""):
			message, remnants = expand_header_key_value(message, severity, remnants = remnants, fold_msg = fold_msg)

		message, severity = override_severity(message, severity)
		return facility, severity, message, remnants

	message, _timestamp = split_http_style(message, None)

	# For messages of the format
	# [10/Feb/2020:23:09:45 +0000][...]
	message, _timestamp = split_dd_mmm_yyyy_timestamp(message, None)

	# tensorflow-style
	message, _timestamp, severity, facility = split_tensorflow_style(message, None, severity, facility)

	# Some logs have the severity before the timestamp
	message, tmpseverity = split_colon_severity(message, severity)
	severity = min(tmpseverity, severity)

	# Another timestamp to strip
	message, _timestamp = split_iso_timestamp(message, None)

	# While other logs have the severity after the timestamp
	message, tmpseverity = split_colon_severity(message, severity)
	severity = min(tmpseverity, severity)

	# tuned (possibly others) can have some messages with yet another format
	message, facility, tmpseverity = split_tuned_style(message, facility = facility)
	severity = min(tmpseverity, severity)

	# For messages of the format
	# [main] 2021/03/27 20:45:25 Starting Tiller v2.16.10 (tls=false)
	message, facility = split_tiller_style(message, facility = facility)

	# For messages of the format
	# W facility.cc] [...]
	# I suspect that this should be handled by split_tensorflow_style
	tmp = re.match(r"^([A-Z]) (.*?:\d+)] (.*)", message)
	if tmp is not None:
		# XXX: This is just to be able to debug this
		raise Exception(f"triggered by message: {message}")
		severity = letter_to_severity(tmp[1])
		facility = tmp[2]
		message = tmp[3]

	# JSON/Python dict
	message, severity, facility, remnants = split_json_style(message, severity = severity, facility = facility, fold_msg = fold_msg)
	message, severity = override_severity(message, severity)

	return facility, severity, message, remnants

# seldon-controller-manager:
# 2020-06-24T09:16:12.085Z        INFO    controller-runtime.metrics      metrics server is starting to listen    {"addr": ":8080"}
# github.com/go-logr/zapr.(*zapLogger).Error
#         /go/pkg/mod/github.com/go-logr/zapr@v0.1.0/zapr.go:128
def seldon(message, fold_msg = True):
	remnants = None
	severity = loglevel.INFO
	facility = ""

	# Another timestamp to strip
	message, _timestamp = split_iso_timestamp(message, None)

	# This log uses a rather special format for severity and facility
	tmp = re.match(r"^\s*([A-Z]+)\s*([-a-zA-Z.]*)\s*(.*)", message)
	if tmp is not None:
		severity = str_to_severity(tmp[1])
		facility = tmp[2]
		message = tmp[3]

	# Some log messages have an additional JSON portion at the end;
	# expand it if available and the configuration requests this
	tmp = re.match(r"^(.*?)\s*?({.*})", message)
	if tmp is not None:
		message = tmp[1]
		extra_message, severity, facility, remnants = split_json_style(tmp[2], severity = severity, facility = facility, fold_msg = fold_msg)
		if len(extra_message) > 0:
			if remnants is None or len(remnants) == 0:
				message = "%s  %s" % (message, extra_message)
			else:
				raise Exception("message: %s\nextra_message: %s" % (message, extra_message))

	return facility, severity, message, remnants

# mysql:
# 2020-06-24 09:16:04+00:00 [Note] [Entrypoint]: Entrypoint script for MySQL Server 5.6.48-1debian9 started.
# 2020-06-24 09:16:05 0 [Note] mysqld (mysqld 5.6.48) starting as process 1 ...
# Version: '5.6.48'  socket: '/var/run/mysqld/mysqld.sock'  port: 3306  MySQL Community Server (GPL)
def mysql(message, fold_msg = True):
	remnants = []
	severity = loglevel.INFO
	facility = ""

	# If the line starts with a number it's another timestamp,
	# if it starts with a letter check if it's a severity
	if len(message) > 0 and message[0] in "0123456789":
		message, _timestamp = split_iso_timestamp(message, None)
	else:
		tmp = re.match(r"^([A-Z][a-z]+):\s+(.*)", message)
		if tmp is not None:
			_severity = str_to_severity(tmp[1], -1)
			if severity != -1:
				severity = _severity
				message = tmp[2]
				return facility, severity, message, remnants

	# Some lines begin with a mysterious number (possibly the PID); remove it
	tmp = re.match(r"^\d+ (.*)", message)
	if tmp is not None:
		message = tmp[1]

	# Get the severity (if specified)
	message, tmpseverity = split_bracketed_severity(message)
	severity = min(tmpseverity, severity)

	# Some lines have what presumably is a mysql internal error prefix; remove it
	tmp = re.match(r"^\[MY-\d+\] (.*)", message)
	if tmp is not None:
		message = tmp[1]

	tmp = re.match(r"^\[(Entrypoint|Server|InnoDB)\]:? (.*)", message)
	if tmp is not None:
		facility = tmp[1]
		message = tmp[2]
	else:
		# Only match this if we didn't remove a bracketed prefix
		tmp = re.match(r"^(InnoDB): (.*)", message)
		if tmp is not None:
			facility = tmp[1]
			message = tmp[2]

	# Override the severity for the version string
	tmp = re.match(r".*mysqld? \(mysqld .*?\) starting as process", message)
	if tmp is not None:
		severity = loglevel.NOTICE
	# Override severity for a message that looks like it should be warning
	message, severity = override_severity(message, severity)

	return facility, severity, message, remnants

# k8s-mlperf-image-classification-training/k8s-mlperf-image-classification-training
# INFO:tensorflow:Done running local_init_op.
# 2020-02-24 11:52:00.243943: W [...]
# facilities:
#	tensorflow/core/common_runtime/gpu/gpu_device.cc:971
#	tensorflow:
def mlperf_image_classification_training(message, fold_msg = True):
	facility = ""
	remnants = []

	# INFO:tensorflow:Done running local_init_op.
	# 2020-02-24 11:52:00.243943: W [...]
	# 2020-02-24 11:51:47.827157: I
	# Trim any leading superfluous timestamps;
	# we've already got one, you see. Oh yes,
	# it's very nice.
	tmp = re.match(r"^([A-Z]) (.*?:\d+)] (.*)", message)
	if tmp is not None:
		severity = letter_to_severity(tmp[1])
		facility = tmp[2]
		message = tmp[3]
	elif message.startswith("ERROR:"):
		severity = loglevel.ERR
		message = message[len("ERROR:"):]
	elif message.startswith("WARNING:"):
		severity = loglevel.WARNING
		message = message[len("WARNING:"):]
	elif message.startswith("NOTICE:"):
		severity = loglevel.NOTICE
		message = message[len("NOTICE:"):]
	elif message.startswith("INFO:"):
		severity = loglevel.INFO
		message = message[len("INFO:"):]
	elif message.startswith("DEBUG:"):
		severity = loglevel.DEBUG
		message = message[len("DEBUG:"):]
	else:
		severity = loglevel.INFO

	return facility, severity, message, remnants

# nvidia-smi-exporter
# Examples:
# nvidia-smi-exporter/*:<bla bla.rb:\d+: >:< warning: >:no extra ts:/var/lib/gems/2.5.0/gems/bundler-1.17.2/lib/bundler/rubygems_integration.rb:200: warning: constant Gem::ConfigMap is deprecated
def nvidia_smi_exporter(message, fold_msg = True):
	remnants = []

	tmp = re.match(r"(/.*?\.rb:\d+): (.*?): (.*)", message)

	if tmp is not None:
		facility = tmp[1]
		severity = str_to_severity(tmp[2])
		message = tmp[3]
	else:
		facility = ""
		severity = loglevel.INFO

	return facility, severity, message, remnants

def format_key_value(key, value, severity, force_severity = False):
	if key in ["error", "err"]:
		tmp = [(f"{key}", ("types", "key_error")), ("separators", "keyvalue_log"), (f"{value}", ("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
	elif force_severity == True:
		tmp = [(f"{key}", ("types", "key")), ("separators", "keyvalue_log"), (f"{value}", ("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
	else:
		tmp = [(f"{key}", ("types", "key")), ("separators", "keyvalue_log"), (f"{value}", ("types", "value"))]
	return tmp

# Severity: lvl=|level=
# Timestamps: t=|ts=|time= (all of these are ignored)
# Facility: subsys|caller|logger|source
def key_value(message, severity = loglevel.INFO, facility = "", fold_msg = True, options = {}):
	remnants = []

	messages = options.get("messages", ["msg"])
	errors = options.get("errors", ["err", "error"])
	timestamps = options.get("timestamps", ["t", "ts", "time"])
	severities = options.get("severities", ["level", "lvl"])
	facilities = options.get("facilities", ["source", "subsys", "caller", "logger", "Topic"])

	# Replace embedded quotes with fancy quotes
	message = message.replace("\\\"", "”")

	# split all key=value pairs
	tmp = re.findall(r"(?:\".*?\"|\S)+", message)
	if tmp is not None:
		d = {}
		for item in tmp:
			tmp2 = re.match(r"^(.*?)=(.*)", item)
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
		level = deep_get_with_fallback(d, severities, "info")
		if logparser_configuration.pop_severity == True:
			for _sev in severities:
				d.pop(_sev, None)
		severity = level_to_severity(level)

		msg = deep_get_with_fallback(d, messages, "")
		if msg.startswith("\"") and msg.endswith("\""):
			msg = msg[1:-1]
		version = d.get("version", "")
		if version.startswith("\"") and version.endswith("\""):
			version = version[1:-1]

		# If the message contains a version,
		# or something similarly useful, bump the severity
		msg, severity = override_severity(msg, severity)
		tmp = re.match(r"Cilium \d+\.\d+", msg)
		if tmp is not None:
			severity = min(severity, loglevel.NOTICE)

		facility = deep_get_with_fallback(d, facilities, facility).strip("\"")
		if logparser_configuration.pop_facility == True:
			for _fac in facilities:
				d.pop(_fac, None)

		if fold_msg == False and len(d) == 2 and logparser_configuration.merge_starting_version == True and "msg" in d and msg.startswith("Starting") and "version" in d and version.startswith("(version="):
			message = f"{msg} {version}"
		elif "err" in d and ("errors occurred:" in d["err"] or "error occurred:" in d["err"]) and fold_msg == False:
			err = d["err"]
			if err.startswith("\"") and err.endswith("\""):
				err = err[1:-1]
			message = f"{msg}"
			tmp = re.match(r"(\d+ errors? occurred:)(.*)", err)
			if tmp is not None:
				remnants.append((tmp[1], severity))
				s = tmp[2].replace("\\t", "").split("\\n")
				for line in s:
					if len(line) > 0:
						# Real bullets look so much nicer
						if line.startswith("* ") and logparser_configuration.msg_realbullets == True:
							remnants.append(([("separators", "logbullet"), (f"{line[2:]}", ("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity))
						else:
							remnants.append((f"{line}", severity))
		else:
			tmp = []
			# If we're extracting msg we always want msg first
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
					if fold_msg == True:
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
							if not any(_err in errors for key in d):
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

			for item in d:
				if fold_msg == False:
					if item == "collector" and logparser_configuration.bullet_collectors == True:
						tmp.append(f"• {d[item]}")
					else:
						tmp.append(format_key_value(item, d[item], severity))
				else:
					tmp.append(f"{item}={d[item]}")

			if fold_msg == True:
				message = " ".join(tmp)
			else:
				if len(tmp) > 0:
					message = tmp.pop(0)
				else:
					message = ""
				remnants = (tmp, severity)

	if logparser_configuration.msg_linebreaks == True and "\\n" in message and type(message) == str and fold_msg == False:
		lines = message.split("\\n")
		message = lines[0]
		_remnants = []
		if len(lines) > 1:
			for line in lines[1:]:
				_remnants.append((line, severity))
			if type(remnants) == tuple:
				for remnant in remnants[0]:
					_remnants.append((remnant, remnants[1]))
				remnants = _remnants
			elif type(remnants) == list:
				remnants = _remnants + remnants
	return facility, severity, message, remnants

# For messages along the lines of:
# "Foo" "key"="value" "key"="value"
# Foo key=value key=value
def key_value_with_leading_message(message, severity = loglevel.INFO, facility = "", fold_msg = True, options = {}):
	global logparser_configuration
	remnants = []

	if fold_msg == True:
		return facility, severity, message, remnants

	# Split into substrings based on spaces
	tmp = re.findall(r"(?:\".*?\"|\S)+", message)
	if tmp is not None and len(tmp) > 0:
		if "=" in tmp[0]:
			# Try parsing this as regular key_value
			facility, severity, message, remnants = key_value(message, fold_msg = fold_msg, severity = severity, facility = facility, options = options)
		else:
			for item in tmp[1:]:
				# we couldn't parse this as "msg key=value"; give up
				if "=" not in item:
					return facility, severity, message, remnants
			rest = message[len(tmp[0]):].lstrip()
			message = tmp[0]
			tmp_msg_extract = logparser_configuration.msg_extract
			logparser_configuration.msg_extract = False
			facility, severity, _message, _remnants = key_value(rest, fold_msg = fold_msg, severity = severity, facility = facility, options = options)
			logparser_configuration.msg_extract = tmp_msg_extract
			if _remnants is not None and len(_remnants) > 0:
				_remnant_strs, _remnants_severity = _remnants
				remnants = ([_message] + _remnant_strs, severity)
			else:
				remnants = ([_message], severity)
	return facility, severity, message, remnants

# [2021-09-24 12:43:53 +0000] [11] [INFO] Booting worker with pid: 11
# | apps.default | INFO | Setting STATIC_DIR to: /src/apps/default/static
def web_app(message, fold_msg = True):
	remnants = []
	facility = ""
	severity = None

	if len(message) > 0:
		if message[0] == "[":
			tmp = re.match(r"^\[(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d .\d\d\d\d)\] \[(\d+)\] \[([A-Z]+)\] (.*)", message)
			if tmp is not None:
				_timestamp = tmp[1]
				_pid = tmp[2]
				severity = str_to_severity(tmp[3])
				message = tmp[4]
		else:
			tmp = re.match(r"^(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d,\d\d\d) \| (.+?) \| ([A-Z]+) \| (.*)", message)
			if tmp is not None:
				_timestamp = tmp[1]
				facility = tmp[2]
				severity = str_to_severity(tmp[3])
				message = tmp[4]

	if severity is None:
		severity = loglevel.INFO

	return facility, severity, message, remnants

# 2020-04-17T10:58:19.855304Z     info    FLAG: --applicationPorts="[]"
# [2020-04-17 10:58:19.870][18][warning][misc] [external/envoy/source/common/protobuf/utility.cc:174] Using deprecated option 'envoy.api.v2.Cluster.hosts' from file cds.proto.
# XXX: We need a better name for this parser; it's also used for kourier and possibly other things as well
def istio(message, fold_msg = True):
	remnants = []
	facility = ""
	severity = None

	# Another timestamp to strip
	message, _timestamp = split_iso_timestamp(message, None)

	tmp = re.match(r"^\s+([a-z]+)\s+(.*)", message)
	if tmp is not None:
		severity = str_to_severity(tmp[1])
		message = tmp[2]

	tmp = re.match(r"^\[(\d+-\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\]\[\d+\]\[([a-z]+)\]\[([a-z]+)\] \[(.+)\] (.*)", message)
	if tmp is not None:
		# timestamp = tmp[1]
		# something = tmp[3]
		if severity is None:
			severity = str_to_severity(tmp[2])
		facility = tmp[4]
		message = tmp[5]

	if severity is None:
		severity = loglevel.INFO

	# split dates of the format [YYYY-MM-DD HH:MM:SS.sssZ]
	tmp = re.match(r"\[\d+-\d\d-\d\dT\d\d:\d\d:\d\d\.\d\d\dZ\] (.*)", message)
	if tmp is not None:
		message = tmp[1]

	# If the message contains a version,
	# or something similarly useful, bump the severity
	message, severity = override_severity(message, severity)

	return facility, severity, message, remnants

def istio_pilot(message, fold_msg = True):
	remnants = []
	facility = None
	severity = None

	# If the line starts with a number it's another timestamp,
	# if it starts with a letter try to treat it as a glog message instead
	if len(message) > 0 and message[0] in "0123456789":
		message, _timestamp = split_iso_timestamp(message, None)
	else:
		message, severity, facility, remnants, _match = split_glog(message)
		return facility, severity, message, remnants

	tmp = re.match(r"^\s+([A-Za-z]+)\s+(.*)", message)
	if tmp is not None:
		severity = str_to_severity(tmp[1])
		message = tmp[2]
	else:
		severity = loglevel.INFO

	tmp = re.match(r"^([A-Za-z-. ]+)\t(.*)", message)
	if tmp is not None:
		facility = tmp[1]
		message = tmp[2]
	else:
		facility = ""

	return facility, severity, message, remnants

# jupyter:
# [I 10:29:35.079 NotebookApp] Writing notebook server cookie secret to /root/.local/share/jupyter/runtime/notebook_cookie_secret
# [W 10:29:35.131 NotebookApp] WARNING: The notebook server is listening on all IP addresses and not using encryption. This is not recommended.
# [C 10:29:35.149 NotebookApp]
def jupyter(message, fold_msg = True):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	tmp = re.match(r"^\[(.) \d\d:\d\d:\d\d\.\d\d\d (.*?)\] ?(.*)", message)

	if tmp is not None:
		facility = tmp[2]
		severity = letter_to_severity(tmp[1])
		message = tmp[3]

	return facility, severity, message, remnants

# tiller:
# [main] 2020/04/15 11:29:07 Starting Tiller v2.16.6 (tls=false)
def tiller(message, fold_msg = True):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	tmp = re.match(r"^\[(.+?)\] ?(.*)", message)

	if tmp is not None:
		facility = tmp[1]
		# Another timestamp to strip
		message, _timestamp = split_iso_timestamp(tmp[2], None)

	# If the message contains a version,
	# or something similarly useful, bump the severity
	message, severity = override_severity(message, severity)

	return facility, severity, message, remnants

# [main] 2021/03/27 20:45:25 Starting Tiller v2.16.10 (tls=false)
# [restful] 2020/03/04 10:24:17 log.go:33: [restful/swagger] listing is available at https://:443/swaggerapi
def split_tiller_style(message, facility = None):
	tmp = re.match(r"^\[(.+?)\] \d\d\d\d\/\d\d\/\d\d \d\d:\d\d:\d\d (.+?:\d+: |)(.*)", message)

	if tmp is not None:
		if len(tmp[2]) > 0:
			facility = tmp[2][:-2]
		else:
			facility = tmp[1]
		message = tmp[3]
	return message, facility

# Messages on the format:
# <key>:<whitespace>...<value>
def modinfo(message, fold_msg = True):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	tmp = re.match(r"^(.+?):(\s*)(.*)", message)
	if tmp is not None:
		key = tmp[1]
		whitespace = tmp[2]
		value = tmp[3]
		message = [
			(key, ("types", "key")),
			("separators", "keyvalue"),
			(whitespace, ("types", "generic")),
			(value, ("types", "value")),
		]
	return facility, severity, message, remnants

# Messages on the format:
# [timestamp] [severity] message
def bracketed_timestamp_severity(message, fold_msg = True):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	# Some messages have double timestamps...
	message, _timestamp = split_iso_timestamp(message, None)
	message, severity = split_bracketed_severity(message, default = loglevel.WARNING)

	if message.startswith(("XPU Manager:", "Build:", "Level Zero:")):
		severity = loglevel.NOTICE

	return facility, severity, message, remnants

def kube_parser_structured_glog(message, fold_msg = True):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	message, severity, facility, remnants, match = split_glog(message)

	# Embedded quotes in the messages causes issues when
	# splitting, so replace them with fancy quotes
	message = message.replace("\\\"", "”")

	if fold_msg == True:
		# Split into substrings based on spaces
		tmp = re.findall(r"(?:\".*?\"|\S)+", message)

		if tmp is not None and len(tmp) > 0 and "=" in tmp[0]:
			fac, sev, message, remnants = key_value(message, fold_msg = fold_msg)
			if len(facility) == 0:
				facility = fac
			if sev < severity:
				severity = sev
	else:
		header = ""

		# Split into substrings based on spaces
		tmp = re.findall(r"(?:\".*?\"|\S)+", message)

		if tmp is not None and len(tmp) > 0:
			if "=" not in tmp[0]:
				header = f"{tmp[0]}: "
				tmp = tmp[1:]

			res = {}
			for item in tmp:
				# First split into [key, value]
				tmp2 = item.split("=", 1)
				if len(tmp2) < 2:
					# We found a non key=value item; treat the entire string as non-key=value
					res = {}
					break

				# Now add key: value into the dict
				if tmp2[1].startswith("”"):
					if not tmp2[1].endswith("”"):
						raise Exception(f"kube_parser_structured_glog(): unbalanced quotes in item: {item}")
					else:
						res[tmp2[0]] = tmp2[1][1:-1]
				else:
					# Now we restore the quotation marks; fancy quotes should be paired,
					# and since we cannot do that we shouldn't pretend that we did
					res[tmp2[0]] = tmp2[1].replace("”", "\"")

			if len(res) > 0:
				resmsg = res.get("msg")
				if resmsg is not None:
					if resmsg.startswith("\"") and resmsg.endswith("\""):
						message = f"{header}{resmsg[1:-1]}"
					else:
						message = f"{header}{resmsg}"
				else:
					message = header

				for entry, value in res.items():
					if severity > loglevel.INFO:
						tmpseverity = loglevel.INFO
					else:
						tmpseverity = severity

					# We have already extracted the message
					if entry == "msg":
						continue
					# We should already have a timestamp
					elif entry in ["ts", "time"]:
						continue
					elif entry == "caller":
						if facility == "":
							facility = value
						continue
					elif entry == "source":
						if facility == "":
							facility = value
						continue
					elif entry == "Topic":
						if facility == "":
							facility = value
						continue
					elif entry == "level":
						s = str_to_severity(value, -1)
						if s != -1 and s < severity:
							severity = s
						continue
					elif entry == "err":
						# alertmanager sometimes folds up multiple errors on one line;
						# try to unfold them
						tmpseverity = severity
						tmp = re.match(r"(\d+ errors occurred:)(.*)", value)
						if tmp is not None:
							remnants.append((f"{entry}: {tmp[1]}\n", tmpseverity))
							s = tmp[2].replace("\\t", "").split("\\n")
							for line in s:
								if len(line) > 0:
									if line.startswith("* "):
										remnants.append(("   {line}\n", tmpseverity))
									else:
										remnants.append(("   * {line}\n", tmpseverity))
							continue
					elif entry == "error":
						tmpseverity = severity
					# Should we highlight this too?
					#elif entry == "cluster-version":
					#	tmpseverity = loglevel.NOTICE
					elif entry in ["version", "git-commit"]:
						tmpseverity = loglevel.NOTICE
					elif entry == "Workflow":
						if message.startswith("Syncing Workflow") and value in message:
							continue
					elif entry == "component":
						# this should have loglevel.INFO or lower severity
						tmpseverity = max(loglevel.INFO, severity, tmpseverity)

					remnants.append(([(entry, ("types", "key")), ("separators", "keyvalue_log"), (value, ("types", "value"))], tmpseverity))
				if len(message) == 0:
					message = remnants[0]
					remnants.pop(0)

	# If the message contains a version,
	# or something similarly useful, bump the severity
	message, severity = override_severity(message, severity, facility = facility)

	return facility, severity, message, remnants

def directory(message, fold_msg = True):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	tmp = re.match(r"^(total)\s+(\d+)$", message)
	if tmp is not None:
		return facility, severity, message, remnants

	tmp = re.match(r"^(.)(.........)(\s+)(\d+)(\s+)(.*?)(\s+)(\*?)(\s+)(\d+)(,\s+\d+|)(\s+)(.+?)(\s+)(\d+)(\s+)(.*?)(\s+)(.+?)(=|\||/|)$", message)
	if tmp is None:
		# This is unlikely to be a directory match
		return facility, severity, message, remnants
	else:
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

		_message = [
			(f"{etype}", ("types", "dir_type")),
			(f"{permissions}", ("types", "dir_permissions")),
			(f"{space1}", ("types", "generic")),
			(f"{linkcount}", ("types", "dir_linkcount")),
			(f"{space2}", ("types", "generic")),
			(f"{owner}", ("types", "dir_owner")),
			(f"{space3}", ("types", "generic")),
			(f"{group}", ("types", "dir_group")),
			(f"{space4}", ("types", "generic")),
			(f"{size}", ("types", "dir_size")),
			(f"{space5}", ("types", "generic")),
			(f"{month}", ("types", "dir_date")),
			(f"{space6}", ("types", "generic")),
			(f"{day}", ("types", "dir_date")),
			(f"{space7}", ("types", "generic")),
			(f"{yearortime}", ("types", "dir_date")),
			(f"{space8}", ("types", "generic")),
		]
		# regular file
		if etype == "-":
			_message += [
				(f"{name}", ("types", "dir_file"))
			]
		# block device
		elif etype == "b":
			_message += [
				(f"{name}", ("types", "dir_dev"))
			]
		# character device
		elif etype == "c":
			_message += [
				(f"{name}", ("types", "dir_dev"))
			]
		# sticky bit has precedence over the regular directory type
		elif permissions.endswith("t"):
			_message += [
				(f"{name}", ("types", "dir_socket"))
			]
		# directory
		elif etype == "d":
			_message += [
				(f"{name}", ("types", "dir_dir"))
			]
		# symbolic link
		elif etype == "l":
			tmp2 = re.match(r"(.+?)( -> )(.+)", name)
			if tmp2 is None:
				_message += [
					(f"{name}", ("types", "dir_symlink_name"))
				]
			else:
				_message += [
					(f"{tmp2[1]}", ("types", "dir_symlink_name")),
					(f"{tmp2[2]}", ("types", "dir_symlink_link"))
				]
				# There's no suffix for devices or regular files,
				# but we can distinguish the two based on the file size;
				# the size for devices isn't really a size per se,
				# but rather major, minor (a normal size never has a comma)
				if len(suffix) == 0:
					if "," in size:
						_message += [
							(f"{tmp2[3]}", ("types", "dir_dev")),
						]
					else:
						_message += [
							(f"{tmp2[3]}", ("types", "dir_file")),
						]
				elif suffix == "|":
					_message += [
						(f"{tmp2[3]}", ("types", "dir_pipe")),
					]
				elif suffix == "=":
					_message += [
						(f"{tmp2[3]}", ("types", "dir_socket")),
					]
				elif suffix == "/":
					_message += [
						(f"{tmp2[3]}", ("types", "dir_dir")),
					]
				else:
					raise Exception("Unhandled suffix {suffix} in line {message}")
		# pipe
		elif etype == "p":
			_message += [
				(f"{name}", ("types", "dir_pipe"))
			]
		# socket
		elif etype == "s":
			_message += [
				(f"{name}", ("types", "dir_socket"))
			]

		if len(suffix) > 0:
			_message += [
				(f"{suffix}", ("types", "dir_suffix"))
			]

	return facility, severity, _message, remnants

# input: nginx 08:44:38.88 INFO  ==> ** Starting NGINX setup **
# output:
#   severity: loglevel.INFO
#   facility: nginx
#   msg: ==> ** Starting NGINX setup **
#   remnants: []
def facility_hh_mm_ss_ms_severity(message, severity = loglevel.INFO, fold_msg = True):
	facility = ""
	remnants = []

	tmp = re.match(r"^(.+?)\s+?(\d\d:\d\d:\d\d\.\d\d)(\s+?|$)(.*)", message)
	if tmp is not None:
		facility = tmp[1]
		message, severity = split_4letter_spaced_severity(tmp[4])
	return facility, severity, message, remnants

# input: [     0.000384s]  INFO ThreadId(01) linkerd2_proxy::rt: Using single-threaded proxy runtime
# output:
#   severity: loglevel.INFO
#   facility: ThreadId(01)
#   msg: [     0.000384s] linkerd2_proxy::rt: Using single-threaded proxy runtime
#   remnants: []
def seconds_severity_facility(message, fold_msg = True):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	tmp = re.match(r"(\[\s*?\d+?\.\d+?s\])\s+([A-Z]+?)\s+(\S+?)\s(.*)", message)
	if tmp is not None:
		severity = str_to_severity(tmp[2], default = severity)
		facility = tmp[3]
		message = [(f"{tmp[1]} ", ("logview", "timestamp")), (f"{tmp[4]}", ("logview", f"severity_{loglevel_to_name(severity).lower()}"))]

	return facility, severity, message, remnants

def substitute_bullets(message, prefix):
	if message.startswith(prefix):
		# We don't want to replace all "*" in the message with bullet, just prefixes
		message = message[0:len(prefix)].replace("*", "•") + message[len(prefix):]
	return message

def python_traceback_scanner(message, fold_msg = True):
	timestamp = None
	facility = ""
	severity = loglevel.ERR
	message, _timestamp = split_iso_timestamp(message, None)
	processor = ["block", python_traceback_scanner]

	# Default case
	remnants = [
		(message, ("logview", "severity_info")),
	]

	tmp = re.match(r"^(\s+File \")(.+?)(\", line )(\d+)(, in )(.*)", message)
	if tmp is not None:
		remnants = [
			(tmp[1], ("logview", "severity_info")),
			(tmp[2], ("types", "path")),
			(tmp[3], ("logview", "severity_info")),
			(tmp[4], ("types", "lineno")),
			(tmp[5], ("logview", "severity_info")),
			(tmp[6], ("types", "path"))
		]
	else:
		tmp = re.match(r"(^\S+?Error:|Exception:|GeneratorExit:|KeyboardInterrupt:|StopIteration:|StopAsyncIteration:|SystemExit:)( .*)", message)
		if tmp is not None:
			remnants = [
				(tmp[1], ("logview", "severity_error")),
				(tmp[2], ("logview", "severity_info"))
			]
			processor = ["end_block", None]
		elif message.lstrip() == message:
			processor = ["break", None]

	return processor, (timestamp, facility, severity, remnants)

def python_traceback(message, fold_msg = True):
	remnants = []
	if message == "Traceback (most recent call last):":
		remnants = [(message, ("logview", "severity_error"))]
		message = ["start_block", python_traceback_scanner]
	return message, remnants

def json_line_scanner(message, fold_msg = True):
	timestamp = None
	facility = ""
	severity = loglevel.INFO
	message, _timestamp = split_iso_timestamp(message, None)

	if message == "}":
		remnants = format_yaml_line(message, override_formatting = {})
		processor = ["end_block", None]
	elif message.lstrip() != message:
		remnants = format_yaml_line(message, override_formatting = {})
		processor = ["block", json_line_scanner]
	else:
		processor = ["break", None]

	return processor, (timestamp, facility, severity, remnants)

def json_line(message, fold_msg = True, options = {}):
	remnants = []
	matched = False

	block_start = deep_get(options, "block_start", [{
		"matchtype": "exact",
		"matchkey": "{",
		"matchline": "any",
	}])
	line = deep_get(options, "__line", 0)

	for _bs in block_start:
		matchtype = _bs["matchtype"]
		matchkey = _bs["matchkey"]
		matchline = _bs["matchline"]
		if matchline == "any" or matchline == "first" and line == 0:
			if matchtype == "exact":
				if message == matchkey:
					matched = True
			elif matchtype == "startswith":
				if message.startswith(matchkey):
					matched = True

	if matched == True:
		remnants = format_yaml_line(message, override_formatting = {})
		message = ["start_block", json_line_scanner]
	return message, remnants

def custom_splitter(message, severity = None, facility = "", fold_msg = True, options = {}):
	regex_pattern = deep_get(options, "regex", None)
	severity_field = deep_get(options, "severity#field", None)
	severity_transform = deep_get(options, "severity#transform", None)
	facility_fields = deep_get_with_fallback(options, ["facility#fields", "facility#field"], None)
	facility_separators = deep_get(options, "facility#separators", "")
	message_field = deep_get(options, "message#field", None)

	# This message is already formatted
	if type(message) == list:
		return message, severity, facility

	# The bare minimum for these rules is
	if regex_pattern is None or message_field is None:
		raise Exception("parser rule is missing regex or message field")

	tmp = re.match(regex_pattern, message)
	if tmp is not None:
		if severity_field is not None and severity_transform is not None:
			if severity_transform == "letter":
				severity = letter_to_severity(tmp[severity_field], severity)
			elif severity_transform == "4letter":
				severity = str_4letter_to_severity(tmp[severity_field], severity)
			elif severity_transform == "str":
				severity = str_to_severity(tmp[severity_field], severity)
			elif severity_transform == "int":
				severity = int(tmp[severity_field])
		if facility_fields is not None and len(facility) == 0:
			if type(facility_fields) == str:
				facility_fields = [facility_fields]
			i = 0
			facility = ""
			for field in facility_fields:
				if i > 0:
					facility += facility_separators[min(i - 1, len(facility_separators) - 1)]
				if field != 0:
					facility += tmp[field]
				i += 1
		message = tmp[message_field]

	return message, severity, facility

def custom_parser(message, fold_msg = True, filters = [], options = {}):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	for _filter in filters:
		if type(_filter) == str:
			# Multiparsers
			if _filter == "glog":
				message, severity, facility, remnants, _match = split_glog(message)
			elif _filter == "spaced_severity_facility":
				message, severity, facility = __split_severity_facility_style(message, severity, facility)
			elif _filter == "letter_severity_colon_facility":
				message, severity, facility = __split_severity_facility_style(message, severity, facility)
			elif _filter == "directory":
				facility, severity, message, remnants = directory(message, fold_msg = fold_msg)
			elif _filter == "seconds_severity_facility":
				facility, severity, message, remnants = seconds_severity_facility(message, fold_msg = fold_msg)
			elif _filter == "facility_hh_mm_ss_ms_severity":
				facility, severity, message, remnants = facility_hh_mm_ss_ms_severity(message, severity = severity, fold_msg = fold_msg)
			elif _filter == "expand_event":
				if message.startswith("Event(v1.ObjectReference{"):
					message, remnants = expand_event(message, severity = severity, remnants = remnants, fold_msg = fold_msg)
			elif _filter == "modinfo":
				facility, severity, message, remnants = modinfo(message, fold_msg = fold_msg)
			# Timestamp formats
			elif _filter == "ts_8601": # Anything that resembles ISO-8601
				message = strip_iso_timestamp(message)
			elif _filter == "ts_8601_tz": # ISO-8601 with 3-letter timezone; since the offset is dependent on date we don't even try to parse
				message = strip_iso_timestamp_with_tz(message)
			# Facility formats
			elif _filter == "colon_facility":
				message, facility = split_colon_facility(message, facility)
			elif _filter == "angle_bracketed_facility":
				message, facility = split_angle_bracketed_facility(message, facility)
			# Severity formats
			elif _filter == "colon_severity":
				message, severity = split_colon_severity(message, severity)
			elif _filter == "4letter_colon_severity":
				message, severity = split_4letter_colon_severity(message, severity)
			elif _filter == "4letter_spaced_severity":
				message, severity = split_4letter_spaced_severity(message, severity)
			# Filters
			elif _filter == "strip_ansicodes":
				message = strip_ansicodes(message)
			elif _filter == "strip_bracketed_pid":
				message = strip_bracketed_pid(message)
			# Block starters
			elif _filter == "python_traceback":
				message, remnants = python_traceback(message, fold_msg = fold_msg)
			else:
				sys.exit(f"Parser rule error; {_filter} is not a supported filter type; aborting.")
		elif type(_filter) == tuple:
			# Multiparsers
			if _filter[0] == "bracketed_timestamp_severity_facility":
				message, severity, facility = split_bracketed_timestamp_severity_facility(message, default = _filter[1])
			elif _filter[0] == "custom_splitter":
				_parser_options = _filter[1]
				message, severity, facility = custom_splitter(message, severity = severity, facility = facility, fold_msg = fold_msg, options = _parser_options)
			elif _filter[0] == "json":
				_parser_options = _filter[1]
				if message.startswith("{\""):
					message, severity, facility, remnants = split_json_style(message, fold_msg = fold_msg, options = _parser_options)
			elif _filter[0] == "json_event":
				_parser_options = _filter[1]
				# We don't extract the facility/severity from folded messages, so just skip if fold_msg == True
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
			elif _filter[0] == "override_severity":
				severity = custom_override_severity(message, severity, _filter[1])
			# Filters
			elif _filter[0] == "substitute_bullets":
				message = substitute_bullets(message, _filter[1])
			# Block starters
			elif _filter[0] == "json_line":
				_parser_options = {**_filter[1], **options}
				message, remnants = json_line(message, fold_msg = fold_msg, options = _parser_options)
			else:
				sys.exit(f"Parser rule error; {_filter} is not a supported filter type; aborting.")

	if severity is None:
		severity = loglevel.INFO

	return facility, severity, message, remnants

builtin_parsers = [
	# Formats:
	# pod, container, image, parser (old style)
	# parser_name, show_in_selector, [match_rules], parser (new style)
	#
	# One or more of pod, container, image must be specified

	("internal_error", "", "", "basic_8601_colon_severity"),

	("3scale-kourier-gateway", "", "", "istio"),

	("activator", "istio-init_init", "", "basic_8601"),
	("activator", "istio-proxy", "", "istio"),
	("admission-webhook-bootstrap-stateful-set", "bootstrap", "", "basic_8601"),
	("admission-webhook-bootstrap", "", "", "basic_8601"),
	("admission-webhook-deployment", "admission-webhook", "", "kube_parser_1"),
	("admission-webhook-deployment", "", "", "kube_parser_1"),
	("application-controller-stateful-set", "manager", "", "kube_parser_1"),
	("argo-ui", "argo-ui", "", "basic_8601_colon_severity"),
	("autoscaler-hpa", "autoscaler-hpa", "", "kube_parser_1"),
	("autoscaler", "istio-init_init", "", "basic_8601"),
	("autoscaler", "istio-proxy", "", "istio"),

	("blackbox-exporter", "", "", "kube_parser_structured_glog"),

	("cass-operator", "", "", "kube_parser_json"),
	("cdi-controller", "", "", "kube_parser_1"),
	("cdi-node", "", "", "kube_parser_1"),
	("centraldashboard", "", "", "basic_8601"),
	("cifar10-training-gpu-worker", "", "", "kube_parser_1"),
	("cluster-local-gateway", "istio-proxy", "", "istio"),

	("", "", "quay.io/dexidp/dex", "key_value"),
	("dist-mnist", "", "", "jupyter"),
	("dns-autoscaler", "", "", "kube_parser_structured_glog"),

	("grafana", "", "", "key_value"),
	("", "grafana-operator", "", "kube_parser_json_glog"),

	("helm-", "", "", "kube_parser_1"),

	("istio-citadel", "citadel", "", "istio"),
	("istio-cleanup-secrets", "kubectl", "", "istio"),
	("istio-egressgateway", "istio-proxy", "", "istio"),
	("istio-galley", "galley", "", "istio"),
	("istio-ingressgateway", "istio-proxy", "", "istio"),
	("", "", "docker.io/istio/proxyv2", "istio_pilot"),
	("", "", "docker.io/istio/pilot", "istio_pilot"),
	("istio-pilot", "", "", "istio"),
	("istio-policy", "", "", "istio"),
	("istio-sidecar-injector", "sidecar-injector-webhook", "", "istio"),
	("istio-telemetry", "mixer", "", "kube_parser_json"),
	("istio-telemetry", "", "", "istio"),

	("katib-controller", "", "", "kube_parser_json_glog"),
	("katib-db-manager", "", "", "kube_parser_1"),
	("katib-ui", "", "", "kube_parser_1"),
	("kfserving-controller-manager", "", "", "kube_parser_1"),
	("kfserving-ingressgateway", "istio-proxy", "", "istio"),
	("kiali", "", "", "kube_parser_1"),
	("kilo", "", "", "kube_parser_json_glog"),
	("", "", "gcr.io/knative", "kube_parser_1"),
	("k8s-mlperf-image-classification-training", "", "", "kube_parser_1"),
	("kube-app-manager-controller", "kube-app-manager", "", "kube_app_manager"),
	# kubeflow
	("", "", "gcr.io/arrikto/kubeflow/oidc-authservice", "key_value"),

	("local-path-provisioner", "", "", "kube_parser_1"),

	("metacontroller", "metacontroller", "", "kube_parser_1"),
	("metadata-db", "db-container", "", "mysql"),
	("metadata-deployment", "container", "", "kube_parser_1"),
	("metadata-envoy-deployment", "container", "", "istio"),
	("metadata-grpc-deployment", "container", "", "kube_parser_1"),
	("metadata-ui", "metadata-ui", "", "basic_8601"),

	("minio", "minio", "", "basic_8601"),
	("ml-pipeline", "ml-pipeline-api-server", "", "kube_parser_1"),
	("ml-pipeline", "ml-pipeline-visualizationserver", "", "kube_parser_1"),	#UNKNOWN
	("ml-pipeline", "ml-pipeline-persistenceagent", "", "kube_parser_structured_glog"),
	("ml-pipeline", "ml-pipeline-scheduledworkflow", "", "kube_parser_structured_glog"),
	("ml-pipeline", "ml-pipeline-ui", "", "kube_parser_1"),
	("ml-pipeline", "ml-pipeline-viewer-controller", "", "kube_parser_1"),
	("", "", "docker.io/kubeflow/mxnet-operator", "kube_parser_json_glog"),
	("mysql", "mysql", "", "mysql"),
	("", "", "docker.io/library/mysql", "mysql"),

	("networking-istio", "networking-istio", "", "kube_parser_1"),
	("node-exporter", "", "", "key_value"),
	("node-problem-detector", "", "", "kube_parser_1"),
	("nodelocaldns", "", "", "kube_parser_1"),
	("notebook-controller-deployment", "manager", "", "seldon"),
	("gpu-feature-discovery", "toolkit-validation", "", "basic_8601"),
	("gpu-feature-discovery", "", "", ("custom", ["colon_facility", "ts_8601"])),
	("nvidia-cuda-validator", "", "", "basic_8601"),
	("nvidia-device-plugin", "", "", "basic_8601"),
	("nvidia-container-toolkit", "driver-validation", "", "basic_8601"),
	("nvidia-container-toolkit", "", "", "key_value"),
	("nvidia-dcgm", "toolkit-validation", "", "basic_8601"),
	("nvidia-dcgm", "", "", "key_value"),
	("nvidia-operator-validator", "cuda-validation", "", "key_value"),
	("nvidia-operator-validator", "plugin-validation", "", "key_value"),
	("nvidia-operator-validator", "", "", "basic_8601"),
	("nvidia-smi-exporter", "", "", "nvidia_smi_exporter"),

	("", "", "docker.io/openshift/origin-hypershift", "kube_parser_1"),
	("", "", "docker.io/openshift/origin-service", "kube_parser_1"),
	("", "", "docker.io/openshift/origin-docker", "key_value"),
	("", "", "docker.io/openshift/origin-docker", "key_value"),
	("", "", "docker.io/openshift/origin-", "kube_parser_1"),

	("", "", "quay.io/operator-framework/olm", "kube_parser_structured_glog"),
	("", "", "quay.io/operatorhubio/catalog", "kube_parser_structured_glog"),

	("apiserver", "", "", "kube_parser_1"),
	("openshift-apiserver", "", "", "kube_parser_1"),
	("openshift-config", "", "", "kube_parser_1"),
	("openshift-controller-manager", "", "", "kube_parser_1"),
	("controller-manager", "", "", "kube_parser_structured_glog"),
	("console", "", "quay.io/openshift", "kube_parser_1"),
	("dns-operator", "", "", "kube_parser_structured_glog"),
	("dns-default", "", "", "kube_parser_1"),
	("authentication-operator", "", "", "kube_parser_1"),
	("oauth-openshift", "", "", "kube_parser_1"),
	("machine-approver", "", "", "kube_parser_1"),
	("tuned", "", "", "kube_parser_1"),
	("cluster-samples-operator", "cluster-samples-operator-watch", "", "kube_parser_1"),
	("cluster-samples-operator", "", "", "key_value"),
	("cluster-image-registry-operator", "", "", "kube_parser_1"),
	("image-registry", "", "", "key_value"),
	("openshift-kube-scheduler-operator", "", "", "kube_parser_1"),
	("openshift-kube-scheduler-crc", "", "", "kube_parser_1"),
	("certified-operators", "", "", "key_value"),
	("community-operators", "", "", "key_value"),
	("marketplace-operator", "", "", "key_value"),
	("redhat-marketplace", "", "", "key_value"),
	("multus", "", "", "kube_parser_1"),
	("network-metrics", "", "", "kube_parser_1"),
	("network-check-", "", "", "kube_parser_1"),
	("catalog-operator", "", "", "kube_parser_structured_glog"),

	# FIXME
	#("olm-operator", "", "", "kube_parser_structured_glog"),

	("packageserver", "", "", "kube_parser_structured_glog"),
	("sdn-", "", "", "kube_parser_1"),
	("service-ca-", "", "", "kube_parser_1"),

	# FIXME
	#("ingress-operator", "", "", "seldon"),

	("parallel-pipeline", "", "", "kube_parser_1"),
	("pmem-csi-", "", "", "kube_parser_1"),
	("profiles-deployment", "kfam", "", "kube_parser_1"),
	("profiles-deployment", "manager", "", "seldon"),
	("", "kube-prometheus-stack", "", "kube_parser_structured_glog"),
	("pytorch-operator", "", "", "kube_parser_1"),	#ALMOST

	("", "reaper-operator", "", "kube_app_manager"),

	("seldon-controller-manager", "", "", "seldon"),
	("spark-operatorcrd-cleanup", "delete-scheduledsparkapp-crd", "", "kube_parser_1"),	#ALMOST
	("spark-operatorcrd-cleanup", "delete-sparkapp-crd", "", "kube_parser_1"),	#ALMOST
	("spark-operatorsparkoperator", "", "", "kube_parser_1"),
	("spartakus-volunteer", "", "", "kube_parser_1"),

	("tensorboard-controller-controller-manager", "manager", "", "istio_pilot"),
	("tensorboard", "tensorboard", "", "kube_parser_1"),
	("tf-job-operator", "", "", "kube_parser_1"),
	("tiller-deploy", "tiller", "", "tiller"),

	("svclb-traefik", "", "", "kube_parser_1"),

	("", "", "gcr.io/ml-pipeline/viewer-crd-controller", "kube_parser_1"),
	("volcano-admission-init", "", "docker.io/volcanosh/vc-webhook-manager", "basic_8601_raw"),
	("", "", "docker.io/volcanosh/vc-webhook-manager", "kube_parser_1"),
	("", "", "docker.io/volcanosh/vc-controller-manager", "kube_parser_1"),
	("", "", "docker.io/volcanosh/vc-scheduler", "kube_parser_1"),

	("jupyter-web-app", "", "", "web_app"),
	("tensorboards-web-app", "", "", "web_app"),
	("volumes-web-app", "", "", "web_app"),
	("workflow-controller", "", "", "kube_parser_structured_glog"),

	("", "", "docker.io/kubeflow/xgboost-operator", "kube_parser_json"),

	("raw", "", "", "basic_8601_raw"),
	# This should always be last
	("", "", "", "basic_8601")
]

Parser = namedtuple("Parser", "parser_name show_in_selector match_rules parser")
parsers = []

iktconfig = None

def init_parser_list():
	global parsers
	global iktconfig

	# Get a full list of parsers from all parser directories
	# Start by adding files from the parsers directory

	parser_dirs = []

	if iktconfig is None:
		iktconfig = iktlib.read_iktconfig()
		parser_dirs += deep_get(iktconfig, "Pods#local_parsers", [])

	parser_dirs.append(os.path.join(IKTDIR, PARSER_DIRNAME))

	parser_files = []

	for parser_dir in parser_dirs:
		if parser_dir.startswith("{HOME}"):
			parser_dir = parser_dir.replace("{HOME}", HOMEDIR, 1)

		if not os.path.isdir(parser_dir):
			continue

		for filename in natsorted(os.listdir(parser_dir)):
			if filename.startswith(("~", ".")) or not filename.endswith((".yaml", ".yml")):
				continue

			parser_files.append(os.path.join(parser_dir, filename))

	for parser_file in parser_files:
		with open(parser_file, "r") as f:
			try:
				d = yaml.safe_load(f)
			except:
				sys.exit(f"Parser-file {parser_file} is invalid; aborting.")

			try:
				for parser in d:
					pass
			except:
				sys.exit(f"Parser-file {parser_file} is invalid; aborting.")

			for parser in d:
				parser_name = parser.get("name", "")
				if len(parser_name) == 0:
					continue
				show_in_selector = parser.get("show_in_selector", False)
				matchrules = []
				for matchkey in parser.get("matchkeys"):
					pod_name = matchkey.get("pod_name", "")
					container_name = matchkey.get("container_name", "")
					image_name = matchkey.get("image_name", "")
					container_type = matchkey.get("container_type", "container")
					# We need at least one way of matching
					if len(pod_name) == 0 and len(container_name) == 0 and len(image_name) == 0:
						continue
					matchrule = (pod_name, container_name, image_name, container_type)
					matchrules.append(matchrule)

				if len(matchrules) == 0:
					continue

				parser_rules = parser.get("parser_rules")
				if parser_rules is None or len(parser_rules) == 0:
					continue

				rules = []
				for rule in parser_rules:
					if type(rule) == dict:
						rule_name = rule.get("name")
						if rule_name in ["colon_severity", "4letter_colon_severity", "angle_bracketed_facility", "colon_facility", "glog", "strip_ansicodes", "ts_8601", "ts_8601_tz", "strip_bracketed_pid", "postgresql_severity", "facility_hh_mm_ss_ms_severity", "seconds_severity_facility", "4letter_spaced_severity", "expand_event", "spaced_severity_facility", "modinfo", "python_traceback"]:
							rules.append(rule_name)
						elif rule_name in ["json", "json_event", "json_line", "key_value", "key_value_with_leading_message", "custom_splitter"]:
							rules.append((rule_name, rule.get("options", {})))
						elif rule_name == "substitute_bullets":
							prefix = rule.get("prefix", "* ")
							rules.append((rule_name, prefix))
						elif rule_name == "override_severity":
							overrides = []
							for override in rule.get("overrides"):
								matchtype = override.get("matchtype", "")
								if len(matchtype) == 0:
									sys.exit(f"Parser {parser_file} has an invalid override rule; matchtype cannot be empty; aborting.")
								matchkey = override.get("matchkey", "")
								if len(matchkey) == 0:
									sys.exit(f"Parser {parser_file} has an invalid override rule; matchkey cannot be empty; aborting.")
								_loglevel = override.get("loglevel", "")
								if len(_loglevel) == 0:
									sys.exit(f"Parser {parser_file} has an invalid override rule; loglevel cannot be empty; aborting.")
								try:
									severity = name_to_loglevel(_loglevel)
								except:
									sys.exit(f"Parser {parser_file} contains an invalid loglevel {_loglevel}; aborting.")

								overrides.append((matchtype, matchkey, severity))
							rules.append((rule_name, overrides))
						elif rule_name in ["bracketed_severity", "bracketed_timestamp_severity_facility"]:
							_loglevel = rule.get("default_loglevel", "info")
							try:
								default_loglevel = name_to_loglevel(_loglevel)
							except:
								sys.exit(f"Parser {parser_file} contains an invalid loglevel {_loglevel}; aborting.")
							rules.append((rule_name, default_loglevel))
						else:
							sys.exit(f"Parser {parser_file} has an unknown rule-type {rule}; aborting.")
					else:
						rules.append(rule)

				parsers.append(Parser(parser_name = parser_name, show_in_selector = show_in_selector, match_rules = matchrules, parser = ("custom", rules)))

	# Now do the same for built-in parsers
	for builtin_parser in builtin_parsers:
		# Old-style parser definition
		if type(builtin_parser[2]) == str:
			if type(builtin_parser[3]) == tuple and builtin_parser[3][0] == "custom":
				parser_name = "custom"
				show_in_selector = False
			elif type(builtin_parser[3]) == list:
				parser_name = "|".join(builtin_parser[3])
				show_in_selector = False
			else:
				parser_name = builtin_parser[3]
				show_in_selector = True
			matchrules = [(builtin_parser[0], builtin_parser[1], builtin_parser[2], "container")]
		# New-style parser definition;
		elif type(builtin_parser[2]) == list:
			parser_name = builtin_parser[0]
			show_in_selector = builtin_parser[1]
			matchrules = builtin_parser[2]
			parser = builtin_parser[3]
		else:
			sys.exit(f"Could not determine parser type for entry: {builtin_parser}; aborting.")

		parsers.append(Parser(parser_name = parser_name, show_in_selector = show_in_selector, match_rules = matchrules, parser = builtin_parser[3]))

def get_parser_list():
	_parsers = set()
	for parser in parsers:
		if parser.show_in_selector == False:
			continue
		else:
			_parsers.add(parser.parser_name)

	return _parsers

# pod_name, container_name, and image_name are used to decide what parser to use;
# this allows for different containers in the same pod to use different parsers,
# and different versions of pod to use different parsers
# "basic_8601" is for used unknown formats with ISO8601 timestamps, or other timestamps
# with similar ordering (YYYY MM DD HH MM SS, with several choices for separators and whitespace,
# include none, accepted)
#	2020-02-16T22:03:08.736292621Z
def logparser(pod_name, container_name, image_name, message, fold_msg = True, override_parser = None, container_type = "container", line = 0):
	# First extract the Kubernetes timestamp
	message, timestamp = split_iso_timestamp(message, None)

	if len(parsers) == 0:
		init_parser_list()

	if override_parser is not None:
		# Any other timestamps (as found in the logs) are ignored
		try:
			pod_name, severity, message, remnants = eval(override_parser)(message, fold_msg = fold_msg)
			return timestamp, pod_name, severity, message, remnants, ("<override>", str(override_parser))
		except Exception as e:
			return timestamp, "", loglevel.ERR, f"Could not parse using {str(override_parser)}:", [(message, loglevel.INFO)], ("<override>", str(override_parser))

	if image_name.startswith("docker-pullable://"):
		image_name = image_name[len("docker-pullable://"):]

	for parser in parsers:
		uparser = None
		lparser = None

		for matchrule in parser.match_rules:
			pod_prefix = matchrule[0]
			container_prefix = matchrule[1]
			image_prefix = matchrule[2]
			_container_type = matchrule[3]
			_image_name = image_name
			if image_prefix.startswith("/"):
				tmp = image_name.split("/", 1)
				if len(tmp) == 2:
					_image_name = "/" + tmp[1]

			if pod_name.startswith(pod_prefix) and container_name.startswith(container_prefix) and _image_name.startswith(image_prefix) and container_type  == _container_type:
				uparser = parser.parser_name
				# This allows for multiple parsers to be tested on the same log until a match is found
				if type(parser.parser) == list:
					for uparser in parser.parser:
						try:
							pod_name, severity, message, remnants = eval(uparser)(message, fold_msg = fold_msg)
							break
						except:
							pass
				elif type(parser.parser) == tuple and parser.parser[0] == "custom":
					options = {
						"__line": line,
					}
					pod_name, severity, message, remnants = custom_parser(message, fold_msg = fold_msg, filters = parser.parser[1], options = options)
				else:
					pod_name, severity, message, remnants = eval(parser.parser)(message, fold_msg = fold_msg)
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
	if uparser is None and lparser is None or len(lparser) == 0:
		pod_name, severity, message, remnants = basic_8601(message, fold_msg = fold_msg)
		lparser = "<unknown format>"
		uparser = "basic_8601"

	if len(message) > 16383:
		remnants = (message[0:16383], severity)
		severity = loglevel.ERR
		message = f"Line too long ({len(message)} bytes); truncated to 16384 bytes"

	# The UI gets mightily confused by tabs, so replace them with spaces
	# XXX: Doing this here doesn't make sense; at this point we don't know how long the line is.
	#      The only place where we can do this sensibly is in the curses helper.
	message = replace_tabs(message)
	remnants = replace_tabs(remnants)

	return timestamp, pod_name, severity, message, remnants, (lparser, str(uparser))
