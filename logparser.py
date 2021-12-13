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
except ModuleNotFoundError:
	import json
import re
import sys

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

def get_loglevel_names():
	# Ugly way of removing duplicate values from dict
	return list(dict.fromkeys(list(loglevel_mappings.values())))

def loglevel_to_name(severity):
	return loglevel_mappings[min(loglevel.DIFFSAME, severity)]

def name_to_loglevel(name):
	for severity in loglevel_mappings:
		if loglevel_mappings[severity] == name:
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
def letter_to_severity(letter):
	severities = {
		"F": loglevel.EMERG,
		"E": loglevel.ERR,
		"W": loglevel.WARNING,
		"N": loglevel.NOTICE,
		"C": loglevel.NOTICE,	# Used by jupyter for the login token
		"I": loglevel.INFO,
		"D": loglevel.DEBUG,
	}

	return severities.get(letter, loglevel.INFO)

def text_to_severity(text, default = loglevel.INFO):
	severities = {
		"error": loglevel.ERR,
		"warn": loglevel.WARNING,
		"warning": loglevel.WARNING,
		"notice": loglevel.NOTICE,
		"info": loglevel.INFO,
		"debug": loglevel.DEBUG,
	}

	return severities.get(text.lower(), default)

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

def split_4letter_severity(message):
	severities = {
		"CRIT: ": loglevel.CRIT,
		"FATA: ": loglevel.CRIT,
		"ERRO: ": loglevel.ERR,
		"WARN: ": loglevel.WARNING,
		"NOTI: ": loglevel.NOTICE,
		"INFO: ": loglevel.INFO,
		"DEBU: ": loglevel.DEBUG,
	}

	severity = severities.get(message[0:len("ERRO: ")], -1)
	if severity == -1:
		severity = loglevel.INFO
	else:
		message = message[len("ERRO: "):]

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
	else:
		severity = loglevel.INFO

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
		# 2020-02-13T12:06:18[+-]0000 (+timezone)
		tmp = re.match(r"^(\d\d\d\d-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)([\+-])(\d\d):?(\d\d) ?(.*)", message)
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
		severity = text_to_severity(tmp[1], default = severity)
		facility = tmp[2]
		message = tmp[3]

	return message, severity, facility

# 2020-12-27T02:57:49.887Z        INFO    controller-runtime.manager      starting metrics server {"path": "/metrics"}
def split_severity_facility_style(message, severity = loglevel.INFO, facility = ""):
	_message, _timestamp = split_iso_timestamp(message, None)
	if _message != message:
		message, severity, facility = split_severity_facility_style(_message, severity, facility)

	return message, severity, facility

def split_json_style(message, timestamp, severity = loglevel.INFO, facility = "", fold_msg = True):
	logentry = None
	remnants = None

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
				logentry = json.loads(json.dumps(d))
			except ValueError as e:
				pass

	if logentry is not None and type(logentry) == dict:
		msg = logentry.pop("msg", "")
		level = logentry.pop("level", None)
		# FIXME: timestamp since epoch?!
		# if timestamp = "":
		#	tmptimestamp = logentry.pop("ts", None)
		logentry.pop("ts", None)
		logentry.pop("time", None)
		logentry.pop("timestamp", None)

		logger = logentry.pop("logger", None)
		caller = logentry.pop("caller", None)

		if level is not None:
			tmpseverity = text_to_severity(level)
		else:
			tmpseverity = loglevel.DEBUG

		severity = min(tmpseverity, severity)

		if facility == "":
			if caller is not None:
				facility = caller
			elif logger is not None:
				facility = logger

		# Only if the facility is still empty after all this we try the filename
		if facility == "":
			facility = logentry.pop("filename", "")

		# If the message is folded, append the rest
		if fold_msg == True:
			# Append all remaining fields to message
			tmp = ""
			if msg == "":
				message = str(logentry)
			else:
				if len(logentry) > 0:
					message = f"{msg}  {logentry}"
				else:
					message = msg
		# else return an expanded representation
		else:
			message = msg
			if len(logentry) > 0:
				# Don't make the mistake of setting the loglevel higher than that of the main message
				if severity < loglevel.INFO:
					tmpseverity = loglevel.INFO
				else:
					tmpseverity = severity
				remnants = (json.dumps(logentry, indent = 8), tmpseverity)

	return message, timestamp, severity, facility, remnants

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

def split_colon_facility(message, facility = ""):
	tmp = re.match(r"^(.+?):\s?(.*)", message)
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
# transcode-server-gpu/{dirs,transcode-server-fifo,transcode-server-gpu}
# transcode-server-cpu/{dirs,transcode-server-fifo,transcode-server-gpu}
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

def strip_ansicodes(message):
	tmp = re.findall(r"(\x1b\[\d*m|\x1b\[\d+;\d+m|\x1b\[\d+;\d+;\d+m|.*?)", message)
	if tmp is not None:
		message = "".join(item for item in tmp if not item.startswith("\x1b"))

	return message

def split_bracketed_timestamp_severity_facility(message):
	severity = loglevel.INFO
	facility = ""

	tmp = re.match(r"\[(.*?) (.*?) (.*?)\]: (.*)", message)

	if tmp is not None:
		severity = text_to_severity(tmp[2])
		facility = tmp[3]
		message = tmp[4]

	return message, severity, facility

def antrea_ovs(message, fold_msg = True):
	facility = ""
	remnants = []

	message = strip_ansicodes(message)

	message, severity, facility = split_bracketed_timestamp_severity_facility(message)

	return facility, severity, message, remnants

