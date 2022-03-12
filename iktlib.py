#! /usr/bin/env python3
from datetime import datetime, timezone, timedelta, date
from functools import reduce
import os
from pathlib import Path
import re
import sys
import yaml

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: you probably need to install python3-natsort")

HOMEDIR = str(Path.home())
IKTDIR = f"{HOMEDIR}/.ikt"
IKT_CONFIG_FILENAME = "ikt.yaml"
IKT_CONFIG_FILE = f"{IKTDIR}/{IKT_CONFIG_FILENAME}"
IKT_CONFIG_FILE_DIR = f"{IKTDIR}/{IKT_CONFIG_FILENAME}.d"

iktconfig = {}

class stgroup:
	DONE = 7
	OK = 6
	PENDING = 5
	WARNING = 4
	ADMIN = 3
	NOT_OK = 2
	UNKNOWN = 1
	CRIT = 0

stgroup_mapping = {
	stgroup.CRIT: "status_critical",
	stgroup.UNKNOWN: "status_unknown",
	stgroup.NOT_OK: "status_not_ok",
	stgroup.ADMIN: "status_admin",
	stgroup.WARNING: "status_warning",
	stgroup.OK: "status_ok",
	stgroup.PENDING: "status_pending",
	stgroup.DONE: "status_done",
}

def none_timestamp():
	return (datetime.combine(date.min, datetime.min.time()) + timedelta(days = 1)).astimezone()

def deep_set(dictionary, path, value, create_path = False):
	if dictionary is None or path is None or len(path) == 0:
		raise Exception(f"deep_set: dictionary {dictionary} or path {path} invalid/unset")

	ref = dictionary
	pathsplit = path.split("#")
	for i in range(0, len(pathsplit)):
		if pathsplit[i] in ref:
			if i == len(pathsplit) - 1:
				ref[pathsplit[i]] = value
				break
			else:
				ref = ref.get(pathsplit[i])
				if ref is None or not isinstance(ref, dict):
					raise Exception(f"Path {path} does not exist in dictionary {dictionary} or is the wrong type {type(ref)}")
		elif create_path == True:
			if i == len(pathsplit) - 1:
				ref[pathsplit[i]] = value
			else:
				ref[pathsplit[i]] = {}

def deep_get(dictionary, path, default = None):
	if dictionary is None:
		return default
	if path is None or len(path) == 0:
		return default
	result = reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, path.split("#"), dictionary)
	if result is None:
		result = default
	return result

def deep_get_recursive(dictionary, path_fragments, result = []):
	for i in range(0, len(path_fragments)):
		tmp = deep_get(dictionary, path_fragments[i])
		if i + 1 == len(path_fragments):
			if tmp is None:
				return result
			else:
				return tmp

		elif type(tmp) == dict:
			result = deep_get_recursive(tmp, path_fragments[i + 1:len(path_fragments)], result)
		elif type(tmp) == list:
			for tmp2 in tmp:
				result = deep_get_recursive(tmp2, path_fragments[i + 1:len(path_fragments)], result)

	return result

def deep_get_list(dictionary, paths, default = None, fallback_on_empty = False):
	for path in paths:
		result = deep_get_recursive(dictionary, path.split("#"))

		if result is not None and not (type(result) in [list, str, dict] and len(result) == 0 and fallback_on_empty == True):
			break
	if result is None or type(result) in [list, str, dict] and len(result) == 0 and fallback_on_empty == True:
		result = default
	return result

def deep_get_with_fallback(obj, paths, default = None, fallback_on_empty = False):
	result = None
	for path in paths:
		result = deep_get(obj, path)
		if result is not None and not (type(result) in [list, str, dict] and len(result) == 0 and fallback_on_empty == True):
			break
	if result is None or type(result) in [list, str, dict] and len(result) == 0 and fallback_on_empty == True:
		result = default
	return result

