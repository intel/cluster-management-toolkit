#! /usr/bin/env python3

"""
Format text as themearrays
"""

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
import re
import sys
from typing import Any, Callable, cast, Dict, List, Optional, Union
try:
	import yaml
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: Could not import yaml; you may need to (re-)run `cmt-install` or `pip3 install PyYAML`; aborting.")

from cmttypes import deep_get, DictPath

import cmtlib
from cmtlib import split_msg, strip_ansicodes

from curses_helper import ThemeAttr, ThemeRef, ThemeString

if json_is_ujson:
	def json_dumps(obj: Dict) -> str:
		"""
		Dump Python object to JSON in text format; ujson version

			Parameters:
				obj (dict): The JSON object to dump
			Returns:
				str: The serialized JSON object
		"""

		indent = 2
		return json.dumps(obj, indent = indent, escape_forward_slashes = False)
else:
	def json_dumps(obj: Dict) -> str:
		"""
		Dump Python object to JSON in text format; json version

			Parameters:
				obj (dict): The JSON object to dump
			Returns:
				str: The serialized JSON object
		"""

		indent = 2
		return json.dumps(obj, indent = indent)

def __str_representer(dumper: yaml.Dumper, data: Any) -> yaml.Node:
	"""
	Reformat yaml with |-style str

		Parameters:
			dumper: Opaque type internal to python-yaml
			data: Opaque type internal to python-yaml
		Returns:
			Opaque type internal to python-yaml
	"""

	if "\n" in data:
		return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
	return dumper.represent_scalar("tag:yaml.org,2002:str", data)