# Calico
# Calico uses a mix of Kubernetes style logging and its own log format
# Example(s):
# I1007 15:50:18.167829       1 client.go:360] parsed scheme: "endpoint"
# 2020-10-28 16:12:03.681 [INFO][48] felix/int_dataplane.go 1259: Finished applying updates to dataplane. msecToApply=10.347240000000001
# time="2020-11-14T04:56:17Z" level=info msg="Running as a Kubernetes pod" source="install.go:140"
def calico(message, fold_msg = True):
	remnants = []
	facility = ""

	message, _timestamp = split_iso_timestamp(message, None)
	message, severity = split_bracketed_severity(message)

	if message.startswith("time=\""):
		# Try to parse this as key=value
		facility, severity, message, remnants = key_value(message, fold_msg = fold_msg)
	else:
		tmp = re.match(r"^(\[\d+\])\s+(.*\..*)\s+(\d+): (.*)", message)
		if tmp is not None:
			# We don't really care about the pid,
			# but let's assign it just to document what it is
			pid = tmp[1]
			facility = f"{tmp[2]}:{tmp[3]}"
			message = tmp[4]
		else:
			message, severity, facility, remnants, _match = split_glog(message)

	if message.startswith("CNI plugin version"):
		severity = min(loglevel.NOTICE, severity)
	if message.endswith("\\n"):
		message = message[:-2]

	return facility, severity, message, remnants

# K8s etcd/etcd
# Note: Uses logger which has its own log messages
#       to warn about deprecated usage...
# So we're essentially parsing two formats in one. "Yay!"
# Example(s):
# Also, all lines (except the raft lines) seem to be prefixed
# by a facility
# raft2020/02/21 23:26:05 INFO:
# There are also log messages from grpc that have another format...
# WARNING: 2020/04/03 04:54:55 grpc: Server.processUnaryRPC failed [...]
def etcd(message, fold_msg = True):
	remnants = []

	message, tmpseverity1, facility, remnants, _match = split_glog(message)

	# Reformat log messages from grpc
	# Do this before splitting second round of timestamps
	# since the warning precedes the timestamp
	message, tmpseverity2 = split_colon_severity(message)

	# Split second round of timestamps...
	message, _timestamp = split_iso_timestamp(message, None)

	# Get rid of the warning from logger
	message, tmpseverity3 = split_bracketed_severity(message)
	severity = min(tmpseverity1, tmpseverity2, tmpseverity3)

	tmp = re.match(r"^(. \| |[A-Z]+: )(.*)", message)

	if tmp is not None:
		if tmp[1][2] == "|":
			severity = letter_to_severity(tmp[1][0])
			message = tmp[2]
		else:
			# The severity we get here is "<severity>: "
			# the parser expects "<severity>",
			# so strip the last two characters
			severity = text_to_severity(tmp[1][:-2])
			message = tmp[2]

	tmp = re.match(r"^(raft)\d+\/\d\d\/\d\d \d\d:\d\d:\d\d ([A-Z]+): (.*)", message)
	if tmp is not None:
		facility = tmp[1]
		severity = text_to_severity(tmp[2])
		message = tmp[3]
	else:
		tmp = re.match(r"^(.*?): (.*)", message)

		if tmp is not None:
			facility = tmp[1]
			message = tmp[2]
		else:
			facility = ""

		if message.startswith("etcd Version: "):
			severity = loglevel.NOTICE
		elif message == "/health OK (status code 200)":
			severity = loglevel.DEBUG

	return facility, severity, message, remnants

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
		extra_message, _timestamp, _severity, _facility, remnants = split_json_style(tmp[2], None, severity = severity, facility = facility, fold_msg = fold_msg)
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
			tmpseverity = text_to_severity(level)
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
				remnants = (json.dumps(logentry, indent = 8), tmpseverity)
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

		"cilium-envoy  version",
		"Cilium Operator",
		"CoreDNS-",
		"Kiali: Version: ",
		"Kiali: Console version: ",
		"Kubernetes host: ",
		"kube-router version",
		"NGINX Ingress controller",
		"nginx version:",
		"Node Feature Discovery Master v",
		"Node Feature Discovery Worker v",
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
					# This is used as severity by prometheus,
					# but probably not by cert-manager
					s = text_to_severity(value, -1)
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

# kube-apiserver/kube-api-server
# kube-proxy/kube-proxy
# nginx-ingress-controller/nginx-ingress-controller
# metrics-server/metrics-server
# kube-state-metrics/*
# Example(s):
# I0221 23:26:05.862399       1 server.go:150] Version: v1.17.3
# E0702 11:03:23.913858859       1 server_chttp2.cc:40]        {"created":
# http-style messages
# [10/Feb/2020:23:09:45 +0000]TCP200000.000
# coredns
# [INFO] plugin/reload: Running configuration MD5 = cb191f785bff0d5c3182d766e6656707
# metrics-server:
# [restful] 2020/03/04 10:24:17 log.go:33: [restful/swagger] listing is available at https://:443/swaggerapi
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

	# coredns (possibly others) can have some messages with another severity format
	message, tmpseverity = split_bracketed_severity(message)
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

	# metrics-server has something special going on
	tmp = re.match(r"^\[.*?\]\s.*?\s.*?\s(.+?:\d+?): (\[.*?\]\s.*)", message)
	if tmp is not None:
		facility = tmp[1]
		message = tmp[2]

	# JSON/Python dict
	message, _timestamp, severity, facility, remnants = split_json_style(message, None, severity, facility, fold_msg)
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
		severity = text_to_severity(tmp[1])
		facility = tmp[2]
		message = tmp[3]

	# Some log messages have an additional JSON portion at the end;
	# expand it if available and the configuration requests this
	tmp = re.match(r"^(.*?)\s*?({.*})", message)
	if tmp is not None:
		message = tmp[1]
		extra_message, _timestamp, severity, facility, remnants = split_json_style(tmp[2], None, severity, facility, fold_msg)
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
			_severity = text_to_severity(tmp[1], -1)
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