def read_iktconfig():
	global iktconfig

	if os.path.isfile(IKT_CONFIG_FILE) is False:
		return

	# Read the base configuration file
	with open(IKT_CONFIG_FILE) as f:
		iktconfig = yaml.safe_load(f)

	# Now read ikt.yaml.d/* if available
	if os.path.isdir(IKT_CONFIG_FILE_DIR) is False:
		return

	for item in natsorted(os.listdir(IKT_CONFIG_FILE_DIR)):
		# Only read entries that end with .y{,a}ml
		if not (item.endswith(".yml") or item.endswith(".yaml")):
			continue

		# Read the conflet files
		with open(f"{IKT_CONFIG_FILE_DIR}/{item}") as f:
			moreiktconfig = yaml.safe_load(f)

		# Handle config files without any values defined
		if moreiktconfig is not None:
			iktconfig = {**iktconfig, **moreiktconfig}

	return iktconfig

# Helper functions
def versiontuple(ver):
	filled = []
	for point in ver.split("."):
		filled.append(point.zfill(8))
	return tuple(filled)

def join_tuple_list(items, _tuple = "", item_prefix = None, item_suffix = None, separator = None):
	_list = []
	first = True

	for item in items:
		if first == False and separator is not None:
			_list.append(separator)
		if item_prefix is not None:
			_list.append(item_prefix)
		if type(item) == tuple:
			_list.append(item)
		else:
			_list.append((item, _tuple))
		if item_suffix is not None:
			_list.append(item_suffix)
		first = False
	return _list

def age_to_seconds(age):
	seconds = 0

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

def seconds_to_age(seconds, negative_is_skew = False):
	age = ""
	fields = 0
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

def get_since(timestamp):
	if timestamp is None:
		since = 0
	elif timestamp == -1:
		since = -1
	else:
		timediff = datetime.now(timezone.utc) - timestamp
		since = timediff.days * 24 * 60 * 60 + timediff.seconds

	return since

# Will take datetime and convert it to a timestamp
def datetime_to_timestamp(timestamp):
	if timestamp is None or timestamp == none_timestamp():
		string = ""
	elif timestamp == datetime.fromtimestamp(0).astimezone():
		string = "".ljust(len(str(datetime.fromtimestamp(0).astimezone())))
	else:
		string = timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
	return string

# Will take a timestamp and convert it to datetime
def timestamp_to_datetime(timestamp, default = none_timestamp()):
	if timestamp is None or type(timestamp) == int and timestamp == 0 or type(timestamp) == str and timestamp in ["", "None"]:
		return default

	if timestamp == -1:
		return -1

	# Timestamps that end with Z are already in UTC; strip that
	if timestamp.endswith("Z"):
		timestamp = timestamp[:-1]

	# For timestamp without timezone add one; all timestamps are assumed to be UTC
	timestamp += "+0000"

	dt = None

	for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z"):
		try:
			return datetime.strptime(timestamp, fmt)
		except ValueError:
			pass
	raise ValueError(f"Could not parse date: {timestamp}")

def __str_representer(dumper, data):
	if "\n" in data:
		return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
	return dumper.represent_scalar("tag:yaml.org,2002:str", data)

def format_yaml_line(line, override_formatting = {}):
	if type(override_formatting) == dict:
		generic_format = ("types", "generic")
		comment_format = ("types", "yaml_comment")
		key_format = ("types", "yaml_key")
		value_format = ("types", "yaml_value")
		list_format = ("separators", "yaml_list")
		separator_format = ("types", "generic")
		reference_format = ("types", "yaml_reference")
	elif type(override_formatting) == tuple:
		generic_format = override_formatting
		comment_format = override_formatting
		key_format = override_formatting
		value_format = override_formatting
		list_format = ("- ", override_formatting)
		separator_format = override_formatting
		reference_format = override_formatting

	tmpline = []
	if line.lstrip(" ").startswith("#"):
		tmpline += [
			(line, comment_format),
		]
		return tmpline
	if line.lstrip(" ").startswith("- "):
		tmp = re.match(r"^(\s*?)- (.*)", line)
		tmpline += [
			(f"{tmp[1]}", generic_format),
			list_format,
		]
		line = tmp[2]
		if len(line) == 0:
			return tmpline

	if line.endswith(":"):
		if type(override_formatting) == dict:
			_key_format = deep_get(override_formatting, f"{line[:-1]}#key", key_format)
		else:
			_key_format = key_format
		tmpline += [
			(f"{line[:-1]}", _key_format),
			(":", separator_format),
		]
	else:
		tmp = re.match(r"^(.*?)(:\s*?)(&|\.|)(.*)", line)
		if tmp is not None and (tmp[1].strip().startswith("\"") and tmp[1].strip().endswith("\"") or (not tmp[1].strip().startswith("\"") and not tmp[1].strip().endswith("\""))):
			key = tmp[1]
			reference = tmp[2]
			separator = tmp[3]
			value = tmp[4]
			if type(override_formatting) == dict:
				_key_format = deep_get(override_formatting, f"{key.strip()}#key", key_format)
				if value.strip() in ["{", "["]:
					_value_format = value_format
				else:
					_value_format = deep_get(override_formatting, f"{key.strip()}#value", value_format)
			else:
				_key_format = key_format
				_value_format = value_format
			tmpline += [
				(f"{key}", _key_format),
				(f"{separator}", separator_format),
				(f"{reference}", reference_format),
				(f"{value}", _value_format),
			]
		else:
			if type(override_formatting) == dict:
				_value_format = deep_get(override_formatting, f"{line}#value", value_format)
			else:
				_value_format = value_format
			tmpline += [
				(f"{line}", _value_format),
			]

	return tmpline