# pylint: disable-next=unused-argument
def format_binary(lines: bytes, **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	Binary "formatter"; Just returns a message saying that binary views cannot be viewed

		Parameters:
			lines (opaque): Unused
			kwargs (dict): unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	return [[ThemeString("Binary file; cannot view", ThemeAttr("types", "generic"))]]

# pylint: disable=unused-argument
def format_none(lines: Union[str, List[str]], **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	Noop formatter; returns the text without syntax highlighting

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): a string with newlines that should be split
			kwargs (dict): unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps: List[List[Union[ThemeRef, ThemeString]]] = []

	if isinstance(lines, str):
		lines = split_msg(lines)

	for line in lines:
		dumps.append([ThemeString(line, ThemeAttr("types", "generic"))])
	return dumps

# pylint: disable-next=unused-argument
def format_ansible_line(line: str, override_formatting: Optional[Union[ThemeAttr, Dict]] = None) -> List[Union[ThemeRef, ThemeString]]:
	"""
	Formats a single line of an Ansible play

		Parameters:
			line (str): a string
			override_formatting (dict): Overrides instead of default Ansible-formatting
		Returns:
			themearray: a themearray
	"""

	tmpline: List[Union[ThemeRef, ThemeString]] = []
	if override_formatting is None:
		formatting = ThemeAttr("types", "generic")
	else:
		formatting = cast(ThemeAttr, override_formatting)

	tmpline += [
		ThemeString(line, formatting),
	]
	return tmpline

# pylint: disable-next=unused-argument
def format_diff_line(line: str, override_formatting: Optional[Union[ThemeAttr, Dict]] = None) -> List[Union[ThemeRef, ThemeString]]:
	"""
	Formats a single line of a diff

		Parameters:
			line (str): a string
			override_formatting (dict): Overrides instead of default diff-formatting
		Returns:
			themearray: a themearray
	"""

	tmpline: List[Union[ThemeRef, ThemeString]] = []

	if line.startswith("+ "):
		tmpline += [
			ThemeString(line, ThemeAttr("logview", "severity_diffplus")),
		]
		return tmpline
	if line.startswith("- "):
		tmpline += [
			ThemeString(line, ThemeAttr("logview", "severity_diffminus")),
		]
		return tmpline
	tmpline += [
		ThemeString(line, ThemeAttr("logview", "severity_diffsame")),
	]
	return tmpline

def format_yaml_line(line: str, **kwargs: Dict) -> List[Union[ThemeRef, ThemeString]]:
	"""
	Formats a single line of YAML

		Parameters:
			line (str): a string
			override_formatting (dict): Overrides instead of default YAML-formatting
			kwargs (dict): Additional parameters
		Returns:
			themearray: a themearray
			list[themearray]: A list of themearrays, in case the YAML-line is expanded into multiple lines;
			                  used when encountering keys belonging to  expandd_newline_fields
	"""

	override_formatting: Optional[Union[ThemeAttr, Dict]] = deep_get(kwargs, DictPath("override_formatting"))
	expand_newline_fields: Tuple[str] = deep_get(kwargs, DictPath("expand_newline_fields"), ())
	value_strip_ansicodes: bool = deep_get(kwargs, DictPath("value_strip_ansicodes"), True)
	value_expand_tabs: bool = deep_get(kwargs, DictPath("value_expand_tabs"), False)
	remnants = []

	if override_formatting is None:
		override_formatting = {}

	if isinstance(override_formatting, dict):
		# Since we do not necessarily override all
		# formatting we need to set defaults;
		# doing it here instead of in the code makes
		# it easier to change the defaults of necessary
		generic_format = ThemeAttr("types", "generic")
		comment_format = ThemeAttr("types", "yaml_comment")
		key_format = ThemeAttr("types", "yaml_key")
		value_format = ThemeAttr("types", "yaml_value")
		list_format: Union[ThemeRef, ThemeString] = ThemeRef("separators", "yaml_list")
		separator_format = ThemeAttr("types", "generic")
		reference_format = ThemeAttr("types", "yaml_reference")
	elif isinstance(override_formatting, ThemeAttr):
		generic_format = override_formatting
		comment_format = override_formatting
		key_format = override_formatting
		value_format = override_formatting
		list_format = ThemeString("- ", override_formatting)
		separator_format = override_formatting
		reference_format = override_formatting
		override_formatting = {}

	tmpline: List[Union[ThemeRef, ThemeString]] = []

	if line.lstrip(" ").startswith("#"):
		tmpline += [
			ThemeString(line, comment_format),
		]
		return tmpline, remnants
	if line.lstrip(" ").startswith("- "):
		# Safe
		tmp = re.match(r"^(\s*?)- (.*)", line)
		if tmp is not None:
			tmpline += [
				ThemeString(tmp[1], generic_format),
				list_format,
			]
			line = tmp[2]
			if len(line) == 0:
				return tmpline, remnants

	if line.endswith(":"):
		if isinstance(override_formatting, dict):
			_key_format = deep_get(override_formatting, DictPath(f"{line[:-1]}#key"), key_format)
		else:
			_key_format = key_format
		tmpline += [
			ThemeString(f"{line[:-1]}", _key_format),
			ThemeString(":", separator_format),
		]
	else:
		# Safe
		tmp = re.match(r"^(.*?)(:\s*?)(&|\.|)(.*)", line)
		# pylint: disable-next=line-too-long
		if tmp is not None and (tmp[1].strip().startswith("\"") and tmp[1].strip().endswith("\"") or (not tmp[1].strip().startswith("\"") and not tmp[1].strip().endswith("\""))):
			key = tmp[1]
			reference = tmp[2]
			separator = tmp[3]
			value = tmp[4]
			if isinstance(override_formatting, dict):
				_key_format = deep_get(override_formatting, DictPath(f"{key.strip()}#key"), key_format)
				if value.strip() in ("{", "["):
					_value_format = value_format
				else:
					_value_format = deep_get(override_formatting, DictPath(f"{key.strip()}#value"), value_format)
			else:
				_key_format = key_format
				_value_format = value_format

			if value_strip_ansicodes:
				value = strip_ansicodes(value)

			key_stripped = key.strip(" \"")
			if key_stripped in expand_newline_fields:
				split_value = split_msg(value.replace("\\n", "\n"))
				value_line_indent = 0

				for i, value_line in enumerate(split_value):
					if value_expand_tabs:
						tmp_split_value_line = value_line.replace("\\t", "\t").split("\t")
						tmp_value_line = ""
						for j, split_value_line_segment in enumerate(tmp_split_value_line):
							tabsize = 0
							if j < len(tmp_split_value_line):
								tabsize = 8 - len(tmp_value_line) % 8
							tmp_value_line += split_value_line_segment  + "".ljust(tabsize)
						value_line = tmp_value_line

					if i == 0:
						tmpline = [
							ThemeString(f"{key}", _key_format),
							ThemeString(f"{separator}", separator_format),
							ThemeString(f"{reference}", reference_format),
							ThemeString(f"{value_line}", _value_format),
						]
						value_line_indent = len(value_line) - len(value_line.lstrip(" \""))
					else:
						remnants.append([
							ThemeString("".ljust(value_line_indent + len(key + separator + reference)), _key_format),
							ThemeString(f"{value_line}", _value_format),
						])
			else:
				if value_expand_tabs:
					tmp_split_value = value.replace("\\t", "\t").split("\t")
					tmp_value = ""
					for j, split_value_segment in enumerate(tmp_split_value):
						tabsize = 0
						if j < len(tmp_split_value):
							tabsize = 8 - len(tmp_value) % 8
						tmp_value += split_value_segment  + "".ljust(tabsize)
					value = tmp_value

				tmpline += [
					ThemeString(f"{key}", _key_format),
					ThemeString(f"{separator}", separator_format),
					ThemeString(f"{reference}", reference_format),
					ThemeString(f"{value}", _value_format),
				]
		else:
			if isinstance(override_formatting, dict):
				_value_format = deep_get(override_formatting, DictPath(f"{line}#value"), value_format)
			else:
				_value_format = value_format
			tmpline += [
				ThemeString(f"{line}", _value_format),
			]

	return tmpline, remnants

def format_yaml(lines: Union[str, List[str]], **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	YAML formatter; returns the text with syntax highlighting for YAML

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Additional parameters
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps: List[List[Union[ThemeRef, ThemeString]]] = []
	indent = deep_get(cmtlib.cmtconfig, DictPath("Global#indent"), 2)

	if isinstance(lines, str):
		if deep_get(kwargs, DictPath("json"), False):
			try:
				d = json.loads(lines)
				lines = [json_dumps(d)]
			except DecodeException:
				return format_none(lines)
		else:
			lines = [lines]

	generic_format = ThemeAttr("types", "generic")

	override_formatting: Union[ThemeAttr, Dict] = {}

	if deep_get(kwargs, DictPath("raw"), False):
		override_formatting = generic_format

	yaml.add_representer(str, __str_representer)

	for i, obj in enumerate(lines):
		if isinstance(obj, dict):
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
			if first:
				first = False
				if line in ("|", "|-"):
					continue
			if len(line) == 0:
				continue

			kwargs["override_formatting"] =  override_formatting
			tmpline: List[Union[ThemeRef, ThemeString]] = []
			remnants: List[List[Union[ThemeRef, ThemeString]]] = []
			tmpline, remnants = format_yaml_line(line, **kwargs)
			if truncated:
				tmpline += [ThemeString(" [...] (Truncated)", ThemeAttr("types", "yaml_key_error"))]
			dumps.append(tmpline)
			if len(remnants) > 0:
				dumps += remnants

		if i < len(lines) - 1:
			dumps.append([ThemeString("", generic_format)])
			dumps.append([ThemeString("", generic_format)])
			dumps.append([ThemeString("", generic_format)])

	return dumps

def reformat_json(lines: Union[str, List[str]], **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	kwargs["json"] = True
	return format_yaml(lines, **kwargs)

KEY_HEADERS = [
	"-----BEGIN CERTIFICATE-----",
	"-----END CERTIFICATE-----",
	"-----BEGIN CERTIFICATE REQUEST-----",
	"-----END CERTIFICATE REQUEST-----",
	"-----BEGIN PKCS7-----",
	"-----END PKCS7-----",
	"-----BEGIN OPENSSH PRIVATE KEY-----",
	"-----END OPENSSH PRIVATE KEY-----",
	"-----BEGIN SSH2 PUBLIC KEY-----",
	"-----END SSH2 PUBLIC KEY-----",
	"-----BEGIN PUBLIC KEY-----",
	"-----END PUBLIC KEY-----",
	"-----BEGIN PRIVATE KEY-----",
	"-----END PRIVATE KEY-----",
	"-----BEGIN DSA PRIVATE KEY-----",
	"-----END DSA PRIVATE KEY-----",
	"-----BEGIN RSA PRIVATE KEY-----",
	"-----END RSA PRIVATE KEY-----",
	"-----BEGIN EC PRIVATE KEY-----",
	"-----END EC PRIVATE KEY-----",
]

def format_crt(lines: Union[str, List[str]], **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	CRT formatter; returns the text with syntax highlighting for certificates

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps: List[List[Union[ThemeRef, ThemeString]]] = []

	if deep_get(kwargs, DictPath("raw"), False):
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	for line in lines:
		if line in KEY_HEADERS:
			dumps.append([ThemeString(line, ThemeAttr("types", "separator"))])
		else:
			dumps.append([ThemeString(line, ThemeAttr("types", "generic"))])
	return dumps

def format_haproxy(lines: Union[str, List[str]], **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	HAProxy formatter; returns the text with syntax highlighting for HAProxy

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps: List[List[Union[ThemeRef, ThemeString]]] = []

	if isinstance(lines, str):
		lines = split_msg(lines)

	if deep_get(kwargs, DictPath("raw"), False):
		return format_none(lines)

	# Safe
	haproxy_section_regex = re.compile(r"^(\s*)(global|defaults|frontend|backend|listen|resolvers|mailers|peers)(\s*)(.*)")
	# Safe
	haproxy_setting_regex = re.compile(r"^(\s*)(\S+)(\s+)(.+)")

	for line in lines:
		# Is it whitespace?
		if len(line.strip()) == 0:
			dumps.append([ThemeString(line, ThemeAttr("types", "generic"))])
			continue

		# Is it a new section?
		tmp = haproxy_section_regex.match(line)
		if tmp is not None:
			whitespace1 = tmp[1]
			section = tmp[2]
			whitespace2 = tmp[3]
			label = tmp[4]
			tmpline: List[Union[ThemeRef, ThemeString]] = [
				ThemeString(whitespace1, ThemeAttr("types", "generic")),
				ThemeString(section, ThemeAttr("types", "haproxy_section")),
				ThemeString(whitespace2, ThemeAttr("types", "generic")),
				ThemeString(label, ThemeAttr("types", "haproxy_label")),
			]
			dumps.append(tmpline)
			continue

		# Is it settings?
		tmp = haproxy_setting_regex.match(line)
		if tmp is not None:
			whitespace1 = tmp[1]
			setting = tmp[2]
			whitespace2 = tmp[3]
			values = tmp[4]
			tmpline = [
				ThemeString(whitespace1, ThemeAttr("types", "generic")),
				ThemeString(setting, ThemeAttr("types", "haproxy_setting")),
				ThemeString(whitespace2, ThemeAttr("types", "generic")),
				ThemeString(values, ThemeAttr("types", "generic")),
			]
			dumps.append(tmpline)
			continue

		# Unknown data; just append it unformatted
		dumps.append([ThemeString(line, ThemeAttr("types", "generic"))])

	return dumps

def format_caddyfile(lines: Union[str, List[str]], **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	CaddyFile formatter; returns the text with syntax highlighting for CaddyFiles

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps: List[List[Union[ThemeRef, ThemeString]]] = []

	if deep_get(kwargs, DictPath("raw"), False):
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	single_site = True
	site = False

	# Safe
	block_open_regex = re.compile(r"^(\s*)({)(.*)")
	# Safe
	snippet_regex = re.compile(r"^(\s*)(\(.+?\))(.*)")
	# Safe
	site_regex = re.compile(r"^(\s*)(\S+?)(\s+{\s*$|$)")
	# Safe
	block_close_regex = re.compile(r"^(\s*)(}\s*$)")
	# Safe
	matcher_regex = re.compile(r"^(\s*)(@.*?|\*/.*?)(\s.*)")
	# Safe
	directive_regex = re.compile(r"^(\s*)(.+?)(\s.*|$)")
	# Safe
	argument_regex = re.compile(r"^(.*?)(\s{\s*$|$)")

	for line in lines:
		tmpline: List[Union[ThemeRef, ThemeString]] = []

		# Empty line
		if len(line) == 0 and len(tmpline) == 0:
			tmpline = [
				ThemeString("", ThemeAttr("types", "xml_content")),
			]

		directive = False
		block_depth = 0

		while len(line) > 0:
			# Is this a comment?
			if "#" in line:
				tmpline += [
					ThemeString(line, ThemeAttr("types", "caddyfile_comment")),
				]
				line = ""
				continue

			# Are we opening a block?
			tmp = block_open_regex.match(line)
			if tmp is not None:
				block_depth += 1
				if len(tmp[1]) > 0:
					tmpline += [
						ThemeString(tmp[1], ThemeAttr("types", "caddyfile_block")),
					]
				tmpline += [
					ThemeString(tmp[2], ThemeAttr("types", "caddyfile_block")),
				]
				line = tmp[3]
				if site:
					single_site = False
				continue

			# Is this a snippet?
			tmp = snippet_regex.match(line)
			if tmp is not None:
				if len(tmp[1]) > 0:
					tmpline += [
						ThemeString(tmp[1], ThemeAttr("types", "caddyfile_snippet")),
					]
				tmpline += [
					ThemeString(tmp[2], ThemeAttr("types", "caddyfile_snippet")),
				]
				line = tmp[3]
				continue

			# Is this a site?
			tmp = site_regex.match(line)
			if tmp is not None:
				if block_depth == 0 and not site and (single_site or "{" in tmp[3]):
					if len(tmp[1]) > 0:
						tmpline += [
							ThemeString(tmp[1], ThemeAttr("types", "caddyfile_site")),
						]
					tmpline += [
						ThemeString(tmp[2], ThemeAttr("types", "caddyfile_site")),
					]
					line = tmp[3]
					site = True
					single_site = False
					continue

			# Are we closing a block?
			tmp = block_close_regex.match(line)
			if tmp is not None:
				block_depth -= 1
				if len(tmp[1]) > 0:
					tmpline += [
						ThemeString(tmp[1], ThemeAttr("types", "caddyfile_block")),
					]
				tmpline += [
					ThemeString(tmp[2], ThemeAttr("types", "caddyfile_block")),
				]
				line = ""
				continue

			# Is this a matcher?
			tmp = matcher_regex.match(line)
			if tmp is not None:
				if len(tmp[1]) > 0:
					tmpline += [
						ThemeString(tmp[1], ThemeAttr("types", "caddyfile_matcher")),
					]
				tmpline += [
					ThemeString(tmp[2], ThemeAttr("types", "caddyfile_matcher")),
				]
				line = tmp[3]
				continue

			# Is this a directive?
			if not directive:
				tmp = directive_regex.match(line)
				if tmp is not None:
					if len(tmp[1]) > 0:
						tmpline += [
							ThemeString(tmp[1], ThemeAttr("types", "caddyfile_directive")),
						]
					tmpline += [
						ThemeString(tmp[2], ThemeAttr("types", "caddyfile_directive")),
					]
					line = tmp[3]
					directive = True
					continue
			else:
				# OK, we have a directive already, and this is not a matcher or a block,
				# which means that it is an argument
				tmp = argument_regex.match(line)
				if tmp is not None:
					tmpline += [
						ThemeString(tmp[1], ThemeAttr("types", "caddyfile_argument")),
					]
					line = tmp[2]
					continue

		dumps.append(tmpline)

	return dumps

def format_mosquitto(lines: Union[str, List[str]], **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	Mosquitto formatter; returns the text with syntax highlighting for Mosquitto

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps: List[List[Union[ThemeRef, ThemeString]]] = []

	if isinstance(lines, str):
		lines = split_msg(lines)

	if deep_get(kwargs, DictPath("raw"), False):
		return format_none(lines)

	# Safe
	mosquitto_variable_regex = re.compile(r"^(\S+)(\s)(.+)")

	for line in lines:
		# Is it whitespace?
		if len(line.strip()) == 0:
			dumps.append([ThemeString(line, ThemeAttr("types", "generic"))])
			continue

		# Is it a comment?
		if line.startswith("#"):
			dumps.append([ThemeString(line, ThemeAttr("types", "mosquitto_comment"))])
			continue

		# Is it a variable + value?
		tmp = mosquitto_variable_regex.match(line)
		if tmp is not None:
			variable = tmp[1]
			whitespace = tmp[2]
			value = tmp[3]
			tmpline: List[Union[ThemeRef, ThemeString]] = [
				ThemeString(variable, ThemeAttr("types", "mosquitto_variable")),
				ThemeString(whitespace, ThemeAttr("types", "generic")),
				ThemeString(value, ThemeAttr("types", "generic")),
			]
			dumps.append(tmpline)
			continue

		# Unknown data; just append it unformatted
		dumps.append([ThemeString(line, ThemeAttr("types", "generic"))])

	return dumps

def format_nginx(lines: Union[str, List[str]], **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	NGINX formatter; returns the text with syntax highlighting for NGINX

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps: List[List[Union[ThemeRef, ThemeString]]] = []

	if deep_get(kwargs, DictPath("raw"), False):
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	# Safe
	key_regex = re.compile(r"^(\s*)(#.*$|}|\S+|$)(.+;|.+{|)(\s*#.*$|)")

	for line in lines:
		dump: List[Union[ThemeRef, ThemeString]] = []
		if len(line.strip()) == 0:
			if len(dump) == 0:
				dump += [
					ThemeString("", ThemeAttr("types", "generic"))
				]
			dumps.append(dump)
			continue

		# key {
		# key value[ value...];
		# key value[ value...] {
		tmp = key_regex.match(line)
		if tmp is not None:
			if len(tmp[1]) > 0:
				dump += [
					ThemeString(tmp[1], ThemeAttr("types", "generic")),	# whitespace
				]
			if len(tmp[2]) > 0:
				if tmp[2] == "}":
					dump += [
						ThemeString(tmp[2], ThemeAttr("types", "generic")),	# block end
					]
				elif tmp[2].startswith("#"):
					dump += [
						ThemeString(tmp[2], ThemeAttr("types", "nginx_comment"))
					]
				else:
					dump += [
						ThemeString(tmp[2], ThemeAttr("types", "nginx_key"))
					]
			if len(tmp[3]) > 0:
				dump += [
					ThemeString(tmp[3][:-1], ThemeAttr("types", "nginx_value")),
					ThemeString(tmp[3][-1:], ThemeAttr("types", "generic")),	# block start / statement end
				]
			if len(tmp[4]) > 0:
				dump += [
					ThemeString(tmp[4], ThemeAttr("types", "nginx_comment"))
				]
			dumps.append(dump)
		else:
			sys.exit(f"__format_nginx(): Could not match line={line}")
	return dumps

def format_xml(lines: Union[str, List[str]], **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	XML formatter; returns the text with syntax highlighting for XML

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps: List[List[Union[ThemeRef, ThemeString]]] = []

	tag_open = False
	tag_named = False
	comment = False

	if deep_get(kwargs, DictPath("raw"), False):
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	# Safe
	escape_regex = re.compile(r"^(\s*)(&)(.+?)(;)(.*)")
	# Safe
	content_regex = re.compile(r"^(.*?)(<.*|&.*)")
	# Safe
	tag_open_regex = re.compile(r"^(\s*)(</|<!--|<\?|<)(.*)")
	# Safe
	tag_named_regex = re.compile(r"^(.+?)(\s*>|\s*\?>|\s*$|\s+.*)")
	# Safe
	tag_close_regex = re.compile(r"^(\s*)(/>|\?>|-->|--!>|>)(.*)")
	# Safe
	remainder_regex = re.compile(r"^(\s*\S+?)(=|)(\"[^\"]+?\"|)(\s*$|\s*/>|\s*\?>|\s*-->|\s*>|\s+)(.*|)")

	i = 0
	for line in lines:
		tmpline: List[Union[ThemeRef, ThemeString]] = []

		# Empty line
		if len(line) == 0 and len(tmpline) == 0:
			tmpline = [
				ThemeString("", ThemeAttr("types", "xml_content")),
			]

		while len(line) > 0:
			before = line
			if not tag_open:
				# Are we opening a tag?
				tmp = tag_open_regex.match(line)
				if tmp is not None:
					tag_open = True
					tag_named = False

					# Do not add 0-length "indentation"
					if len(tmp[1]) > 0:
						tmpline += [
							ThemeString(tmp[1], ThemeAttr("types", "xml_declaration")),
						]

					if tmp[2] == "<?":
						# declaration tags are implicitly named
						tag_named = True
						tmpline += [
							ThemeString(tmp[2], ThemeAttr("types", "xml_declaration")),
						]
						line = tmp[3]
						continue

					if tmp[2] == "<!--":
						comment = True
						tmpline += [
							ThemeString(tmp[2], ThemeAttr("types", "xml_comment")),
						]
						line = tmp[3]
						continue

					tmpline += [
						ThemeString(tmp[2], ThemeAttr("types", "xml_tag")),
					]
					line = tmp[3]
					continue

				# Is this an escape?
				tmp = escape_regex.match(line)
				if tmp is not None:
					tmpline += [
						ThemeString(tmp[1], ThemeAttr("types", "xml_content")),
						ThemeString(tmp[2], ThemeAttr("types", "xml_escape")),
						ThemeString(tmp[3], ThemeAttr("types", "xml_escape_data")),
						ThemeString(tmp[4], ThemeAttr("types", "xml_escape")),
					]
					line = tmp[5]
					continue

				# Nope, it is content; split to first & or <
				tmp = content_regex.match(line)
				if tmp is not None:
					tmpline += [
						ThemeString(tmp[1], ThemeAttr("types", "xml_content")),
					]
					line = tmp[2]
				else:
					tmpline += [
						ThemeString(line, ThemeAttr("types", "xml_content")),
					]
					line = ""
			else:
				# Are we closing a tag?
				tmp = tag_close_regex.match(line)
				if tmp is not None:
					# Do not add 0-length "indentation"
					if len(tmp[1]) > 0:
						tmpline += [
							ThemeString(tmp[1], ThemeAttr("types", "xml_comment")),
						]

					# > is ignored within comments
					if tmp[2] == ">" and comment or tmp[2] == "-->":
						tmpline += [
							ThemeString(tmp[2], ThemeAttr("types", "xml_comment")),
						]
						line = tmp[3]
						if tmp[2] == "-->":
							comment = False
							tag_open = False
						continue

					if tmp[2] == "?>":
						tmpline += [
							ThemeString(tmp[2], ThemeAttr("types", "xml_declaration")),
						]
						line = tmp[3]
						tag_open = False
						continue

					tmpline += [
						ThemeString(tmp[2], ThemeAttr("types", "xml_tag")),
					]
					line = tmp[3]
					tag_open = False
					continue

				if not tag_named and not comment:
					# Is this either "[<]tag", "[<]tag ", "[<]tag>" or "[<]tag/>"?
					tmp = tag_named_regex.match(line)
					if tmp is not None:
						tmpline += [
							ThemeString(tmp[1], ThemeAttr("types", "xml_tag")),
						]
						line = tmp[2]
						tag_named = True
						continue
				else:
					# This *should* match all remaining cases
					tmp = remainder_regex.match(line)
					if tmp is None:
						raise SyntaxError(f"XML syntax highlighter failed to parse {line}")

					if comment:
						tmpline += [
							ThemeString(tmp[1], ThemeAttr("types", "xml_comment")),
							ThemeString(tmp[2], ThemeAttr("types", "xml_comment")),
							ThemeString(tmp[3], ThemeAttr("types", "xml_comment")),
						]
					else:
						tmpline += [
							ThemeString(tmp[1], ThemeAttr("types", "xml_attribute_key")),
						]

						if len(tmp[2]) > 0:
							tmpline += [
								ThemeString(tmp[2], ThemeAttr("types", "xml_content")),
								ThemeString(tmp[3], ThemeAttr("types", "xml_attribute_value")),
							]
					line = tmp[4] + tmp[5]
					continue
			if before == line:
				raise SyntaxError(f"XML syntax highlighter parse failure at line #{i + 1}:\n"
						   "{lines}\n"
						   "Parsed fragments of line:\n"
						   "{tmpline}\n"
						   "Unparsed fragments of line:\n"
						   "{line}")

		dumps.append(tmpline)
		i += 1

	return dumps

def format_toml(lines: Union[str, List[str]], **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	TOML formatter; returns the text with syntax highlighting for TOML

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	# FIXME: necessary improvements:
	# * Instead of only checking for lines that end with a comment for key = value,
	#   and for full comment lines, check for lines that end with a comment
	#   in any situation (except multiline). Split out the comment and add it last.
	# * Handle quoting and escaping of quotes; \''' should not end a multiline, for instance.
	# * XXX: should we highlight key=value for inline tables? Probably not
	# * XXX: should we highlight different types (integer, string, etc.)? Almost certainly not.
	dumps: List[List[Union[ThemeRef, ThemeString]]] = []

	multiline_basic = False
	multiline_literal = False

	if deep_get(kwargs, DictPath("raw"), False):
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	# Safe
	key_value_regex = re.compile(r"^(\s*)(\S+)(\s*=\s*)(\S+)")
	# Safe
	comment_end_regex = re.compile(r"^(.*)(#.*)")

	tmpline: List[Union[ThemeRef, ThemeString]] = []

	for line in lines:
		if len(line) == 0:
			continue

		if multiline_basic or multiline_literal:
			tmpline += [
				ThemeString(line, ThemeAttr("types", "toml_value")),
			]
			dumps.append(tmpline)
			if multiline_basic and line.lstrip(" ").endswith("\"\"\""):
				multiline_basic = False
			elif multiline_literal and line.lstrip(" ").endswith("'''"):
				multiline_literal = False
			continue

		tmpline = []
		if line.lstrip().startswith("#"):
			tmpline += [
				ThemeString(line, ThemeAttr("types", "toml_comment")),
			]
			dumps.append(tmpline)
			continue

		if line.lstrip().startswith("[") and line.rstrip(" ").endswith("]"):
			tmpline += [
				ThemeString(line, ThemeAttr("types", "toml_table")),
			]

			dumps.append(tmpline)
			continue

		tmp = key_value_regex.match(line)
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
				tmp = comment_end_regex.match(value)
				if tmp is not None:
					value = tmp[1]
					comment = tmp[2]
				else:
					comment = ""
			tmpline += [
				ThemeString(f"{indentation}", ThemeAttr("types", "generic")),
				ThemeString(f"{key}", ThemeAttr("types", "toml_key")),
				ThemeString(f"{separator}", ThemeAttr("types", "toml_key_separator")),
				ThemeString(f"{value}", ThemeAttr("types", "toml_value")),
			]
			if len(comment) > 0:
				tmpline += [
					ThemeString(f"{comment}", ThemeAttr("types", "toml_comment")),
				]
			dumps.append(tmpline)
		# dumps.append([ThemeString(line, ThemeAttr("types", "generic"))])
	return dumps

def format_fluentbit(lines: Union[str, List[str]], **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	FluentBit formatter; returns the text with syntax highlighting for FluentBit

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps: List[List[Union[ThemeRef, ThemeString]]] = []

	if deep_get(kwargs, DictPath("raw"), False):
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	# Safe
	key_value_regex = re.compile(r"^(\s*)(\S*)(\s*)(.*)")

	for line in lines:
		if line.lstrip().startswith("#"):
			tmpline: List[Union[ThemeRef, ThemeString]] = [
				ThemeString(line, ThemeAttr("types", "ini_comment")),
			]
		elif line.lstrip().startswith("[") and line.rstrip().endswith("]"):
			tmpline = [
				ThemeString(line, ThemeAttr("types", "ini_section")),
			]
		elif len(line.strip()) == 0:
			tmpline = [
				ThemeString("", ThemeAttr("types", "generic")),
			]
		else:
			tmp = key_value_regex.match(line)
			if tmp is not None:
				indentation = tmp[1]
				key = tmp[2]
				separator = tmp[3]
				value = tmp[4]

				tmpline = [
					ThemeString(f"{indentation}", ThemeAttr("types", "generic")),
					ThemeString(f"{key}", ThemeAttr("types", "ini_key")),
					ThemeString(f"{separator}", ThemeAttr("types", "ini_key_separator")),
					ThemeString(f"{value}", ThemeAttr("types", "ini_value")),
				]
		dumps.append(tmpline)
	return dumps

def format_ini(lines: Union[str, List[str]], **kwargs: Dict) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	INI formatter; returns the text with syntax highlighting for INI

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps: List[List[Union[ThemeRef, ThemeString]]] = []

	if deep_get(kwargs, DictPath("raw"), False):
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	# Safe
	key_value_regex = re.compile(r"^(\s*)(\S+)(\s*=\s*)(\S+)")

	for line in lines:
		tmpline: List[Union[ThemeRef, ThemeString]] = []
		if line.lstrip().startswith(("#", ";")):
			tmpline = [
				ThemeString(line, ThemeAttr("types", "ini_comment")),
			]
		elif line.lstrip().startswith("[") and line.rstrip().endswith("]"):
			tmpline = [
				ThemeString(line, ThemeAttr("types", "ini_section")),
			]
		else:
			tmp = key_value_regex.match(line)
			if tmp is not None:
				indentation = tmp[1]
				key = tmp[2]
				separator = tmp[3]
				value = tmp[4]

				tmpline = [
					ThemeString(f"{indentation}", ThemeAttr("types", "generic")),
					ThemeString(f"{key}", ThemeAttr("types", "ini_key")),
					ThemeString(f"{separator}", ThemeAttr("types", "ini_key_separator")),
					ThemeString(f"{value}", ThemeAttr("types", "ini_value")),
				]
		dumps.append(tmpline)
	return dumps

def map_dataformat(dataformat: str) -> Callable[[Union[str, List[str]]], List[List[Union[ThemeRef, ThemeString]]]]:
	"""
	Identify what formatter to use, based either on a file ending or an explicit dataformat tag

		Parameters:
			dataformat: The data format *or* the name of the file
		Returns:
			(function reference): The formatter to use
	"""

	if dataformat in {"YAML", "JSON", "NDJSON"} or dataformat.endswith((".yml", ".yaml", ".json", ".ndjson")):
		formatter = format_yaml
	elif dataformat == "TOML" or dataformat.endswith((".toml")):
		formatter = format_toml
	elif dataformat == "CRT" or dataformat.endswith((".crt", "tls.key", ".pem", "CAKey")):
		formatter = format_crt
	elif dataformat == "XML" or dataformat.endswith((".xml")):
		formatter = format_xml
	elif dataformat == "INI" or dataformat.endswith((".ini")):
		formatter = format_ini
	elif dataformat == "FluentBit":
		formatter = format_fluentbit
	elif dataformat in {"HAProxy", "haproxy.cfg"}:
		formatter = format_haproxy
	elif dataformat == "CaddyFile":
		formatter = format_caddyfile
	elif dataformat == {"mosquitto", "mosquitto.conf"}:
		formatter = format_mosquitto
	elif dataformat == "NGINX":
		formatter = format_nginx
	else:
		formatter = format_none
	return formatter

# Formatters acceptable for direct use in view files
formatter_allowlist = {
	"format_caddyfile": format_caddyfile,
	"format_crt": format_crt,
	"format_fluentbit": format_fluentbit,
	"format_haproxy": format_haproxy,
	"format_ini": format_ini,
	"format_mosquitto": format_mosquitto,
	"format_nginx": format_nginx,
	"format_none": format_none,
	"format_toml": format_toml,
	"format_xml": format_xml,
	"format_yaml": format_yaml,
	"reformat_json": reformat_json,
}