# K8s weave-scope
# Example(s):
# time="2020-11-03T22:35:47Z" level=info msg="publishing to: weave-scope-app.weave.svc.cluster.local:80"
# <probe> INFO: 2020/11/03 22:35:47.831489 Basic authentication disabled
def weave_scope(message, fold_msg = True):
	facility = ""
	remnants = None

	# There only seems to be one type of key=value; the initial timestamp message
	tmp = re.match(r"^<(.*?)> ([A-Z][A-Z][A-Z][A-Z]: .*)", message)
	if tmp is not None:
		facility = tmp[1]
		message = tmp[2]

		message, severity = split_4letter_severity(message)
		message, _timestamp = split_iso_timestamp(message, None)
	else:
		# Try to parse this as key=value
		facility, severity, message, remnants = key_value(message, fold_msg = fold_msg)

	return facility, severity, message, remnants

# K8s weave-net/weave
# K8s weave-net/weave-npc
# Example(s):
#INFO: 2020/02/22 00:13:38.845733 weave  2.6.0
#DEBU: 2020/02/22 00:13:40.072753 [kube-peers] [...]
#Sat Feb 22 00:13:44 2020 <5> ulogd.c:843 building new pluginstance stack: 'log1:NFLOG,base1:BASE,pcap1:PCAP'
def weave(message, fold_msg = True):
	facility = ""
	remnants = None

	# It seems for some reason we may end up with NUL in the log; remove them
	message = message.replace("\0", "")

	message, severity = split_4letter_severity(message)
	# Another timestamp to remove
	message, _timestamp = split_iso_timestamp(message, None)

	message, severity, facility, remnants, _match = split_glog(message, severity)

	# Believe it or not, another timestamp format... A seriously weird format.
	message, _timestamp = split_wd_mmm_dd_hh_mm_ss_yyyy_timestamp(message, None)

	# The message we get back from the previous timestamp might contain facility and severity
	# on the format <5> ulogd.c:843; extract it

	tmp = re.match(r"^<(\d)> (.*?:\d+) (.*)", message)

	if tmp is not None:
		severity = int(tmp[1])
		facility = tmp[2]
		message = tmp[3]

	# Some log messages have an additional JSON portion at the end;
	# expand it if available and the configuration requests this.
	# However, there are update messages that are used to indicate change
	# from one state to another: this means that there are two JSON objects
	# on one line. This will make the parser puke, which is generally not
	# a good idea.
	#
	# When the line is folded we don't really care though,
	# since the parser will simply return the message unchanged
	# if it cannot parse it.
	raw_message = message
	tmp = re.match(r"^(.*?)\s*?({.*})", message)
	if tmp is not None:
		message = tmp[1]

		if fold_msg == False and tmp[1].startswith("EVENT") and "} {" in tmp[2]:
			tmp = re.match(r"^({.*})\s*({.*})", tmp[2])

			if tmp is not None:
				old = tmp[1]
				new = tmp[2]

				if old != new:
					# We cannot do anything sensible here except ignore extra_message
					old_extra_message, _timestamp, severity, facility, old_remnants = split_json_style(old, None, severity, facility, fold_msg)
					new_extra_message, _timestamp, severity, facility, new_remnants = split_json_style(new, None, severity, facility, fold_msg)

					oldstring = None
					newstring = None
					try:
						oldstring, oldseverity = old_remnants
					except TypeError:
						pass
					try:
						newstring, newseverity = new_remnants
					except TypeError:
						pass
					if oldstring is None or newstring is None:
						message = raw_message
						tmp = None
					else:
						remnants = []
						y = 0
						for el in difflib.unified_diff(oldstring.split("\n"), newstring.split("\n"), n = sys.maxsize, lineterm = ""):
							y += 1
							if y < 4:
								continue
							if el.startswith("+"):
								remnants.append((el, loglevel.DIFFPLUS))
							elif el.startswith("-"):
								remnants.append((el, loglevel.DIFFMINUS))
							else:
								remnants.append((el, loglevel.DIFFSAME))

						if severity > loglevel.INFO:
							tmpseverity = loglevel.INFO
						else:
							tmpseverity = severity
						message += " [State modified]"
						# To avoid processing twice
						tmp = None
				else:
					message += " [No changes]"

	if tmp is not None:
		# No matter if we got one or two objects tmp[2] will conveniently contain a copy of the object
		extra_message, _timestamp, severity, facility, remnants = split_json_style(tmp[2], None, severity, facility, fold_msg)
		if len(extra_message) > 0:
			if remnants is None or len(remnants) == 0:
				message = "%s  %s" % (message, extra_message)
			else:
				raise Exception("message: %s\nextra_message: %s" % (message, extra_message))

	# Override the severity for the version string
	message, severity = override_severity(message, severity)
	if re.match(r"^weave\W+\d+\.\d+\.\d+$", message):
		severity = loglevel.NOTICE
	elif re.match(r"^Weave version.*is available; please update", message):
		severity = loglevel.NOTICE

	return facility, severity, message, remnants

# K8s dashboard-metrics-scraper/dashboard-metrics-scraper
# Example(s):
# 10.32.0.1 - - [22/Feb/2020:16:34:30 +0000] "GET / HTTP/1.1" 200 6 " [...]
# {"level":"error","msg":"Error [...]","time":"2020-02-22T16:34:39Z"}
def dashboard_metrics_scraper(message, fold_msg = True):
	facility = ""
	remnants = []

	severity = loglevel.INFO

	# Try to parse it as json
	if message.startswith("{\""):
		message, _timestamp, severity, facility, remnants = split_json_style(message, None)

	tmp = re.match(r"(\d+\.\d+\.\d+\.\d+ .*) \[\d+/[A-Z][a-z][a-z]/\d+:\d\d:\d\d:\d\d [\+-]\d+\] (.*)", message)
	if tmp is not None:
		message = "%s %s" % (tmp[1], tmp[2])

	# Override severity for the Kubernetes host message
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
		severity = text_to_severity(tmp[2])
		message = tmp[3]
	else:
		facility = ""
		severity = loglevel.INFO

	return facility, severity, message, remnants