# Takes a list of yaml dictionaries and returns a single list of themearray
def format_yaml(objects, override_formatting = {}):
	dumps = []
	indent = deep_get(iktconfig, "Global#indent", 4)

	yaml.add_representer(str, __str_representer)

	for i in range(0, len(objects)):
		obj = objects[i]
		if type(obj) == dict:
			split_dump = yaml.dump(obj, default_flow_style = False, indent = indent, width = sys.maxsize).splitlines()
		else:
			split_dump = obj.splitlines()
		first = True
		if len(split_dump) > 0 and "\n" not in obj and split_dump[0].startswith("'") and split_dump[0].endswith("'"):
			split_dump[0] = split_dump[0][1:-1]

		for line in split_dump:
			truncated = False

			if len(line) >= 16384 - len(" [...] (Truncated)") - 1:
				line = line[0:16384 - len(" [...] (Truncated)") - 1]
				truncated = True
			# This allows us to use the yaml formatter for json too
			if first == True:
				first = False
				if line in ["|", "|-"]:
					continue
			if len(line) == 0:
				continue

			tmpline = format_yaml_line(line, override_formatting = override_formatting)
			if truncated == True:
				tmpline += [(" [...] (Truncated)", ("types", "yaml_key_error"))]
			dumps.append(tmpline)

		if i < len(objects) - 1:
			dumps.append([("", generic_format)])
			dumps.append([("", generic_format)])
			dumps.append([("", generic_format)])

	return dumps

# Take a certificate and highlight the markup
def format_crt(cert):
	dumps = []

	for line in cert:
		if line in ["-----BEGIN CERTIFICATE-----", "-----END CERTIFICATE-----"]:
			dumps.append([(line, ("types", "separator"))])
		else:
			dumps.append([(line, ("types", "generic"))])
	return dumps

