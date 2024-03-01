#! /usr/bin/env python3
#
# Copyright the Cluster Management Toolkit for Kubernetes contributors.
# SPDX-License-Identifier: MIT

"""
Format text as themearrays
"""

import base64
import binascii
# ujson is much faster than json,
# but it might not be available
try:
	import ujson as json
	json_is_ujson = True
	# The exception raised by ujson when parsing fails is different
	# from what json raises
	DecodeException = ValueError
except ModuleNotFoundError:  # pragma: no cover
	import json  # type: ignore
	json_is_ujson = False
	DecodeException = json.decoder.JSONDecodeError  # type: ignore
import re
import sys
from typing import Any, Callable, cast, Dict, List, Optional, Tuple, Union
try:
	import yaml
except ModuleNotFoundError:  # pragma: no cover
	sys.exit("ModuleNotFoundError: Could not import yaml; you may need to (re-)run `cmt-install` or `pip3 install PyYAML`; aborting.")

from cmttypes import deep_get, DictPath

import cmtlib
from cmtlib import split_msg, strip_ansicodes

from curses_helper import ThemeAttr, ThemeRef, ThemeString, themearray_len

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
else:  # pragma: no cover
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

def format_markdown(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	Markdown formatter; returns the text with syntax highlighting for a subset of Markdown

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			**kwargs (dict[str, Any]): Keyword arguments
				start ((str)): Start indicator(s)
				include_start (bool): Include the start line
				end ((str)): End indicator(s)
		Returns:
			list[themearray]: A list of themearrays
	"""

	format_lookup = {
		# codeblock, bold, italics
		(False, False, False): ThemeAttr("types", "generic"),
		(True, False, False): ThemeAttr("types", "markdown_code"),
		(True, True, False): ThemeAttr("types", "markdown_code_bold"),
		(True, False, True): ThemeAttr("types", "markdown_code_italics"),
		(True, True, True): ThemeAttr("types", "markdown_code_bold_italics"),
		(False, True, False): ThemeAttr("types", "markdown_bold"),
		(False, False, True): ThemeAttr("types", "markdown_italics"),
		(False, True, True): ThemeAttr("types", "markdown_bold_italics"),
	}

	dumps: List[List[Union[ThemeRef, ThemeString]]] = []
	start = deep_get(kwargs, DictPath("start"), None)
	include_start = deep_get(kwargs, DictPath("include_start"), False)
	end = deep_get(kwargs, DictPath("end"), None)

	if isinstance(lines, str):
		# Remove all commented-out blocks
		lines = re.sub(r"<!--.*?-->", r"", lines, flags = re.DOTALL)
		lines = split_msg(lines)

	emptylines: List[Union[ThemeRef, ThemeString]] = []
	started = False
	codeblock = ""
	for line in lines:
		if started and end is not None and line.startswith(end):
			break

		if codeblock != "~~~":
			codeblock = ""

		# Skip past all non-start line until we reach the start
		if not started and start is not None:
			if not line.startswith(start):
				continue
			started = True
			# This is the start line, but we don't want to include it
			if not include_start:
				continue

		if not line:
			emptylines.append(ThemeString("", ThemeAttr("types", "generic")))
			continue
		if (not strip_empty_start or dumps) and emptylines:
			dumps.append(emptylines)
			emptylines = []

		if line in ("~~~", "```"):
			if codeblock == "":
				codeblock = "~~~"
			else:
				codeblock = ""
			continue
		# For headers we are--for now--lazy
		# Level 1 header
		if line.startswith("# "):
			tformat = ThemeAttr("types", "markdown_header_1")
			line = line[len("# "):]
		# Level 2 header
		elif line.startswith("## "):
			tformat = ThemeAttr("types", "markdown_header_2")
			line = line[len("## "):]
		# Level 3 header
		elif line.startswith("### "):
			tformat = ThemeAttr("types", "markdown_header_3")
			line = line[len("### "):]
		else:
			tmpline: List[Union[ThemeRef, ThemeString]] = []
			if line.startswith("    "):
				tformat = ThemeAttr("types", "markdown_code")
				codeblock = "    "

			if line.lstrip().startswith("- "):
				striplen = len(line) - len(line.lstrip())
				if striplen:
					tmpline.append(ThemeString("".ljust(striplen), ThemeAttr("types", "generic")))
				tmpline.append(ThemeRef("separators", "genericbullet"))
				line = line[themearray_len(tmpline):]

			tformat = ThemeAttr("types", "generic")

			# Rescue backticks
			line = line.replace("\\`", "<<<backtick>>>")
			code_blocks = line.split("`")

			for i, codesection in enumerate(code_blocks):
				codesection = codesection.replace("<<<backtick>>>", "\\`")
				# Toggle codeblock
				if i and codeblock in ("`", ""):
					if codeblock == "`":
						codeblock = ""
					else:
						codeblock = "`"
				# Assume consistent use of **/*/__/_
				if "**" in codesection and codeblock == "":
					bold_sections = codesection.split("**")
				elif "__" in codesection and codeblock == "":
					bold_sections = codesection.split("__")
				else:
					bold_sections = [codesection]
				bold = True

				for _j, section in enumerate(bold_sections):
					if section.startswith("#### "):
						section = section[len("#### "):]
						bold = True
					else:
						bold = not bold
					if (section.startswith("*") or " *" in section) and codeblock == "":
						italics_sections = section.split("*")
					elif (section.startswith("_") or " _" in section) and codeblock == "":
						italics_sections = section.split("_")
					else:
						italics_sections = [section]
					italics = True
					for _k, italics_section in enumerate(italics_sections):
						italics = not italics
						if not italics_section:
							continue
						tmpline.append(ThemeString(italics_section, format_lookup[(codeblock != "", bold, italics)]))
			dumps.append(tmpline)
			continue
		dumps.append([ThemeString(line, tformat)])
		continue

	if not strip_empty_end and emptylines:
		dumps.append(emptylines)
	return dumps

# pylint: disable-next=unused-argument
def format_binary(lines: bytes, **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
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
def format_none(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
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
def format_diff_line(line: str, **kwargs: Any) -> List[Union[ThemeRef, ThemeString]]:
	"""
	Formats a single line of a diff

		Parameters:
			line (str): a string
			override_formatting (dict): Overrides instead of default diff-formatting
			kwargs (dict): Additional parameters
		Returns:
			themearray: a themearray
	"""
	_override_formatting: Optional[Union[ThemeAttr, Dict]] = deep_get(kwargs, DictPath("override_formatting"))
	indent = deep_get(kwargs, DictPath("indent"), "")

	tmpline: List[Union[ThemeRef, ThemeString]] = []

	if line.startswith(f"{indent}+ "):
		tmpline += [
			ThemeString(line, ThemeAttr("logview", "severity_diffplus")),
		]
		return tmpline
	if line.startswith(f"{indent}- "):
		tmpline += [
			ThemeString(line, ThemeAttr("logview", "severity_diffminus")),
		]
		return tmpline
	tmpline += [
		ThemeString(line, ThemeAttr("logview", "severity_diffsame")),
	]
	return tmpline

def format_yaml_line(line: str, **kwargs: Any) -> Tuple[List[Union[ThemeRef, ThemeString]], List[List[Union[ThemeRef, ThemeString]]]]:
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
	remnants: List[List[Union[ThemeRef, ThemeString]]] = []

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
		separator_format = ThemeAttr("types", "yaml_separator")
		reference_format = ThemeAttr("types", "yaml_reference")
		anchor_format = ThemeAttr("types", "yaml_anchor")
	elif isinstance(override_formatting, ThemeAttr):
		# We just return the line unformatted
		return [ThemeString(line, override_formatting)], []
	else:
		raise TypeError(f"type(override_formatting) is {type(override_formatting)}; should be either {repr(ThemeAttr)} or {repr(dict)}")

	tmpline: List[Union[ThemeRef, ThemeString]] = []

	# [whitespace]-<whitespace><value>
	yaml_list_regex = re.compile(r"^(\s*)- (.*)")
	# <key>:<whitespace><value>
	# <key>:<whitespace>&<anchor>[<whitespace><value>]
	# <key>: *<alias>
	yaml_key_reference_value_regex = re.compile(r"^([^:]+)(:\s*)(&|\*|)([^\s]+)([\s]+[^\s]+|)")

	if line.lstrip(" ").startswith("#"):
		tmpline += [
			ThemeString(line, comment_format),
		]
		return tmpline, remnants
	if line.lstrip(" ").startswith("- "):
		tmp = yaml_list_regex.match(line)
		if tmp is not None:
			tmpline += [
				ThemeString(tmp[1], generic_format),
				list_format,
			]
			line = tmp[2]
			if not line:
				return tmpline, remnants

	if line.endswith(":"):
		_key_format = deep_get(override_formatting, DictPath(f"{line[:-1]}#key"), key_format)
		tmpline += [
			ThemeString(f"{line[:-1]}", _key_format),
			ThemeString(":", separator_format),
		]
	else:
		tmp = yaml_key_reference_value_regex.match(line)

		# pylint: disable-next=line-too-long
		if tmp is not None and (tmp[1].strip().startswith("\"") and tmp[1].strip().endswith("\"") or (not tmp[1].strip().startswith("\"") and not tmp[1].strip().endswith("\""))):
			key = tmp[1]
			separator = tmp[2]
			reference = tmp[3]
			anchor = ""
			value_or_anchor = tmp[4]
			value = tmp[5]

			if reference:
				if value:
					anchor = value_or_anchor
				else:
					anchor = value_or_anchor
					value = ""
				value_or_anchor = ""
			else:
				value = value_or_anchor
				value_or_anchor = ""

			_key_format = deep_get(override_formatting, DictPath(f"{key.strip()}#key"), key_format)
			if value.strip() in ("{", "["):
				_value_format = value_format
			else:
				_value_format = deep_get(override_formatting, DictPath(f"{key.strip()}#value"), value_format)

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
						]
						if reference:
							tmpline.append(ThemeString(f"{reference}", reference_format))
						if anchor:
							tmpline.append(ThemeString(f"{anchor}", anchor_format))
						tmpline.append(ThemeString(f"{value_line}", _value_format))
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
					first = True
					for j, split_value_segment in enumerate(tmp_split_value):
						tabsize = 0
						if j < len(tmp_split_value):
							tabsize = 8 - len(tmp_value) % 8
						if not first:
							tmp_value += "".ljust(tabsize)
						else:
							first = False
						tmp_value += split_value_segment
					value = tmp_value

				tmpline += [
					ThemeString(f"{key}", _key_format),
					ThemeString(f"{separator}", separator_format),
				]
				if reference:
					tmpline.append(ThemeString(f"{reference}", reference_format))
				if anchor:
					tmpline.append(ThemeString(f"{anchor}", anchor_format))
				if value:
					tmpline.append(ThemeString(f"{value}", _value_format))
		else:
			_value_format = deep_get(override_formatting, DictPath(f"{line}#value"), value_format)
			tmpline += [
				ThemeString(f"{line}", _value_format),
			]

	return tmpline, remnants

def format_yaml(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	YAML formatter; returns the text with syntax highlighting for YAML

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (Any): Additional parameters
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

	override_formatting: Union[ThemeAttr, Dict] = deep_get(kwargs, DictPath("override_formatting"), {})

	if deep_get(kwargs, DictPath("raw"), False):
		override_formatting = generic_format

	yaml.add_representer(str, __str_representer)

	for i, obj in enumerate(lines):
		if isinstance(obj, dict):
			split_dump = yaml.dump(obj, default_flow_style = False, indent = indent, width = sys.maxsize).splitlines()
		else:
			split_dump = obj.splitlines()
		first = True
		if split_dump and "\n" not in obj and split_dump[0].startswith("'") and split_dump[0].endswith("'"):
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
			if not line:
				continue

			kwargs["override_formatting"] = override_formatting
			tmpline: List[Union[ThemeRef, ThemeString]] = []
			remnants: List[List[Union[ThemeRef, ThemeString]]] = []
			tmpline, remnants = format_yaml_line(line, **kwargs)
			if truncated:
				tmpline += [ThemeString(" [...] (Truncated)", ThemeAttr("types", "yaml_key_error"))]
			dumps.append(tmpline)
			if remnants:
				dumps += remnants

		if i < len(lines) - 1:
			dumps.append([ThemeString("", generic_format)])
			dumps.append([ThemeString("", generic_format)])
			dumps.append([ThemeString("", generic_format)])

	return dumps

def reformat_json(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
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

def format_crt(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
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

def format_haproxy(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
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

	haproxy_section_regex = re.compile(r"^(\s*)(global|defaults|frontend|backend|listen|resolvers|mailers|peers)(\s*)(.*)")
	haproxy_setting_regex = re.compile(r"^(\s*)(\S+)(\s+)(.+)")

	for line in lines:
		# Is it whitespace?
		if not line.strip():
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

def format_caddyfile(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
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

	block_open_regex = re.compile(r"^(\s*)({)(.*)")
	snippet_regex = re.compile(r"^(\s*)(\(.+?\))(.*)")
	site_regex = re.compile(r"^(\s*)(\S+?)(\s+{\s*$|$)")
	block_close_regex = re.compile(r"^(\s*)(}\s*$)")
	matcher_regex = re.compile(r"^(\s*)(@.*?|\*/.*?)(\s.*)")
	directive_regex = re.compile(r"^(\s*)(.+?)(\s.*|$)")
	argument_regex = re.compile(r"^(.*?)(\s{\s*$|$)")

	for line in lines:
		tmpline: List[Union[ThemeRef, ThemeString]] = []

		# Empty line
		if not line and not tmpline:
			tmpline = [
				ThemeString("", ThemeAttr("types", "xml_content")),
			]

		directive = False
		block_depth = 0

		while line:
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
				if tmp[1]:
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
				if tmp[1]:
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
				if not block_depth and not site and (single_site or "{" in tmp[3]):
					if tmp[1]:
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
				if tmp[1]:
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
				if tmp[1]:
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
					if tmp[1]:
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

def format_mosquitto(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
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

	mosquitto_variable_regex = re.compile(r"^(\S+)(\s)(.+)")

	for line in lines:
		# Is it whitespace?
		if not line.strip():
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

def format_nginx(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
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

	key_regex = re.compile(r"^(\s*)(#.*$|}|\S+|$)(.+;|.+{|)(\s*#.*$|)")

	for line in lines:
		dump: List[Union[ThemeRef, ThemeString]] = []
		if not line.strip():
			if not dump:
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
			if tmp[1]:
				dump += [
					ThemeString(tmp[1], ThemeAttr("types", "generic")),	# whitespace
				]
			if tmp[2]:
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
			if tmp[3]:
				dump += [
					ThemeString(tmp[3][:-1], ThemeAttr("types", "nginx_value")),
					ThemeString(tmp[3][-1:], ThemeAttr("types", "generic")),	# block start / statement end
				]
			if tmp[4]:
				dump += [
					ThemeString(tmp[4], ThemeAttr("types", "nginx_comment"))
				]
			dumps.append(dump)
		else:
			sys.exit(f"__format_nginx(): Could not match line={line}")
	return dumps

def format_xml(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
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

	escape_regex = re.compile(r"^(\s*)(&)(.+?)(;)(.*)")
	content_regex = re.compile(r"^(.*?)(<.*|&.*)")
	tag_open_regex = re.compile(r"^(\s*)(</|<!--|<\?|<)(.*)")
	tag_named_regex = re.compile(r"^(.+?)(\s*>|\s*\?>|\s*$|\s+.*)")
	tag_close_regex = re.compile(r"^(\s*)(/>|\?>|-->|--!>|>)(.*)")
	remainder_regex = re.compile(r"^(\s*\S+?)(=|)(\"[^\"]+?\"|)(\s*$|\s*/>|\s*\?>|\s*-->|\s*>|\s+)(.*|)")

	i = 0
	for line in lines:
		tmpline: List[Union[ThemeRef, ThemeString]] = []

		# Empty line
		if not line and not tmpline:
			tmpline = [
				ThemeString("", ThemeAttr("types", "xml_content")),
			]

		while line:
			before = line
			if not tag_open:
				# Are we opening a tag?
				tmp = tag_open_regex.match(line)
				if tmp is not None:
					tag_open = True
					tag_named = False

					# Do not add 0-length "indentation"
					if tmp[1]:
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
					if tmp[1]:
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

						if tmp[2]:
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

def format_python_traceback(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	Python Traceback formatter; returns the text with syntax highlighting for Python Tracebacks

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

	block = False

	for line in lines:
		if not block and line == "Traceback (most recent call last):":
			dumps.append([
				ThemeString(line, ThemeAttr("logview", "severity_error"))
			])
			block = True
			continue
		if block:
			tmp = re.match(r"^(\s+File \")(.+?)(\", line )(\d+)(, in )(.*)", line)
			if tmp is not None:
				dumps.append([
					ThemeString(tmp[1], ThemeAttr("logview", "severity_info")),
					ThemeString(tmp[2], ThemeAttr("types", "path")),
					ThemeString(tmp[3], ThemeAttr("logview", "severity_info")),
					ThemeString(tmp[4], ThemeAttr("types", "lineno")),
					ThemeString(tmp[5], ThemeAttr("logview", "severity_info")),
					ThemeString(tmp[6], ThemeAttr("types", "path"))
				])
				continue
			tmp = re.match(r"(^\S+?Error:|Exception:|GeneratorExit:|KeyboardInterrupt:|StopIteration:|StopAsyncIteration:|SystemExit:|socket.gaierror:)( .*)", line)
			if tmp is not None:
				dumps.append([
					ThemeString(tmp[1], ThemeAttr("logview", "severity_error")),
					ThemeString(tmp[2], ThemeAttr("logview", "severity_info"))
				])
				block = False
				continue
		dumps.append([ThemeString(line, ThemeAttr("logview", "severity_info"))])
	return dumps

def format_toml(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
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

	key_value_regex = re.compile(r"^(\s*)(\S+)(\s*=\s*)(\S+)")
	comment_end_regex = re.compile(r"^(.*)(#.*)")

	tmpline: List[Union[ThemeRef, ThemeString]] = []

	for line in lines:
		if not line:
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
			if comment:
				tmpline += [
					ThemeString(f"{comment}", ThemeAttr("types", "toml_comment")),
				]
			dumps.append(tmpline)
		# dumps.append([ThemeString(line, ThemeAttr("types", "generic"))])
	return dumps

def format_fluentbit(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
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
		elif not line.strip():
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

def format_ini(lines: Union[str, List[str]], **kwargs: Any) -> List[List[Union[ThemeRef, ThemeString]]]:
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

				if indentation:
					tmpline = [
						ThemeString(f"{indentation}", ThemeAttr("types", "generic")),
					]
				else:
					tmpline = []

				tmpline += [
					ThemeString(f"{key}", ThemeAttr("types", "ini_key")),
					ThemeString(f"{separator}", ThemeAttr("types", "ini_key_separator")),
					ThemeString(f"{value}", ThemeAttr("types", "ini_value")),
				]
		dumps.append(tmpline)
	return dumps

formatter_mapping = (
	# (startswith, endswith, formatter)
	("YAML", "YAML", format_yaml),
	("JSON", "JSON", format_yaml),
	("NDJSON", "NDJSON", format_yaml),
	("", (".yml", ".yaml", ".json", ".ndjson"), format_yaml),
	("TOML", "TOML", format_toml),
	("", ".toml", format_toml),
	("CRT", "CRT", format_crt),
	("", (".crt", "tls.key", ".pem", "CAKey"), format_crt),
	("XML", "XML", format_xml),
	("", ".xml", format_xml),
	("INI", "INI", format_ini),
	("", ".ini", format_ini),
	("JWS", "JWS", format_none),
	("FluentBit", "FluentBit", format_fluentbit),
	("HAProxy", "HAProxy", format_haproxy),
	("haproxy.cfg", "haproxy.cfg", format_haproxy),
	("CaddyFile", "CaddyFile", format_caddyfile),
	("mosquitto", "", format_mosquitto),
	("NGINX", "NGINX", format_nginx),
)

def map_dataformat(dataformat: str) -> Callable[[Union[str, List[str]]], List[List[Union[ThemeRef, ThemeString]]]]:
	"""
	Identify what formatter to use, based either on a file ending or an explicit dataformat tag

		Parameters:
			dataformat: The data format *or* the name of the file
		Returns:
			(function reference): The formatter to use
	"""

	for prefix, suffix, formatter_ in formatter_mapping:
		if dataformat.startswith(prefix) and dataformat.endswith(suffix):  # type: ignore[arg-type]
			return formatter_
	return format_none

# Formatters acceptable for direct use in view files
formatter_allowlist: Dict[str, Callable] = {
	"format_caddyfile": format_caddyfile,
	"format_crt": format_crt,
	"format_fluentbit": format_fluentbit,
	"format_haproxy": format_haproxy,
	"format_ini": format_ini,
	"format_markdown": format_markdown,
	"format_mosquitto": format_mosquitto,
	"format_nginx": format_nginx,
	"format_none": format_none,
	"format_python_traceback": format_python_traceback,
	"format_toml": format_toml,
	"format_xml": format_xml,
	"format_yaml": format_yaml,
	"reformat_json": reformat_json,
}

# These are based on attributes of the name of the cmdata
cmdata_format: List[Tuple[str, str, str, str, str]] = [
	# cm namespace, cm name prefix, cmdata prefix, cmdata suffix, dataformat
	# To do an exact match on cmdata set both cmdata prefix and cmdata suffix to the same string
	# (this will work unless you have a string that contains the same substring twice)
	("", "", "caBundle", "caBundle", "CRT"),
	("", "image-registry-certificates", "", "", "CRT"),
	("", "", "", ".crt", "CRT"),
	("", "", "", ".pem", "CRT"),
	("", "", "", "client-ca-file", "CRT"),
	("", "", "haproxy.cfg", "haproxy.cfg", "HAProxy"),
	("", "", "", ".ini", "INI"),
	("", "", "", ".ndjson", "NDJSON"),
	("", "", "", ".json", "JSON"),
	("", "", "mosquitto.conf", "mosquitto.conf", "mosquitto"),
	("", "", "", ".sh", "Shell Script"),
	("", "", "", ".toml", "TOML"),
	("", "", "", ".xml", "XML"),
	("", "", "", ".yaml", "YAML"),
	("", "", "", ".yml", "YAML"),
	("calico-system", "cni-config", "", "", "JSON"),
	("", "canal-config", "cni_network_config", "", "JSON"),
	("", "", "fluentbit.conf", "", "FluentBit"),
	("", "intel-iaa-config", "iaa.conf", "iaa.conf", "JSON"),
	("istio-system", "istio", "", "", "YAML"),
	("", "k10-k10-metering-config", "", "", "YAML"),
	("", "kubeapps-clusters-config", "clusters.conf", "", "JSON"),
	("", "kubeapps-internal-kubeappsapis-configmap", "plugins.conf", "", "JSON"),
	("kube-public", "cluster-info", "kubeconfig", "", "YAML"),
	("kube-public", "cluster-info", "jws-", "", "JWS"),
	("kube-system", "antrea", "antrea-agent", "", "YAML"),
	("kube-system", "antrea", "antrea-controller", "", "YAML"),
	("kube-system", "antrea", "antrea-cni", "", "JSON"),
	("kube-system", "cluster-config", "install-config", "", "YAML"),
	("kube-system", "", "cni_network_config", "", "JSON"),
	("", "coredns", "Corefile", "", "CaddyFile"),
	("kube-system", "rke2-coredns", "Corefile", "", "CaddyFile"),
	("kube-system", "rke2-coredns", "linear", "", "YAML"),
	("kube-system", "rke2-etcd-snapshots", "", "", "JSON"),
	("kube-system", "kubeadm-config", "", "", "YAML"),
	("kube-system", "kubeconfig-in-cluster", "kubeconfig", "", "YAML"),
	("kube-system", "kubelet-config", "", "", "YAML"),
	("kube-system", "kube-proxy", "", "config.conf", "YAML"),
	("kube-system", "scheduler-extender-policy", "policy.cfg", "", "JSON"),
	("", "", "nginx.conf", "nginx.conf", "NGINX"),
	("", "kubeshark-nginx", "default.conf", "default.conf", "NGINX"),
	("", "kubeapps", "vhost.conf", "vhost.conf", "NGINX"),
	("", "kubeapps", "k8s-api-proxy.conf", "k8s-api-proxy.conf", "NGINX"),
	("", "linkerd-config", "values", "", "YAML"),
	("", "nfd-worker-conf", "nfd-worker.conf", "", "YAML"),
	("", "trivy-operator", "nodeCollector.volumeMounts", "", "JSON"),
	("", "trivy-operator", "nodeCollector.volumes", "", "JSON"),
	("", "trivy-operator", "scanJob.podTemplateContainerSecurityContext", "", "JSON"),
	("", "", "", ".py", "Python"),
	# Openshift
	("", "dns-default", "Corefile", "", "CaddyFile"),
	("", "v4-0-config-system-cliconfig", "v4-0-config-system-cliconfig", "", "JSON"),
	("openshift-authentication", "v4-0-config-system-metadata", "oauthMetadata", "", "JSON"),
	("openshift-config-managed", "oauth-openshift", "oauthMetadata", "", "JSON"),
	("openshift-kube-apiserver", "check-endpoints-kubeconfig", "kubeconfig", "", "YAML"),
	("openshift-kube-apiserver", "config", "kubeconfig", "", "JSON"),
	("openshift-kube-apiserver", "control-plane-node-kubeconfig", "kubeconfig", "", "YAML"),
	("openshift-kube-apiserver", "kube-apiserver-cert-syncer-kubeconfig", "kubeconfig", "", "YAML"),
	("openshift-kube-apiserver", "oauth-metadata", "oauthMetadata", "", "JSON"),
	("openshift-kube-controller-manager", "controller-manager-kubeconfig", "kubeconfig", "", "JSON"),
	("openshift-kube-controller-manager", "kube-controller-cert-syncer-kubeconfig", "kubeconfig", "", "JSON"),
	("openshift-kube-scheduler", "kube-scheduler-cert-syncer-kubeconfig", "kubeconfig", "", "JSON"),
	("openshift-kube-scheduler", "scheduler-kubeconfig", "kubeconfig", "", "JSON"),
	("openshift-machine-config-operator", "coreos-bootimages", "stream", "", "JSON"),
	("openshift-operator", "applied-cluster", "applied", "", "JSON"),
	# Keep last; match everything that does not match anything
	("", "", "", "", "Text"),
]

# These are based on the data itself
cmdata_header: List[Tuple[str, str]] = [
	("<?xml ", "XML"),
	("/bin/sh", "Shell Script"),
	("/usr/bin/env bash", "BASH"),
	("/usr/bin/env perl", "Perl"),
	("/usr/bin/env python", "Python"),
	("/bin/bash", "BASH"),
	("/bin/dash", "Shell Script"),
	("/bin/zsh", "ZSH"),
	("python", "Python"),
	("perl", "Perl"),
	("perl", "Ruby"),
	("-----BEGIN CERTIFICATE-----", "CRT"),
]

# Binary file headers
cmdata_bin_header: List[Tuple[int, List[int], str]] = [
	(0, [0x1f, 0x8b], "gz / tar+gz"),
	(0, [0x1f, 0x9d], "lzw / tar+lzw"),
	(0, [0x1f, 0xa0], "lzh / tar+lzh"),
	(0, [0xfd, 0x37, 0x7a, 0x58, 0x5a, 0x0], "xz / tar+xz"),
	(0, [0x42, 0x5a, 0x68], "bz2 / tar+bz2"),
	(0, [0x4c, 0x49, 0x50], "lzip"),
	(2, [0x2d, 0x68, 0x6c, 0x30, 0x2d], "lzh (no compression)"),
	(2, [0x2d, 0x68, 0x6c, 0x35, 0x2d], "lzh (8KiB sliding window)"),
	(0, [0x51, 0x46, 0x49], "qcow"),
	(0, [0x30, 0x37, 0x30, 0x37, 0x30, 0x37], "cpio"),
	(0, [0x28, 0xb5, 0x2f, 0xfd], "zstd"),
	(0, [0x50, 0x4b, 0x03, 0x04], "zip"),
	(0, [0x50, 0x4b, 0x05, 0x06], "zip (empty)"),
	(0, [0x50, 0x4b, 0x07, 0x08], "zip (spanned archive)"),
	(0, [0x52, 0x61, 0x72, 0x21, 0x1a, 0x07, 0x00], "rar (v1.50+)"),
	(0, [0x52, 0x61, 0x72, 0x21, 0x1a, 0x07, 0x01, 0x00], "rar (v5.00+)"),
	(0, [0x7f, 0x45, 0x4c, 0x46], "ELF"),
	(0x8001, [0x43, 0x44, 0x30, 0x30, 0x31], "ISO 9660"),
	(0x8801, [0x43, 0x44, 0x30, 0x30, 0x31], "ISO 9660"),
	(0x9001, [0x43, 0x44, 0x30, 0x30, 0x31], "ISO 9660"),
	(0, [0x75, 0x73, 0x74, 0x61, 0x72, 0x00, 0x30, 0x30], "tar"),
	(0, [0x75, 0x73, 0x74, 0x61, 0x72, 0x20, 0x20, 0x00], "tar"),
	(0, [0x78, 0x61, 0x72, 0x21], "xar"),
	(0, [0x21, 0x3c, 0x61, 0x72, 0x63, 0x68, 0x3e, 0x0a], "deb"),
	(0, [0xed, 0xab, 0xee, 0xdb], "rpm"),
]

def identify_cmdata(cmdata_name: str, cm_name: str, cm_namespace: str, data: Any) -> Tuple[str, Callable]:
	if not data:
		return "Empty", format_none

	uudata = False

	if "\n" not in data:
		try:
			decoded = base64.b64decode(data)
			if base64.b64encode(decoded) == bytes(data, encoding = "utf-8"):
				uudata = True
		except binascii.Error:
			pass

	if uudata:
		try:
			data = decoded.decode("utf-8")
		except UnicodeDecodeError:
			for offset, match_bin_infix, dataformat in cmdata_bin_header:
				if len(decoded) < len(match_bin_infix) + offset:
					continue

				if bytes(match_bin_infix) == decoded[offset:len(match_bin_infix) + offset]:
					return dataformat, format_binary
			return "Text or Base64 encoded binary", format_none

	splitmsg = split_msg(data)
	dataformat = ""

	# We are in luck; there is an interpreter signature
	# or other type of signature to help
	if splitmsg and splitmsg[0].startswith(("#!", "-----")):
		for tmp in cmdata_header:
			match_infix, dataformat = tmp
			if match_infix in data:
				break

	if not dataformat:
		for match_cm_namespace, match_cm_name, match_cmdata_prefix, match_cmdata_suffix, dataformat in cmdata_format:
			if (not match_cm_namespace or match_cm_namespace == cm_namespace) and cm_name.startswith(match_cm_name) and cmdata_name.startswith(match_cmdata_prefix) and cmdata_name.endswith(match_cmdata_suffix):
				break

	formatter = map_dataformat(dataformat)

	return dataformat, formatter

def identify_formatter(dataformat: str, kind: Optional[str] = None, obj: Optional[Dict[str, Any]] = None, path: Optional[str] = None) -> Callable:
	formatter = format_none

	if dataformat is None:
		if kind is not None and obj is not None and path is not None:
			if kind == ("ConfigMap", ""):
				cmdata_name = path
				cm_name = deep_get(obj, DictPath("metadata#name"))
				cm_namespace = deep_get(obj, DictPath("metadata#namespace"))
				data = deep_get(obj, DictPath(f"data#{path}"))
				dataformat, formatter = identify_cmdata(cmdata_name, cm_name, cm_namespace, data)
			else:
				raise ValueError(f"We do not know how to auto-identify data for kind {kind}")
		else:
			raise ValueError("identify_formatter was called without dataformat and kind, obj, or path=None")

	return formatter