def format_key_value(key, value, severity):
	if key == "error":
		tmp = [(f"{key}", ("types", "key_error")), ("separators", "keyvalue_log"), (f"{value}", ("logview", f"severity_{loglevel_to_name(severity).lower()}"))]
	else:
		tmp = [(f"{key}", ("types", "key")), ("separators", "keyvalue_log"), (f"{value}", ("types", "value"))]
	return tmp

# Severity: lvl=|level=
# Timestamps: t=|ts=|time= (all of these are ignored)
# Facility: subsys|caller|logger|source
def key_value(message, fold_msg = True):
	extract_msg = True		# msg="foo" or msg=foo => foo
	bullet_collectors = True	# collector=foo => • foo
	merge_starting_version = True	# msg="Starting foo" version="(version=.*)" => Starting foo (version=.*)
	facility = ""
	remnants = []
	severity = loglevel.INFO

	# Replace embedded quotes with fancy quotes
	message = message.replace("\\\"", "”")

	# split all key=value pairs
	tmp = re.findall(r'(?:[^\s,"]|"(?:\\.|[^"])*")+', message)
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

		d.pop("t", None)
		d.pop("ts", None)
		d.pop("time", None)
		level = d.pop("level", None)
		if level is None:
			level = d.pop("lvl", "info")
		severity = level_to_severity(level)

		msg = d.get("msg", "")
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

		facility = d.pop("subsys", "")
		if facility == "":
			facility = d.pop("caller", "")
		if facility == "":
			facility = d.pop("logger", "")
		if facility == "":
			facility = d.pop("source", "").strip("\"")
		if facility == "":
			facility = d.pop("Topic", "")

		if fold_msg == False and len(d) == 2 and merge_starting_version == True and "msg" in d and msg.startswith("Starting") and "version" in d and version.startswith("(version="):
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
						if line.startswith("* "):
							remnants.append(([("separators", "logbullet"), (f"{line[2:]}", ("logview", f"severity_{loglevel_to_name(severity).lower()}"))], severity))
						else:
							remnants.append((f"{line}", severity))
		else:
			tmp = []
			# We always want msg first
			if extract_msg == True and fold_msg == False and len(msg) > 0:
				tmp.append(msg)
				d.pop("msg", "")
			else:
				msg = d.pop("msg", "")
				if len(msg) > 0:
					tmp.append(f"msg={msg}")

			for item in d:
				if fold_msg == False:
					if item == "collector" and bullet_collectors == True:
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
				severity = text_to_severity(tmp[3])
				message = tmp[4]
		else:
			tmp = re.match(r"^(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d,\d\d\d) \| (.+?) \| ([A-Z]+) \| (.*)", message)
			if tmp is not None:
				_timestamp = tmp[1]
				facility = tmp[2]
				severity = text_to_severity(tmp[3])
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
		severity = text_to_severity(tmp[1])
		message = tmp[2]

	tmp = re.match(r"^\[(\d+-\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\]\[\d+\]\[([a-z]+)\]\[([a-z]+)\] \[(.+)\] (.*)", message)
	if tmp is not None:
		# timestamp = tmp[1]
		# something = tmp[3]
		if severity is None:
			severity = text_to_severity(tmp[2])
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
		severity = text_to_severity(tmp[1])
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

# nginx:
# 10-listen-on-ipv6-by-default.sh: error: /etc/nginx/conf.d/default.conf is not a file or does not exist
# [notice] 1#1: nginx/1.19.3
def nginx(message, fold_msg = True):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	# Another timestamp to strip
	message, _timestamp = split_iso_timestamp(message, None)

	message, severity = split_bracketed_severity(message)

	tmp = re.match(r"^(.*?):\s(.*)", message)
	if tmp is not None:
		facility = tmp[1]
		message = tmp[2]

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

def split_tiller_style(message, facility = None):
	tmp = re.match(r"^\[(.+?)\] \d\d\d\d/\d\d/\d\d \d\d:\d\d:\d\d (.*)", message)

	if tmp is not None:
		facility = tmp[1]
		# Another timestamp to strip
		message, _timestamp = split_iso_timestamp(tmp[2], None)
	return message, facility

# This should possibly be merged with kube_parser_structured_glog
def linkerd(message, fold_msg = True):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	# Linkerd specific
	tmp = re.match(r"\[[0-9.\ss]+\]\s*([A-Z]+)\s(ThreadId\(\d+\))\s*(.*)", message)

	if tmp is not None:
		severity = text_to_severity(tmp[1])
		facility = f"{tmp[2]}"
		message = tmp[3]

	# Split into substrings based on spaces
	tmp = re.findall(r"(?:\".*?\"|\S)+", message)

	if tmp is not None and len(tmp) > 0 and "=" in tmp[0]:
		fac, sev, message, remnants = key_value(message, fold_msg = fold_msg)
		if len(facility) == 0:
			facility = fac
		if sev < severity:
			severity = sev

	# If the message contains a version,
	# or something similarly useful, bump the severity
	message, severity = override_severity(message, severity)

	return facility, severity, message, remnants

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