# Take a CaddyFile and highlight the markup
def format_caddyfile(lines):
	dumps = []

	i = 0

	single_site = True
	site = False

	for line in lines:
		tmpline = []

		# Empty line
		if len(line) == 0 and len(tmpline) == 0:
			tmpline = [
				("", ("types", "xml_content")),
			]

		directive = False
		block_depth = 0

		while len(line) > 0:
			# Is this a comment?
			if "#" in line:
				tmpline += [
					(line, ("types", "caddyfile_comment")),
				]
				line = ""
				continue

			# Are we opening a block?
			tmp = re.match(r"(\s*)({)(.*)", line)
			if tmp is not None:
				block_depth += 1
				if len(tmp[1]) > 0:
					tmpline += [
						(tmp[1], ("types", "caddyfile_block")),
					]
				tmpline += [
					(tmp[2], ("types", "caddyfile_block")),
				]
				line = tmp[3]
				if site == True:
					single_site = False
				continue

			# Is this a snippet?
			tmp = re.match(r"(\s*)(\(.+?\))(.*)", line)
			if tmp is not None:
				if len(tmp[1]) > 0:
					tmpline += [
						(tmp[1], ("types", "caddyfile_snippet")),
					]
				tmpline += [
					(tmp[2], ("types", "caddyfile_snippet")),
				]
				line = tmp[3]
				continue

			# Is this a site?
			tmp = re.match(r"(\s*)(.+?)(\s+{\s*$|$)", line)
			if tmp is not None:
				if block_depth == 0 and site == False and (single_site == True or "{" in tmp[3]):
					if len(tmp[1]) > 0:
						tmpline += [
							(tmp[1], ("types", "caddyfile_site")),
						]
					tmpline += [
						(tmp[2], ("types", "caddyfile_site")),
					]
					line = tmp[3]
					site = True
					single_site = False
					continue

			# Are we closing a block?
			tmp = re.match(r"(\s*)(}\s*$)", line)
			if tmp is not None:
				block_depth -= 1
				if len(tmp[1]) > 0:
					tmpline += [
						(tmp[1], ("types", "caddyfile_block")),
					]
				tmpline += [
					(tmp[2], ("types", "caddyfile_block")),
				]
				line = ""
				continue

			# Is this a matcher?
			tmp = re.match(r"(\s*)(@.*?|\*/.*?)(\s.*)", line)
			if tmp is not None:
				if len(tmp[1]) > 0:
					tmpline += [
						(tmp[1], ("types", "caddyfile_matcher")),
					]
				tmpline += [
					(tmp[2], ("types", "caddyfile_matcher")),
				]
				line = tmp[3]
				continue

			# Is this a directive?
			if directive == False:
				tmp = re.match(r"(\s*)(.+?)(\s.*|$)", line)
				if tmp is not None:
					if len(tmp[1]) > 0:
						tmpline += [
							(tmp[1], ("types", "caddyfile_directive")),
						]
					tmpline += [
						(tmp[2], ("types", "caddyfile_directive")),
					]
					line = tmp[3]
					directive = True
					continue
			else:
				# OK, we have a directive already, and this isn't a matcher or a block,
				# which means that it's an argument
				tmp = re.match(r"(.*?)(\s{\s*$|$)", line)
				if tmp is not None:
					tmpline += [
						(tmp[1], ("types", "caddyfile_argument")),
					]
					line = tmp[2]
					continue

		dumps.append(tmpline)

	return dumps

# Take an NGINX file and apply syntax highlighting
def format_nginx(lines):
	dumps = []

	for line in lines:
		dump = []
		if len(line.strip()) == 0:
			if len(dump) == 0:
				dump += [
					("", ("types", "generic"))
				]
			dumps.append(dump)
			continue

		# key {
		# key value[ value...];
		# key value[ value...] {
		tmp = re.match(r"^(\s*)(#.*$|}|\S+|$)(.+;|.+{|)(\s*#.*$|)", line)
		if tmp is not None:
			if len(tmp[1]) > 0:
				dump += [
					(tmp[1], ("types", "generic")),	# whitespace
				]
			if len(tmp[2]) > 0:
				if tmp[2] == "}":
					dump += [
						(tmp[2], ("types", "generic")),	# block end
					]
				elif tmp[2].startswith("#"):
					dump += [
						(tmp[2], ("types", "nginx_comment"))
					]
				else:
					dump += [
						(tmp[2], ("types", "nginx_key"))
					]
			if len(tmp[3]) > 0:
					dump += [
						(tmp[3][:-1], ("types", "nginx_value")),
						(tmp[3][-1:], ("types", "generic")),	# block start / statement end
					]
			if len(tmp[4]) > 0:
				dump += [
					(tmp[4], ("types", "nginx_comment"))
				]
			dumps.append(dump)
		else:
			sys.exit(f"__format_nginx(): Couldn't match line={line}")
	return dumps