def aic_manager(message, fold_msg = True):
	facility = ""
	severity = loglevel.INFO
	remnants = []

	tmp = re.match(r"^(.)/(.+?)\( (\d+?)\): (.*)", message)
	if tmp is not None:
		severity = letter_to_severity(tmp[1])
		facility = tmp[2]
		pid = tmp[3]
		message = tmp[4]
		return facility, severity, message, remnants

	tmp = re.match(r"^(sh): (\d+?): (.*)", message)
	if tmp is not None:
		facility = f"{tmp[1]}:{tmp[2]}"
		message = tmp[3]
		if message.startswith("cannot create"):
			severity = loglevel.WARNING
		return facility, severity, message, remnants

	tmp = re.match("\[(/.+?) \((\d+?/\d+?)\)\] (.*)", message)
	if tmp is not None:
		facility = tmp[1]
		pid = tmp[2]
		message = tmp[3]

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

# cert-manager:
# I0414 22:31:37.014288       1 start.go:76] cert-manager "level"=0 "msg"="starting controller"  "git-commit"="b030b7eb4" "version"="v0.11.0"
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

		# Handle both cert-manager and prometheus
		#tmp = re.match(r"^(.*?) (.*)", message)
		#if tmp is not None and not "=" in tmp[1]:
		#	header = tmp[1]
		#	message = tmp[2]

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
						# This is used as severity by prometheus,
						# but probably not by cert-manager
						s = text_to_severity(value, -1)
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

def custom_parser(message, fold_msg = True, filters = []):
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
			elif _filter == "key_value" and "=" in message:
				facility, severity, message, remnants = key_value(message, fold_msg = fold_msg)
			elif _filter == "directory":
				facility, severity, message, remnants = directory(message, fold_msg = fold_msg)
			# Timestamp formats
			elif _filter == "8601": # Anything that resembles ISO-8601
				message, _timestamp = split_iso_timestamp(message, None)
			# Facility formats
			elif _filter == "colon_facility":
				message, facility = split_colon_facility(message, facility)
			# Severity formats
			elif _filter == "colon_severity":
				message, severity = split_colon_severity(message, severity)
		elif type(_filter) == tuple:
			# Severity formats
			if _filter[0] == "bracketed_severity":
				message, severity = split_bracketed_severity(message, default = _filter[1])

	return facility, severity, message, remnants

# istio-proxy:
# 2020-04-17T10:58:19.855304Z     info    FLAG: --applicationPorts="[]"
# 2020-04-17T10:58:19.855418Z     info    Version root@1844d064-72cc-11e9-a0d5-0a580a2c0304-docker.io/istio-1.1.6-04850e14d38a69a38c16c800e237b1108056513e-Clean
# [2020-04-17 10:58:19.870][18][warning][misc] [external/envoy/source/common/protobuf/utility.cc:174] Using deprecated option 'envoy.api.v2.Cluster.hosts' from file cds.proto.
# 2020-04-14T14:20:47.966209Z     info    ControlZ available at 10.32.0.25:9876

# application-controller-stateful-set
# 2020/04/17 12:41:22 Requested Deployment.apps, Registered: apps/v1beta1, Kind=DeploymentList
# 2020/04/17 12:41:22 *v1beta1.Application/knative-serving/knative-serving-install(cmpnt:app)  Expected Resources:

# argo-ui:
# start argo-ui on 0.0.0.0:8001
# info: 200 GET 13ms / {"meta":{},"timestamp":"2020-04-17T10:18:48.775Z"}