# Take an XML file and highlight the markup
def format_xml(lines):
	dumps = []
	tag_open = False
	tag_named = False
	comment = False

	i = 0
	for line in lines:
		tmpline = []

		# Empty line
		if len(line) == 0 and len(tmpline) == 0:
			tmpline = [
				("", ("types", "xml_content")),
			]

		while len(line) > 0:
			before = line
			if tag_open == False:
				# Are we opening a tag?
				tmp = re.match(r"(\s*)(</|<!--|<\?|<)(.*)", line)
				if tmp is not None:
					tag_open = True
					tag_named = False

					# Don't add 0-length "indentation"
					if len(tmp[1]) > 0:
						tmpline += [
							(tmp[1], ("types", "xml_declaration")),
						]

					if tmp[2] == "<?":
						# declaration tags are implicitly named
						tag_named = True
						tmpline += [
							(tmp[2], ("types", "xml_declaration")),
						]
						line = tmp[3]
						continue
					elif tmp[2] == "<!--":
						comment = True
						tmpline += [
							(tmp[2], ("types", "xml_comment")),
						]
						line = tmp[3]
						continue
					else:
						tmpline += [
							(tmp[2], ("types", "xml_tag")),
						]
						line = tmp[3]
						continue

				# Is this an escape?
				tmp = re.match(r"(\s*)(&)(.+?)(;)(.*)", line)
				if tmp is not None:
					tmpline += [
						(tmp[1], ("types", "xml_content")),
						(tmp[2], ("types", "xml_escape")),
						(tmp[3], ("types", "xml_escape_data")),
						(tmp[4], ("types", "xml_escape")),
					]
					line = tmp[5]
					continue

				# Nope, it's content; split to first & or <
				tmp = re.match(r"(.*?)(<.*|&.*)", line)
				if tmp is not None:
					tmpline += [
						(tmp[1], ("types", "xml_content")),
					]
					line = tmp[2]
				else:
					tmpline += [
						(line, ("types", "xml_content")),
					]
					line = ""
			else:
				# Are we closing a tag?
				tmp = re.match(r"(\s*)(/>|\?>|-->|>)(.*)", line)
				if tmp is not None:
					# Don't add 0-length "indentation"
					if len(tmp[1]) > 0:
						tmpline += [
							(tmp[1], ("types", "xml_comment")),
						]

					# > is ignored within comments
					if tmp[2] == ">" and comment == True or tmp[2] == "-->":
						tmpline += [
							(tmp[2], ("types", "xml_comment")),
						]
						line = tmp[3]
						if tmp[2] == "-->":
							comment = False
							tag_open = False
						continue
					elif tmp[2] == "?>":
						tmpline += [
							(tmp[2], ("types", "xml_declaration")),
						]
						line = tmp[3]
						tag_open = False
						continue
					else:
						tmpline += [
							(tmp[2], ("types", "xml_tag")),
						]
						line = tmp[3]
						tag_open = False
						continue

				if tag_named == False and comment == False:
					# Is this either "[<]tag", "[<]tag ", "[<]tag>" or "[<]tag/>"?
					tmp = re.match(r"(.+?)(\s*>|\s*\?>|\s*$|\s+.*)", line)
					if tmp is not None:
						tmpline += [
							(tmp[1], ("types", "xml_tag")),
						]
						line = tmp[2]
						tag_named = True
						continue
				else:
					# This *should* match all remaining cases
					tmp = re.match(r"(\s*.+?)(=|)(\".+?\"|)(\s*$|\s*/>|\s*\?>|\s*-->|\s*>|\s+)(.*|)", line)
					if tmp is not None:
						if comment == True:
							tmpline += [
								(tmp[1], ("types", "xml_comment")),
								(tmp[2], ("types", "xml_comment")),
								(tmp[3], ("types", "xml_comment")),
							]
						else:
							tmpline += [
								(tmp[1], ("types", "xml_attribute_key")),
							]

							if len(tmp[2]) > 0:
								tmpline += [
									(tmp[2], ("types", "xml_content")),
									(tmp[3], ("types", "xml_attribute_value")),
								]
						line = tmp[4] + tmp[5]
						continue
					else:
						raise Exception(f"XML syntax highlighter failed to parse {line}")
			if before == line:
				raise Exception(f"XML syntax highlighter parse failure at line #{i + 1}:\n{lines}\nParsed fragments of line:\n{tmpline}\nUnparsed fragments of line:\n{line}")

		dumps.append(tmpline)
		i += 1

	return dumps