Parser = namedtuple("Parser", "facility subfacility subsubfacility parser")
parsers = [
	# Format: pod, container, image, parser
	# One or more of pod, container, image can be left empty

	Parser("internal_error", "", "", "basic_8601_colon_severity"),

	Parser("3scale-kourier-gateway", "", "", "istio"),

	Parser("activator", "istio-init_init", "", "basic_8601"),
	Parser("activator", "istio-proxy", "", "istio"),
	Parser("admission-webhook-bootstrap-stateful-set", "bootstrap", "", "basic_8601"),
	Parser("admission-webhook-bootstrap", "", "", "basic_8601"),
	Parser("admission-webhook-deployment", "admission-webhook", "", "kube_parser_1"),
	Parser("admission-webhook-deployment", "", "", "kube_parser_1"),
	Parser("alertmanager-main", "config-reloader", "", "kube_parser_structured_glog"),
	Parser("alertmanager-main", "", "", "key_value"),
	Parser("antrea", "antrea-ovs", "", "antrea_ovs"),
	Parser("antrea", "", "", "kube_parser_1"),
	Parser("application-controller-stateful-set", "manager", "", "kube_parser_1"),
	Parser("argo-ui", "argo-ui", "", "basic_8601_colon_severity"),
	Parser("autoscaler-hpa", "autoscaler-hpa", "", "kube_parser_1"),
	Parser("autoscaler", "istio-init_init", "", "basic_8601"),
	Parser("autoscaler", "istio-proxy", "", "istio"),

	Parser("blackbox-exporter", "", "", "kube_parser_structured_glog"),
	Parser("aic-manager", "aic-manager", "", "aic_manager"),
	Parser("aic-manager", "init-android", "", "modinfo"),

	Parser("calico", "", "", "calico"),
	Parser("canal", "install-cni", "", "kube_parser_structured_glog"),
	Parser("canal", "", "", "calico"),
	Parser("cass-operator", "", "", "kube_parser_json"),
	Parser("cdi-controller", "", "", "kube_parser_1"),
	Parser("cdi-node", "", "", "kube_parser_1"),
	Parser("cert-manager", "", "", "kube_parser_structured_glog"),
	Parser("centraldashboard", "", "", "basic_8601"),
	Parser("cifar10-training-gpu-worker", "", "", "kube_parser_1"),
	Parser("cilium", "", "", "key_value"),
	Parser("cluster-local-gateway", "istio-proxy", "", "istio"),
	Parser("coredns", "", "", "kube_parser_1"),

	Parser("dashboard-metrics-scraper", "", "", "dashboard_metrics_scraper"),
	Parser("", "", "k8s.gcr.io/descheduler/descheduler", "kube_parser_structured_glog"),
	Parser("", "", "quay.io/dexidp/dex", "key_value"),
	Parser("dist-mnist", "", "", "jupyter"),
	Parser("dns-autoscaler", "", "", "kube_parser_structured_glog"),

	Parser("etcd", "etcd-metrics", "", "kube_parser_json"),
	Parser("etcd", "", "", ["kube_parser_json", "etcd"]),
	Parser("master-etcd", "", "", "etcd"),

	Parser("gpu-aware-scheduling", "", "", "kube_parser_1"),
	Parser("grafana", "", "", "key_value"),
	Parser("", "grafana-operator", "", "kube_parser_json_glog"),

	Parser("helm-", "", "", "kube_parser_1"),

	Parser("ingress-nginx-controller", "", "", "kube_parser_1"),
	Parser("inteldeviceplugins-controller-manager", "", "", "kube_parser_structured_glog"),
	Parser("intel-gpu-plugin", "", "", "kube_parser_1"),
	Parser("intel-qat-plugin", "", "", "kube_parser_1"),
	Parser("intel-sgx-aesmd", "", "", "kube_parser_1"),
	Parser("intel-sgx-plugin", "", "", "kube_parser_1"),
	Parser("intel-telemetry-plugin", "", "", "kube_parser_1"),
	Parser("intel-vpu-plugin", "", "", "kube_parser_1"),
	Parser("istio-citadel", "citadel", "", "istio"),
	Parser("istio-cleanup-secrets", "kubectl", "", "istio"),
	Parser("istio-egressgateway", "istio-proxy", "", "istio"),
	Parser("istio-galley", "galley", "", "istio"),
	Parser("istio-ingressgateway", "istio-proxy", "", "istio"),
	Parser("", "", "docker.io/istio/proxyv2", "istio_pilot"),
	Parser("", "", "docker.io/istio/pilot", "istio_pilot"),
	Parser("istio-pilot", "", "", "istio"),
	Parser("istio-policy", "", "", "istio"),
	Parser("istio-sidecar-injector", "sidecar-injector-webhook", "", "istio"),
	Parser("istio-telemetry", "mixer", "", "kube_parser_json"),
	Parser("istio-telemetry", "", "", "istio"),
	Parser("istio-tracing", "jaeger", "", "kube_parser_json"),

	Parser("jaeger", "", "", "kube_parser_structured_glog"),

	Parser("katib-controller", "", "", "kube_parser_json_glog"),
	Parser("katib-db-manager", "", "", "kube_parser_1"),
	Parser("katib-ui", "", "", "kube_parser_1"),
	Parser("kfserving-controller-manager", "", "", "kube_parser_1"),
	Parser("kfserving-ingressgateway", "istio-proxy", "", "istio"),
	Parser("kiali", "", "", "kube_parser_1"),
	Parser("kilo", "", "", "kube_parser_json_glog"),
	Parser("", "", "gcr.io/knative", "kube_parser_1"),
	Parser("k8s-mlperf-image-classification-training", "", "", "kube_parser_1"),
	Parser("kubernetes-dashboard", "", "", "basic_8601"),
	Parser("kube-apiserver", "", "", "kube_parser_structured_glog"),
	Parser("", "kube-rbac-proxy", "", "kube_parser_1"),
	Parser("kube-app-manager-controller", "kube-app-manager", "", "kube_app_manager"),
	Parser("kube-controller-manager", "", "", "kube_parser_structured_glog"),
	Parser("kube-flannel", "install-cni", "", "kube_parser_structured_glog"),
	Parser("kube-flannel", "kube-flannel", "", "kube_parser_1"),
	# kubeflow
	Parser("", "", "gcr.io/arrikto/kubeflow/oidc-authservice", "key_value"),
	Parser("kube-proxy", "", "", "kube_parser_structured_glog"),
	Parser("kubernetes-metrics-scraper", "", "", "dashboard_metrics_scraper"),
	Parser("kube-router", "", "", "kube_parser_structured_glog"),
	Parser("kube-scheduler", "", "", "kube_parser_structured_glog"),
	Parser("kube-state-metrics", "", "", "kube_parser_1"),

	Parser("linkerd", "linkerd-init", "", "basic_8601"),
	Parser("linkerd", "", "", "linkerd"),
	Parser("local-path-provisioner", "", "", "kube_parser_1"),

	Parser("metacontroller", "metacontroller", "", "kube_parser_1"),
	Parser("metadata-db", "db-container", "", "mysql"),
	Parser("metadata-deployment", "container", "", "kube_parser_1"),
	Parser("metadata-envoy-deployment", "container", "", "istio"),
	Parser("metadata-grpc-deployment", "container", "", "kube_parser_1"),
	Parser("metadata-ui", "metadata-ui", "", "basic_8601"),

	Parser("", "", "docker.io/metallb", "kube_parser_json_glog"),
	Parser("", "", "metallb", "kube_parser_json_glog"),

	Parser("metrics-server", "", "", "kube_parser_1"),
	Parser("minio", "minio", "", "basic_8601"),
	Parser("ml-pipeline", "ml-pipeline-api-server", "", "kube_parser_1"),
	Parser("ml-pipeline", "ml-pipeline-visualizationserver", "", "kube_parser_1"),	#UNKNOWN
	Parser("ml-pipeline", "ml-pipeline-persistenceagent", "", "kube_parser_structured_glog"),
	Parser("ml-pipeline", "ml-pipeline-scheduledworkflow", "", "kube_parser_structured_glog"),
	Parser("ml-pipeline", "ml-pipeline-ui", "", "kube_parser_1"),
	Parser("ml-pipeline", "ml-pipeline-viewer-controller", "", "kube_parser_1"),
	Parser("", "", "docker.io/kubeflow/mxnet-operator", "kube_parser_json_glog"),
	Parser("mysql", "mysql", "", "mysql"),
	Parser("", "", "docker.io/library/mysql", "mysql"),

	Parser("networking-istio", "networking-istio", "", "kube_parser_1"),
	Parser("nfd-master", "", "", "kube_parser_1"),
	Parser("nfd-worker", "", "", "kube_parser_1"),
	Parser("", "", "k8s.gcr.io/sig-storage/nfs-subdir-external-provisioner", "kube_parser_1"),
	Parser("node-exporter", "", "", "key_value"),
	Parser("node-problem-detector", "", "", "kube_parser_1"),
	Parser("nodelocaldns", "", "", "kube_parser_1"),
	Parser("notebook-controller-deployment", "manager", "", "seldon"),
	Parser("nginx-ingress-controller", "", "", "kube_parser_1"),
	Parser("nginx", "", "", "nginx"),
	Parser("gpu-feature-discovery", "toolkit-validation", "", "basic_8601"),
	Parser("gpu-feature-discovery", "", "", ("custom", ["colon_facility", "8601"])),
	Parser("gpu-operator", "", "", ("custom", ["glog", "8601", "spaced_severity_facility", "key_value", "colon_severity"])),
	Parser("nvidia-cuda-validator", "", "", "basic_8601"),
	Parser("nvidia-device-plugin", "", "", "basic_8601"),
	Parser("nvidia-container-toolkit", "driver-validation", "", "basic_8601"),
	Parser("nvidia-container-toolkit", "", "", "key_value"),
	Parser("nvidia-dcgm", "toolkit-validation", "", "basic_8601"),
	Parser("nvidia-dcgm", "", "", "key_value"),
	Parser("nvidia-operator-validator", "cuda-validation", "", "key_value"),
	Parser("nvidia-operator-validator", "plugin-validation", "", "key_value"),
	Parser("nvidia-operator-validator", "", "", "basic_8601"),
	Parser("nvidia-smi-exporter", "", "", "nvidia_smi_exporter"),

	Parser("", "", "docker.io/openshift/origin-hypershift", "kube_parser_1"),
	Parser("", "", "docker.io/openshift/origin-service", "kube_parser_1"),
	Parser("", "", "docker.io/openshift/origin-docker", "key_value"),
	Parser("", "", "openshift/origin-docker", "key_value"),
	Parser("", "", "openshift/origin-", "kube_parser_1"),

	Parser("", "", "quay.io/operator-framework/olm", "kube_parser_structured_glog"),
	Parser("", "", "quay.io/operatorhubio/catalog", "kube_parser_structured_glog"),

	Parser("apiserver", "", "", "kube_parser_1"),
	Parser("openshift-apiserver", "", "", "kube_parser_1"),
	Parser("openshift-config", "", "", "kube_parser_1"),
	Parser("openshift-controller-manager", "", "", "kube_parser_1"),
	Parser("controller-manager", "", "", "kube_parser_structured_glog"),
	Parser("console", "", "quay.io/openshift", "kube_parser_1"),
	Parser("dns-operator", "", "", "kube_parser_structured_glog"),
	Parser("dns-default", "", "", "kube_parser_1"),
	Parser("authentication-operator", "", "", "kube_parser_1"),
	Parser("oauth-openshift", "", "", "kube_parser_1"),
	Parser("machine-approver", "", "", "kube_parser_1"),
	Parser("tuned", "", "", "kube_parser_1"),
	Parser("cluster-samples-operator", "cluster-samples-operator-watch", "", "kube_parser_1"),
	Parser("cluster-samples-operator", "", "", "key_value"),
	Parser("cluster-image-registry-operator", "", "", "kube_parser_1"),
	Parser("image-registry", "", "", "key_value"),
	Parser("openshift-kube-scheduler-operator", "", "", "kube_parser_1"),
	Parser("openshift-kube-scheduler-crc", "", "", "kube_parser_1"),
	Parser("certified-operators", "", "", "key_value"),
	Parser("community-operators", "", "", "key_value"),
	Parser("marketplace-operator", "", "", "key_value"),
	Parser("redhat-marketplace", "", "", "key_value"),
	Parser("multus", "", "", "kube_parser_1"),
	Parser("network-metrics", "", "", "kube_parser_1"),
	Parser("network-check-", "", "", "kube_parser_1"),
	Parser("catalog-operator", "", "", "kube_parser_structured_glog"),

	# FIXME
	#Parser("olm-operator", "", "", "kube_parser_structured_glog"),

	Parser("packageserver", "", "", "kube_parser_structured_glog"),
	Parser("sdn-", "", "", "kube_parser_1"),
	Parser("service-ca-", "", "", "kube_parser_1"),

	# FIXME
	#Parser("ingress-operator", "", "", "seldon"),

	Parser("parallel-pipeline", "", "", "kube_parser_1"),
	Parser("pmem-csi-", "", "", "kube_parser_1"),
	Parser("profiles-deployment", "kfam", "", "kube_parser_1"),
	Parser("profiles-deployment", "manager", "", "seldon"),
	Parser("prometheus-adapter", "", "", "kube_parser_1"),
	Parser("prometheus-k8s", "rules-configmap-reloader", "", "basic_8601"),
	Parser("prometheus-k8s", "", "", "kube_parser_structured_glog"),
	Parser("prometheus-operator", "", "", "key_value"),
	Parser("", "kube-prometheus-stack", "", "kube_parser_structured_glog"),
	# This needs to be last of the prometheus parsers
	Parser("prometheus", "prometheus", "", "kube_parser_structured_glog"),
	Parser("pytorch-operator", "", "", "kube_parser_1"),	#ALMOST

	Parser("", "reaper-operator", "", "kube_app_manager"),

	Parser("seldon-controller-manager", "", "", "seldon"),
	Parser("spark-operatorcrd-cleanup", "delete-scheduledsparkapp-crd", "", "kube_parser_1"),	#ALMOST
	Parser("spark-operatorcrd-cleanup", "delete-sparkapp-crd", "", "kube_parser_1"),	#ALMOST
	Parser("spark-operatorsparkoperator", "", "", "kube_parser_1"),
	Parser("spartakus-volunteer", "", "", "kube_parser_1"),

	# This is starboard; the pod names seem to be UUIDs, so pointless to try to match
	# XXX: The kube-bench log format is actually structured, but it seems to be malformed
	Parser("", "kube-bench", "", "basic_8601"),
	Parser("", "kube-hunter", "", "kube_parser_json"),
	Parser("", "polaris", "", "kube_parser_structured_glog"),
	Parser("", "create", "docker.io/aquasec/trivy", "kube_parser_json_glog"),
	Parser("", "", "docker.io/aquasec/trivy", "basic_8601"),
	Parser("starboard-operator", "", "", "kube_parser_json_glog"),

	Parser("telemetry-aware-scheduling", "", "", "kube_parser_1"),
	Parser("tensorboard-controller-controller-manager", "manager", "", "istio_pilot"),
	Parser("tensorboard", "tensorboard", "", "kube_parser_1"),
	Parser("tf-job-operator", "", "", "kube_parser_1"),
	Parser("tiller-deploy", "tiller", "", "tiller"),
	Parser("traefik", "", "", "kube_parser_json"),

	Parser("svclb-traefik", "", "", "kube_parser_1"),

	Parser("", "", "gcr.io/ml-pipeline/viewer-crd-controller", "kube_parser_1"),
	Parser("virt-operator", "", "", "kube_parser_json"),
	Parser("volcano-admission-init", "", "docker.io/volcanosh/vc-webhook-manager", "basic_8601_raw"),
	Parser("", "", "docker.io/volcanosh/vc-webhook-manager", "kube_parser_1"),
	Parser("", "", "docker.io/volcanosh/vc-controller-manager", "kube_parser_1"),
	Parser("", "", "docker.io/volcanosh/vc-scheduler", "kube_parser_1"),

	Parser("weave-net", "", "", "weave"),
	Parser("weave-scope", "", "", "weave_scope"),
	Parser("jupyter-web-app", "", "", "web_app"),
	Parser("tensorboards-web-app", "", "", "web_app"),
	Parser("volumes-web-app", "", "", "web_app"),
	Parser("workflow-controller", "", "", "kube_parser_structured_glog"),

	Parser("", "", "docker.io/kubeflow/xgboost-operator", "kube_parser_json"),

	Parser("raw", "", "", "basic_8601_raw"),
	# This should always be last
	Parser("", "", "", "basic_8601")
]

def get_parser_list():
	_parsers = set()
	for _pod, _image, _container, parser in parsers:
		if type(parser) == list:
			for p in parser:
				_parsers.add(p)
		elif type(parser) == tuple:
			# Since custom parser are, by definition, custom
			# we shouldn't include them in the list of parsers
			continue
		else:
			_parsers.add(parser)
	return _parsers

# facility is the originator of the log message;
# for K8s this is the name of the pod
# subfacility is for further distinction;
# for K8s this is the container--sometimes a pod has containers with different log formats
# subsubfacility is yet another distinction;
# for K8s this would be used for the name of a docker image when neither pod name nor container
# name forms a useful distinction
# "basic_8601" is for used unknown formats with ISO8601 timestamps
#	2020-02-16T22:03:08.736292621Z
def logparser(facility, subfacility, subsubfacility, message, fold_msg = True, override_parser = None):
	# First extract the Kubernetes timestamp
	message, timestamp = split_iso_timestamp(message, None)

	if override_parser is not None:
		# Any other timestamps (as found in the logs) are ignored
		try:
			facility, severity, message, remnants = eval(override_parser)(message, fold_msg = fold_msg)
			return timestamp, facility, severity, message, remnants, ("<override>", str(override_parser))
		except Exception as e:
			return timestamp, "", loglevel.ERR, f"Could not parse using {str(override_parser)}:", [(message, loglevel.INFO)], ("<override>", str(override_parser))

	if subsubfacility.startswith("docker-pullable://"):
		subsubfacility = subsubfacility[len("docker-pullable://"):]

	for parser in parsers:
		if facility.startswith(parser.facility) and subfacility.startswith(parser.subfacility) and subsubfacility.startswith(parser.subsubfacility):
			# Any other timestamps (as found in the logs) are ignored
			if type(parser.parser) == list:
				for uparser in parser.parser:
					try:
						facility, severity, message, remnants = eval(uparser)(message, fold_msg = fold_msg)
						break
					except:
						pass
			elif type(parser.parser) == tuple and parser.parser[0] == "custom":
				uparser = "custom"
				facility, severity, message, remnants = custom_parser(message, fold_msg = fold_msg, filters = parser.parser[1])
			else:
				uparser = parser.parser
				facility, severity, message, remnants = eval(uparser)(message, fold_msg = fold_msg)
			if len(parser.facility) > 0:
				lparser = parser.facility
			elif len(parser.subfacility) > 0:
				lparser = parser.subfacility
			elif len(parser.subsubfacility) > 0:
				lparser = parser.subsubfacility
			else:
				lparser = "unknown"
			break

	if len(message) > 16383:
		remnants = (message[0:16383], severity)
		severity = loglevel.ERR
		message = f"Line too long ({len(message)} bytes); truncated to 16384 bytes"

	# The UI gets mightily confused by tabs, so replace them with spaces
	# XXX: Doing this here doesn't make sense; at this point we don't know how long the line is.
	#      The only place where we can do this sensibly is in the curses helper.
	message = replace_tabs(message)
	remnants = replace_tabs(remnants)

	return timestamp, facility, severity, message, remnants, (lparser, str(uparser))