# Takes a TOML file and returns a single list of themearray
def format_toml(lines):
	# FIXME: necessary improvements:
	# * Instead of only checking for lines that end with a comment for key = value,
	#   and for full comment lines, check for lines that end with a comment
	#   in any situation (except multiline). Split out the comment and add it last.
	# * Handle quoting and escaping of quotes; \''' shouldn't end a multiline, for instance.
	# * XXX: should we highlight key=value for inline tables? Probably not
	# * XXX: should we highlight different types (integer, string, etc.)? Almost certainly not.
	dumps = []
	multiline_basic = False
	multiline_literal = False

	for line in lines:
		if len(line) == 0:
			continue

		if multiline_basic == True or multiline_literal == True:
			tmpline += [
				(line, ("types", "toml_value")),
			]
			dumps.append(tmpline)
			if multiline_basic == True and line.lstrip(" ").endswith("\"\"\""):
				multiline_basic = False
			elif multiline_literal == True and line.lstrip(" ").endswith("'''"):
				multiline_literal = False
			continue

		tmpline = []
		if line.lstrip().startswith("#"):
			tmpline += [
				(line, ("types", "toml_comment")),
			]
			dumps.append(tmpline)
			continue
		elif line.lstrip().startswith("[") and line.rstrip(" ").endswith("]"):
			tmpline += [
				(line, ("types", "toml_table")),
			]

			dumps.append(tmpline)
			continue
		else:
			tmp = re.match(r"^(\s*?)(.*)(\s*?=\s*?)(.*)", line)
			if tmp is not None:
				indentation = tmp[1]
				key = tmp[2]
				separator = tmp[3]
				value = tmp[4]
				if value.rstrip(" ").endswith("\"\"\""):
					multiline_basic = True
				elif value.rstrip(" ").endswith("'''"):
					multiline_literal = True
				else:
					# Does this line end with a comment?
					tmp = re.match(r"^(.*?)(#.*)", value)
					if tmp is not None:
						value = tmp[1]
						comment = tmp[2]
					else:
						comment = ""
				tmpline += [
					(f"{indentation}", ("types", "generic")),
					(f"{key}", ("types", "toml_key")),
					(f"{separator}", ("types", "toml_key_separator")),
					(f"{value}", ("types", "toml_value")),
				]
				if len(comment) > 0:
					tmpline += [
						(f"{comment}", ("types", "toml_comment")),
					]
				dumps.append(tmpline)


			# dumps.append([(line, ("types", "generic"))])
	return dumps

def format_fluentbit(lines):
	dumps = []

	for line in lines:
		if line.lstrip().startswith("#"):
			tmpline = [
				(line, ("types", "ini_comment")),
			]
		elif line.lstrip().startswith("[") and line.rstrip().endswith("]"):
			tmpline = [
				(line, ("types", "ini_section")),
			]
		elif len(line.strip()) == 0:
			tmpline = [
				("", ("types", "generic")),
			]
		else:
			tmp = re.match(r"^(\s*)(\S*)(\s*)(.*)", line)
			if tmp is not None:
				indentation = tmp[1]
				key = tmp[2]
				separator = tmp[3]
				value = tmp[4]

				tmpline = [
					(f"{indentation}", ("types", "generic")),
					(f"{key}", ("types", "ini_key")),
					(f"{separator}", ("types", "ini_key_separator")),
					(f"{value}", ("types", "ini_value")),
				]
		dumps.append(tmpline)
	return dumps

# Takes an INI file and returns a single list of themearray
def format_ini(lines):
	dumps = []

	for line in lines:
		tmpline = []
		if line.lstrip().startswith(("#", ";")):
			tmpline = [
				(line, ("types", "ini_comment")),
			]
		elif line.lstrip().startswith("[") and line.rstrip().endswith("]"):
			tmpline = [
				(line, ("types", "ini_section")),
			]
		else:
			tmp = re.match(r"^(\s*?)(.*)(\s*?=\s*?)(.*)", line)
			if tmp is not None:
				indentation = tmp[1]
				key = tmp[2]
				separator = tmp[3]
				value = tmp[4]

				tmpline = [
					(f"{indentation}", ("types", "generic")),
					(f"{key}", ("types", "ini_key")),
					(f"{separator}", ("types", "ini_key_separator")),
					(f"{value}", ("types", "ini_value")),
				]
		dumps.append(tmpline)
	return dumps
